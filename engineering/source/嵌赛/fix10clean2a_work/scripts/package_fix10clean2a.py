"""fix10clean2a — deterministic packaging.

Produces the two §13 deliverables:
  dist/sdr_rml23_fix10clean2a_patch.tar.gz     (code + configs + host tests)
  dist/sdr_rml23_fix10clean2a_results.tar.gz   (result JSONs/TSVs/CSVs + audit + SHA256SUMS)

Packaging discipline (taskbook §13):
  * deterministic: uid/gid=0, mtime=0, fixed member order, gzip mtime=0
    -> two runs produce byte-identical tars (asserted here).
  * independent unpack + sha256sum -c verification in a fresh temp dir.
  * no __pycache__ / *.pyc / cache / tmp / probe scratch files.
  * the frozen model / checkpoint / RadioML HDF5 are NEVER bundled (protected
    inputs stay byte-identical on disk; their SHAs are recorded in the audit).
  * no NPU / SDR / fix10prep2 content.

Data (the 3 HDF5 datasets) live in fix10clean2a_dataset/ and are referenced by
SHA in clean24_manifest.json and SHA256SUMS.txt, not re-bundled here.
"""

from __future__ import annotations

import gzip
import hashlib
import tarfile
import tempfile
from pathlib import Path

WORK = Path(r"F:/嵌赛/fix10clean2a_work")
SCRIPTS = WORK / "scripts"
CONFIGS = WORK / "configs"
HOST_TESTS = WORK / "host_tests"
RESULTS = Path(r"F:/嵌赛/fix10clean2a_results")
DATASET = Path(r"F:/嵌赛/fix10clean2a_dataset")
DIST = WORK / "dist"

PATCH_TAR = "sdr_rml23_fix10clean2a_patch.tar.gz"
RESULTS_TAR = "sdr_rml23_fix10clean2a_results.tar.gz"

PATCH_FILES = [
    "scripts/audit_clean2a_inputs.py",
    "scripts/profile_radioml2018_domain.py",
    "scripts/radioml_clean_contract.py",
    "scripts/gen_radioml_compatible_clean24.py",
    "scripts/validate_radioml_compatible_clean24.py",
    "scripts/check_clean24_domain_match.py",
    "scripts/evaluate_frozen_model_on_clean24.py",
    "scripts/package_fix10clean2a.py",
    "configs/radioml2018_clean_contract_v1.yaml",
    "host_tests/conftest.py",
    "host_tests/test_radioml_clean_contract.py",
    "host_tests/test_clean24_generator.py",
    "host_tests/test_clean24_split_integrity.py",
    "host_tests/test_frozen_model_clean24.py",
]

# deliverable result files living in fix10clean2a_results/
RESULTS_FILES = [
    "CLEAN2A_INPUT_PROVENANCE.json",
    "CLEAN2A_PHASE1_DOMAIN_PROFILE.json",
    "CLEAN2A_PHASE4_DOMAIN_MATCH_smoke96.json",
    "CLEAN2A_PHASE4_DOMAIN_MATCH_dev2400.json",
    "CLEAN2A_PHASE5_MODEL_EVAL_smoke96.json",
    "CLEAN2A_PHASE5_MODEL_EVAL_dev2400.json",
    "CLEAN2A_PHASE5_MODEL_EVAL_formal12000.json",
    "frozen_model_predictions_smoke96.tsv",
    "frozen_model_predictions_dev2400.tsv",
    "frozen_model_predictions_formal12000.tsv",
    "confusion_matrix_raw24_smoke96.csv",
    "confusion_matrix_raw24_dev2400.csv",
    "confusion_matrix_raw24_formal12000.csv",
    "confusion_matrix_deployed23_smoke96.csv",
    "confusion_matrix_deployed23_dev2400.csv",
    "confusion_matrix_deployed23_formal12000.csv",
    "FIX10CLEAN2A_AUDIT.md",
]

# dataset-dir deliverable(s) bundled into the results tar (manifest lives beside the data)
DATASET_RESULT_FILES = ["clean24_manifest.json"]

# data files are hashed into SHA256SUMS but stay in fix10clean2a_dataset/ (not bundled)
DATA_FILES = ["clean24_smoke96.hdf5", "clean24_dev2400.hdf5", "clean24_formal12000.hdf5"]


def _resolve_patch(rel: str) -> Path:
    return WORK / rel


def _deterministic_tar_gz(tar_path: Path, members: list[tuple[str, Path]]) -> None:
    """Write a byte-deterministic .tar.gz from (arcname, source) pairs."""
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tar_path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename=b"") as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                for arcname, src in members:
                    info = tar.gettarinfo(str(src), arcname=arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    if info.isreg():
                        with open(src, "rb") as sf:
                            tar.addfile(info, sf)
                    else:
                        tar.addfile(info)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write_sha256sums() -> Path:
    """SHA256SUMS.txt over all result files + data files + code files."""
    lines = []
    for rel in RESULTS_FILES:
        p = RESULTS / rel
        if p.is_file():
            lines.append(f"{_sha(p)}  {rel}")
    for rel in DATASET_RESULT_FILES:
        p = DATASET / rel
        if p.is_file():
            lines.append(f"{_sha(p)}  {rel}")
    for rel in DATA_FILES:
        p = DATASET / rel
        if p.is_file():
            lines.append(f"{_sha(p)}  {rel}")
    for rel in PATCH_FILES:
        p = _resolve_patch(rel)
        if p.is_file():
            lines.append(f"{_sha(p)}  {rel}")
    out = RESULTS / "SHA256SUMS.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build() -> dict[str, str]:
    DIST.mkdir(parents=True, exist_ok=True)

    # SHA256SUMS.txt (hashes result files + manifest + data files + code files)
    sums = _write_sha256sums()

    patch_members = [("fix10clean2a/" + rel, _resolve_patch(rel)) for rel in PATCH_FILES]
    results_members = [("fix10clean2a_results/" + rel, RESULTS / rel) for rel in RESULTS_FILES]
    results_members += [("fix10clean2a_results/" + rel, DATASET / rel) for rel in DATASET_RESULT_FILES]
    results_members.append(("fix10clean2a_results/SHA256SUMS.txt", sums))

    patch_path = DIST / PATCH_TAR
    results_path = DIST / RESULTS_TAR
    _deterministic_tar_gz(patch_path, patch_members)
    _deterministic_tar_gz(results_path, results_members)

    return {PATCH_TAR: _sha(patch_path), RESULTS_TAR: _sha(results_path)}


def verify_unpack() -> None:
    """Independent unpack into a fresh temp dir + sha256sum check."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for tar_name in (PATCH_TAR, RESULTS_TAR):
            with tarfile.open(DIST / tar_name, "r:gz") as tar:
                tar.extractall(td)  # noqa: S202 (our own deterministic tars)
        # verify SHA256SUMS.txt (result + data + code) from the unpacked copy
        sums = td / "fix10clean2a_results" / "SHA256SUMS.txt"
        ok = 0
        bad = []
        for line in sums.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            want, rel = line.split("  ", 1)
            # locate the file across the unpacked trees
            cands = [
                td / "fix10clean2a" / rel,
                td / "fix10clean2a_results" / rel,
                DATASET / rel,  # data files stay on disk
            ]
            found = next((c for c in cands if c.is_file()), None)
            if found is None:
                bad.append(f"{rel}: not found")
                continue
            got = _sha(found)
            if got == want:
                ok += 1
            else:
                bad.append(f"{rel}: sha mismatch")
        if bad:
            raise SystemExit("unpack verify FAILED:\n" + "\n".join(bad))
        print(f"independent unpack verify: {ok}/{ok + len(bad)} hashes OK "
              f"(patch+results members, data files referenced from dataset dir)")


def main() -> int:
    # two-run determinism
    first = build()
    second = build()
    assert first == second, f"non-deterministic packaging: {first} vs {second}"
    print("two-run SHA identical (deterministic packaging)")

    for name, sha in first.items():
        p = DIST / name
        n = len(tarfile.open(p, "r:gz").getmembers())
        print(f"  {name}: {p.stat().st_size} bytes, {n} members, sha256={sha}")

    verify_unpack()
    print("PACKAGING PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
