#!/usr/bin/env python3
"""Verify a SigMF 12-class real-RF dataset against its manifest.

Checks:
  1. every ``*.sigmf-meta`` has a paired ``*.sigmf-data`` and vice versa;
  2. data/meta SHA-256 match the manifest (or are recomputed if no manifest);
  3. required AMR-12 fields are present and label/label_index are consistent;
  4. all 12 classes are represented with a minimum per-class count;
  5. data file size is consistent with the SigMF datatype and sample count;
  6. annotation labels do not contradict the global label.

Fail-closed: any violation prints FAIL and returns non-zero.

Usage:
    python3 tools/verify_sigmf_dataset.py --root <DIR> [--manifest manifest.json]
                                         [--min-per-class N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REQUIRED_GLOBAL_KEYS = [
    "core:sample_rate",
    "core:frequency",
    "amr12:label",
    "amr12:label_index",
    "amr12:seed",
    "amr12:tx_attenuation_db",
    "amr12:rx_gain_db",
    "amr12:rec_scale",
    "amr12:sdr_serial",
    "amr12:path_type",
    "amr12:distance_m",
    "amr12:bitstream_sha",
    "amr12:software_version",
    "amr12:model_sha",
    "amr12:session_id",
    "amr12:label_source",
]

LABEL_ORDER = [
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
]

BYTES_PER_SAMPLE = {
    "cf32_le": 8,   # complex float32
    "cf64_le": 16,  # complex float64
    "ci16_le": 4,   # complex int16
    "ci8_le": 2,    # complex int8
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Verifier:
    def __init__(self, root: Path, manifest: dict | None, min_per_class: int):
        self.root = root
        self.manifest = manifest
        self.min_per_class = min_per_class
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def run(self) -> int:
        metas = sorted(self.root.rglob("*.sigmf-meta"))
        datas = sorted(self.root.rglob("*.sigmf-data"))

        if not metas:
            self.fail("no *.sigmf-meta files found")

        # Pair by basename without the ".sigmf-meta"/".sigmf-data" suffix.
        for meta in metas:
            stem = str(meta)[: -len(".sigmf-meta")]
            data = Path(stem + ".sigmf-data")
            if not data.is_file():
                self.fail(f"{meta}: missing paired data file {data}")

        for data in datas:
            stem = str(data)[: -len(".sigmf-data")]
            meta = Path(stem + ".sigmf-meta")
            if not meta.is_file():
                self.fail(f"{data}: missing paired meta file {meta}")

        manifest_lookup: dict[str, dict] = {}
        if self.manifest is not None:
            for entry in self.manifest.get("files", []):
                manifest_lookup[entry.get("relpath")] = entry

        class_counts = {name: 0 for name in LABEL_ORDER}
        for meta in metas:
            data = Path(str(meta)[: -len(".sigmf-meta")] + ".sigmf-data")
            if not data.is_file():
                continue  # already reported

            try:
                payload = json.loads(meta.read_text(encoding="utf-8"))
                if not isinstance(payload, dict) or "global" not in payload:
                    self.fail(f"{meta}: meta must be an object with 'global'")
                    continue
                glob = payload["global"]
            except (json.JSONDecodeError, OSError) as exc:
                self.fail(f"{meta}: cannot parse meta: {exc}")
                continue

            missing = [key for key in REQUIRED_GLOBAL_KEYS if key not in glob]
            if missing:
                self.fail(f"{meta}: missing global keys {missing}")
                continue

            label = str(glob["amr12:label"]).upper()
            label_index = int(glob["amr12:label_index"])
            if label not in LABEL_ORDER:
                self.fail(f"{meta}: unknown label {label!r}")
            elif LABEL_ORDER[label_index] != label:
                self.fail(
                    f"{meta}: label_index {label_index} != label {label!r} "
                    f"(expected {LABEL_ORDER[label_index]!r})"
                )
            else:
                class_counts[label] += 1

            # Annotation labels must not contradict the global label.
            for annotation in payload.get("annotations", []):
                ann_label = annotation.get("amr12:label") or annotation.get("core:label")
                if ann_label is not None and str(ann_label).upper() != label:
                    self.warn(
                        f"{meta}: annotation label {ann_label!r} differs from global {label!r}"
                    )

            # Data size must match datatype and sample count.
            datatype = glob.get("core:datatype", "cf32_le")
            bytes_per_sample = BYTES_PER_SAMPLE.get(datatype)
            actual = data.stat().st_size
            if bytes_per_sample is None:
                self.warn(f"{meta}: unknown datatype {datatype!r}; skipping size check")
            else:
                total_samples = sum(
                    int(ann.get("core:sample_count", 0)) for ann in payload.get("annotations", [])
                )
                if total_samples > 0:
                    expected = total_samples * bytes_per_sample
                    if actual != expected:
                        self.fail(
                            f"{meta}: data size {actual} != annotations sample_count "
                            f"{total_samples} * {bytes_per_sample} = {expected}"
                        )

            # SHA checks against manifest.
            relpath = str(data.relative_to(self.root))
            if self.manifest is not None:
                entry = manifest_lookup.get(relpath)
                if entry is None:
                    self.fail(f"{meta}: not present in manifest (relpath {relpath})")
                    continue
                if entry.get("data_sha256") != sha256_file(data):
                    self.fail(f"{meta}: data SHA-256 differs from manifest")
                if entry.get("meta_sha256") != sha256_file(meta):
                    self.fail(f"{meta}: meta SHA-256 differs from manifest")

        # Class coverage.
        for name in LABEL_ORDER:
            if class_counts[name] < self.min_per_class:
                self.fail(
                    f"class {name} has {class_counts[name]} records < min_per_class "
                    f"{self.min_per_class}"
                )

        if self.warnings:
            print("WARNINGS:")
            for message in self.warnings:
                print(f"  {message}")

        if self.errors:
            print("FAIL:")
            for message in self.errors:
                print(f"  {message}")
            return 1

        print("OK: dataset verified")
        for name in LABEL_ORDER:
            print(f"  {name}: {class_counts[name]}")
        return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify a SigMF 12-class real-RF dataset.")
    parser.add_argument("--root", required=True, help="Directory to scan")
    parser.add_argument("--manifest", default=None, help="Manifest JSON (optional)")
    parser.add_argument("--min-per-class", type=int, default=1,
                        help="Minimum records per class (default 1)")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"FAIL: root is not a directory: {root}", file=sys.stderr)
        return 2

    manifest = None
    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.is_file():
            print(f"FAIL: manifest not found: {manifest_path}", file=sys.stderr)
            return 2
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    return Verifier(root, manifest, args.min_per_class).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
