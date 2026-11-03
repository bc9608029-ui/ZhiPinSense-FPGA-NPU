"""Public-pretrained twelve-class V1.1 target training entrypoint."""

from __future__ import annotations

import argparse
from typing import Any

from datasets.modulation_generator import V1_1_12_MODULATIONS
from training.train_ad_amr_v1_1_data_v2 import run_data_v2_training
from training.utils import load_yaml


def assert_twelve_class_contract(config: dict[str, Any]) -> None:
    classes = tuple(str(value).upper() for value in config["signal"]["modulations"])
    if classes != V1_1_12_MODULATIONS:
        raise RuntimeError(
            f"data-v3 requires fixed twelve-class order {V1_1_12_MODULATIONS}, received {classes}"
        )
    aliases = config["training"]["distillation"].get("class_aliases")
    if aliases:
        raise RuntimeError("twelve-class training forbids teacher class aliases")


def run_data_v3_training(
    config_or_path: dict[str, Any] | str,
    *,
    resume: bool = False,
    stop_after_epoch: int | None = None,
    initialize_from_public: bool = True,
) -> dict[str, Any]:
    config = load_yaml(config_or_path) if isinstance(config_or_path, str) else config_or_path
    assert_twelve_class_contract(config)
    result = run_data_v2_training(
        config, resume=resume, stop_after_epoch=stop_after_epoch,
        initialize_from_public=initialize_from_public,
    )
    result["class_contract"] = list(V1_1_12_MODULATIONS)
    result["target_class_count"] = len(V1_1_12_MODULATIONS)
    result["ten_class_head_reused"] = False
    result["architecture_changed_from_v1_1"] = True
    result["architecture_change_scope"] = "classifier output width only: 10 -> 12"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1_data_v3_12class.yaml")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--stop-after-epoch", type=int, default=None)
    args = parser.parse_args()
    result = run_data_v3_training(
        args.config, resume=args.resume, stop_after_epoch=args.stop_after_epoch,
        initialize_from_public=not args.scratch,
    )
    print(
        f"best_epoch={result['best_epoch']} best_f1={result['best_validation_macro_f1']:.6f} "
        f"rated={result['best_validation_rated_0_20_accuracy']:.6f}", flush=True,
    )


if __name__ == "__main__":
    main()
