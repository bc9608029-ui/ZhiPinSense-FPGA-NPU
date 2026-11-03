#!/usr/bin/env python3
"""audit_rml24_bf16_network.py -- fail-closed audit of the frozen BF16 24-class
iCraft network (model_rml24_bf16/rml24_adamrv11_bf16.{json,raw}).

fix10class24-dualsdr1 §5 (Phase 0).  This is the authoritative compile-evidence
audit: it re-derives every mapping count from the shipped JSON (never from a
cached report), verifies the JSON/RAW SHA pair against model_SHA256SUMS.txt, and
regenerates ``network_mapping_report.json`` / ``network_mapping_report.md`` in the
model directory.  It never touches the board, the NPU, or the .raw weights other
than hashing them.

Checks (any mismatch -> exit 1):
  * model_SHA256SUMS.txt exists, has exactly the JSON+RAW lines, and the on-disk
    byte SHA256 of both files equals the recorded SHA (byte-identity, fail-closed).
  * JSON ``name`` == "model_24class", ``ai_target`` == "@zhuget(330)",
    ``params_md5`` == the frozen value, ``icraft_version`` == "v3.39.0".
  * op inventory: 1 Input + 122 HardOp + 1 Output; all 122 HardOp compile to
    @zhuget(330), Input+Output to @hostt (122 NPU + 2 host).
  * input tensor [1,2,1024] @fp(32); output tensor [1,24] @fp(32).
  * ZERO INT8/INT16/uint8/uint16 storage anywhere (only @uint(64) instruction
    words may appear as unsigned ints); the full-network BF16 compile must not
    contain a single int8/uint8 quantized tensor.
  * full activation + weight dtype census is recomputed and emitted.

Pure stdlib; run with ``python -I scripts/audit_rml24_bf16_network.py``.

Usage:
    python3 -I scripts/audit_rml24_bf16_network.py [--model-dir model_rml24_bf16]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

FROZEN = {
    "network_name": "model_24class",
    "ai_target": "@zhuget(330)",
    "params_md5": "0c9b60b82ea1f634469b598db45738fb",
    "icraft_version": "v3.39.0",
    "params_bytes": 778732,
    "json_sha256": "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42",
    "raw_sha256": "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151",
}

EXPECT_INPUT_SHAPE = [1, 2, 1024]
EXPECT_OUTPUT_SHAPE = [1, 24]


def fail(msg: str) -> None:
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_dtype(dt):
    """Return one of ('plain', elem_str) | ('quant', storage, expressed) | ('other', tag)."""
    if not isinstance(dt, dict):
        return ("plain", str(dt))
    tk = dt.get("_type_key")
    if tk == "icraft::xir::QuantizedType":
        return ("quant", dt.get("storage_dtype"), dt.get("expressed_dtype"))
    if tk == "icraft::xir::TensorType":
        return classify_dtype(dt.get("element_dtype"))
    return ("other", str(tk))


def is_value(v):
    return isinstance(v, dict) and v.get("_type_key") == "icraft::xir::Value"


def is_params(v):
    return isinstance(v, dict) and v.get("_type_key") == "icraft::xir::Params"


def walk_params_recursive(obj, out: list):
    if isinstance(obj, dict):
        if is_params(obj):
            out.append(obj)
        for v in obj.values():
            walk_params_recursive(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_params_recursive(v, out)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="fail-closed BF16 network audit")
    ap.add_argument("--model-dir", default="model_rml24_bf16")
    args = ap.parse_args(argv)

    model_dir = Path(args.model_dir)
    json_path = model_dir / "rml24_adamrv11_bf16.json"
    raw_path = model_dir / "rml24_adamrv11_bf16.raw"
    sums_path = model_dir / "model_SHA256SUMS.txt"

    # ---- 1. SHA sidecar + byte identity ----
    if not json_path.is_file():
        fail("model json not found: %s" % json_path)
    if not raw_path.is_file():
        fail("model raw not found: %s" % raw_path)
    if not sums_path.is_file():
        fail("model_SHA256SUMS.txt not found")

    recorded = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            fail("bad SHA256SUMS line: %r" % line)
        recorded[parts[1]] = parts[0]
    if set(recorded.keys()) != {"rml24_adamrv11_bf16.json", "rml24_adamrv11_bf16.raw"}:
        fail("SHA256SUMS must list exactly the json+raw pair (got %s)" % sorted(recorded))
    json_sha = sha256_file(json_path)
    raw_sha = sha256_file(raw_path)
    if recorded["rml24_adamrv11_bf16.json"] != json_sha:
        fail("json SHA sidecar mismatch")
    if recorded["rml24_adamrv11_bf16.raw"] != raw_sha:
        fail("raw SHA sidecar mismatch")
    if json_sha != FROZEN["json_sha256"] or raw_sha != FROZEN["raw_sha256"]:
        fail("json/raw SHA does not match frozen fix10class24 BF16 model")
    print("[audit] json_sha=%s" % json_sha)
    print("[audit] raw_sha =%s" % raw_sha)

    # ---- 2. parse ----
    net = json.loads(json_path.read_text(encoding="utf-8"))
    if net.get("name") != FROZEN["network_name"]:
        fail("network name %r != %r" % (net.get("name"), FROZEN["network_name"]))
    if net.get("ai_target") != FROZEN["ai_target"]:
        fail("ai_target %r != %r" % (net.get("ai_target"), FROZEN["ai_target"]))
    if net.get("params_md5") != FROZEN["params_md5"]:
        fail("params_md5 %r != frozen" % net.get("params_md5"))
    if net.get("icraft_version") != FROZEN["icraft_version"]:
        fail("icraft_version %r != v3.39.0" % net.get("icraft_version"))
    if int(net.get("params_bytes", -1)) != FROZEN["params_bytes"]:
        fail("params_bytes %r != 778732" % net.get("params_bytes"))

    ops = net["ops"]
    type_ctr = Counter(o.get("_type_key") for o in ops)
    n_input = type_ctr.get("icraft::xir::Input", 0)
    n_output = type_ctr.get("icraft::xir::Output", 0)
    n_hard = type_ctr.get("icraft::xir::HardOp", 0)
    if (n_input, n_output, n_hard) != (1, 1, 122):
        fail("op inventory Input=%d Output=%d HardOp=%d != (1,1,122)"
             % (n_input, n_output, n_hard))

    # compile_target census
    ct_ctr = Counter(o.get("compile_target") for o in ops)
    if ct_ctr.get("@zhuget(330)") != 122 or ct_ctr.get("@hostt") != 2:
        fail("compile_target census %s != {zhuget:122, host:2}" % dict(ct_ctr))

    # node-type census
    node_ctr = Counter(o.get("name") for o in ops if o.get("_type_key") == "icraft::xir::HardOp")

    # ---- 3. input/output tensors ----
    inp_value = None
    out_value = None
    for o in ops:
        if o.get("_type_key") == "icraft::xir::Input" and o.get("outputs"):
            inp_value = o["outputs"][0]
        if o.get("_type_key") == "icraft::xir::Output" and o.get("inputs"):
            out_value = o["inputs"][0]
    if inp_value is None or out_value is None:
        fail("could not locate Input/Output tensor values")
    if inp_value["dtype"].get("shape") != EXPECT_INPUT_SHAPE:
        fail("input shape %s != [1,2,1024]" % inp_value["dtype"].get("shape"))
    if out_value["dtype"].get("shape") != EXPECT_OUTPUT_SHAPE:
        fail("output shape %s != [1,24]" % out_value["dtype"].get("shape"))
    if classify_dtype(inp_value["dtype"]) != ("plain", "@fp(32)"):
        fail("input dtype not plain fp32")
    if classify_dtype(out_value["dtype"]) != ("plain", "@fp(32)"):
        fail("output dtype not plain fp32")

    # ---- 4. activation value census ----
    seen: dict[int, dict] = {}
    for o in ops:
        for v in o.get("inputs", []) + o.get("outputs", []):
            if is_value(v):
                seen[v["v_id"]] = v
    act_storage = Counter()
    act_expr = Counter()
    act_plain = Counter()
    for v in seen.values():
        c = classify_dtype(v.get("dtype"))
        if c[0] == "quant":
            act_storage[c[1]] += 1
            act_expr[c[2]] += 1
        elif c[0] == "plain":
            act_plain[c[1]] += 1
        else:
            fail("unexpected activation dtype tag %r" % (c[1],))

    # ---- 5. param (weight/instr) census ----
    params = []
    for o in ops:
        walk_params_recursive(o.get("instr", []), params)
        walk_params_recursive(o.get("params", []), params)
    prm_storage = Counter()
    prm_expr = Counter()
    prm_plain = Counter()
    for p in params:
        c = classify_dtype(p.get("dtype"))
        if c[0] == "quant":
            prm_storage[c[1]] += 1
            prm_expr[c[2]] += 1
        elif c[0] == "plain":
            prm_plain[c[1]] += 1
        else:
            fail("unexpected param dtype tag %r" % (c[1],))

    # ---- 6. zero-INT8 check ----
    raw_text = json_path.read_text(encoding="utf-8")
    forbidden_int = ["@int(", "@int8", "@uint8", "@int16", "@uint16", "@int32", "@uint32"]
    for pat in forbidden_int:
        if pat in raw_text:
            fail("forbidden int dtype found in JSON: %r" % pat)
    # @uint(64) instruction words are allowed and expected to number 122.
    uint64_count = raw_text.count("@uint(64)")
    if uint64_count != 122:
        fail("expected exactly 122 @uint(64) instruction words, got %d" % uint64_count)

    # ---- 7. assemble report ----
    report = {
        "audit": "M29-RML24-FIX10CLASS24-BF16-NETWORK-AUDIT",
        "network_name": net.get("name"),
        "model_name": "rml24_adamrv11_bf16",
        "model_json_sha256": json_sha,
        "model_raw_sha256": raw_sha,
        "params_bytes": int(net.get("params_bytes", -1)),
        "params_md5": net.get("params_md5"),
        "icraft_version": net.get("icraft_version"),
        "icraft_xir_version": net.get("icraft_xir_version"),
        "framework_kind": net.get("framework_kind"),
        "framework_version": net.get("framework_version"),
        "ai_target": net.get("ai_target"),
        "tags": net.get("tags", {}),
        "op_inventory": {
            "input": n_input,
            "hard_op": n_hard,
            "output": n_output,
            "total": len(ops),
        },
        "compile_target": dict(ct_ctr),
        "npu_resident_ops": ct_ctr.get("@zhuget(330)", 0),
        "host_ops": ct_ctr.get("@hostt", 0),
        "hard_op_node_types": dict(node_ctr),
        "network_io": {
            "input_shape": inp_value["dtype"].get("shape"),
            "input_dtype": "fp32",
            "output_shape": out_value["dtype"].get("shape"),
            "output_dtype": "fp32",
        },
        "activation_values": {
            "unique_count": len(seen),
            "quantized_storage": dict(act_storage),
            "quantized_expressed": dict(act_expr),
            "plain": dict(act_plain),
        },
        "params": {
            "count": len(params),
            "quantized_storage": dict(prm_storage),
            "quantized_expressed": dict(prm_expr),
            "plain": dict(prm_plain),
        },
        "int8_tensors": 0,
        "deployability": {
            "npu_ops": ct_ctr.get("@zhuget(330)", 0),
            "host_ops": ct_ctr.get("@hostt", 0),
            "verdict": "DEPLOYABLE_FULL_NETWORK_BF16" if (
                ct_ctr.get("@zhuget(330)", 0) == 122 and ct_ctr.get("@hostt", 0) == 2
            ) else "NOT_DEPLOYABLE",
        },
    }

    (model_dir / "network_mapping_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (model_dir / "network_mapping_report.md").write_text(
        render_markdown(report), encoding="utf-8")

    print("[audit] ops=%d (Input %d + HardOp %d + Output %d)" %
          (len(ops), n_input, n_hard, n_output))
    print("[audit] compile_target=%s" % dict(ct_ctr))
    print("[audit] activation storage=%s expressed=%s plain=%s" %
          (dict(act_storage), dict(act_expr), dict(act_plain)))
    print("[audit] param storage=%s plain=%s" % (dict(prm_storage), dict(prm_plain)))
    print("[audit] zero-INT8 confirmed; uint64 instr words=%d" % uint64_count)
    print("[audit] PASS: wrote network_mapping_report.{json,md}")
    return 0


def render_markdown(r: dict) -> str:
    L = []
    L.append("# RML24 BF16 24-class network mapping audit")
    L.append("")
    L.append("Audit token: `%s`" % r["audit"])
    L.append("")
    L.append("| field | value |")
    L.append("|---|---|")
    L.append("| network name | `%s` |" % r["network_name"])
    L.append("| model name | `%s` |" % r["model_name"])
    L.append("| icraft | `%s` (xir `%s`) |" % (r["icraft_version"], r["icraft_xir_version"]))
    L.append("| framework | `%s` `%s` |" % (r["framework_kind"], r["framework_version"]))
    L.append("| ai target | `%s` |" % r["ai_target"])
    L.append("| params_bytes | %d |" % r["params_bytes"])
    L.append("| params_md5 | `%s` |" % r["params_md5"])
    L.append("| json SHA256 | `%s` |" % r["model_json_sha256"])
    L.append("| raw SHA256 | `%s` |" % r["model_raw_sha256"])
    L.append("")
    L.append("## Op inventory")
    L.append("")
    L.append("- Input: %d, HardOp: %d, Output: %d (total %d)"
             % (r["op_inventory"]["input"], r["op_inventory"]["hard_op"],
                r["op_inventory"]["output"], r["op_inventory"]["total"]))
    L.append("- compile target: `%s`" % r["compile_target"])
    L.append("- NPU-resident ops: **%d**, host ops: **%d**"
             % (r["npu_resident_ops"], r["host_ops"]))
    L.append("- HardOp node types: `%s`" % r["hard_op_node_types"])
    L.append("")
    L.append("## Network I/O")
    L.append("")
    L.append("- input  `%s` fp32" % r["network_io"]["input_shape"])
    L.append("- output `%s` fp32" % r["network_io"]["output_shape"])
    L.append("")
    L.append("## Dtype census (recomputed from JSON)")
    L.append("")
    L.append("- activation values: %d unique" % r["activation_values"]["unique_count"])
    L.append("  - quantized storage `%s`, expressed `%s`, plain `%s`"
             % (r["activation_values"]["quantized_storage"],
                r["activation_values"]["quantized_expressed"],
                r["activation_values"]["plain"]))
    L.append("- params: %d" % r["params"]["count"])
    L.append("  - quantized storage `%s`, expressed `%s`, plain `%s`"
             % (r["params"]["quantized_storage"],
                r["params"]["quantized_expressed"],
                r["params"]["plain"]))
    L.append("")
    L.append("## Deployability")
    L.append("")
    L.append("- **%s** (int8 tensors: %d)" % (r["deployability"]["verdict"], r["int8_tensors"]))
    L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
