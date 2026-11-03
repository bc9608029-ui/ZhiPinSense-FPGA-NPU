import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
failures: list[str] = []

for artifact in manifest["artifacts"]:
    path = Path(artifact["path"])
    if not path.is_file():
        failures.append(f"MISSING {artifact['role']}: {path}")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != artifact["sha256"].lower():
        failures.append(
            f"SHA_MISMATCH {artifact['role']}: expected={artifact['sha256']} actual={actual}"
        )
    else:
        print(f"SHA_OK {artifact['role']} {actual}")

scan_root = Path(manifest["authoritative_paths"]["scan_evidence_root"])
summary = json.loads((scan_root / "FINAL_SCAN_AUTOTEST_SUMMARY.json").read_text(encoding="utf-8"))
expected = manifest["verified_metrics"]["centered_scan"]
if (summary["candidate_scan_correct"], summary["candidate_scan_total"]) != (
    expected["correct"], expected["total"]
):
    failures.append("METRIC_MISMATCH centered scan summary")
else:
    print(f"METRIC_OK centered_scan {expected['correct']}/{expected['total']}")

for name in (
    "fixed_r1_results.json",
    "fixed_r2_results.json",
    "centered_wide_v2_results.json",
    "centered_narrow_v2_results.json",
):
    records = json.loads((scan_root / name).read_text(encoding="utf-8"))["records"]
    seq = sorted({int(row["seq"]) for row in records})
    if len(records) != 240 or seq != list(range(240)):
        failures.append(f"DENOMINATOR_INVALID {name} rows={len(records)} unique={len(seq)}")
    else:
        print(f"DENOMINATOR_OK {name} 240/240 unique seq=0..239")

if failures:
    for failure in failures:
        print(f"FAIL {failure}")
    raise SystemExit(1)

print("FINAL_PC_PREFLIGHT result=PASS board_integration_still_required=1")
