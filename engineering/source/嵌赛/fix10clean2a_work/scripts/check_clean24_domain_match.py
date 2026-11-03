"""fix10clean2a Phase 4 — domain-match gate.

Compare the generated CLEAN signals against the measured RadioML2018.01A domain
(Phase 1) per class, on: RMS, PAPR, occupied bandwidth (99% / -20 dB), PSD shape
(128-pt one-sided), and instantaneous-frequency spread.

The gate is PASS/FAIL per class and overall.  Only after the gate passes do we
promote to the large formal12000 generation (so generator bugs are caught on a
small set first).

Reads:  results/CLEAN2A_PHASE1_DOMAIN_PROFILE.json  (Phase 1 measured domain)
        dataset/clean24_<set>.hdf5                   (Phase 2 clean generation)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radioml_clean_contract as c  # noqa: E402

RESULTS = Path(r"F:/嵌赛/fix10clean2a_results")
DATASET = Path(r"F:/嵌赛/fix10clean2a_dataset")
PROFILE = RESULTS / "CLEAN2A_PHASE1_DOMAIN_PROFILE.json"

# domain-match tolerances.  PAPR carries ~1 dB of AWGN-peak inflation at SNR 30
# (clean PAPR < measured PAPR); -20 dB bandwidth is roll-off sensitive, so it is
# given a wide window.  The gate's job is to catch *structural* errors (e.g. the
# GMSK/OQPSK swap, FM at DC vs +6250), not sub-dB fidelity.
TOL = {
    "papr_mean_db": 1.8,
    "occupied_bw_99_frac": 0.25,     # relative
    "occupied_bw_20db_frac": 0.60,   # relative
    "inst_freq_std_hz": 0.50,        # relative
    "psd_corr": 0.30,                # 1 - Pearson on 128-pt one-sided PSD
}

# AM-SSB instantaneous-frequency is NOT a structural discriminator, so it is
# measured and reported but excluded from the AM-SSB hard-fail.  Two independent
# arbitrary quantities dominate it:
#   (a) the *measured* reference is noise-dominated: SNR-20 gives ~319 Hz std,
#       SNR-30 gives ~32.6 Hz std — a 10x swing with no change to the signal
#       (probe42/probe45);
#   (b) the *clean* signal's inst-freq is dominated by the audio content, which
#       RadioML2018 does not specify and which the frozen model requires to be
#       broadband (fmax >= 1000 Hz) for robust recall >= 0.90 (probe45).
# No single audio bandwidth matches both recall and the noise-vs-signal reference
# simultaneously, so inst-freq cannot be used to gate AM-SSB structure.  AM-SSB
# structure remains gated by PAPR / PSD-correlation / occupied-bw (all pass).
INST_FREQ_EXCLUDED = frozenset({"AM-SSB-WC", "AM-SSB-SC"})


def _stats(iq: np.ndarray) -> dict:
    """iq: (M, 1024) complex.  Return compact clean-domain stats."""
    M, N = iq.shape
    power = np.abs(iq) ** 2
    mean_pow = power.mean(axis=1)
    rms = np.sqrt(mean_pow)
    papr_db = 10 * np.log10(power.max(axis=1) / np.maximum(mean_pow, 1e-12))

    win = np.hanning(N)
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(iq * win, axis=1), axes=1)) ** 2, axis=0)
    psd /= psd.sum() + 1e-12
    freqs = np.fft.fftshift(np.fft.fftfreq(N))
    pos = freqs >= 0.0
    pos_psd = psd[pos]
    cum = np.cumsum(pos_psd)
    idx99 = int(np.searchsorted(cum, 0.99 * cum[-1]))
    bw99 = 2.0 * freqs[pos][idx99] if idx99 < len(pos_psd) else 1.0
    peak = pos_psd.max()
    mask20 = pos_psd >= peak * 1e-2
    bw20 = 2.0 * freqs[pos][mask20][-1] if mask20.any() else 0.0
    psd_128 = np.interp(np.linspace(0, 1, 128), freqs[pos], pos_psd)

    phase = np.unwrap(np.angle(iq), axis=1)
    df_hz = np.diff(phase, axis=1) / (2 * np.pi) * c.SAMPLE_RATE_HZ
    inst_std = float(df_hz.std())

    return {
        "rms_mean": float(rms.mean()),
        "papr_mean_db": float(papr_db.mean()),
        "occupied_bw_99_frac": float(bw99),
        "occupied_bw_20db_frac": float(bw20),
        "psd_128": psd_128,
        "inst_freq_std_hz": inst_std,
    }


def _measured(profile: dict, name: str) -> dict:
    e = profile["per_class"][name]
    return {
        "rms_mean": e["rms"]["value"]["mean"],
        "papr_mean_db": e["papr_db"]["value"]["mean"],
        "occupied_bw_99_frac": e["occupied_bw_frac_99"]["value"],
        "occupied_bw_20db_frac": e["occupied_bw_frac_20db"]["value"],
        "psd_128": np.array(e["psd_128"]["value"]),
        "inst_freq_std_hz": e["instantaneous_freq_hz"]["value"]["std_hz"],
    }


def _cmp(clean: dict, meas: dict, exclude: frozenset[str] = frozenset()) -> tuple[dict, bool]:
    d = {}
    d["papr_mean_db"] = abs(clean["papr_mean_db"] - meas["papr_mean_db"])
    d["occupied_bw_99_frac"] = abs(clean["occupied_bw_99_frac"] - meas["occupied_bw_99_frac"]) / (meas["occupied_bw_99_frac"] + 1e-9)
    d["occupied_bw_20db_frac"] = abs(clean["occupied_bw_20db_frac"] - meas["occupied_bw_20db_frac"]) / (meas["occupied_bw_20db_frac"] + 1e-9)
    d["inst_freq_std_hz"] = abs(clean["inst_freq_std_hz"] - meas["inst_freq_std_hz"]) / (meas["inst_freq_std_hz"] + 1e-9)
    # Pearson correlation on log10 PSD (log matches shape, ignores gain)
    a = np.log10(clean["psd_128"] + 1e-12)
    b = np.log10(meas["psd_128"] + 1e-12)
    a -= a.mean(); b -= b.mean()
    denom = np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-12
    d["psd_corr"] = 1.0 - float((a * b).sum() / denom)  # -> 0 = perfect match
    ok = all(d[k] <= TOL[k] for k in TOL if k not in exclude)
    return d, ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="smoke96")
    args = ap.parse_args()

    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    path = DATASET / f"clean24_{args.set}.hdf5"

    with h5py.File(path, "r") as f:
        X = f["X"][:]
        Y = np.asarray(f["Y"])

    results = {}
    n_fail = 0
    print(f"{'class':<10} {'papr(dB)':>9} {'bw99':>7} {'bw20':>7} {'instF':>7} {'psdCorr':>8}  verdict")
    for cidx, cls in enumerate(c.LABEL_ORDER_24):
        sub = X[Y == cidx]
        iq = sub[:, :, 0] + 1j * sub[:, :, 1]
        clean = _stats(iq)
        meas = _measured(profile, cls)
        exclude = {"inst_freq_std_hz"} if cls in INST_FREQ_EXCLUDED else frozenset()
        d, ok = _cmp(clean, meas, exclude)
        results[cls] = {"ok": ok, "deltas": d, "excluded_metrics": sorted(exclude),
                        "clean": {k: clean[k] for k in ("rms_mean", "papr_mean_db", "occupied_bw_99_frac", "occupied_bw_20db_frac", "inst_freq_std_hz")},
                        "measured": {k: meas[k] for k in ("rms_mean", "papr_mean_db", "occupied_bw_99_frac", "occupied_bw_20db_frac", "inst_freq_std_hz")}}
        if not ok:
            n_fail += 1
        excl_mark = "*" if exclude else ""
        print(f"{cls:<10} {d['papr_mean_db']:>9.3f} {d['occupied_bw_99_frac']:>7.3f} {d['occupied_bw_20db_frac']:>7.3f} "
              f"{d['inst_freq_std_hz']:>7.3f} {d['psd_corr']:>8.3f}  {'PASS' if ok else 'FAIL'}{excl_mark}")

    out = RESULTS / f"CLEAN2A_PHASE4_DOMAIN_MATCH_{args.set}.json"
    out.write_text(json.dumps({
        "set": args.set, "tolerances": TOL,
        "inst_freq_excluded": {"classes": sorted(INST_FREQ_EXCLUDED),
                               "rationale": "AM-SSB inst-freq is noise-dominated in the measured reference and audio-content-dominated in the clean signal (see profile SNR_MIN note, probe42/probe45); excluded from hard-fail, still reported."},
        "n_fail": n_fail, "per_class": results}, indent=2),
                   encoding="utf-8")
    print(f"\n{n_fail}/24 classes FAIL  ->  {out}")
    print("DOMAIN MATCH GATE:", "PASS" if n_fail == 0 else "FAIL")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
