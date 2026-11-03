#!/usr/bin/env python3
"""predict_clean_baseline.py -- fix10-prep Stage 3 (N6): frozen offline baseline
prediction for the GENERATED-CLEAN 23-class dataset (Path B/C).

Runs the frozen 24-class offline model (checkpoint 96cd25f8…, the SAME checkpoint
fix9r2g1 uses) over the D2-recovered [2,1024] fp32 tensors that
gen_generated_clean_23.py writes, and emits the 6-column clean baseline TSV the
C++ clean runner (iq_clean_iq_23class_fix10.hpp) compares against:

    source_index  file_name  sha256  deployed_class  split_role  frozen_baseline_pred

  * source_index        stable unique key (0..N-1), from the 24-col manifest.
  * file_name           the CI16 TX file name (quantized_file) -- the SAME file
                        the Path C dual-SDR runner transmits, keyed by source_index.
  * sha256              the CI16 TX SHA (quantized_sha256) recorded by the
                        generator; this is the byte that ties Path B/C to one
                        batch (§10 SHA-identity proof), NOT re-derived here.
  * deployed_class      deployed23_class (ground-truth label, print-only).
  * split_role          always "holdout" for clean (K is global/fixed, no
                        calibration subset).
  * frozen_baseline_pred  the model's OWN prediction, argmax of the 24-class
                        logits folded through the 24->23 AM merge.  NEVER
                        deployed_class -- even when pred == label we store the
                        real inference evidence (forbidden to back-fill).

The 24->23 merge is monotonic (rml23_merged.hpp merge_logits_23 logaddexp fold
preserves argmax), so `SOURCE_TO_DEPLOYED[argmax_24]` is exact.

This script runs ONLY on the API machine (torch + RML24 project + the frozen
checkpoint); it never enters the board run path.  Its non-inference logic
(manifest parse, tensor load, SHA verify, 6-col write, merge) is exercised by
`--self-test` with a mock model, which runs anywhere.

Never modifies model/weights/labels/24->23 mapping; never retrains.

Usage (API machine):
    python3 -I scripts/predict_clean_baseline.py \
        --rml24-root /path/to/rml24_ood_v1_1 \
        --config configs/rml24_base.yaml \
        --checkpoint /path/to/checkpoint_96cd25f8.pt \
        --d2-manifest /path/to/route_d2_rf_manifest.tsv \
        --tensor-dir /path/to/clean_tensor_d2 \
        --out /path/to/clean_baseline.tsv [--expect-holdout 720]

    python3 -I scripts/predict_clean_baseline.py --self-test
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import sys
from pathlib import Path

import numpy as np

# 24->23 AM merge (== C++ rml23_merged.hpp kSourceToDeployed).  source 17
# (AM-SSB-WC) and 18 (AM-SSB-SC) both deploy to 17 (AM-SSB).
SOURCE_TO_DEPLOYED = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 17, 18, 19, 20, 21, 22,
]
N_DEPLOYED = 23

BASELINE_HEADER = ["source_index", "file_name", "sha256", "deployed_class",
                   "split_role", "frozen_baseline_pred"]

D2_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]


def fail(msg: str) -> None:
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def is_hex64(s: str) -> bool:
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_d2_manifest(path: Path) -> list[dict[str, str]]:
    """Parse the 24-col clean manifest (route_d2_rf_manifest.tsv), fail-closed."""
    if not path.is_file():
        fail("manifest not found: %s" % path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        fail("manifest empty")
    header = lines[0].rstrip("\n").split("\t")
    if header != D2_HEADER:
        fail("manifest header not the 24-col D2 schema (got %d cols)" % len(header))
    rows = []
    seen_sample: set[int] = set()
    for lineno, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) != len(D2_HEADER):
            fail("manifest line %d has %d cols (want %d)" % (lineno, len(f), len(D2_HEADER)))
        row = dict(zip(D2_HEADER, f))
        sid = int(row["sample_index"])
        if sid in seen_sample:
            fail("manifest duplicate sample_index=%d (line %d)" % (sid, lineno))
        seen_sample.add(sid)
        if row["split_role"] not in ("calibration", "holdout"):
            fail("manifest line %d bad split_role %r" % (lineno, row["split_role"]))
        if not is_hex64(row["quantized_sha256"]):
            fail("manifest line %d quantized_sha256 not 64-hex" % lineno)
        if not is_hex64(row["recovered_tensor_sha256"]):
            fail("manifest line %d recovered_tensor_sha256 not 64-hex" % lineno)
        dep = int(row["deployed23_class"])
        if not (0 <= dep < N_DEPLOYED):
            fail("manifest line %d deployed23_class out of range %d" % (lineno, dep))
        rows.append(row)
    if not rows:
        fail("manifest has no data rows")
    return rows


def load_recovered_tensor(tensor_dir: Path, file_name: str, expect_sha: str) -> np.ndarray:
    """Load a recovered tensor as [2,1024] fp32, fail-closed on size and SHA."""
    raw = (tensor_dir / file_name).read_bytes()
    if len(raw) != 2 * 1024 * 4:
        fail("%s size %dB (want 8192B)" % (file_name, len(raw)))
    if sha256_bytes(raw) != expect_sha:
        fail("%s SHA mismatch (manifest vs file)" % file_name)
    return np.frombuffer(raw, dtype="<f4").reshape(2, 1024).copy()


def merge_argmax(logits_24: np.ndarray) -> int:
    """argmax of 24-class logits folded through the monotonic 24->23 AM merge."""
    merged = np.full(N_DEPLOYED, -np.inf, dtype=np.float64)
    for s in range(24):
        d = SOURCE_TO_DEPLOYED[s]
        merged[d] = np.logaddexp(merged[d], logits_24[s])
    return int(np.argmax(merged))


def run_inference(model, x: np.ndarray, torch) -> int:
    """Deterministic single-sample inference -> deployed-class prediction."""
    t = torch.from_numpy(x).unsqueeze(0)  # [1,2,1024]
    with torch.inference_mode():
        logits, _ = model(t)              # [1,24]
    arg24 = int(torch.argmax(logits[0]).item())
    return SOURCE_TO_DEPLOYED[arg24]


def write_baseline(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(BASELINE_HEADER) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in BASELINE_HEADER) + "\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rml24-root", default=None,
                    help="RML24 project root (contracts/ models/ training/)")
    ap.add_argument("--config", default="configs/rml24_base.yaml",
                    help="RML24 config yaml (relative to --rml24-root)")
    ap.add_argument("--checkpoint", default=None, help="frozen checkpoint .pt")
    ap.add_argument("--d2-manifest", default=None,
                    help="24-col clean manifest (route_d2_rf_manifest.tsv)")
    ap.add_argument("--tensor-dir", default=None, help="recovered tensor .f32 dir")
    ap.add_argument("--out", default=None, help="output 6-col baseline TSV")
    ap.add_argument("--expect-holdout", type=int, default=720)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    for name in ("rml24_root", "checkpoint", "d2_manifest", "tensor_dir", "out"):
        if getattr(args, name) is None:
            ap.error("--%s is required (or use --self-test)" % name.replace("_", "-"))

    rml24_root = Path(args.rml24_root).resolve()
    if str(rml24_root) not in sys.path:
        sys.path.insert(0, str(rml24_root))

    from contracts.rml24_contract import LABEL_ORDER_24
    from models.rml24_net import build_rml24_model
    from training.utils import load_yaml

    import torch

    config = load_yaml(rml24_root / args.config)
    model_cfg = config["model"]
    ckpt_path = Path(args.checkpoint).resolve()
    if not ckpt_path.is_file():
        fail("checkpoint not found: %s" % ckpt_path)
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if ckpt.get("class_names") not in (None, LABEL_ORDER_24) and \
            list(ckpt.get("class_names", [])) != list(LABEL_ORDER_24):
        fail("checkpoint class_names != LABEL_ORDER_24")
    print("[infer] checkpoint epoch=%s model_name=%s"
          % (ckpt.get("epoch"), ckpt.get("model_name")))

    model = build_rml24_model(24, **model_cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    rows = parse_d2_manifest(Path(args.d2_manifest))
    holdouts = [r for r in rows if r["split_role"] == "holdout"]
    if len(holdouts) != args.expect_holdout:
        fail("holdout count %d != expected %d" % (len(holdouts), args.expect_holdout))

    tensor_dir = Path(args.tensor_dir)
    out_rows = []
    seen_src: set[int] = set()
    for r in holdouts:
        src = int(r["source_index"])
        if src in seen_src:
            fail("duplicate source_index=%d" % src)
        seen_src.add(src)
        x = load_recovered_tensor(tensor_dir, r["recovered_tensor_file"],
                                  r["recovered_tensor_sha256"])
        pred = run_inference(model, x, torch)
        if not (0 <= pred < N_DEPLOYED):
            fail("source_index=%d illegal deployed pred %d" % (src, pred))
        out_rows.append({
            "source_index": src,
            "file_name": r["quantized_file"],
            "sha256": r["quantized_sha256"],
            "deployed_class": int(r["deployed23_class"]),
            "split_role": "holdout",
            "frozen_baseline_pred": pred,
        })

    write_baseline(Path(args.out), out_rows)
    dist = {}
    for r in out_rows:
        dist[r["deployed_class"]] = dist.get(r["deployed_class"], 0) + 1
    agree = sum(1 for r in out_rows if r["frozen_baseline_pred"] == r["deployed_class"])
    print("PREDICT_CLEAN_BASELINE holdout=%d out=%s" % (len(out_rows), args.out))
    print("  deployed_class_distribution=%s"
          % ",".join("%d:%d" % (d, dist.get(d, 0)) for d in range(N_DEPLOYED)))
    print("  prediction_matches_label=%d/%d" % (agree, len(out_rows)))
    return 0


def self_test() -> int:
    npass = 0

    # 1. merge_argmax is the monotonic 24->23 fold (AM-SSB 17+18 both -> 17).
    logits = np.full(24, -10.0)
    logits[18] = 5.0                      # peak in AM-SSB-SC (source 18)
    if merge_argmax(logits) == 17:
        npass += 1
        print("  OK  merge_argmax folds source18 -> deployed17")
    else:
        print("  BAD merge_argmax")

    # 2. SOURCE_TO_DEPLOYED shape: 24 entries, 23 deployed, AM merge at 17/18.
    if (len(SOURCE_TO_DEPLOYED) == 24
            and SOURCE_TO_DEPLOYED[17] == 17 and SOURCE_TO_DEPLOYED[18] == 17
            and len(set(SOURCE_TO_DEPLOYED)) == N_DEPLOYED):
        npass += 1
        print("  OK  SOURCE_TO_DEPLOYED 24->23 with AM merge")
    else:
        print("  BAD SOURCE_TO_DEPLOYED")

    # 3. parse_d2_manifest: valid header/rows + fail-closed bad sha.
    import tempfile, os, shutil
    tmp = tempfile.mkdtemp(prefix="clean_base_")
    header = "\t".join(D2_HEADER)
    def mk_row(sample, src, dep):
        sha = "%064x" % (sample + 1)
        return "\t".join([
            str(sample), str(src), str(dep), str(dep), "QPSK", "nan", "holdout",
            "2048", "0.0", "0.0", "1.0", "1.0", "53760", "2560000",
            "893.0", "4000.0", "0", "zero", "832", "", sha, sha,
            "clean_d2_2p56m_%06d.ci16" % sample,
            "clean_tensor_d2_%06d.f32" % sample])
    mpath = os.path.join(tmp, "route_d2_rf_manifest.tsv")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for i in range(4):
            f.write(mk_row(i, i, i % 23) + "\n")
    rows = parse_d2_manifest(Path(mpath))
    if len(rows) == 4 and rows[0]["quantized_file"] == "clean_d2_2p56m_000000.ci16":
        npass += 1
        print("  OK  parse_d2_manifest 4 rows")
    else:
        print("  BAD parse_d2_manifest")
    # bad sha -> fail-closed
    bad = os.path.join(tmp, "bad.tsv")
    with open(bad, "w", encoding="utf-8") as f:
        f.write(header + "\n" + mk_row(0, 0, 0).replace("%064x" % 1, "zz", 1) + "\n")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            parse_d2_manifest(Path(bad))
        print("  BAD bad-sha manifest not detected")
    except SystemExit:
        npass += 1
        print("  OK  bad-sha manifest detected")

    # 4. load_recovered_tensor: correct size + SHA, fail-closed on both.
    tdir = os.path.join(tmp, "tensors")
    os.makedirs(tdir, exist_ok=True)
    arr = np.random.default_rng(0).standard_normal((2, 1024)).astype("<f4")
    raw = arr.tobytes()
    tname = "clean_tensor_d2_000000.f32"
    with open(os.path.join(tdir, tname), "wb") as f:
        f.write(raw)
    good_sha = sha256_bytes(raw)
    loaded = load_recovered_tensor(Path(tdir), tname, good_sha)
    if loaded.shape == (2, 1024) and loaded.dtype == np.float32:
        npass += 1
        print("  OK  load_recovered_tensor (size+SHA ok)")
    else:
        print("  BAD load_recovered_tensor")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            load_recovered_tensor(Path(tdir), tname, "0" * 64)
        print("  BAD SHA mismatch not detected")
    except SystemExit:
        npass += 1
        print("  OK  SHA mismatch detected")

    # 5. write_baseline 6-col header + rows, keyed fields correct.
    out = os.path.join(tmp, "clean_baseline.tsv")
    out_rows = [{"source_index": i, "file_name": "clean_d2_2p56m_%06d.ci16" % i,
                 "sha256": "%064x" % (i + 1), "deployed_class": i % 23,
                 "split_role": "holdout", "frozen_baseline_pred": (i * 7 + 3) % 23}
                for i in range(4)]
    write_baseline(Path(out), out_rows)
    with open(out, "r", encoding="utf-8") as f:
        wl = f.read().splitlines()
    if (len(wl) == 5 and wl[0].split("\t") == BASELINE_HEADER
            and wl[1].split("\t")[5] == str((0 * 7 + 3) % 23)
            and wl[1].split("\t")[1] == "clean_d2_2p56m_000000.ci16"):
        npass += 1
        print("  OK  write_baseline 6-column header + rows")
    else:
        print("  BAD write_baseline")

    shutil.rmtree(tmp, ignore_errors=True)
    print("self-test: %d/7 correct" % npass)
    return 0 if npass == 7 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
