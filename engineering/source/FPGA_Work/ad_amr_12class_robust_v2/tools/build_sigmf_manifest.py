#!/usr/bin/env python3
"""Build a SigMF manifest for the 12-class real-RF capture dataset.

Scans a directory tree for ``*.sigmf-meta`` files, pairs each with its
``*.sigmf-data`` sibling, computes SHA-256 for both, extracts the required
AMR-12 metadata fields, and writes a deterministic JSON manifest.

Fail-closed: any meta without a paired data file, or any record missing a
required field, aborts with a non-zero exit.

Usage:
    python3 tools/build_sigmf_manifest.py --root <DIR> [--out manifest.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# --- Required AMR-12 extension fields (must be present in ``global``) ---
# These mirror docs/REAL_RF_CAPTURE_PROTOCOL.md.  Standard core: fields are
# read when present; the amr12: fields are the authoritative custom metadata.
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_meta(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or "global" not in payload:
        raise ValueError(f"{path}: SigMF meta must be an object with a 'global' key")
    return payload


def find_pairs(root: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    for meta in sorted(root.rglob("*.sigmf-meta")):
        data = meta.with_suffix("")  # strip ".sigmf-meta" -> base stem + ".sigmf-data"
        data = Path(str(meta)[: -len(".sigmf-meta")] + ".sigmf-data")
        if not data.is_file():
            raise SystemExit(f"FAIL: meta {meta} has no paired data file {data}")
        key = str(meta.resolve())
        if key in seen:
            raise SystemExit(f"FAIL: duplicate meta resolved to same path {meta}")
        seen.add(key)
        pairs.append((meta, data))
    if not pairs:
        raise SystemExit("FAIL: no *.sigmf-meta files found under root")
    return pairs


def build_manifest(root: Path) -> dict:
    entries: list[dict] = []
    total_bytes = 0
    class_counts: dict[str, int] = {name: 0 for name in LABEL_ORDER}
    for meta_path, data_path in find_pairs(root):
        meta = load_meta(meta_path)
        glob = meta["global"]
        missing = [key for key in REQUIRED_GLOBAL_KEYS if key not in glob]
        if missing:
            raise SystemExit(f"FAIL: {meta_path} missing required global keys: {missing}")

        label = str(glob["amr12:label"]).upper()
        label_index = int(glob["amr12:label_index"])
        if label not in LABEL_ORDER:
            raise SystemExit(f"FAIL: {meta_path} unknown label {label!r}")
        if LABEL_ORDER[label_index] != label:
            raise SystemExit(
                f"FAIL: {meta_path} label_index {label_index} does not match label {label!r} "
                f"(expected {LABEL_ORDER[label_index]!r})"
            )

        data_sha = sha256_file(data_path)
        meta_sha = sha256_file(meta_path)
        data_size = data_path.stat().st_size
        total_bytes += data_size
        class_counts[label] += 1

        entries.append({
            "relpath": str(data_path.relative_to(root)),
            "meta_relpath": str(meta_path.relative_to(root)),
            "data_sha256": data_sha,
            "meta_sha256": meta_sha,
            "data_size_bytes": data_size,
            "label": label,
            "label_index": label_index,
            "seed": glob["amr12:seed"],
            "sample_rate": glob["core:sample_rate"],
            "center_freq_hz": glob["core:frequency"],
            "tx_attenuation_db": glob["amr12:tx_attenuation_db"],
            "rx_gain_db": glob["amr12:rx_gain_db"],
            "rec_scale": glob["amr12:rec_scale"],
            "sdr_serial": glob["amr12:sdr_serial"],
            "path_type": glob["amr12:path_type"],
            "distance_m": glob["amr12:distance_m"],
            "bitstream_sha": glob["amr12:bitstream_sha"],
            "software_version": glob["amr12:software_version"],
            "model_sha": glob["amr12:model_sha"],
            "session_id": str(glob["amr12:session_id"]),
            "label_source": glob["amr12:label_source"],
        })

    # Deterministic ordering by data relative path.
    entries.sort(key=lambda entry: entry["relpath"])
    return {
        "schema_version": 1,
        "root": str(root.resolve()),
        "file_count": len(entries),
        "total_data_bytes": total_bytes,
        "class_counts": class_counts,
        "label_order": LABEL_ORDER,
        "files": entries,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build a SigMF manifest for 12-class real-RF data.")
    parser.add_argument("--root", required=True, help="Directory to scan for *.sigmf-meta files")
    parser.add_argument("--out", default=None, help="Output manifest path (default: <root>/manifest.json)")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"FAIL: root is not a directory: {root}", file=sys.stderr)
        return 2

    manifest = build_manifest(root)
    out = Path(args.out) if args.out else root / "manifest.json"
    with out.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"OK: wrote {out}")
    print(f"  files={manifest['file_count']} total_data_bytes={manifest['total_data_bytes']}")
    for name in LABEL_ORDER:
        print(f"  {name}: {manifest['class_counts'][name]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
