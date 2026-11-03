"""fix10clean2a Phase 3 — validate the generated clean datasets.

Checks, per dataset:
  1. file / shape / dtype / attribute contract
  2. all finite, no NaN/Inf (acceptance: NaN/Inf == 0)
  3. per-class RMS reproduces TARGET_RMS (tolerance 0.5%)
  4. balanced label counts (acceptance: formal_scored == n, excluded == 0)
  5. seed disjointness across sets (5-way leakage isolation: unique seed => unique
     message/audio/symbol-seq/window)
  6. GMSK/OQPSK class index correctness (source 22/23)
  7. determinism: a fresh regeneration reproduces the same SHA (report-only here;
     the generator is re-invoked by the host test to assert byte-identity)

Exit code 0 only when every check passes for every dataset requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radioml_clean_contract as c  # noqa: E402

OUT_DIR = Path(r"F:/嵌赛/fix10clean2a_dataset")
PYTHON = sys.executable
RMS_TOL = 0.005


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def validate_set(name: str) -> dict:
    path = OUT_DIR / f"clean24_{name}.hdf5"
    _fail(f"{name}: missing {path}") if not path.is_file() else None

    report: dict = {"name": name, "checks": {}}
    with h5py.File(path, "r") as f:
        X = f["X"]
        Y = np.asarray(f["Y"])
        seeds = np.asarray(f["seeds"])

        # 1. contract
        assert X.shape == (len(Y), c.SAMPLE_LENGTH, 2), X.shape
        assert X.dtype == np.float32, X.dtype
        assert Y.dtype == np.int64 and seeds.dtype == np.int64
        report["checks"]["shape"] = [int(X.shape[0]), int(X.shape[1]), int(X.shape[2])]
        report["checks"]["dtype"] = str(X.dtype)

        # 2. finite
        finite = bool(np.all(np.isfinite(X)))
        nan_count = int(np.isnan(X).sum())
        inf_count = int(np.isinf(X).sum())
        report["checks"]["finite"] = finite
        report["checks"]["nan_inf"] = [nan_count, inf_count]
        assert finite, f"{name}: non-finite samples (nan={nan_count} inf={inf_count})"

        # 3. per-class RMS
        rms_err_max = 0.0
        for cidx, cls in enumerate(c.LABEL_ORDER_24):
            sub = X[Y == cidx]
            assert sub.shape[0] > 0, f"{name}: class {cls} empty"
            frame = sub.reshape(-1, c.SAMPLE_LENGTH, 2)
            iq = frame[:, :, 0] + 1j * frame[:, :, 1]
            rms = float(np.sqrt(np.mean(np.abs(iq) ** 2)))
            target = c.TARGET_RMS[cls]
            err = abs(rms - target) / target
            rms_err_max = max(rms_err_max, err)
            assert err < RMS_TOL, f"{name}: {cls} rms {rms:.4f} vs target {target:.4f}"
        report["checks"]["rms_max_err"] = rms_err_max

        # 4. balance
        counts = np.bincount(Y, minlength=24)
        report["checks"]["per_class_counts"] = [int(v) for v in counts]
        assert counts.min() == counts.max(), f"{name}: unbalanced {counts}"
        report["checks"]["balanced"] = True
        report["checks"]["n_total"] = int(len(Y))
        report["checks"]["excluded"] = 0

        # 5. seed uniqueness within set
        assert len(np.unique(seeds)) == len(seeds), f"{name}: duplicate seeds"
        report["checks"]["seeds_unique"] = True
        report["checks"]["seed_range"] = [int(seeds.min()), int(seeds.max())]

        # 6. GMSK/OQPSK class order
        lo = json.loads(f.attrs["label_order"])
        assert lo == list(c.LABEL_ORDER_24), "label_order mismatch"
        assert lo[22] == "GMSK" and lo[23] == "OQPSK", "GMSK/OQPSK swap detected"
        report["checks"]["gmsk_oqpsk_ok"] = True
        report["checks"]["gen_sha"] = f.attrs["generator_sha256"][:16]

    report["path"] = str(path)
    report["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["smoke96", "dev2400", "formal12000"], default=None)
    ap.add_argument("--regenerate-determinism", action="store_true",
                    help="re-generate into a temp file and assert byte-identity")
    args = ap.parse_args()

    names = [args.set] if args.set else ["smoke96", "dev2400", "formal12000"]
    reports = []
    seed_ranges: dict[str, tuple[int, int]] = {}

    for name in names:
        r = validate_set(name)
        seed_ranges[name] = r["checks"]["seed_range"]
        reports.append(r)
        print(f"[PASS] {name}: n={r['checks']['n_total']} "
              f"rms_max_err={r['checks']['rms_max_err']:.5f} "
              f"nan_inf={r['checks']['nan_inf']} "
              f"seeds={r['checks']['seed_range']} sha={r['sha256'][:16]}")

    # cross-set seed disjointness (leakage isolation)
    if len(seed_ranges) > 1:
        ranges = sorted(seed_ranges.values(), key=lambda r: r[0])
        for i in range(len(ranges) - 1):
            assert ranges[i][1] < ranges[i + 1][0], f"seed overlap {ranges[i]} vs {ranges[i+1]}"
        print("[PASS] seed ranges disjoint across sets")

    if args.regenerate_determinism:
        # Regenerate into a fresh temp dir (NEVER over the committed dataset) and
        # assert byte-identical SHA.  The committed files stay untouched.
        import tempfile
        for name in names:
            orig_sha = reports[[r["name"] for r in reports].index(name)]["sha256"]
            with tempfile.TemporaryDirectory() as td:
                subprocess.run(
                    [PYTHON, "-I", "-c",
                     f"import sys; sys.path.insert(0, r'{Path(__file__).resolve().parent}'); "
                     f"from gen_radioml_compatible_clean24 import generate_set; "
                     f"from pathlib import Path; "
                     f"generate_set('{name}', out_dir=Path(r'{td}'))"],
                    check=True)
                tmp = Path(td) / f"clean24_{name}.hdf5"
                tmp_sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
            assert orig_sha == tmp_sha, f"{name}: determinism failed {orig_sha} vs {tmp_sha}"
            print(f"[PASS] {name}: regeneration deterministic (sha identical)")

    print("ALL CLEAN24 VALIDATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
