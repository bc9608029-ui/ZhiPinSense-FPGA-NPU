from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np
import pytest
import torch

from datasets.radioml2018_dataset import OFFICIAL_CLASS_ORDER, RadioML2018Dataset, read_class_names
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from scripts.audit_radioml2018 import audit
from scripts.package_ad_amr_v1_1_data_v2_autodl import included_files
from scripts.run_ad_amr_v1_1_data_v2_formal import _formal_config
from training.pretrain_ad_amr_v1_1_radioml import run_public_pretraining
from training.train_ad_amr_v1_1_data_v2 import (
    CLASSIFIER_OUTPUT_KEYS, load_public_trunk, run_data_v2_training,
)
from training.utils import load_yaml


SNR_VALUES = tuple(range(-20, 31, 2))


def _dataset_args(public: dict) -> dict:
    return {name: public[name] for name in (
        "hdf5_path", "classes_path", "audit_path", "index_path",
    )}


@pytest.fixture(scope="module")
def toy_public(tmp_path_factory):
    root = tmp_path_factory.mktemp("radioml2018")
    hdf5_path = root / "toy.hdf5"
    classes_path = root / "classes.txt"
    audit_path = root / "audit.json"
    index_path = root / "indices.npz"
    classes_path.write_text("\n".join(OFFICIAL_CLASS_ORDER) + "\n", encoding="utf-8")
    per_stratum = 5
    samples = len(OFFICIAL_CLASS_ORDER) * len(SNR_VALUES) * per_stratum
    with h5py.File(hdf5_path, "w") as handle:
        x = handle.create_dataset("X", shape=(samples, 1024, 2), dtype="f4", chunks=(8, 1024, 2))
        y = handle.create_dataset("Y", shape=(samples, 24), dtype="f4")
        z = handle.create_dataset("Z", shape=(samples, 1), dtype="f4")
        cursor = 0
        for label in range(24):
            for snr in SNR_VALUES:
                for repeat in range(per_stratum):
                    x[cursor, :, 0] = (label + 1) / 24.0
                    x[cursor, :, 1] = (snr + repeat) / 100.0
                    y[cursor] = np.eye(24, dtype=np.float32)[label]
                    z[cursor, 0] = snr
                    cursor += 1
    config = {
        "public_data": {
            "hdf5_path": str(hdf5_path), "classes_path": str(classes_path),
            "audit_path": str(audit_path), "index_path": str(index_path),
            "split_seed": 17, "split_ratios": [0.6, 0.2, 0.2], "audit_chunk_size": 113,
            "x_audit_chunk_size": 41, "expected_snr_values": list(SNR_VALUES),
            "expected_samples": samples, "expected_per_stratum": per_stratum,
        }
    }
    report = audit(config)
    return root, config, report


def test_public_audit_is_deterministic_and_leakage_free(toy_public) -> None:
    _root, config, first = toy_public
    first_index = Path(config["public_data"]["index_path"]).read_bytes()
    second = audit(config)
    second_index = Path(config["public_data"]["index_path"]).read_bytes()
    assert first["status"] == "pass"
    assert first["split_counts"] == {"train": 1872, "validation": 624, "test": 624}
    assert first["overlap_counts"] == {
        "train_validation": 0, "train_test": 0, "validation_test": 0,
    }
    assert first["index_sha256"] == second["index_sha256"]
    assert first_index == second_index


def test_public_dataset_contract_and_test_is_not_used_for_training(toy_public) -> None:
    _root, config, _report = toy_public
    public = config["public_data"]
    train = RadioML2018Dataset(
        **_dataset_args(public), split="train", allowed_snrs=[0], max_per_stratum=1
    )
    validation = RadioML2018Dataset(
        **_dataset_args(public), split="validation", allowed_snrs=[0], max_per_stratum=1
    )
    assert len(train) == len(validation) == 24
    sample = train[0]
    assert sample["noisy_iq"].shape == (2, 1024)
    assert torch.equal(sample["clean_iq"], sample["noisy_iq"])
    assert sample["split"] == "radioml2018_train"
    assert set(train.indices.tolist()).isdisjoint(validation.indices.tolist())


def test_public_data_fails_closed_and_rejects_wrong_class_order(toy_public, tmp_path) -> None:
    _root, config, _report = toy_public
    public = dict(config["public_data"])
    public["hdf5_path"] = str(tmp_path / "missing.hdf5")
    with pytest.raises(FileNotFoundError, match="required public-data artifact"):
        RadioML2018Dataset(**_dataset_args(public), split="train")
    wrong = tmp_path / "wrong_classes.txt"
    values = list(OFFICIAL_CLASS_ORDER)
    values[0], values[1] = values[1], values[0]
    wrong.write_text("\n".join(values), encoding="utf-8")
    with pytest.raises(RuntimeError, match="class order differs"):
        read_class_names(wrong)


def test_public_dataset_rejects_tampered_index(toy_public, tmp_path) -> None:
    _root, config, report = toy_public
    source = Path(config["public_data"]["index_path"])
    tampered = tmp_path / "tampered.npz"
    tampered.write_bytes(source.read_bytes() + b"tamper")
    audit_copy = tmp_path / "audit.json"
    payload = dict(report)
    payload["index_path"] = str(tampered)
    audit_copy.write_text(json.dumps(payload), encoding="utf-8")
    public = dict(config["public_data"])
    public.update({"audit_path": str(audit_copy), "index_path": str(tampered)})
    with pytest.raises(RuntimeError, match="index SHA-256"):
        RadioML2018Dataset(**_dataset_args(public), split="train")


def test_public_transfer_copies_trunk_but_not_ten_class_head(tmp_path) -> None:
    torch.manual_seed(11)
    source = build_ad_amr_v1_1_model(24)
    torch.manual_seed(29)
    target = build_ad_amr_v1_1_model(10)
    head_before = {name: value.clone() for name, value in target.state_dict().items()
                   if name in CLASSIFIER_OUTPUT_KEYS}
    checkpoint = tmp_path / "public.pt"
    torch.save({
        "epoch": 3, "class_names": list(OFFICIAL_CLASS_ORDER),
        "model_state": source.state_dict(),
        "checkpoint_metadata": {
            "dataset": "RadioML2018.01A", "dataset_sha256": "a" * 64,
            "index_sha256": "b" * 64, "public_test_accessed": False,
        },
    }, checkpoint)
    report = load_public_trunk(target, checkpoint)
    target_state = target.state_dict()
    source_state = source.state_dict()
    for name in target_state:
        if name in CLASSIFIER_OUTPUT_KEYS:
            assert torch.equal(target_state[name], head_before[name])
        else:
            assert torch.equal(target_state[name], source_state[name])
    assert report["excluded_tensors"] == sorted(CLASSIFIER_OUTPUT_KEYS)
    assert report["source_epoch"] == 3


def test_public_pretrain_resume_and_target_transfer_smoke(toy_public) -> None:
    root, toy_config, _report = toy_public
    config = load_yaml("configs/ad_amr_v1_1_data_v2.yaml")
    config["device"] = "cpu"
    config["public_data"].update(toy_config["public_data"])
    config["public_data"]["allowed_snrs"] = [0]
    config["public_pretraining"].update({
        "output_root": str(root / "public_training"), "epochs": 2, "batch_size": 24,
        "minimum_epochs_before_stopping": 2, "early_stopping_patience": 2,
        "num_workers": 0, "max_train_per_stratum": 1,
        "max_validation_per_stratum": 1, "amp": False,
    })
    first = run_public_pretraining(config, resume=False, stop_after_epoch=1)
    resumed = run_public_pretraining(config, resume=True, stop_after_epoch=1)
    assert [row["epoch"] for row in first["history"]] == [1]
    assert [row["epoch"] for row in resumed["history"]] == [1, 2]
    public_checkpoint = root / "public_training/checkpoints/best.pt"
    checkpoint = torch.load(public_checkpoint, map_location="cpu", weights_only=False)
    assert checkpoint["checkpoint_metadata"]["public_test_accessed"] is False

    config["output_root"] = str(root / "target_training")
    config["initialization"]["public_checkpoint"] = str(public_checkpoint)
    config["dataset"].update({"train_samples": 210, "val_samples": 210, "num_workers": 0})
    config["training"].update({
        "epochs": 1, "batch_size": 32, "minimum_epochs_before_stopping": 1,
        "early_stopping_patience": 1, "amp": False,
    })
    config["training"]["distillation"]["enabled"] = False
    target = run_data_v2_training(config, resume=False, stop_after_epoch=1)
    assert [row["epoch"] for row in target["history"]] == [1]
    assert target["architecture_changed_from_v1_1"] is False
    assert target["initialization"]["copied_tensor_count"] > 0


def test_source_package_excludes_public_data_and_generated_indices() -> None:
    names = [path.as_posix().lower() for path in included_files()]
    assert any(name.endswith("data/radioml2018/classes.txt") for name in names)
    assert not any(name.endswith((".h5", ".hdf5", ".npz")) for name in names)
    assert not any(name.endswith("data/radioml2018/audit.json") for name in names)


def test_formal_config_is_two_seed_and_keeps_public_initialization() -> None:
    base = load_yaml("configs/ad_amr_v1_1_data_v2.yaml")
    assert base["data_v2_formal"]["seeds"] == [2026, 2027]
    first = _formal_config(base, 2026)
    second = _formal_config(base, 2027)
    assert first["seed"] == 2026 and second["seed"] == 2027
    assert first["output_root"].endswith("formal/seed2026")
    assert second["output_root"].endswith("formal/seed2027")
    assert first["initialization"]["public_checkpoint"] == base["initialization"]["public_checkpoint"]
    assert first["training"]["epochs"] == 100


def test_data_v2_autodl_formal_script_is_packaged() -> None:
    names = [path.relative_to(Path(__file__).resolve().parents[1]).as_posix()
             for path in included_files()]
    assert "autodl_ad_amr_v1_1_data_v2/run_formal.sh" in names
    assert "scripts/run_ad_amr_v1_1_data_v2_formal.py" in names
