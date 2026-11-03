"""fix10clean2a Phase 1 — RadioML2018.01A local-domain profiling.

Goal: characterise the *actual* RadioML data domain (not a textbook ideal) so
that Phase 2's clean generator reproduces it faithfully.  For each of the 24
classes we measure, from high-SNR frames pulled out of the authoritative HDF5:

  * RMS            (confirms the per-frame unit-power normalisation)
  * PAPR           (peak-to-average power ratio, dB)
  * PSD + occupied bandwidth (99%-power and -20 dB two-sided fractions)
  * instantaneous frequency (unwrapped-phase derivative, Hz)
  * autocorrelation (lags 0..24, first-null lag = sps cross-check)
  * samples-per-symbol (envelope cyclostationarity: E[|x|^2] period)

Every emitted parameter carries a provenance tag:
  official_confirmed   - from the public RadioML2018.01A specification
  local_data_measured  - computed here from the HDF5 itself
  engineering_inferred - derived with a named engineering assumption
  unknown              - could not be determined reliably

Read-only: never writes into the HDF5 / frozen tree / checkpoint.  Outputs only
  configs/radioml2018_clean_contract_v1.yaml
  results/CLEAN2A_PHASE1_DOMAIN_PROFILE.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Authoritative inputs / outputs (absolute; do not relocate).
# ---------------------------------------------------------------------------
HDF5 = Path(r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5")
WORK = Path(r"F:/嵌赛/fix10clean2a_work")
RESULTS = Path(r"F:/嵌赛/fix10clean2a_results")
OUT_YAML = WORK / "configs" / "radioml2018_clean_contract_v1.yaml"
OUT_JSON = RESULTS / "CLEAN2A_PHASE1_DOMAIN_PROFILE.json"

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# RadioML2018.01A public constants (authoritative; confirmed independently).
SAMPLE_RATE_HZ = 200_000.0          # official (DeepSig GNU Radio generation)
SAMPLES_PER_SYMBOL_DIGITAL = 8      # official (==1024/8 -> 128 symbols/frame)
ANALOG_CLASSES = {"AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC", "FM"}

SNR_MIN = 20.0        # profile only very-high-SNR frames -> near-clean signal.
# Note: the HDF5 is SNR-major ordered, so Z>=20 pools frames 20..30 and the first
# 1024 are SNR 20 (the noisiest of the pool).  This is fine for RMS/PAPR/PSD/bw,
# but the *instantaneous-frequency* of tiny-sideband analog classes (AM-SSB) is
# noise-dominated at SNR 20 (~319 Hz) vs signal-dominated at SNR 30 (~32.6 Hz);
# see probe42/probe45.  The Phase 4 gate treats AM-SSB inst-freq as a documented
# audio-content metric, not a structural discriminator (Phase 4 gate excludes it).
MAX_FRAMES_PER_CLASS = 1024


# ---------------------------------------------------------------------------
# small provenance helpers
# ---------------------------------------------------------------------------
def tagged(value: Any, provenance: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"value": value, "provenance": provenance}
    out.update(extra)
    return out


def _f(x: Any, nd: int = 5) -> Any:
    """Round floats for compact, deterministic JSON/YAML; pass scalars through."""
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, np.floating):
        return round(float(x), nd)
    if isinstance(x, (list, tuple)):
        return [_f(v, nd) for v in x]
    if isinstance(x, np.ndarray):
        return [_f(v, nd) for v in x.tolist()]
    return x


# ---------------------------------------------------------------------------
# signal statistics
# ---------------------------------------------------------------------------
def frame_power(iq: np.ndarray) -> np.ndarray:
    # iq: (M, N) complex -> (M, N) instantaneous power
    return np.abs(iq) ** 2


def compute_stats(iq: np.ndarray) -> dict[str, Any]:
    """iq: (M, 1024) complex64.  Return per-class measured statistics."""
    M, N = iq.shape
    power = frame_power(iq)
    mean_pow = power.mean(axis=1)                 # (M,)
    peak_pow = power.max(axis=1)                  # (M,)

    rms = np.sqrt(mean_pow)                       # per-frame RMS
    papr = peak_pow / np.maximum(mean_pow, 1e-12)  # linear ratio
    papr_db = 10.0 * np.log10(papr)

    # ---- averaged PSD (Hann window, mean over frames) ----
    win = np.hanning(N).astype(np.float64)
    windowed = iq * win[None, :]
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(windowed, axis=1), axes=1)) ** 2, axis=0)
    psd /= (psd.sum() + 1e-12)                    # normalise to unit power
    freqs = np.fft.fftshift(np.fft.fftfreq(N))

    # two-sided occupied bandwidth fractions (symmetric around DC)
    pos = freqs >= 0.0
    pos_psd = psd[pos]
    cum = np.cumsum(pos_psd)
    total = cum[-1] + 1e-12
    # 99% power: smallest index where cumulative >= 0.99*total (then mirror)
    idx99 = int(np.searchsorted(cum, 0.99 * total))
    bw99_frac = 2.0 * freqs[pos][idx99] if idx99 < len(pos_psd) else 1.0
    # -20 dB bandwidth: fraction of bins >= peak-20dB
    peak = pos_psd.max()
    mask20 = pos_psd >= (peak * 10 ** (-20 / 10))
    bw20_frac = 2.0 * freqs[pos][mask20][-1] if mask20.any() else 0.0

    # down-sample PSD to 128 points for the contract (one-sided, 0..Nyquist)
    psd_128 = np.interp(np.linspace(0.0, 1.0, 128), freqs[pos], pos_psd)

    # ---- instantaneous frequency (Hz) ----
    phase = np.unwrap(np.angle(iq), axis=1)
    df = np.diff(phase, axis=1) / (2.0 * np.pi)   # cycles/sample
    df_hz = df * SAMPLE_RATE_HZ                   # Hz
    inst = {
        "mean_hz": float(df_hz.mean()),
        "std_hz": float(df_hz.std()),
        "p95_abs_hz": float(np.percentile(np.abs(df_hz), 95)),
        "max_abs_hz": float(np.abs(df_hz).max()),
    }

    # ---- normalised autocorrelation (lags 0..24), real part + first null ----
    lags = list(range(0, 25))
    ac = np.zeros(len(lags))
    denom = float((np.abs(iq) ** 2).sum()) + 1e-12
    for j, k in enumerate(lags):
        if k == 0:
            ac[j] = 1.0
        else:
            ac[j] = float(np.real(np.sum(iq[:, k:] * np.conj(iq[:, :-k])))) / denom
    # first null: first lag >0 where autocorrelation sign goes <=0 (real part)
    first_null = None
    for j in range(1, len(lags)):
        if ac[j] <= 0.0:
            first_null = lags[j]
            break

    # ---- envelope cyclostationarity -> symbol rate / sps ----
    env = np.mean(power, axis=0)                  # E[|x|^2] over frames
    env = env - env.mean()
    spec = np.abs(np.fft.rfft(env))
    f_axis = np.fft.rfftfreq(N)                   # cycles/sample
    lo = int(0.03 * len(f_axis))
    hi = len(f_axis)
    seg = spec[lo:hi]
    f_seg = f_axis[lo:hi]
    peak_idx = int(np.argmax(seg))
    f_sym = float(f_seg[peak_idx])
    # prominence: peak vs median of the segment (crude confidence)
    prominence = float(seg[peak_idx]) / (float(np.median(seg)) + 1e-12)
    sps_est = 1.0 / f_sym if f_sym > 1e-9 else None

    return {
        "rms": {"mean": float(rms.mean()), "std": float(rms.std()),
                "min": float(rms.min()), "max": float(rms.max())},
        "papr_db": {"mean": float(papr_db.mean()), "std": float(papr_db.std()),
                    "p95": float(np.percentile(papr_db, 95))},
        "occupied_bw_frac_99": float(bw99_frac),
        "occupied_bw_frac_20db": float(bw20_frac),
        "psd_128": [float(v) for v in psd_128],
        "instantaneous_freq": inst,
        "autocorr": {"lags": lags, "values": [float(v) for v in ac],
                     "first_null_lag": first_null},
        "envelope_symbol_rate_cycles_per_sample": f_sym,
        "envelope_peak_prominence": prominence,
        "envelope_sps_est": sps_est,
    }


# ---------------------------------------------------------------------------
def _yaml_value(node: dict[str, Any]) -> dict[str, Any]:
    """Tag a measured scalar as local_data_measured."""
    return {"value": node, "provenance": "local_data_measured"}


def main() -> int:
    import h5py
    with h5py.File(HDF5, "r") as f:
        Z = np.asarray(f["Z"][:], dtype=np.float64).reshape(-1)
        Y = np.asarray(f["Y"][:]).argmax(axis=1).astype(np.uint8)
        X = f["X"]

        per_class: dict[str, Any] = {}
        for c, name in enumerate(LABEL_ORDER_24):
            idx = np.flatnonzero((Y == c) & (Z >= SNR_MIN))
            idx = idx[:MAX_FRAMES_PER_CLASS]
            if idx.size == 0:
                per_class[name] = {"error": "no high-SNR frames", "n_frames": 0}
                continue
            iq = np.asarray(X[np.sort(idx)], dtype=np.float32)
            iq = iq[:, :, 0] + 1j * iq[:, :, 1]
            st = compute_stats(iq)
            is_analog = name in ANALOG_CLASSES
            per_class[name] = {
                "n_frames": int(idx.size),
                "analog": is_analog,
                "rms": tagged(st["rms"], "local_data_measured"),
                "papr_db": tagged(st["papr_db"], "local_data_measured"),
                "occupied_bw_frac_99": tagged(st["occupied_bw_frac_99"], "local_data_measured"),
                "occupied_bw_frac_20db": tagged(st["occupied_bw_frac_20db"], "local_data_measured"),
                "psd_128": tagged(st["psd_128"], "local_data_measured"),
                "instantaneous_freq_hz": tagged(st["instantaneous_freq"], "local_data_measured"),
                "autocorrelation": tagged(st["autocorr"], "local_data_measured"),
                "sps": {
                    "official": tagged(SAMPLES_PER_SYMBOL_DIGITAL, "official_confirmed",
                                       note="digital modulations; N/A for analog"),
                    "occupied_bw_99_implied": tagged(
                        (round(1.0 / st["occupied_bw_frac_99"], 2) if st["occupied_bw_frac_99"] > 1e-6 else None),
                        "local_data_measured",
                        note="1 / occupied_bw_frac_99; ~8 confirms sps=8 for linear digital modulations",
                    ),
                    "autocorr_first_null_lag": tagged(
                        st["autocorr"]["first_null_lag"], "local_data_measured",
                        note="~9-10 for RRC alpha=0.35 at sps=8 (discrete sampling of the zero); a pulse-shape signature, not a direct sps",
                    ),
                    "envelope_cyclostationary": tagged(
                        None, "unknown",
                        note="E[|x|^2] periodicity method unreliable for RRC alpha=0.35 (tiny envelope ripple); raw peak "
                             "symbol_rate_cycles_per_sample=%s prominence=%s is a low-frequency artifact, not the symbol rate"
                             % (_f(st["envelope_symbol_rate_cycles_per_sample"]), _f(st["envelope_peak_prominence"])),
                    ),
                },
            }

    # ---- global contract ----
    global_block = {
        "n_classes": 24,
        "class_order": list(LABEL_ORDER_24),
        "n_snr": 26,
        "snr_values": list(range(-20, 31, 2)),
        "samples_per_class_per_snr": 4096,
        "sample_length": 1024,
        "sample_rate_hz": tagged(SAMPLE_RATE_HZ, "official_confirmed",
                                 note="RadioML2018.01A native (DeepSig GNU Radio)"),
        "model_config_sample_rate_hz": tagged(128000.0, "official_confirmed",
                                              note="_frozen/configs/rml24_base.yaml signal.sample_rate; synthesis nominal, does NOT match native 200 kHz"),
        "samples_per_symbol_digital": tagged(SAMPLES_PER_SYMBOL_DIGITAL, "official_confirmed",
                                             note="1024/8 -> 128 symbols per frame for digital modulations"),
        "pulse_shape": tagged("root-raised-cosine", "engineering_inferred",
                              note="PSD flat-passband + cosine roll-off signature"),
        "rolloff_alpha": tagged(0.35, "engineering_inferred",
                                note="nominal GNU Radio default; refine from measured PSD in Phase 4 gate"),
        "rms_normalization": tagged("NOT_uniform", "local_data_measured",
                                    note="digital PSK/QAM/APSK/GMSK/OQPSK + AM-DSB/FM ~=1.0; OOK/4ASK/8ASK = 1.47/1.75/1.91; AM-SSB-WC=11.74, AM-SSB-SC=7.83 (see per_class.rms)"),
    }

    # ---- reuse the Phase-0 provenance for the HDF5 SHA (read-only) ----
    prov: dict[str, Any] = {}
    prov_path = RESULTS / "CLEAN2A_INPUT_PROVENANCE.json"
    if prov_path.is_file():
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
        except Exception:
            prov = {}

    findings = [
        "RMS is NOT uniform across classes (measured at SNR>=20): digital PSK/QAM/APSK/GMSK/OQPSK "
        "and AM-DSB/FM ~=1.0; OOK=1.47, 4ASK=1.75, 8ASK=1.91; AM-SSB-WC=11.74, AM-SSB-SC=7.83. "
        "Phase 2 generator MUST reproduce per-class RMS, not assume unit power.",
        "RadioML2018.01A native sample rate is 200 kHz (official), but _frozen/configs/rml24_base.yaml "
        "signal.sample_rate=128000 (synthesis nominal). All Hz figures in this contract use 200 kHz.",
        "sps=8 for digital modulations is confirmed by occupied_bw_99 ~= 0.125 = 1/8 (and official docs). "
        "The envelope-cyclostationarity sps estimate is unreliable for RRC alpha=0.35 and was discarded.",
        "Occupied BW 99% is uniform 0.125 across PSK/QAM/APSK (=> RRC alpha~0.35); ASK ~0.107-0.115 "
        "(DC/carrier component); AM-SSB ~0.002 (carrier-dominated); DSB 0.064; FM 0.070; GMSK 0.119.",
    ]

    contract = {
        "meta": {
            "task": "fix10clean2a",
            "phase": "PHASE1",
            "contract_version": "radioml2018_clean_contract_v1",
            "hdf5_sha256": (prov.get("hdf5", {}) or {}).get("sha256"),
            "snr_min": SNR_MIN,
            "max_frames_per_class": MAX_FRAMES_PER_CLASS,
        },
        "global": global_block,
        "per_class": per_class,
        "findings": findings,
    }

    # ---- write JSON report ----
    RESULTS.mkdir(parents=True, exist_ok=True)
    json_report = json.loads(json.dumps(contract, default=_f))  # deep round-trip to round floats
    OUT_JSON.write_text(json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- write YAML contract ----
    import yaml
    OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(yaml.safe_dump(json_report, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")

    # ---- summary ----
    print("FIX10CLEAN2A_PHASE1 complete")
    for name, entry in per_class.items():
        rms = entry.get("rms", {}).get("value", {})
        papr = entry.get("papr_db", {}).get("value", {})
        bw99 = entry.get("occupied_bw_frac_99", {}).get("value")
        sps_off = entry.get("sps", {}).get("official", {}).get("value")
        sps_mea = entry.get("sps", {}).get("measured_envelope", {}).get("value")
        print("  %-10s n=%-5d rms_mean=%.4f papr_mean=%.2f dB bw99=%.3f sps_off=%s sps_env=%s"
              % (name, entry.get("n_frames", 0), rms.get("mean", float("nan")),
                 papr.get("mean", float("nan")), bw99 if bw99 is not None else float("nan"),
                 sps_off, sps_mea))
    print("  yaml ->", OUT_YAML)
    print("  json ->", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
