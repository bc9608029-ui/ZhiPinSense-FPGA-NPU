"""M29 fix10class24-dualsdr-rf-adapt-prep1 — dual-SDR RF dataset contract v1.

Pure-stdlib and importable under ``python -I``.  This module is PREP ONLY: it
freezes the data contract, the deterministic capture plan, and the leak-free
split for the FUTURE real-RF dual-SDR domain-adaptation dataset.  It does not
capture, train, or quantize anything, and it does NOT modify the frozen
24-class label contract (``rml24_raw_contract.py``) or the 23-class merged
contract (``rml23_merged_contract.py``).

Single source of truth for every downstream tool in this prep task:
``build_fix10class24_dualsdr_rf_dataset.py``, ``train_fix10class24_rf_adapt.py``,
``evaluate_fix10class24_rf_adapt.py``, the export/compile scripts, and the
host tests all import from here.
"""
from __future__ import annotations

import hashlib
import json

# ---------------------------------------------------------------------------
# frozen identities (verbatim from the verified source assets; DO NOT EDIT)
# ---------------------------------------------------------------------------
FROZEN = {
    # FP32 source checkpoint (init point for adaptation) and its ONNX export
    "fp32_checkpoint_sha256": "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d",
    "onnx_sha256": "976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51",
    # frozen 24-class label contract
    "label_contract_sha256": "3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549",
    # production BF16 model (never overwritten)
    "bf16_json_sha256": "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42",
    "bf16_raw_sha256": "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151",
    # TF32 A/B model (sibling experiment, never overwritten)
    "tf32_json_sha256": "8d00a1c31835611f18064389e5b9ecab755afefa5bacd78a983119757e65fa37",
    "tf32_raw_sha256": "f8366a109576ea53c9b3ddfd2e7b690590515ff3dfb33c6af7cf6ccafcdb392e",
}

NETWORK_NAME = "model_24class"
MODEL_IO = {
    "input_shape": [1, 2, 1024],
    "input_dtype": "fp32",
    "input_bytes": 2 * 1024 * 4,  # 8192
    "output_shape": [1, 24],
    "output_dtype": "fp32",
}

# ---------------------------------------------------------------------------
# frozen 24-class label order (verbatim from rml24_raw_contract.py)
# ---------------------------------------------------------------------------
SOURCE_LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)
SOURCE_CLASS_COUNT = 24

# deployed23 index for each raw24 class (AM-SSB-WC/SC both fold to 17)
SOURCE_TO_DEPLOYED23 = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 17, 18, 19, 20, 21, 22,
)
DEPLOYED_LABEL_ORDER_23 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB", "AM-DSB-WC", "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)
DEPLOYED_CLASS_COUNT = 23

# ---------------------------------------------------------------------------
# source_index scheme:  source_index = class_index * 500 + intra_class_offset
# ---------------------------------------------------------------------------
SOURCE_CLASS_PER_INDEX = 500
MAX_INTRA_CLASS_OFFSET = 499  # offsets must stay within one 500-block

# capture plan (Pilot 24x10=240, Formal 24x30=720; disjoint offset ranges)
PILOT_OFFSETS = tuple(range(0, 10))          # 0..9  (10 per class)
FORMAL_OFFSETS = tuple(range(10, 40))        # 10..39 (30 per class)
PILOT_PER_CLASS = len(PILOT_OFFSETS)
FORMAL_PER_CLASS = len(FORMAL_OFFSETS)

# deterministic formal split by intra_class_offset (leak-free by construction)
FORMAL_TRAIN_OFFSETS = tuple(range(10, 28))  # 18/class
FORMAL_VAL_OFFSETS = tuple(range(28, 34))    # 6/class
FORMAL_TEST_OFFSETS = tuple(range(34, 40))   # 6/class
assert (len(FORMAL_TRAIN_OFFSETS) + len(FORMAL_VAL_OFFSETS) +
        len(FORMAL_TEST_OFFSETS)) == FORMAL_PER_CLASS

# ---------------------------------------------------------------------------
# C4 frozen RF capture configuration (verbatim from task book 39e5)
# ---------------------------------------------------------------------------
RF_CONFIG = {
    "center_freq_hz": 2400000000,
    "sample_rate_hz": 2560000,
    "rx_gain": 35,
    "rx_bw_hz": 18000000,
    "tx_bw_hz": 18000000,
    "tx_atten_db": -40,
    "tx_target_rms": 2048,
    "rf_path": "direct-cable",
}

# gate statuses (recovery chain's 0.100 residual gate)
GATE_PASSED = "PASSED"
GATE_DIAGNOSTIC_PROVISIONAL = "DIAGNOSTIC_PROVISIONAL"  # gate-rejected, retained
GATE_REJECTED = "REJECTED"                              # hard-fail, discarded
GATE_STATUSES = (GATE_PASSED, GATE_DIAGNOSTIC_PROVISIONAL, GATE_REJECTED)

# ---------------------------------------------------------------------------
# dataset manifest schema (full field list; see the companion .md)
# ---------------------------------------------------------------------------
MANIFEST_COLUMNS = (
    "sample_id", "source_index", "raw24_class_index", "raw24_label",
    "deployed23_index", "deployed23_label", "modulation",
    "intra_class_offset", "phase", "split_role", "link", "gate_status",
    "payload_training_residual", "corr", "cfo_hz", "wide_linear_ratio",
    "capture_attempts", "capture_session_id", "center_freq_hz",
    "sample_rate_hz", "rx_gain", "rx_bw_hz", "tx_bw_hz", "tx_atten_db",
    "tx_target_rms", "rf_path", "raw_rx_iq_sha256", "model_input_sha256",
    "frozen_raw24_pred",
)

CAPTURE_PLAN_COLUMNS = (
    "plan_id", "phase", "source_index", "raw24_class_index", "raw24_label",
    "modulation", "intra_class_offset", "split_role", "session_requirement",
    "quality_stratum", "gate_policy", "center_freq_hz", "sample_rate_hz",
    "rx_gain", "rx_bw_hz", "tx_bw_hz", "tx_atten_db", "tx_target_rms",
    "rf_path", "notes",
)

# ---------------------------------------------------------------------------
# preregistered pilot training spec (frozen; train/eval scripts import this)
# ---------------------------------------------------------------------------
PILOT_TRAINING_SPEC = {
    "init_from_checkpoint_sha256": FROZEN["fp32_checkpoint_sha256"],
    "candidates": ["classification-head-only", "full-network-low-LR"],
    "optimizer": "AdamW",
    "learning_rates": [1e-5, 3e-5, 1e-4],
    "weight_decay": 0.01,
    "grad_clip_norm": 1.0,
    "lr_schedule": "cosine",
    "warmup_fraction": 0.05,
    "max_epochs": 20,
    "early_stopping_patience": 4,
    "seeds": [17, 29, 43],
    "data_mix": ["real-rf-only", "clean-plus-real-rf-balanced"],
    "per_batch_class_balanced": True,
    "selection": "val-only-never-test",
    "class_count": SOURCE_CLASS_COUNT,
    "input_shape": MODEL_IO["input_shape"],
}


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path) -> str:
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def label_order_sha256() -> str:
    return sha256_bytes(_json_bytes(list(SOURCE_LABEL_ORDER_24)))


def assert_label_order_frozen() -> None:
    actual = label_order_sha256()
    if actual != FROZEN["label_contract_sha256"]:
        raise ValueError(
            f"24-class label order SHA mismatch: {actual} != "
            f"{FROZEN['label_contract_sha256']}"
        )


def source_index_to_class(source_index: int) -> int:
    return source_index // SOURCE_CLASS_PER_INDEX


def source_index_to_offset(source_index: int) -> int:
    return source_index % SOURCE_CLASS_PER_INDEX


def class_offset_to_source_index(class_index: int, offset: int) -> int:
    if not (0 <= class_index < SOURCE_CLASS_COUNT):
        raise ValueError(f"class_index {class_index} out of range [0,{SOURCE_CLASS_COUNT})")
    if not (0 <= offset <= MAX_INTRA_CLASS_OFFSET):
        raise ValueError(f"offset {offset} out of range [0,{MAX_INTRA_CLASS_OFFSET}]")
    return class_index * SOURCE_CLASS_PER_INDEX + offset


def raw24_label(class_index: int) -> str:
    return SOURCE_LABEL_ORDER_24[class_index]


def deployed23_index_of(raw24_class_index: int) -> int:
    return SOURCE_TO_DEPLOYED23[raw24_class_index]


def deployed23_label_of(raw24_class_index: int) -> str:
    return DEPLOYED_LABEL_ORDER_23[deployed23_index_of(raw24_class_index)]


def split_role_of(phase: str, offset: int) -> str:
    """Deterministic split role for a (phase, offset).  Pilot has no train/val/test."""
    if phase == "pilot":
        return "pilot"
    if phase == "formal":
        if offset in FORMAL_TRAIN_OFFSETS:
            return "train"
        if offset in FORMAL_VAL_OFFSETS:
            return "val"
        if offset in FORMAL_TEST_OFFSETS:
            return "test"
    raise ValueError(f"unknown phase {phase!r} / offset {offset}")


def capture_plan_rows():
    """Yield one dict per planned capture slot (960 rows), in a stable order."""
    for phase, offsets in (("pilot", PILOT_OFFSETS), ("formal", FORMAL_OFFSETS)):
        session_req = ">=1 session" if phase == "pilot" else ">=2 sessions"
        for class_index in range(SOURCE_CLASS_COUNT):
            for offset in offsets:
                source_index = class_offset_to_source_index(class_index, offset)
                label = raw24_label(class_index)
                role = split_role_of(phase, offset)
                yield {
                    "plan_id": f"{phase}_{class_index:02d}_{offset:03d}",
                    "phase": phase,
                    "source_index": source_index,
                    "raw24_class_index": class_index,
                    "raw24_label": label,
                    "modulation": label,
                    "intra_class_offset": offset,
                    "split_role": role,
                    "session_requirement": session_req,
                    "quality_stratum": "nominal",
                    "gate_policy": (
                        f"{GATE_PASSED}->keep; {GATE_DIAGNOSTIC_PROVISIONAL}->keep-as-provisional; "
                        f"{GATE_REJECTED}->bounded-retry<=3-then-record"
                    ),
                    "center_freq_hz": RF_CONFIG["center_freq_hz"],
                    "sample_rate_hz": RF_CONFIG["sample_rate_hz"],
                    "rx_gain": RF_CONFIG["rx_gain"],
                    "rx_bw_hz": RF_CONFIG["rx_bw_hz"],
                    "tx_bw_hz": RF_CONFIG["tx_bw_hz"],
                    "tx_atten_db": RF_CONFIG["tx_atten_db"],
                    "tx_target_rms": RF_CONFIG["tx_target_rms"],
                    "rf_path": RF_CONFIG["rf_path"],
                    "notes": (
                        "WC/SC both map deployed23=17 (AM-SSB)"
                        if label in ("AM-SSB-WC", "AM-SSB-SC")
                        else ""
                    ),
                }


def all_source_indices() -> list:
    """All 960 planned source_indices, in capture-plan order."""
    return [r["source_index"] for r in capture_plan_rows()]


def assert_split_is_leakfree() -> None:
    """Fail closed if any two splits share a source_index (i.e. a physical capture)."""
    seen = {}
    for row in capture_plan_rows():
        role = row["split_role"]
        si = row["source_index"]
        if si in seen and seen[si] != role:
            raise AssertionError(
                f"source_index {si} appears in two splits: {seen[si]} and {role}"
            )
        seen[si] = role
    # pilot vs formal offset ranges must be disjoint
    assert set(PILOT_OFFSETS).isdisjoint(set(FORMAL_OFFSETS))
    # train/val/test offsets must be pairwise disjoint and cover formal
    assert set(FORMAL_TRAIN_OFFSETS).isdisjoint(set(FORMAL_VAL_OFFSETS))
    assert set(FORMAL_TRAIN_OFFSETS).isdisjoint(set(FORMAL_TEST_OFFSETS))
    assert set(FORMAL_VAL_OFFSETS).isdisjoint(set(FORMAL_TEST_OFFSETS))
    assert set(FORMAL_OFFSETS) == (
        set(FORMAL_TRAIN_OFFSETS) | set(FORMAL_VAL_OFFSETS) | set(FORMAL_TEST_OFFSETS)
    )


# ---------------------------------------------------------------------------
# minimal YAML emit/load for the flat training-config shape (no yaml dependency)
# ---------------------------------------------------------------------------
def yaml_dump_simple(obj, indent: int = 0) -> str:
    """Serialize a dict of scalars / lists-of-scalars to a readable YAML subset."""
    lines = []
    pad = "  " * indent
    for key, value in obj.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
            lines.append(f"{pad}{key}: {value}")
        elif value is None:
            lines.append(f"{pad}{key}: null")
        elif isinstance(value, (int, float)):
            lines.append(f"{pad}{key}: {value}")
        elif isinstance(value, str):
            lines.append(f"{pad}{key}: {value}")
        elif isinstance(value, (list, tuple)):
            items = [str(v) for v in value]
            lines.append(f"{pad}{key}: [{', '.join(items)}]")
        elif isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.append(yaml_dump_simple(value, indent + 1))
        else:
            raise TypeError(f"cannot serialize {type(value).__name__} for key {key}")
    return "\n".join(lines)


def _scalar(s: str):
    s = s.strip()
    if s == "true":
        return True
    if s == "false":
        return False
    if s == "null":
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def yaml_load_simple(text: str) -> dict:
    """Parse the flat YAML subset produced by yaml_dump_simple."""
    out = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            continue  # nested dicts not used in the config shape
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            items = [_scalar(x) for x in inner.split(",")] if inner else []
            out[key] = items
        else:
            out[key] = _scalar(value)
    return out


def dataset_contract_sha256() -> str:
    """Deterministic SHA of the whole frozen dataset contract (identity stamp)."""
    return sha256_bytes(_json_bytes({
        "label_order": list(SOURCE_LABEL_ORDER_24),
        "source_to_deployed23": list(SOURCE_TO_DEPLOYED23),
        "pilot_offsets": list(PILOT_OFFSETS),
        "formal_offsets": list(FORMAL_OFFSETS),
        "formal_train_offsets": list(FORMAL_TRAIN_OFFSETS),
        "formal_val_offsets": list(FORMAL_VAL_OFFSETS),
        "formal_test_offsets": list(FORMAL_TEST_OFFSETS),
        "rf_config": RF_CONFIG,
        "training_spec": PILOT_TRAINING_SPEC,
        "manifest_columns": list(MANIFEST_COLUMNS),
        "capture_plan_columns": list(CAPTURE_PLAN_COLUMNS),
        "frozen": FROZEN,
    }))


def assert_contract_consistent() -> None:
    assert_label_order_frozen()
    assert len(SOURCE_LABEL_ORDER_24) == SOURCE_CLASS_COUNT
    assert len(SOURCE_TO_DEPLOYED23) == SOURCE_CLASS_COUNT
    assert len(DEPLOYED_LABEL_ORDER_23) == DEPLOYED_CLASS_COUNT
    assert set(SOURCE_TO_DEPLOYED23) == set(range(DEPLOYED_CLASS_COUNT))
    assert SOURCE_TO_DEPLOYED23[17] == 17 and SOURCE_TO_DEPLOYED23[18] == 17
    assert_split_is_leakfree()
    assert len(list(capture_plan_rows())) == 24 * (PILOT_PER_CLASS + FORMAL_PER_CLASS)
    assert len(PILOT_TRAINING_SPEC["seeds"]) == 3
    assert set(PILOT_TRAINING_SPEC["candidates"]) == {
        "classification-head-only", "full-network-low-LR"}


if __name__ == "__main__":
    assert_contract_consistent()
    rows = list(capture_plan_rows())
    print(f"contract_sha256  = {dataset_contract_sha256()}")
    print(f"label_sha256     = {label_order_sha256()}")
    print(f"capture_plan_rows= {len(rows)} (pilot {24*PILOT_PER_CLASS}, formal {24*FORMAL_PER_CLASS})")
    print(f"train/val/test   = {24*len(FORMAL_TRAIN_OFFSETS)}/{24*len(FORMAL_VAL_OFFSETS)}/{24*len(FORMAL_TEST_OFFSETS)}")
