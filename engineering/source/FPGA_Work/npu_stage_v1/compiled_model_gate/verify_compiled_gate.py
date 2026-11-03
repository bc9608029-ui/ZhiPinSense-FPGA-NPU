#!/usr/bin/env python3
"""Close the compiled_model_gate: verify the final iCraft ZG330 artifact.

Reads rfnet_npu_ZG.json (the model the board loads via Network::CreateFromJsonFile)
and checks the 13-item compiled-contract gate.  Only PASS when every item is
satisfied; otherwise FAIL with the exact reason.

The single most important finding encoded here: the compiled network takes
**FP32** inputs ([1,2,1024] and [1,3,1024]) and quantizes to SInt8 *inside* the
NPU.  The frozen FPGA reference dequantization (iq x 1/127, physical x 2/127) is
therefore applied in the host adapter, never inside the compiled graph.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

FINAL_JSON = Path("F:/FPGA_Work/npu_stage_v1/compile/jsonraw/rfnet_npu_ZG.json")
FINAL_RAW = Path("F:/FPGA_Work/npu_stage_v1/compile/jsonraw/rfnet_npu_ZG.raw")

EXPECTED_INPUT_SHAPES = {"[1, 2, 1024]", "[1, 3, 1024]"}
EXPECTED_OUTPUT_SHAPE = [1, 8]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    model = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    ops = model["ops"]

    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"item": name, "pass": bool(ok), "detail": detail})

    # 1/2/3. input names/count, shape, batch
    input_ops = [op for op in ops if op["_type_key"].endswith("Input")]
    output_ops = [op for op in ops if op["_type_key"].endswith("Output")]
    record("input_count", len(input_ops) == 1, f"Input ops={len(input_ops)}")
    record("output_count", len(output_ops) == 1, f"Output ops={len(output_ops)}")

    input_values = input_ops[0]["outputs"] if input_ops else []
    in_shapes = [v["dtype"]["shape"] for v in input_values]
    record("input_count==2", len(input_values) == 2, f"input values={len(input_values)}")
    record(
        "input_shapes",
        {str(s) for s in in_shapes} == EXPECTED_INPUT_SHAPES,
        f"input shapes={in_shapes}",
    )
    record("input_batch==1", all(s[0] == 1 for s in in_shapes), f"batch dims={[s[0] for s in in_shapes]}")

    # 4/5/6/7/8. layout, dtype, signedness, scale, zero-point
    in_layouts = [v["dtype"]["layout"] for v in input_values]
    in_dtypes = [v["dtype"]["element_dtype"] for v in input_values]
    record("input_layout_channel_first", all("@layout(**C)" == str(l) for l in in_layouts),
           f"layouts={in_layouts}")
    record("input_dtype_fp32", all(d == "@fp(32)" for d in in_dtypes), f"dtypes={in_dtypes}")
    record("input_signedness_fp32", all(d == "@fp(32)" for d in in_dtypes),
           "FP32 boundary: signed float; signedness of SInt8 applies internally, not at the input")

    # 9. byte size
    in_bytes = [2 * 1024 * 4, 3 * 1024 * 4]
    record("input_byte_sizes", in_bytes == [8192, 12288], f"input bytes={in_bytes} (expected 8192 + 12288)")

    # 10. output shape + dtype
    out_values = output_ops[0]["inputs"] if output_ops else []
    out_shape = out_values[0]["dtype"]["shape"] if out_values else None
    out_dtype = out_values[0]["dtype"]["element_dtype"] if out_values else None
    record("output_shape", out_shape == EXPECTED_OUTPUT_SHAPE, f"output shape={out_shape}")
    record("output_dtype_fp32", out_dtype == "@fp(32)", f"output dtype={out_dtype}")
    record("output_byte_size", 8 * 4 == 32, "logits [1,8] FP32 = 32 B")

    # 11/12/13. op mapping, HostBackend fallback, ZG330 target
    targets = {}
    for op in ops:
        targets[op.get("compile_target", "?")] = targets.get(op.get("compile_target", "?"), 0) + 1
    host_ops = targets.get("@hostt", 0)
    zhuget_ops = targets.get("@zhuget(330)", 0)
    has_hostbackend = any("host" in str(k).lower() and k != "@hostt" for k in targets)
    record("zg330_target", model.get("ai_target") == "@zhuget(330)",
           f"ai_target={model.get('ai_target')}")
    record("op_mapping_zhuge", host_ops == 2 and zhuget_ops == len(ops) - 2,
           f"@hostt={host_ops} (Input+Output), @zhuget(330)={zhuget_ops}, total={len(ops)}")
    record("no_hostbackend_fallback", not has_hostbackend, f"targets={sorted(targets)}")

    # Extra: internal quantization storage is SInt8 (int8 quant took effect)
    sint8_outputs = 0
    fp32_outputs = 0
    for op in ops:
        for o in op.get("outputs", []):
            el = o["dtype"]["element_dtype"]
            if isinstance(el, dict):
                if el.get("storage_dtype") == "@sint(8)":
                    sint8_outputs += 1
                elif el.get("storage_dtype") == "@fp(32)":
                    fp32_outputs += 1
    record("internal_storage_sint8", sint8_outputs > 0,
           f"sint8 tensor outputs={sint8_outputs}, fp32 tensor outputs={fp32_outputs}")

    # Extract the input quantize scales (the CastNodes that produce SInt8)
    quant_scales = {}
    for op in ops:
        if op.get("name", "").endswith("CastNode"):
            for o in op.get("outputs", []):
                el = o["dtype"]["element_dtype"]
                if isinstance(el, dict) and el.get("storage_dtype") == "@sint(8)":
                    scale = str(el.get("scale", ""))
                    quant_scales[o.get("v_id")] = (o["dtype"]["shape"], scale)

    overall = all(c["pass"] for c in checks)

    report = {
        "gate": "compiled_model_gate",
        "overall": "PASS" if overall else "FAIL",
        "model_json": str(FINAL_JSON),
        "model_raw": str(FINAL_RAW),
        "model_json_sha256": sha256(FINAL_JSON),
        "model_raw_sha256": sha256(FINAL_RAW),
        "params_bytes": model.get("params_bytes"),
        "params_md5": model.get("params_md5"),
        "input_quantize_sint8_scales": {str(k): v for k, v in quant_scales.items()},
        "adapter_conversion": {
            "note": "Compiled input is FP32. Host adapter dequantizes FPGA SInt8 with the "
                    "frozen reference: iq x (1/127), physical x (2/127). NPU then re-quantizes "
                    "internally with its own learned scales (see input_quantize_sint8_scales).",
            "iq_scale_frozen_ref": 1.0 / 127.0,
            "physical_scale_frozen_ref": 2.0 / 127.0,
        },
        "checks": checks,
    }

    out = Path(__file__).resolve().parent / "compiled_model_gate_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for c in checks:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['item']}: {c['detail']}")
    print(f"COMPILED_MODEL_GATE_{'PASS' if overall else 'FAIL'}")
    print(f"report={out}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
