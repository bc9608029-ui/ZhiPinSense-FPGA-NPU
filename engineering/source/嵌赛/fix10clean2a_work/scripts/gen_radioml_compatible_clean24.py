"""fix10clean2a Phase 2/3 — batch-generate clean RadioML-compatible IQ datasets.

Produces three balanced, deterministic HDF5 datasets from the synthesis contract
(radioml_clean_contract.py):  smoke96 / dev2400 / formal12000.

Leakage isolation (5 dimensions) — all derived from a single per-sample seed,
so each dimension is isolated whenever the seed is:
  * seed       — every sample gets a UNIQUE seed; the three sets use disjoint
                 seed ranges (SMOKE/dev/formal never overlap).
  * message    — information bits are drawn from a per-sample local PCG64.
  * audio      — analog audio tones are drawn from the same per-sample RNG.
  * symbol-seq — linear-digital symbol indices from the same per-sample RNG.
  * window     — each frame is generated in full (1024 samples), never sliced
                 out of a longer signal, so no window can overlap another.

No global RNG state: re-running with the same args reproduces byte-identical
files (verified by the validator's determinism check).

Output layout (mirrors RadioML2018.01A):  X [N,1024,2] float32 (t,0)=real,
(t,1)=imag;  Y [N] int64 class index 0..23 (LABEL_ORDER_24);  attrs carry
label_order / set_name / seed_base / samples_per_class / generator_sha.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radioml_clean_contract as c  # noqa: E402

OUT_DIR = Path(r"F:/嵌赛/fix10clean2a_dataset")

SETS = {
    "smoke96": {"samples_per_class": 4, "seed_base": 0},
    "dev2400": {"samples_per_class": 100, "seed_base": 1_000_000},
    "formal12000": {"samples_per_class": 500, "seed_base": 2_000_000},
}


def _generator_sha() -> str:
    src = Path(c.__file__)
    return hashlib.sha256(src.read_bytes()).hexdigest()


def _seed_for(cidx: int, k: int, base: int, spc: int) -> int:
    # contiguous, balanced, disjoint: [base + c*spc, base + c*spc + spc)
    return base + cidx * spc + k


def generate_set(name: str, out_dir: Path = OUT_DIR) -> Path:
    cfg = SETS[name]
    spc = cfg["samples_per_class"]
    base = cfg["seed_base"]
    n = 24 * spc

    X = np.zeros((n, c.SAMPLE_LENGTH, 2), dtype=np.float32)
    Y = np.zeros((n,), dtype=np.int64)
    seeds = np.zeros((n,), dtype=np.int64)

    idx = 0
    for cidx, cls in enumerate(c.LABEL_ORDER_24):
        for k in range(spc):
            seed = _seed_for(cidx, k, base, spc)
            frame = c.generate_class(cls, int(seed))
            X[idx, :, 0] = frame.real.astype(np.float32)
            X[idx, :, 1] = frame.imag.astype(np.float32)
            Y[idx] = cidx
            seeds[idx] = seed
            idx += 1
    assert idx == n

    out = out_dir / f"clean24_{name}.hdf5"
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as f:
        f.create_dataset("X", data=X, compression="gzip", compression_opts=1)
        f.create_dataset("Y", data=Y)
        f.create_dataset("seeds", data=seeds)
        f.attrs["label_order"] = json.dumps(list(c.LABEL_ORDER_24))
        f.attrs["set_name"] = name
        f.attrs["seed_base"] = int(base)
        f.attrs["samples_per_class"] = int(spc)
        f.attrs["n_classes"] = 24
        f.attrs["sample_length"] = int(c.SAMPLE_LENGTH)
        f.attrs["sample_rate_hz"] = float(c.SAMPLE_RATE_HZ)
        f.attrs["sps"] = int(c.SPS)
        f.attrs["generator_sha256"] = _generator_sha()
        f.attrs["gmsk_oqpsk_fix"] = "source22=GMSK source23=OQPSK"

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default=None,
                    help="which dataset to generate (default: all three)")
    args = ap.parse_args()

    names = [args.set] if args.set else list(SETS)
    manifest = {"generator_sha256": _generator_sha(), "files": {}}
    for name in names:
        path = generate_set(name)
        size = path.stat().st_size
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["files"][name] = {"path": str(path), "bytes": size, "sha256": sha}
        print(f"generated {name}: {path} ({size} B) sha={sha[:16]}...")

    manifest_path = OUT_DIR / "clean24_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("manifest ->", manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
