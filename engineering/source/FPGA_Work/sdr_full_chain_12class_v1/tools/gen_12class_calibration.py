#!/usr/bin/env python3
"""生成十二类 iCraft 3.39 量化校准数据（单输入，原始 fp32 I/Q）。

与 8 类的 generate_calibration.py 的关键区别（架构事实，勿静默改动）：
  8 类基线是【双输入】 iq[1,2,1024] + physical_features[1,3,1024]，其校准域是
  FPGA Mandatory Core 反量化域（iq*1/127、physical*2/127）。
  十二类模型是【单输入】 raw I/Q [1,2,1024]，模型内部自己算特征，无 FPGA 特征
  提取，无反量化。因此校准域 = 训练输入域本身：generate_iq(RMS 1.0) 过
  ChannelPipeline（域随机化）后 np.stack((real, imag)) -> float32 [2,1024]。

本脚本【只读】导入源工程（sys.path 注入，不写任何源工程文件），输出全部落到
新工程 model_12class/calibration/。RNG 复刻 ADAMRPairDataset.__getitem__ 的
SeedSequence([seed, split_code, epoch=0, index])，保证与训练集 train split 逐样本
一致（split_code = blake2s(split)）。

输出：
  model_12class/calibration/cal_data/iq_N.bin   fp32 [1,2,1024] (I 平面, Q 平面) = 8192 B
  model_12class/calibration/forward_list.txt    每行 "iq_N.bin"（单输入）
  model_12class/calibration/calibration_manifest.json
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
SAMPLE_ID_STRIDE = 1_000_000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1_data_v3_12class.yaml")
    parser.add_argument("--num-samples", type=int, default=252)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--split", default="ad_amr_v1_1_train")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("F:/FPGA_Work/sdr_full_chain_12class_v1/model_12class/calibration"))
    args = parser.parse_args()

    config = load_yaml(args.config)
    signal_config = config["signal"]
    channel_config = config["channel"]
    sample_rate = float(signal_config["sample_rate"])
    amplitude = float(signal_config.get("amplitude", 1.0))
    modulations = [name.upper() for name in signal_config["modulations"]]
    snr_values = [float(v) for v in config["dataset"]["snr_values"]]

    split_code = int.from_bytes(hashlib.blake2s(args.split.encode("utf-8"), digest_size=4).digest(), "little")
    channel = ChannelPipeline(channel_config, sample_rate)

    cal_dir = args.output_dir / "cal_data"
    cal_dir.mkdir(parents=True, exist_ok=True)

    forward_lines: list[str] = []
    rows: list[dict] = []

    for index in range(args.num_samples):
        seed_key = [args.seed, split_code, 0, index]
        rng = np.random.default_rng(np.random.SeedSequence(seed_key))

        combination = index % (len(modulations) * len(snr_values))
        label = combination % len(modulations)
        assigned_snr = snr_values[combination // len(modulations)]
        modulation = modulations[label]

        clean, _ = generate_iq(modulation, signal_config, rng)
        noisy, _ = channel(clean, rng, snr_db=assigned_snr)
        iq = np.stack((noisy.real, noisy.imag)).astype(np.float32)  # [2, 1024]
        assert iq.shape == (2, FRAME_LENGTH), iq.shape

        iq_path = cal_dir / f"iq_{index}.bin"
        iq.astype(np.float32).tofile(iq_path)

        forward_lines.append(f"iq_{index}.bin")
        rows.append({
            "index": index,
            "modulation": modulation,
            "label": label,
            "snr_db": assigned_snr,
            "iq_file": iq_path.name,
        })

    forward_list_path = args.output_dir / "forward_list.txt"
    forward_list_path.write_text("\n".join(forward_lines) + "\n", encoding="utf-8")

    manifest = {
        "seed": args.seed,
        "split": args.split,
        "split_code": split_code,
        "num_samples": args.num_samples,
        "modulations": modulations,
        "snr_values": snr_values,
        "amplitude": amplitude,
        "sample_rate": sample_rate,
        "input_shape": [1, 2, FRAME_LENGTH],
        "input_layout": "FD",
        "input_dtype": "fp32",
        "bytes_per_sample": 2 * FRAME_LENGTH * 4,
        "single_input": True,
        "domain": "raw training I/Q (RMS-normalized, ChannelPipeline domain randomization)",
        "forward_list": str(forward_list_path),
        "rows": rows,
    }
    (args.output_dir / "calibration_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    per_class = {m: sum(1 for r in rows if r["modulation"] == m) for m in modulations}
    print(f"CALIBRATION_GENERATED samples={args.num_samples}")
    print(f"  modulations={modulations}")
    print(f"  per_class={per_class}")
    print(f"  input_shape={manifest['input_shape']} bytes/sample={manifest['bytes_per_sample']}")
    print(f"  output_dir={cal_dir}")
    print(f"  forward_list={forward_list_path}")


if __name__ == "__main__":
    main()
