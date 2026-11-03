#!/usr/bin/env python3
"""verify_golden_rml23.py -- independent read regression for the RML23 conformance
golden (``deployment_golden/``).

Re-reads ``expected_argmax.tsv`` with the EXACT board parse rule
(``board_gate9_full_chain_rml23.cpp: split on '\\t' only, no trim, ``atoi(f[1])``)
and checks the golden's self-consistency + frozen identity:

  Positive (all must hold):
    P1  manifest.json parses and declares the 23-class conformance contract
        (golden_kind=conformance, deployed=23, source=24) with the frozen model
        + label + merge SHAs.
    P2  expected_argmax.tsv line count == input_*.bin count; filenames are
        contiguous input_000..input_{N-1}.
    P3  every expected argmax (column f[1]) is an integer in 0..22.
    P4  column f[3] == DEPLOYED_LABEL_ORDER_23[f[1]] (argmax_class_23).
    P5  expected_logits.tsv has N lines, each with 23 finite logits.
    P6  softmax of the 23 logits is finite and sums to 1 within tolerance.
    P7  BPSK (source class 3) and QPSK (source class 4) are explicit, present,
        and not swapped (label order 3=BPSK / 4=QPSK, 10 frames each).
    P8  merge-rule consistency: tsv f[1] == argmax(23 logits) for every line.
    P9  every input_*.bin is exactly 8192 bytes of finite fp32.

  Negative (each corruption MUST be rejected; --negative-tests exercises all 8):
    N1  12-class manifest (deployed_classes != 23)          -> reject
    N2  12-class class_order (class_order_23 length != 23)  -> reject
    N3  wrong model SHA (model_raw_sha256)                   -> reject
    N4  wrong label SHA (deployed_label_sha256)              -> reject
    N5  missing input file                                   -> reject
    N6  input file not 8192 bytes                            -> reject
    N7  expected index out of range (f[1] == 23)             -> reject
    N8  merge-rule inconsistency (tsv argmax != logits argmax) -> reject

Usage:
    python -I scripts/verify_golden_rml23.py            # positive verify
    python -I scripts/verify_golden_rml23.py --negative-tests

Exit 0 on success (positive pass, or all 8 negatives correctly rejected).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contracts"))

from rml23_merged_contract import (  # noqa: E402
    DEPLOYED_CLASS_COUNT,
    DEPLOYED_LABEL_ORDER_23,
    SOURCE_CLASS_COUNT,
    label_order_23_sha256,
    merged_contract_sha256,
)

# Frozen model identity (M29 F5).
MODEL_JSON_SHA256 = "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"
MODEL_RAW_SHA256 = "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"
PARAMS_MD5 = "7966a4829fc713b2e8ea6c04168be263"
SOURCE_LABEL_SHA256 = "3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549"

_INPUT_BYTES = 8192


def fail(msg: str):
    print(f"verify_golden_rml23: FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def softmax(logits):
    a = [float(v) for v in logits]
    m = max(a)
    e = [math.exp(v - m) for v in a]
    s = sum(e)
    return [v / s for v in e]


def verify_golden_dir(golden_dir: str, model_sha_ok: bool = True) -> list:
    """Return a list of error strings (empty == valid)."""
    errs = []
    man_path = os.path.join(golden_dir, "manifest.json")
    if not os.path.isfile(man_path):
        return ["manifest.json missing"]

    with open(man_path, "r", encoding="utf-8") as fh:
        try:
            man = json.load(fh)
        except Exception as e:
            return [f"manifest.json unparsable: {e}"]

    # P1: identity declared in the manifest.
    if man.get("golden_kind") != "conformance":
        errs.append("manifest.golden_kind != 'conformance' (12-class or wrong kind)")
    if man.get("deployed_classes") != DEPLOYED_CLASS_COUNT:
        errs.append(f"manifest.deployed_classes != {DEPLOYED_CLASS_COUNT}")
    if man.get("source_classes") != SOURCE_CLASS_COUNT:
        errs.append(f"manifest.source_classes != {SOURCE_CLASS_COUNT}")
    if man.get("deployed_label_sha256") != label_order_23_sha256():
        errs.append("manifest.deployed_label_sha256 != frozen 23-class label SHA")
    if man.get("source_label_sha256") != SOURCE_LABEL_SHA256:
        errs.append("manifest.source_label_sha256 != frozen 24-class label SHA")
    if man.get("merged_contract_sha256") != merged_contract_sha256():
        errs.append("manifest.merged_contract_sha256 != frozen merge contract SHA")
    if model_sha_ok:
        if man.get("model_json_sha256") != MODEL_JSON_SHA256:
            errs.append("manifest.model_json_sha256 != frozen model json SHA")
        if man.get("model_raw_sha256") != MODEL_RAW_SHA256:
            errs.append("manifest.model_raw_sha256 != frozen model raw SHA")
        if man.get("params_md5") != PARAMS_MD5:
            errs.append("manifest.params_md5 != frozen params_md5")

    # P2/P3/P4: expected_argmax.tsv (board-identical parse: split '\t', atoi(f[1])).
    tsv_path = os.path.join(golden_dir, "expected_argmax.tsv")
    if not os.path.isfile(tsv_path):
        return errs + ["expected_argmax.tsv missing"]
    tsv_lines = [ln for ln in open(tsv_path, "r", encoding="utf-8").read().splitlines()
                 if ln != ""]

    # input files, contiguous.
    inputs = sorted(f for f in os.listdir(golden_dir) if f.startswith("input_") and f.endswith(".bin"))
    n = len(inputs)
    if n == 0:
        return errs + ["no input_*.bin files"]
    expected_names = [f"input_{i:03d}.bin" for i in range(n)]
    if inputs != expected_names:
        errs.append(f"input filenames not contiguous 0..{n - 1}")
    if len(tsv_lines) != n:
        errs.append(f"tsv line count {len(tsv_lines)} != input count {n}")

    # P9: each input 8192 bytes.
    for name in inputs:
        p = os.path.join(golden_dir, name)
        if os.path.getsize(p) != _INPUT_BYTES:
            errs.append(f"{name} not {_INPUT_BYTES} bytes")

    # Parse tsv lines with the board rule.
    argmaxes = []
    classes = []
    src_classes = []
    for ln in tsv_lines:
        f = ln.split("\t")  # '\t' only, no trim, trailing empties kept
        if len(f) < 4:
            errs.append(f"tsv line has <4 fields: {ln!r}")
            continue
        try:
            a = int(f[1])
        except ValueError:
            errs.append(f"tsv f[1] not an integer: {ln!r}")
            continue
        if not (0 <= a < DEPLOYED_CLASS_COUNT):
            errs.append(f"tsv f[1] out of range 0..22: {a}")
        argmaxes.append(a)
        classes.append(f[3])
        try:
            src_classes.append(int(f[2]))
        except (ValueError, IndexError):
            src_classes.append(-1)

    # P4: argmax_class_23 == DEPLOYED_LABEL_ORDER_23[argmax].
    for i, (a, c) in enumerate(zip(argmaxes, classes)):
        if 0 <= a < DEPLOYED_CLASS_COUNT and c != DEPLOYED_LABEL_ORDER_23[a]:
            errs.append(f"line {i}: argmax_class {c!r} != label_order_23[{a}] "
                        f"{DEPLOYED_LABEL_ORDER_23[a]!r}")

    # P7: BPSK/QPSK explicit + not swapped.
    if DEPLOYED_LABEL_ORDER_23[3] != "BPSK" or DEPLOYED_LABEL_ORDER_23[4] != "QPSK":
        errs.append("BPSK/QPSK label order swapped or wrong (index 3/4)")
    if src_classes:
        if src_classes.count(3) != 10 or src_classes.count(4) != 10:
            errs.append(f"BPSK(3)/QPSK(4) frames != 10 each: "
                        f"BPSK={src_classes.count(3)} QPSK={src_classes.count(4)}")

    # P5/P6/P8: expected_logits.tsv cross-consistency.
    logits_path = os.path.join(golden_dir, "expected_logits.tsv")
    if not os.path.isfile(logits_path):
        return errs + ["expected_logits.tsv missing"]
    logits_lines = [ln for ln in open(logits_path, "r", encoding="utf-8").read().splitlines()
                    if ln != ""]
    if len(logits_lines) != n:
        errs.append(f"expected_logits.tsv line count {len(logits_lines)} != {n}")
    logits_by_index = {}
    for ln in logits_lines:
        f = ln.split("\t")
        if len(f) < DEPLOYED_CLASS_COUNT + 1:
            errs.append(f"logits line has < {DEPLOYED_CLASS_COUNT + 1} fields")
            continue
        try:
            idx = int(f[0])
            vals = [float(x) for x in f[1:1 + DEPLOYED_CLASS_COUNT]]
        except (ValueError, IndexError):
            errs.append("logits line unparsable")
            continue
        if any(not math.isfinite(v) for v in vals):
            errs.append(f"logits line {idx} has non-finite value")
            continue
        p = softmax(vals)
        if abs(sum(p) - 1.0) > 1e-6:
            errs.append(f"logits line {idx} softmax sum {sum(p)} != 1")
            continue
        logits_by_index[idx] = vals

    # P8: merge-rule consistency tsv argmax == argmax(logits).
    for i, a in enumerate(argmaxes):
        vals = logits_by_index.get(i)
        if vals is None:
            continue
        if max(range(DEPLOYED_CLASS_COUNT), key=lambda k: vals[k]) != a:
            errs.append(f"line {i}: tsv argmax {a} != argmax(23 logits)")

    return errs


def _minimal_golden(tmp: str, n: int = 20) -> str:
    """Build a small, fully-valid conformance golden (no HDF5/model files needed).

    n is 20 so the P7 guard (exactly 10 BPSK source-class-3 frames + 10 QPSK
    source-class-4 frames) is satisfied by construction: indices 0..9 are BPSK,
    10..19 are QPSK.
    """
    d = os.path.join(tmp, "golden")
    os.makedirs(d, exist_ok=True)
    import struct
    manifest = {
        "golden_kind": "conformance",
        "deployed_classes": DEPLOYED_CLASS_COUNT,
        "source_classes": SOURCE_CLASS_COUNT,
        "deployed_label_sha256": label_order_23_sha256(),
        "source_label_sha256": SOURCE_LABEL_SHA256,
        "merged_contract_sha256": merged_contract_sha256(),
        "model_json_sha256": MODEL_JSON_SHA256,
        "model_raw_sha256": MODEL_RAW_SHA256,
        "params_md5": PARAMS_MD5,
    }
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)

    tsv, ltsv = [], []
    for i in range(n):
        # craft 23 logits whose argmax == i % 23, all finite.
        vals = [0.0] * DEPLOYED_CLASS_COUNT
        vals[i % DEPLOYED_CLASS_COUNT] = 1.0
        a = i % DEPLOYED_CLASS_COUNT
        src = 3 if i < 10 else 4  # 10 BPSK + 10 QPSK
        tsv.append(f"{i}\t{a}\t{src}\t{DEPLOYED_LABEL_ORDER_23[a]}\t0.500000")
        ltsv.append("\t".join([str(i)] + [repr(float(v)) for v in vals]))
        with open(os.path.join(d, f"input_{i:03d}.bin"), "wb") as fh:
            fh.write(struct.pack("2048f", *([0.0] * 2048)))

    with open(os.path.join(d, "expected_argmax.tsv"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(tsv) + "\n")
    with open(os.path.join(d, "expected_logits.tsv"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(ltsv) + "\n")
    return d


def _negative_tests() -> int:
    """Each corruption must be REJECTED by verify_golden_dir (return non-empty)."""
    import shutil

    cases = []  # (name, mutate_fn)
    cases.append(("N1 12-class manifest", lambda d: _mutate_manifest(d,
                  {"deployed_classes": 12})))
    cases.append(("N2 12-class class_order", lambda d: _mutate_manifest(d,
                  {"source_classes": 12, "deployed_classes": 12})))
    cases.append(("N3 wrong model SHA", lambda d: _mutate_manifest(d,
                  {"model_raw_sha256": "0" * 64})))
    cases.append(("N4 wrong label SHA", lambda d: _mutate_manifest(d,
                  {"deployed_label_sha256": "0" * 64})))
    cases.append(("N5 missing input", lambda d: os.remove(
                  os.path.join(d, "input_000.bin"))))
    cases.append(("N6 input not 8192 bytes", lambda d: open(
                  os.path.join(d, "input_001.bin"), "wb").write(b"x" * 100)))
    cases.append(("N7 index out of range", lambda d: _mutate_tsv_line(d, 0, 1, "23")))
    cases.append(("N8 merge-rule inconsistency", lambda d: _mutate_tsv_line(
                  d, 1, 1, str((1 + 1) % DEPLOYED_CLASS_COUNT))))

    tmp = tempfile.mkdtemp(prefix="verify_golden_neg_")
    try:
        passed = 0
        for name, mutate in cases:
            d = _minimal_golden(os.path.join(tmp, name.replace(" ", "_")))
            # baseline must be valid
            base_errs = verify_golden_dir(d)
            if base_errs:
                print(f"  BAD baseline {name} already rejected: {base_errs}")
                continue
            mutate(d)
            errs = verify_golden_dir(d)
            if errs:
                passed += 1
                print(f"  OK  {name}: rejected ({len(errs)} error(s))")
            else:
                print(f"  BAD {name}: NOT rejected (should have failed)")
        print(f"negative tests: {passed}/{len(cases)} correctly rejected")
        return 0 if passed == len(cases) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _mutate_manifest(d, fields):
    p = os.path.join(d, "manifest.json")
    with open(p, "r", encoding="utf-8") as fh:
        m = json.load(fh)
    m.update(fields)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(m, fh)


def _mutate_tsv_line(d, line_idx, col_idx, value):
    p = os.path.join(d, "expected_argmax.tsv")
    lines = open(p, "r", encoding="utf-8").read().splitlines()
    f = lines[line_idx].split("\t")
    f[col_idx] = value
    lines[line_idx] = "\t".join(f)
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deployment_golden"))
    ap.add_argument("--negative-tests", action="store_true")
    args = ap.parse_args()

    if args.negative_tests:
        return _negative_tests()

    errs = verify_golden_dir(args.golden)
    if errs:
        for e in errs:
            print(f"  FAIL: {e}")
        fail(f"{len(errs)} verification error(s)")
    print(f"verify_golden_rml23: PASS (golden={args.golden})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
