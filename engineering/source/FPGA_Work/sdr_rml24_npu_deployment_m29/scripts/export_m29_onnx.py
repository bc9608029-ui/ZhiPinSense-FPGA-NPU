#!/usr/bin/env python
"""M29 Phase B — export the frozen RML2018 24-class model to ONNX (opset 17, IR 8).

Mirrors the 12-class `export_ad_amr_v1_1_onnx.py` gate-for-gate:
  * load checkpoint (weights_only=True), build ADAMRV11Net(num_classes=24)
  * wrap in RML24Classifier (logits-only), eval
  * torch.onnx.export(opset=17, input "iq"[1,2,1024], output "logits"[1,24])
  * onnx.checker + shape inference + NPU operator gate (Add/BatchNormalization/Conv/Gemm/ReduceMean/Relu)
  * ONNX Runtime parity vs PyTorch on a zero sample + a fixed-seed random sample

Writes work/onnx/rml24_24class_opset17.onnx + export_report.json.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)  # front: user-site protobuf 7.x must shadow Anaconda 5.x

import torch  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
V11 = r"F:\FPGA_Work\sdr_amr_rml24_ood_v1_1"
CHECKPOINT = r"F:\FPGA_Work\24class_results\rml24_seed2027_best.pt"
ONNX_DIR = os.path.join(ROOT, "work", "onnx")
ONNX_PATH = os.path.join(ONNX_DIR, "rml24_24class_opset17.onnx")

ALLOWED_OPS = {"Add", "BatchNormalization", "Conv", "Gemm", "ReduceMean", "Relu"}
OPSET_VERSION = 17


def main() -> int:
    sys.path.insert(0, V11)
    import onnx
    import numpy as np
    from models.rml24_net import RML24Classifier, build_rml24_model
    from contracts.rml24_contract import LABEL_ORDER_24

    print("== M29 Phase B: ONNX export ==")

    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    assert list(ckpt.get("class_names", [])) == list(LABEL_ORDER_24), "class order drift"
    model_cfg = {
        "denoiser_channels": 24, "denoiser_blocks": 3,
        "feature_channels": [32, 48, 64, 96], "classifier_hidden": 128, "dropout": 0.15,
    }
    model = build_rml24_model(len(LABEL_ORDER_24), **model_cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    wrapper = RML24Classifier(model).eval()

    os.makedirs(ONNX_DIR, exist_ok=True)
    sample = torch.zeros(1, 2, 1024, dtype=torch.float32)
    torch.onnx.export(wrapper, sample, ONNX_PATH, opset_version=OPSET_VERSION,
                      input_names=["iq"], output_names=["logits"], dynamo=False)
    print(f"  exported: {ONNX_PATH}")

    onnx_model = onnx.load(ONNX_PATH)
    onnx.checker.check_model(onnx_model)
    opset = next(int(v.version) for v in onnx_model.opset_import if v.domain in ("", "ai.onnx"))
    ir = onnx_model.ir_version
    operators = Counter(n.op_type for n in onnx_model.graph.node)
    unexpected = sorted(set(operators) - ALLOWED_OPS)
    print(f"  checker OK; opset={opset} ir={ir}")
    print(f"  op_types={dict(sorted(operators.items()))}")
    if unexpected:
        print(f"  FAIL: unexpected operators {unexpected}")
        return 1

    # input/output shape contract
    inp = onnx_model.graph.input[0]
    outp = onnx_model.graph.output[0]
    def _dims(vp):
        return [d.dim_value for d in vp.type.tensor_type.shape.dim]
    print(f"  input  {inp.name} {_dims(inp)}")
    print(f"  output {outp.name} {_dims(outp)}")
    assert _dims(inp) == [1, 2, 1024], _dims(inp)
    assert _dims(outp) == [1, 24], _dims(outp)

    # shape inference
    inferred = onnx.shape_inference.infer_shapes(onnx_model)
    o = inferred.graph.output[0]
    inferred_dims = [d.dim_value for d in o.type.tensor_type.shape.dim]
    print(f"  shape inference output dims={inferred_dims}")
    assert inferred_dims == [1, 24], inferred_dims

    # ONNX Runtime parity (zero sample + fixed-seed random sample)
    import onnxruntime as ort
    session = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(2027)
    random_sample = (rng.standard_normal((1, 2, 1024)) / 64.0).astype(np.float32)  # ~RMS 0.015, in-range
    parity = {}
    for name, arr in [("zeros", sample.numpy()), ("random", random_sample)]:
        with torch.inference_mode():
            expected = wrapper(torch.from_numpy(arr)).cpu().numpy()
        actual = session.run(None, {"iq": arr})[0]
        diff = np.abs(actual - expected)
        parity[name] = {
            "max_abs_diff": float(diff.max()), "mean_abs_diff": float(diff.mean()),
            "allclose_1e-4": bool(np.allclose(actual, expected, atol=1e-4, rtol=1e-4)),
        }
        print(f"  ort parity[{name}]: max_abs_diff={diff.max():.3e} mean={diff.mean():.3e}")
    ok = all(p["max_abs_diff"] < 1e-3 for p in parity.values())
    if not ok:
        print("  FAIL: ORT parity threshold (1e-3) exceeded")
        return 1

    n_params = sum(p.numel() for p in model.parameters())
    report = {
        "onnx_path": ONNX_PATH,
        "checkpoint": CHECKPOINT,
        "checkpoint_sha256": "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d",
        "checkpoint_epoch": int(ckpt.get("epoch")),
        "model_name": "RML2018_24_BENCHMARK",
        "class_count": 24,
        "opset": opset, "ir_version": ir,
        "input": {"name": inp.name, "dims": _dims(inp), "dtype": "float32"},
        "output": {"name": outp.name, "dims": _dims(outp), "dtype": "float32"},
        "op_types": dict(sorted(operators.items())),
        "unexpected_operators": unexpected,
        "ort_parity": parity,
        "parameter_count": int(n_params),
        "npu_graph_claim": "operator-compatible only; vendor compilation and board parity remain required",
    }
    with open(os.path.join(ONNX_DIR, "export_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(ROOT, "artifacts", "m29_onnx_export_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("  wrote export_report.json + artifacts/m29_onnx_export_report.json")
    print("== M29 Phase B PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
