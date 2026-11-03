#!/usr/bin/env python3
"""Pure-digital verification of the multi-frequency transmit source (2026-10-29).

Proves, WITHOUT any SDR, that the frozen dual-path TX waveform is correct:
  1. source identity (SHA) closes on the frozen generator/preamble chain;
  2. frequency axis + shift sign: A sits at -1.8 MHz (below LO), B at +1.8 MHz;
  3. each path is separable and each common frame is recoverable (corr/NMSE);
  4. occupied bandwidth, guard and Nyquist margin are as expected;
  5. final int16 device waveform has no saturation, sane RMS/PAPR, low quant error;
  6. periodic buffer wrap has no material discontinuity.

Acceptance thresholds are FROZEN here (justified from filter/quantization theory),
never fitted to the output.  Output: machine-readable JSON + PNG spectra.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly, welch, firwin, lfilter, correlate

import tx_common as C

# ---------------------------------------------------------------------------
# FROZEN acceptance thresholds (justification inline; not fitted to results)
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # Recovery correlation is a robust discriminator: downconverting by the CORRECT
    # offset (+/-1.8 MHz) reconstructs the baseband frame and correlates ~0.99+,
    # whereas a wrong shift SIGN (or wrong resample) moves the signal 2x off-center
    # and the FIR removes it -> correlation ~0.  The 4x-up / 4x-down resample_poly
    # chain leaves only the matched filter's band-edge rolloff.
    "recover_corr_resample_min": 0.99,
    "recover_corr_fir_min": 0.98,
    "recover_nmse_fir_max_db": -20.0,
    # Separability: recovering A (and B) out of the SUM still meets the FIR bound.
    "separate_corr_fir_min": 0.98,
    "separate_nmse_fir_max_db": -20.0,
    # Payload de-tile (8 tiles averaged) vs source: same discriminator at payload level.
    "payload_corr_min": 0.98,
    # Spectral centroid of each single path must sit at the exact shift (Welch bin
    # width is 2.5 kHz; the centroid of a symmetric band is accurate to < 1 kHz).
    "center_err_max_hz": 20_000.0,
    # 99% occupied bandwidth: source is band-limited to 1.28 MHz Nyquist so the
    # signal spans ~2.56 MHz; bounds catch both a truncated band and gross
    # widening from a broken resample (transition tail may push 99% a bit past 2.56).
    "occ_bw_min_hz": 2.2e6,
    "occ_bw_max_hz": 3.0e6,
    # First image (the +2.56 MHz sampling replica): the source occupies the FULL
    # 1.28 MHz Nyquist, so the replica's inner edge (1.28 MHz from the signal
    # center) lands exactly on the anti-imaging filter's -6 dB cutoff, not in the
    # stopband.  A working 81-tap Kaiser filter therefore gives ~25-30 dBc (the
    # transition band limits it), while a MISSING/broken filter gives ~0 dBc.
    # >=20 dBc is the discriminator "filter present" vs "filter absent"; the
    # absolute value is reported separately as a known spur to watch on the board.
    "image_suppression_min_db": 20.0,
    # Guard margin on the SUM: the two signals are 3.6 MHz apart with 2.56 MHz
    # occupancy, leaving 1.04 MHz; their skirts must be >20 dB down at mid-gap.
    "guard_suppression_min_db": 20.0,
    # int16 quant: CLIP_GUARD 2047 * 16 = 32752 < 32767 => zero saturation by
    # construction; require peak <= 32752 and zero clipped samples.
    "int16_peak_max": 32752.0,
    "int16_saturation_ratio_max": 0.0,
    # Quantization step 16 (int16) => error var 256/12 per component; require the
    # composite quantization SNR >= 40 dB (very conservative for 16-bit).
    "quant_snr_min_db": 40.0,
    # Periodic wrap: frame ends with 2048 zeros; after resample the tail is spread
    # but must stay far below the signal peak (< -30 dBc).  d==0 (perfectly
    # continuous) is reported as None and passes.
    "wrap_discontinuity_max_dbc": -30.0,
}

# FIR recovery filter: passband 0..1.3 MHz (signal), stopband >= 3.6 MHz (other
# path after down-convert) at 10.24 MS/s, linear phase (group delay 80 samples).
FIR_TAPS = 161
FIR_CUTOFF_HZ = 1.3e6
FIR_DELAY = (FIR_TAPS - 1) // 2

# In-band / guard / out-of-band regions (Hz, relative to LO), frozen + justified:
#   source Nyquist = 1.28 MHz; A centered -1.8 MHz, B centered +1.8 MHz.
BAND_HALF_HZ = C.SAMPLE_RATE / 2.0          # 1.28 MHz
A_LO, A_HI = -1.8e6 - BAND_HALF_HZ, -1.8e6 + BAND_HALF_HZ
B_LO, B_HI = +1.8e6 - BAND_HALF_HZ, +1.8e6 + BAND_HALF_HZ
GUARD_LO, GUARD_HI = A_HI, B_LO             # -0.52 .. +0.52 MHz
NYQUIST = C.TX_SAMPLE_RATE / 2.0            # 5.12 MHz


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _welch(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    f, psd = welch(z, fs=C.TX_SAMPLE_RATE, nperseg=4096, return_onesided=False)
    return np.fft.fftshift(f), np.fft.fftshift(psd)


def _band_power(f: np.ndarray, psd: np.ndarray, lo: float, hi: float) -> float:
    m = (f >= lo) & (f <= hi)
    return float(np.trapezoid(psd[m], f[m]))


def _corr_nmse(rec: np.ndarray, truth: np.ndarray) -> dict:
    """Best-integer-lag normalized correlation and complex-gain NMSE."""
    rec = np.asarray(rec)
    truth = np.asarray(truth)
    if rec.size < 16 or truth.size < 16:
        return {"corr": 0.0, "nmse_db": np.inf, "lag": 0, "gain": 0.0}
    cc = correlate(rec, truth, mode="full", method="fft")
    lag = int(np.argmax(np.abs(cc))) - (truth.size - 1)
    # align truth to rec at best lag
    if lag >= 0:
        a, b = rec[lag:lag + truth.size], truth
    else:
        a, b = rec[:lag], truth[-lag:]
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    if n < 16:
        return {"corr": 0.0, "nmse_db": np.inf, "lag": lag, "gain": 0.0}
    denom = np.sqrt(np.sum(np.abs(a) ** 2) * np.sum(np.abs(b) ** 2))
    corr = 0.0 if denom == 0 else float(abs(np.vdot(a, b)) / denom)
    g = np.vdot(a, b) / np.vdot(b, b) if np.vdot(b, b) != 0 else 0.0
    err = np.sum(np.abs(a - g * b) ** 2)
    sig = np.sum(np.abs(g * b) ** 2)
    nmse_db = float(10 * np.log10(err / sig)) if sig > 0 else np.inf
    return {"corr": corr, "nmse_db": nmse_db, "lag": lag, "gain": complex(g)}


def _recover_exact(comp: np.ndarray, df: float) -> np.ndarray:
    base = comp * np.exp(-2j * np.pi * df * np.arange(len(comp)) / C.TX_SAMPLE_RATE)
    return resample_poly(base, 1, C.UPSAMPLE)


def _recover_fir(comp: np.ndarray, df: float) -> np.ndarray:
    base = comp * np.exp(-2j * np.pi * df * np.arange(len(comp)) / C.TX_SAMPLE_RATE)
    filt = firwin(FIR_TAPS, FIR_CUTOFF_HZ, fs=C.TX_SAMPLE_RATE)
    y = lfilter(filt, 1.0, base)
    return y[FIR_DELAY::C.UPSAMPLE]


def _payload_region(frame: np.ndarray) -> np.ndarray:
    # frame layout: [zeros2048, train2048, tile(source,8)=8192, tail2048, zeros2048]
    return frame[4096:12288]  # 8x1024 payload tiles


def _recover_payload(rec: np.ndarray, truth_frame: np.ndarray, truth_payload: np.ndarray) -> dict:
    """De-tile the recovered payload (8x1024 -> mean) and compare to the known source.

    The truth payload is the first tile of the SCALED frame's payload region, i.e.
    ``source * SCALE``.  This is the "载荷/张量对照" the taskbook asks for.
    """
    rec = np.asarray(rec)
    truth_frame = np.asarray(truth_frame)
    lag = int(np.argmax(np.abs(correlate(rec, truth_frame, mode="full", method="fft")))
              - (truth_frame.size - 1))
    if lag >= 0:
        r = rec[lag:lag + truth_frame.size]
    else:
        r = rec[:lag]
    region = r[4096:12288]  # 8x1024 payload tiles (after 2048 zeros + 2048 train)
    if region.size < 8192:
        return {"corr": 0.0, "nmse_db": np.inf, "lag": lag}
    tiles = region[:8192].reshape(8, 1024)
    payload = tiles.mean(axis=0)
    return _corr_nmse(payload, truth_payload)


def _sanitize(o):
    """Recursively convert to JSON-safe Python types (complex / numpy / non-finite)."""
    if isinstance(o, complex):
        return [float(o.real), float(o.imag)]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return [_sanitize(x) for x in o.tolist()]
    if isinstance(o, float):
        return None if not np.isfinite(o) else o
    if isinstance(o, dict):
        return {str(k): _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(x) for x in o]
    return o


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ui-tx", required=True)
    ap.add_argument("--pilot", required=True)
    ap.add_argument("--link", required=True)
    ap.add_argument("--class-a", type=int, default=3)
    ap.add_argument("--class-b", type=int, default=9)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # -- identity: our reproduction must match the frozen sources -------------
    id_problems = C.verify_identity(Path(args.ui_tx), Path(args.pilot), Path(args.link))
    if id_problems:
        print("IDENTITY_MISMATCH " + json.dumps(id_problems))
        (out / "identity.json").write_text(json.dumps({"ok": False, "problems": id_problems}, indent=2))
        return 1
    print("IDENTITY_OK")

    rows = C.load_manifest(Path(args.manifest))
    sel = {}
    for cls in (args.class_a, args.class_b):
        sel[cls] = next(v for v in rows if int(v["file"].split("_")[0]) == cls)

    dataset = Path(args.dataset)
    payloads = {}
    frames = {}
    for cls, row in sel.items():
        data = (dataset / row["file"]).read_bytes()
        assert _sha(data) == row["source_sha256"], f"source SHA mismatch {row['file']}"
        payloads[cls] = data
        frames[cls] = C.build_frame(data)
        print(f"SOURCE_OK class={cls} file={row['file']} sha={row['source_sha256'][:16]}...")

    dfA, dfB = C.SIGNAL_OFFSETS_HZ
    tx_a = C.resample_shift(frames[args.class_a], dfA)
    tx_b = C.resample_shift(frames[args.class_b], dfB)
    both = tx_a + tx_b
    silence = np.zeros_like(tx_a)

    scenarios = {
        "a_only": tx_a,
        "b_only": tx_b,
        "both": both,
        "silence": silence,
    }
    # freeze waveforms (float complex128 bytes, deterministic)
    wave_shas = {}
    for name, w in scenarios.items():
        b = w.astype("<c16").tobytes()
        wave_shas[name] = _sha(b)
        (out / f"wave_{name}.c16").write_bytes(b)
    print("WAVEFORMS_FROZEN " + json.dumps(wave_shas))

    # -- recovery (shift sign + invertibility + separability + payload) ---------
    recovery = {}
    for tag, df, truth in (("A", dfA, frames[args.class_a]), ("B", dfB, frames[args.class_b])):
        single = tx_a if tag == "A" else tx_b
        rec_resample_single = _recover_exact(single, df)
        rec_fir_single = _recover_fir(single, df)
        rec_resample_both = _recover_exact(both, df)
        rec_fir_both = _recover_fir(both, df)
        truth_payload = truth[4096:5120]  # source * SCALE (first payload tile)
        recovery[tag] = {
            "single_resample": _corr_nmse(rec_resample_single, truth),
            "single_fir": _corr_nmse(rec_fir_single, truth),
            "from_both_resample": _corr_nmse(rec_resample_both, truth),
            "from_both_fir": _corr_nmse(rec_fir_both, truth),
            "payload_single": _recover_payload(rec_fir_single, truth, truth_payload),
            "payload_from_both": _recover_payload(rec_fir_both, truth, truth_payload),
        }

    # -- spectrum: centroid, occupied BW, image rejection, guard margin --------
    def _occ_bw(f: np.ndarray, psd: np.ndarray, cent: float) -> float:
        """99% occupied bandwidth (symmetric around centroid)."""
        df = f[1] - f[0]
        total = float(np.sum(psd)) * df
        order = np.argsort(np.abs(f - cent))
        cum = 0.0
        for i in order:
            cum += float(psd[i]) * df
            if cum >= 0.99 * total:
                return float(2 * abs(f[i] - cent))
        return float(2 * abs(f[order[-1]] - cent))

    def _path_spec(w: np.ndarray, c0: float) -> dict:
        f, psd = _welch(w)
        lo, hi = c0 - BAND_HALF_HZ, c0 + BAND_HALF_HZ
        m = (f >= lo) & (f <= hi)
        p_in = float(np.trapezoid(psd[m], f[m]))
        cent = float(np.trapezoid(f[m] * psd[m], f[m]) / max(np.trapezoid(psd[m], f[m]), 1e-30))
        alias_c = c0 - np.sign(c0) * C.SAMPLE_RATE  # nearest +2.56 MHz image toward 0 Hz
        p_alias = _band_power(f, psd, alias_c - BAND_HALF_HZ, alias_c + BAND_HALF_HZ)
        return {
            "center_hz": cent,
            "center_err_hz": cent - c0,
            "inband_power": p_in,
            "occupied_bw_99_hz": _occ_bw(f, psd, cent),
            "alias_center_hz": alias_c,
            "image_suppression_dbc": float(10 * np.log10(p_alias / p_in)) if p_in > 0 else -np.inf,
        }

    spec_a = _path_spec(tx_a, -1.8e6)
    spec_b = _path_spec(tx_b, +1.8e6)
    f, psd = _welch(both)
    p_guard = _band_power(f, psd, GUARD_LO, GUARD_HI)
    p_in_both = max(spec_a["inband_power"], spec_b["inband_power"])
    spectrum = {
        "a": spec_a,
        "b": spec_b,
        "guard_suppression_dbc": float(10 * np.log10(p_guard / p_in_both)) if p_in_both > 0 else -np.inf,
        "nyquist_margin_hz": float(NYQUIST - B_HI),
    }

    # -- int16 quantization ----------------------------------------------------
    def _quant_metrics(z: np.ndarray, label: str) -> dict:
        iq = C.int16_quantize(z)
        comp = np.abs(iq).max()
        n_sat = C.saturation_count(z)  # float-domain overflow check (int16 cast wraps)
        rms = float(np.sqrt(np.mean(np.abs(C.to_float(iq)) ** 2)))
        per = {k: float(np.sqrt(np.mean(np.abs(C.to_float(C.int16_quantize(w))) ** 2)))
               for k, w in scenarios.items() if k != "silence"}
        float_rms = float(np.sqrt(np.mean(np.abs(z) ** 2)))
        err = C.to_float(iq) - z
        qn = float(np.sqrt(np.mean(np.abs(err) ** 2)))
        snr = float(10 * np.log10(float_rms ** 2 / (qn ** 2))) if qn > 0 else np.inf
        papr = float((np.max(np.abs(z)) ** 2) / (float_rms ** 2)) if float_rms > 0 else np.inf
        return {
            "label": label,
            "int16_peak": int(comp),
            "saturation_ratio": n_sat / (len(z) * 2),
            "total_rms": rms,
            "float_rms": float_rms,
            "papr_db": float(10 * np.log10(papr)) if papr > 0 else np.inf,
            "quant_noise_rms": qn,
            "quant_snr_db": snr,
        }

    quant = {
        "a_only": _quant_metrics(tx_a, "a_only"),
        "b_only": _quant_metrics(tx_b, "b_only"),
        "both": _quant_metrics(both, "both"),
    }
    for k, v in _quant_metrics(tx_a, "_").items():
        pass  # (helper already computed per-scenario)

    # -- periodic wrap discontinuity -------------------------------------------
    # d == 0 means perfectly continuous (best case): report dbc=None, which passes.
    wrap = {}
    for name, w in scenarios.items():
        if name == "silence":
            continue
        d = float(abs(w[-1] - w[0]))
        peak = float(max(np.abs(w).max(), 1e-30))
        dbc = None if d == 0.0 else float(20 * np.log10(d / peak))
        wrap[name] = {"abs": d, "dbc": dbc}

    # -- plots ------------------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 5))
        for name, w in scenarios.items():
            if name == "silence":
                continue
            iq = C.int16_quantize(w)
            wq = C.to_float(iq)
            ff, pp = welch(wq, fs=C.TX_SAMPLE_RATE, nperseg=4096, return_onesided=False)
            ff = np.fft.fftshift(ff) / 1e6
            pp = np.fft.fftshift(pp)
            plt.plot(ff, 10 * np.log10(pp + 1e-30), label=name)
        plt.xlabel("MHz (rel. LO)")
        plt.ylabel("PSD dB")
        plt.title("int16-quantized dual-path TX spectrum (A=-1.8 MHz, B=+1.8 MHz)")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(out / "psd_dual.png", dpi=110)
        plt.close()
    except Exception as exc:  # noqa: BLE001
        print(f"PLOT_SKIPPED {exc!r}")

    report = {
        "kind": "OFFLINE_TX_DIGITAL_VERIFICATION",
        "thresholds": THRESHOLDS,
        "waveform_sha256": wave_shas,
        "recovery": recovery,
        "spectrum": spectrum,
        "quantization": quant,
        "wrap_discontinuity": wrap,
    }
    (out / "verification_report.json").write_text(json.dumps(_sanitize(report), indent=2))

    # -- verdict ----------------------------------------------------------------
    checks = []
    def _c(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    _c("identity", not id_problems, id_problems or "ok")
    _c("A_single_resample", recovery["A"]["single_resample"]["corr"] >= THRESHOLDS["recover_corr_resample_min"],
       recovery["A"]["single_resample"])
    _c("B_single_resample", recovery["B"]["single_resample"]["corr"] >= THRESHOLDS["recover_corr_resample_min"],
       recovery["B"]["single_resample"])
    _c("A_single_fir", recovery["A"]["single_fir"]["corr"] >= THRESHOLDS["recover_corr_fir_min"]
       and recovery["A"]["single_fir"]["nmse_db"] <= THRESHOLDS["recover_nmse_fir_max_db"],
       recovery["A"]["single_fir"])
    _c("B_single_fir", recovery["B"]["single_fir"]["corr"] >= THRESHOLDS["recover_corr_fir_min"]
       and recovery["B"]["single_fir"]["nmse_db"] <= THRESHOLDS["recover_nmse_fir_max_db"],
       recovery["B"]["single_fir"])
    _c("A_separable_from_both", recovery["A"]["from_both_fir"]["corr"] >= THRESHOLDS["separate_corr_fir_min"]
       and recovery["A"]["from_both_fir"]["nmse_db"] <= THRESHOLDS["separate_nmse_fir_max_db"],
       recovery["A"]["from_both_fir"])
    _c("B_separable_from_both", recovery["B"]["from_both_fir"]["corr"] >= THRESHOLDS["separate_corr_fir_min"]
       and recovery["B"]["from_both_fir"]["nmse_db"] <= THRESHOLDS["separate_nmse_fir_max_db"],
       recovery["B"]["from_both_fir"])
    _c("A_payload_from_both", recovery["A"]["payload_from_both"]["corr"] >= THRESHOLDS["payload_corr_min"],
       recovery["A"]["payload_from_both"])
    _c("B_payload_from_both", recovery["B"]["payload_from_both"]["corr"] >= THRESHOLDS["payload_corr_min"],
       recovery["B"]["payload_from_both"])
    _c("A_center_hz", abs(spectrum["a"]["center_err_hz"]) <= THRESHOLDS["center_err_max_hz"],
       spectrum["a"]["center_err_hz"])
    _c("B_center_hz", abs(spectrum["b"]["center_err_hz"]) <= THRESHOLDS["center_err_max_hz"],
       spectrum["b"]["center_err_hz"])
    _c("A_occ_bw", THRESHOLDS["occ_bw_min_hz"] <= spectrum["a"]["occupied_bw_99_hz"] <= THRESHOLDS["occ_bw_max_hz"],
       spectrum["a"]["occupied_bw_99_hz"])
    _c("B_occ_bw", THRESHOLDS["occ_bw_min_hz"] <= spectrum["b"]["occupied_bw_99_hz"] <= THRESHOLDS["occ_bw_max_hz"],
       spectrum["b"]["occupied_bw_99_hz"])
    _c("A_image_suppression", -spectrum["a"]["image_suppression_dbc"] >= THRESHOLDS["image_suppression_min_db"],
       spectrum["a"]["image_suppression_dbc"])
    _c("B_image_suppression", -spectrum["b"]["image_suppression_dbc"] >= THRESHOLDS["image_suppression_min_db"],
       spectrum["b"]["image_suppression_dbc"])
    _c("guard_margin", -spectrum["guard_suppression_dbc"] >= THRESHOLDS["guard_suppression_min_db"],
       spectrum["guard_suppression_dbc"])
    _c("int16_no_saturation", quant["both"]["int16_peak"] <= THRESHOLDS["int16_peak_max"]
       and quant["both"]["saturation_ratio"] <= THRESHOLDS["int16_saturation_ratio_max"],
       f"peak={quant['both']['int16_peak']} sat={quant['both']['saturation_ratio']}")
    _c("quant_snr", quant["both"]["quant_snr_db"] >= THRESHOLDS["quant_snr_min_db"],
       quant["both"]["quant_snr_db"])
    _c("wrap_ok", all(wrap[k]["dbc"] is None or wrap[k]["dbc"] <= THRESHOLDS["wrap_discontinuity_max_dbc"]
                      for k in wrap), wrap)

    (out / "verdict.json").write_text(
        json.dumps(_sanitize({"checks": checks, "pass": all(c["ok"] for c in checks)}), indent=2))
    npass = sum(1 for c in checks if c["ok"])
    print(f"VERDICT pass={npass}/{len(checks)}")
    for c in checks:
        print(f"  {'PASS' if c['ok'] else 'FAIL'} {c['check']} {json.dumps(_sanitize(c['detail']))}")
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
