"""Run the established leakage/balance audit against the merged V3.1 config."""

from __future__ import annotations

import argparse
import copy
import json

from evaluation.dataset_audit import run_dataset_audit
from training.qam_aware_v3_1_utils import load_qam_aware_v3_1_config


def audit_v3_1(config_path: str) -> dict:
    config = copy.deepcopy(load_qam_aware_v3_1_config(config_path))
    config["output_dir"] = config["output_root"]
    config["_config_path"] = config["_requested_config_path"]
    return run_dataset_audit(config)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_1.yaml")
    args = parser.parse_args()
    print(json.dumps(audit_v3_1(args.config), indent=2))


if __name__ == "__main__":
    main()
