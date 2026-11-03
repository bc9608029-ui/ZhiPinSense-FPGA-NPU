"""Strict 24-class RadioML2018.01A audit + frozen split/manifest emission.

Runs the verbatim ``scripts.audit_radioml2018.audit`` (SHA-256 of the 20 GiB
HDF5, fail-closed X/Y/Z validation, per-(class,SNR) stratified split), then
emits the portable artifacts:

* ``manifests/rml24_{train,validation,test}.tsv`` — frozen, deterministic rows;
* ``contracts/rml2018_data_contract.json`` — the portable, machine-independent
  audit facts (HDF5 SHA-256, size, sample count, split seed/ratios/counts);
* ``reports/RML2018_DATA_AUDIT.md`` — the human-readable audit report.

``hdf5_path``/``mtime_ns``/absolute ``index_path`` are machine-local and are
*not* frozen into the portable contract: the same file re-audited on AutoDL
produces an identical SHA-256 and identical split indices (the split depends
only on ``split_seed`` + label + SNR), so the contract's SHA-256 is the
cross-machine ground truth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from scripts.audit_radioml2018 import audit as run_audit
from training.utils import load_yaml, resolve_project_path

_SPLIT_NAMES = ("train", "validation", "test")


def _build_manifests(index_path: Path, class_names: list[str], manifest_dir: Path) -> dict[str, Path]:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    with np.load(index_path, allow_pickle=False) as indices:
        for split in _SPLIT_NAMES:
            rows = indices[f"{split}_indices"].astype(np.int64)
            labels = indices[f"{split}_labels"].astype(np.int64)
            snrs = indices[f"{split}_snrs"].astype(np.float32)
            out = manifest_dir / f"rml24_{split}.tsv"
            with out.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("sample_index\tsource_row\tclass_name\tlabel\tsnr_db\n")
                for i, (row, label, snr) in enumerate(zip(rows, labels, snrs)):
                    handle.write(f"{i}\t{int(row)}\t{class_names[int(label)]}\t{int(label)}\t{float(snr):g}\n")
            written[split] = out
    return written


def _write_contract(report: dict[str, Any], contract_path: Path) -> dict[str, Any]:
    portable = {
        "dataset": report["dataset"],
        "status": report["status"],
        "sha256": report["sha256"],
        "size_bytes": report["size_bytes"],
        "samples": report["samples"],
        "sample_shape": report["sample_shape"],
        "num_classes": len(report["class_names"]),
        "class_names": report["class_names"],
        "split_seed": report["split_seed"],
        "split_ratios": report["split_ratios"],
        "split_counts": report["split_counts"],
        "strata": {"count": len(report["strata_counts"]),
                    "expected": 624,
                    "per_stratum": next(iter(report["strata_counts"].values()))},
        "overlap_counts": report["overlap_counts"],
        "synthetic_fallback": report["synthetic_fallback"],
        "index_sha256": report["index_sha256"],
        "portability_note": (
            "hdf5_path/mtime_ns/absolute index_path are machine-local and regenerated "
            "on AutoDL; sha256/split_seed/split_counts/strata are portable ground truth."
        ),
    }
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(portable, ensure_ascii=False, indent=2), encoding="utf-8")
    return portable


def _write_report(report: dict[str, Any], report_path: Path) -> None:
    lines: list[str] = []
    lines.append("# RadioML2018.01A 严格 24 类数据审计报告\n")
    lines.append(f"状态：`{report['status']}`  —  数据集：`{report['dataset']}`\n")
    lines.append("## 文件身份\n")
    lines.append(f"- 本地路径：`{report['hdf5_path']}`")
    lines.append(f"- 大小：`{report['size_bytes']}` B（≈ {report['size_bytes'] / 1e9:.2f} GiB）")
    lines.append(f"- SHA-256：`{report['sha256']}`")
    lines.append(f"- 修改时间 ns：`{report['mtime_ns']}`（机器本地，跨机不冻结）")
    lines.append("")
    lines.append("## 结构校验\n")
    lines.append(f"- 样本数：`{report['samples']}`（期望 2,555,904）")
    lines.append(f"- 样本形状：`{report['sample_shape']}`（[1024, 2] I/Q 对）")
    lines.append(f"- 类别数：`{len(report['class_names'])}`（严格 24）")
    lines.append(f"- 标签顺序：`{'`, `'.join(report['class_names'])}`")
    lines.append(f"- SNR 档：26 档（-20..30 步长 2），每 (类别,SNR) 4096 样本")
    lines.append(f"- 分层数：`{len(report['strata_counts'])}`（期望 624）")
    lines.append(f"- 有限性 / one-hot / 二值校验：通过（fail-closed）")
    lines.append(f"- 合成回退：`{report['synthetic_fallback']}`")
    lines.append("")
    lines.append("## 切分（防泄漏）\n")
    lines.append(f"- split_seed：`{report['split_seed']}`")
    lines.append(f"- split_ratios：`{report['split_ratios']}`")
    lines.append(f"- split_counts：`{json.dumps(report['split_counts'])}`")
    lines.append(f"- 重叠计数：`{json.dumps(report['overlap_counts'])}`")
    lines.append(f"- 索引 SHA-256：`{report['index_sha256']}`")
    lines.append(f"- 索引路径（机器本地）：`{report['index_path']}`")
    lines.append("")
    lines.append("## 跨机可移植性\n")
    lines.append("HDF5 SHA-256 与切分索引（split_seed + label + SNR 决定）是跨机不变量；"
                 "路径与 mtime 为机器本地值，AutoDL 上需重新运行审计，SHA-256 应保持一致。\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def audit_rml2018(config_or_path: dict[str, Any] | str,
                  hdf5_path: str | None = None) -> dict[str, Any]:
    config = config_or_path if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    if hdf5_path:
        config = {k: (dict(v) if isinstance(v, dict) else v) for k, v in config.items()}
        config["public_data"] = dict(config["public_data"])
        config["public_data"]["hdf5_path"] = hdf5_path

    report = run_audit(config)
    index_path = Path(report["index_path"])
    manifest_dir = resolve_project_path("manifests")
    manifests = _build_manifests(index_path, report["class_names"], manifest_dir)
    contract = _write_contract(report, resolve_project_path("contracts/rml2018_data_contract.json"))
    _write_report(report, resolve_project_path("reports/RML2018_DATA_AUDIT.md"))
    return {
        "report": report,
        "manifests": {split: str(path) for split, path in manifests.items()},
        "contract": contract,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit RadioML2018.01A and freeze the 24-class split")
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--hdf5-path", default=None,
                        help="override public_data.hdf5_path (e.g. the local F:/datasets location)")
    args = parser.parse_args()
    result = audit_rml2018(args.config, args.hdf5_path)
    report = result["report"]
    print(json.dumps({
        "status": report["status"], "sha256": report["sha256"],
        "samples": report["samples"], "split_counts": report["split_counts"],
        "manifests": result["manifests"],
    }, indent=2))
    print("RML24_DATA_AUDIT_OK")


if __name__ == "__main__":
    main()
