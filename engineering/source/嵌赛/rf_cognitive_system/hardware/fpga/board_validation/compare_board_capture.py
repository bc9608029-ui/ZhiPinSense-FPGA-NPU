"""Compare captured Lite-board Mandatory Core output with frozen vectors.

This utility never loads datasets or model predictions.  It accepts CSV rows
captured only on accepted RTL transfers (``valid && ready``) and exits nonzero
on the first contract violation or any element mismatch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PACKAGE_ROOT / "manifest.json"

FEATURE_COLUMNS = ["frame_id", "sample_index", "power", "lag_re", "lag_im"]
TENSOR_COLUMNS = [
    "frame_id",
    "sample_index",
    "buffer_id",
    "iq_i_int8",
    "iq_q_int8",
    "power_int8",
    "lag_re_int8",
    "lag_im_int8",
    "iq_i_addr",
    "iq_q_addr",
    "power_addr",
    "lag_re_addr",
    "lag_im_addr",
]
OPTIONAL_SIDEBANDS = ["frame_start", "frame_done", "frame_error", "irq"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(package_root: Path, relative: str) -> Path:
    path = (package_root / relative).resolve()
    fpga_root = package_root.parent.resolve()
    if fpga_root not in path.parents:
        raise ValueError(f"Package path escapes hardware/fpga: {relative}")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_and_verify_package() -> tuple[dict[str, object], Path]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for key in ("input", "expected", "vector_manifest"):
        item = manifest[key]
        assert isinstance(item, dict)
        path = _resolve(PACKAGE_ROOT, str(item["path"]))
        actual = _sha256(path)
        if actual != str(item["sha256"]).lower():
            raise AssertionError(f"SHA-256 mismatch for {path}: {actual}")
    expected_item = manifest["expected"]
    assert isinstance(expected_item, dict)
    return manifest, _resolve(PACKAGE_ROOT, str(expected_item["path"]))


def _expected_value(row: dict[str, str], column: str) -> int:
    frame_id = int(row["frame_id"])
    sample_index = int(row["sample_index"])
    if column == "buffer_id":
        return frame_id & 1
    if column == "frame_start":
        return int(sample_index == 0)
    if column in {"frame_done", "irq"}:
        return int(sample_index == 1023)
    if column == "frame_error":
        return 0
    return int(row[column])


def _validate_reference(rows: list[dict[str, str]], total_samples: int) -> None:
    if len(rows) != total_samples:
        raise AssertionError(f"Expected {total_samples} reference rows, found {len(rows)}")
    for row_index, row in enumerate(rows):
        expected_frame = row_index // 1024
        expected_sample = row_index % 1024
        if int(row["frame_id"]) != expected_frame or int(row["sample_index"]) != expected_sample:
            raise AssertionError(f"Reference ordering error at row {row_index}")
        if expected_sample == 0 and (int(row["lag_re"]) != 0 or int(row["lag_im"]) != 0):
            raise AssertionError(f"First Lag is not zero in frame {expected_frame}")
        for column in ("iq_i_int8", "iq_q_int8", "power_int8", "lag_re_int8", "lag_im_int8"):
            value = int(row[column])
            if not -127 <= value <= 127:
                raise AssertionError(f"INT8 contract violation row={row_index} {column}={value}")


def _compare_capture(
    capture_path: Path,
    expected: list[dict[str, str]],
    required_columns: list[str],
) -> int:
    actual = _read_csv(capture_path)
    if len(actual) != len(expected):
        raise AssertionError(f"Row count differs: capture={len(actual)}, expected={len(expected)}")
    if not actual:
        raise AssertionError("Capture is empty")
    missing = [column for column in required_columns if column not in actual[0]]
    if missing:
        raise AssertionError(f"Capture is missing columns: {missing}")
    checked_columns = list(required_columns)
    checked_columns.extend(column for column in OPTIONAL_SIDEBANDS if column in actual[0])
    mismatches = 0
    for row_index, (captured, reference) in enumerate(zip(actual, expected, strict=True)):
        for column in checked_columns:
            got = int(captured[column])
            wanted = _expected_value(reference, column)
            if got != wanted:
                mismatches += 1
                if mismatches <= 10:
                    print(
                        f"mismatch row={row_index} column={column} "
                        f"capture={got} expected={wanted}",
                        file=sys.stderr,
                    )
    if mismatches:
        raise AssertionError(f"{mismatches} element mismatches")
    return len(actual) * len(checked_columns)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, help="Raw Power/Lag capture CSV")
    parser.add_argument("--tensor", type=Path, help="Accepted tensor-write capture CSV")
    parser.add_argument("--self-test", action="store_true", help="Verify package hashes and invariants")
    args = parser.parse_args()
    if not args.features and not args.tensor and not args.self_test:
        parser.error("select --self-test and/or provide --features/--tensor")

    try:
        manifest, expected_path = _load_and_verify_package()
        expected = _read_csv(expected_path)
        _validate_reference(expected, int(manifest["total_samples"]))
        checked = 0
        if args.features:
            checked += _compare_capture(args.features, expected, FEATURE_COLUMNS)
        if args.tensor:
            checked += _compare_capture(args.tensor, expected, TENSOR_COLUMNS)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "package": manifest["package_name"],
                    "reference_rows": len(expected),
                    "capture_elements_checked": checked,
                    "final_blind_test_accessed": False,
                },
                indent=2,
            )
        )
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
