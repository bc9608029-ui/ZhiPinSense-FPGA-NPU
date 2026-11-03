"""Create a deterministic manifest and portable archive of V3 formal results."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V3_ROOT = ROOT / "outputs" / "qam_aware_v3"
FORMAL_ROOT = V3_ROOT / "formal"
MANIFEST = V3_ROOT / "formal_results_sha256.txt"
ARCHIVE = V3_ROOT / "qam_aware_v3_formal_results.tar.gz"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    required = (
        FORMAL_ROOT / "checkpoints" / "best.pt",
        FORMAL_ROOT / "checkpoints" / "last.pt",
        FORMAL_ROOT / "tables" / "evaluation.json",
        FORMAL_ROOT / "tables" / "v3_acceptance.json",
        FORMAL_ROOT / "onnx" / "qam_aware_v3_e2e_opset17.onnx",
        FORMAL_ROOT / "onnx" / "qam_aware_v3_npu_partition_opset17.onnx",
        FORMAL_ROOT / "onnx" / "export_report.json",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Cannot package incomplete V3 result; missing: {missing}")

    files = sorted(path for path in FORMAL_ROOT.rglob("*") if path.is_file())
    lines = [f"{sha256(path)}  {path.relative_to(V3_ROOT).as_posix()}" for path in files]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with tarfile.open(ARCHIVE, "w:gz") as tar:
        tar.add(FORMAL_ROOT, arcname="formal")
        tar.add(MANIFEST, arcname=MANIFEST.name)

    report = {
        "formal_files": len(files),
        "archive": str(ARCHIVE.relative_to(ROOT)),
        "archive_sha256": sha256(ARCHIVE),
        "manifest": str(MANIFEST.relative_to(ROOT)),
    }
    (V3_ROOT / "formal_results_package.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
