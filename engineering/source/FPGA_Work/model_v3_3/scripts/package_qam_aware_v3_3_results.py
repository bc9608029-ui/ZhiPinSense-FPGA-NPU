"""Create a deterministic manifest and portable archive of V3.3 formal results.

The formal results live in a multi-seed layout::

    <formal_root>/
      selected_candidate.yaml
      seeds/seed2026/{checkpoints,tables,onnx,logs,config,SEED_DONE.json}
      seeds/seed2027/...
      seeds/seed2028/...
      aggregate/{v3_3_acceptance.json, aggregate_summary.json, per_seed_summary.json}

The archive is only produced when every seed is complete and the multi-seed gate
has been applied.  The manifest is LF-only so ``sha256sum -c`` works on Linux.
When A0 (frozen V2) won selection, the archive instead packages the
``no_promotion.json`` result (no seeds are expected).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

from training.qam_aware_v3_3_utils import write_text_lf
from training.utils import PROJECT_ROOT

ROOT = PROJECT_ROOT
DEFAULT_FORMAL = "outputs/qam_aware_v3_3/formal"
DEFAULT_MANIFEST = "outputs/qam_aware_v3_3/formal_results_sha256.txt"
DEFAULT_ARCHIVE = "outputs/qam_aware_v3_3/qam_aware_v3_3_formal_results.tar.gz"
DEFAULT_PACKAGE_JSON = "outputs/qam_aware_v3_3/formal_results_package.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _seed_dirs(formal_root: Path) -> list[Path]:
    seeds = formal_root / "seeds"
    if not seeds.is_dir():
        return []
    return sorted(path for path in seeds.iterdir() if path.is_dir())


def _required_files(formal_root: Path) -> list[Path]:
    required = [formal_root / "selected_candidate.yaml"]
    if (formal_root / "aggregate" / "no_promotion.json").is_file():
        required.append(formal_root / "aggregate" / "no_promotion.json")
        return required

    required += [
        formal_root / "aggregate" / "v3_3_acceptance.json",
        formal_root / "aggregate" / "aggregate_summary.json",
        formal_root / "aggregate" / "per_seed_summary.json",
    ]
    for seed in _seed_dirs(formal_root):
        required += [
            seed / "SEED_DONE.json",
            seed / "checkpoints" / "best.pt",
            seed / "checkpoints" / "last.pt",
            seed / "tables" / "evaluation.json",
            seed / "onnx" / "export_report.json",
            seed / "onnx" / "qam_aware_v3_3_e2e_opset17.onnx",
            seed / "onnx" / "qam_aware_v3_3_npu_partition_opset17.onnx",
        ]
    return required


def package_results(
    formal_root: str = DEFAULT_FORMAL,
    manifest_path: str = DEFAULT_MANIFEST,
    archive_path: str = DEFAULT_ARCHIVE,
    package_json_path: str = DEFAULT_PACKAGE_JSON,
) -> dict:
    formal = (ROOT / formal_root).resolve()
    manifest = (ROOT / manifest_path).resolve()
    archive = (ROOT / archive_path).resolve()
    package_json = (ROOT / package_json_path).resolve()

    required = _required_files(formal)
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Cannot package incomplete V3.3 result; missing: {missing}")

    files = sorted(path for path in formal.rglob("*") if path.is_file())
    lines = [f"{sha256(path)}  {path.relative_to(manifest.parent).as_posix()}" for path in files]
    write_text_lf(manifest, "\n".join(lines) + "\n")

    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(formal, arcname=formal.name)
        tar.add(manifest, arcname=manifest.name)

    report = {
        "seeds": [path.name for path in _seed_dirs(formal)],
        "formal_files": len(files),
        "archive": str(archive.relative_to(ROOT)),
        "archive_sha256": sha256(archive),
        "manifest": str(manifest.relative_to(ROOT)),
    }
    write_text_lf(package_json, json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-root", default=DEFAULT_FORMAL)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--archive", default=DEFAULT_ARCHIVE)
    parser.add_argument("--package-json", default=DEFAULT_PACKAGE_JSON)
    args = parser.parse_args()
    print(json.dumps(package_results(args.formal_root, args.manifest, args.archive, args.package_json), indent=2))


if __name__ == "__main__":
    main()
