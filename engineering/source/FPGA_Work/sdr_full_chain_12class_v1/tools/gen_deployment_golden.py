#!/usr/bin/env python3
"""生成十二类部署黄金集（deployment_golden/），用于验证 PyTorch -> ONNX Runtime -> NPU。

黄金样本 = 训练输入域（generate_iq -> ChannelPipeline -> real/imag stack）的 fp32
I/Q [1,2,1024]；期望值 = 已导出的 ONNX（ad_amr_v1_1_opset17.onnx）在 CPU ONNX Runtime
上推理得到的 12 维 logits + argmax + softmax confidence。

（PyTorch <-> ONNX 一致性已由源工程 export_report.json 锁定：ort_parity
max_abs_diff 5.48e-6，此处不重复跑 torch，直接用 ONNX 作为部署权威参考。）

输出（>= 每类若干条，默认 12 类 x 20 = 240 条，>= 120）：
  deployment_golden/input_000.bin ...                 fp32 [1,2,1024] 原始 I/Q
  deployment_golden/expected_logits_or_argmax.json    per-sample argmax/class/confidence/logits
  deployment_golden/manifest.json                     来源 ONNX SHA / 类别顺序 / 统计

只读导入源工程，输出全部落到新工程，不修改任何上游文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

SRC = Path("F:/FPGA_Work/_tmp_ad_amr_results_verify/ad_amr_data_v3_12class_ff2b3fb3_run")
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from channel.channel_pipeline import ChannelPipeline  # noqa: E402
from datasets.modulation_generator import generate_iq  # noqa: E402
from training.utils import load_yaml  # noqa: E402

FRAME_LENGTH = 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def softmax(logits: np.ndarray) -> np.ndarray:
    mx = float(logits.max())
    e = np.exp(logits - mx)
    return e / float(e.sum())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1_data_v3_12class.yaml")
    parser.add_argument("--onnx", type=Path,
                        default=SRC / "outputs/ad_amr_v1_1_data_v3_12class/formal/export/onnx/ad_amr_v1_1_opset17.onnx")
    parser.add_argument("--per-class", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2027)  # 与训练 seed 区分，避免与校准集重叠
    parser.add_argument("--split", default="ad_amr_v1_1_validation")  # 黄金集取 val 命名空间
    parser.add_argument("--output-dir", type=Path,
                        default=Path("F:/FPGA_Work/sdr_full_chain_12class_v1/deployment_golden"))
    args = parser.parse_args()

    import onnxruntime as ort

    config = load_yaml(args.config)
    signal_config = config["signal"]
    channel_config = config["channel"]
    sample_rate = float(signal_config["sample_rate"])
    modulations = [name.upper() for name in signal_config["modulations"]]
    num_classes = len(modulations)

    split_code = int.from_bytes(hashlib.blake2s(args.split.encode("utf-8"), digest_size=4).digest(), "little")
    channel = ChannelPipeline(channel_config, sample_rate)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = ort.InferenceSession(str(args.onnx), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name  # "iq"

    total = num_classes * args.per_class
    rows: list[dict] = []
    per_class_count = {m: 0 for m in modulations}

    for index in range(total):
        label = index % num_classes
        modulation = modulations[label]
        # 每条黄金样本固定 SNR 取 10 dB（干净可判），保证 argmax 稳定可复现。
        snr_db = 10.0
        seed_key = [args.seed, split_code, 0, index]
        rng = np.random.default_rng(np.random.SeedSequence(seed_key))

        clean, _ = generate_iq(modulation, signal_config, rng)
        noisy, _ = channel(clean, rng, snr_db=snr_db)
        iq = np.stack((noisy.real, noisy.imag)).astype(np.float32)  # [2, 1024]
        assert iq.shape == (2, FRAME_LENGTH)

        input_path = args.output_dir / f"input_{index:03d}.bin"
        iq.tofile(input_path)

        batch = iq.reshape(1, 2, FRAME_LENGTH)
        logits = np.asarray(session.run(None, {input_name: batch})[0], dtype=np.float32).reshape(-1)
        assert logits.shape == (num_classes,), logits.shape
        probs = softmax(logits).astype(np.float32)
        argmax = int(np.argmax(logits))

        per_class_count[modulation] += 1
        rows.append({
            "index": index,
            "label": label,
            "modulation": modulation,
            "snr_db": snr_db,
            "input_file": input_path.name,
            "argmax_idx": argmax,
            "argmax_class": modulations[argmax],
            "confidence": float(probs[argmax]),
            "logits": [float(v) for v in logits],
        })

    expected = {
        "source_onnx": str(args.onnx),
        "source_onnx_sha256": sha256_file(args.onnx),
        "onnx_input_name": input_name,
        "class_order": modulations,
        "samples": rows,
    }
    (args.output_dir / "expected_logits_or_argmax.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8"
    )

    manifest = {
        "seed": args.seed,
        "split": args.split,
        "split_code": split_code,
        "num_samples": total,
        "per_class": args.per_class,
        "per_class_count": per_class_count,
        "class_order": modulations,
        "source_onnx": str(args.onnx),
        "source_onnx_sha256": sha256_file(args.onnx),
        "input_shape": [1, 2, FRAME_LENGTH],
        "input_dtype": "fp32",
        "snr_db": 10.0,
        "expected_file": "expected_logits_or_argmax.json",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 统计 argmax 与标签一致率（10 dB 高 SNR 下应接近 100%，用于快速发现域/顺序错误）。
    correct = sum(1 for r in rows if r["argmax_idx"] == r["label"])
    print(f"DEPLOYMENT_GOLDEN_GENERATED samples={total} per_class={args.per_class}")
    print(f"  per_class_count={per_class_count}")
    print(f"  argmax_correct={correct}/{total} ({100.0 * correct / total:.1f}%)")
    print(f"  onnx_sha256={manifest['source_onnx_sha256'][:16]}...")
    print(f"  output_dir={args.output_dir}")


if __name__ == "__main__":
    main()
