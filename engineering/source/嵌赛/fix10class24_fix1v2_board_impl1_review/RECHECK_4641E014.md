# Recheck of 4641e014 delivery

Disposition: previously missing interfaces are now implemented, but independent
comparison still needs two bounded correctness fixes before overall approval.
No recovery, model, waveform, hardware or RF-matrix changes are requested.

## Independently verified

- SHA256 4641e014d37efef4a22f845d9e318c71ee65d972d60b76aafcba45d1fd32d182.
- 75308 bytes, single gzip layer, 15 members; all 14 embedded SHA entries match.
- New judger self-test rerun: 8/8 PASS.
- Actual tensor-file hashing, duplicate rejection at load time, digital prediction
  input and analysis_ok/measurement_valid separation are present in the code.
- This review did not access a board, use an SDR, compile aarch64 or run real RF.

## S1 — end-to-end agreement still excludes missing/invalid classifications

compute_prediction divides by n_comparable=len(present rows), not expected=24.
It also uses board_pred without checking gated, finite, capture_ok, no_sync or clip.
Direct calls with the real v2 manifest/baseline reproduced:

    one missing row:
        n_comparable=23, n_agree=23, agreement_rate=1.0
    one finite=0 and capture_ok=0 row retaining a matching board_pred:
        n_comparable=24, n_agree=24, agreement_rate=1.0

A separate measurement_valid=false does not make an ambiguously named 100%
headline agreement an end-to-end /24 statistic. Preserve both scopes explicitly:

- primary agreement_over_expected = valid matching predictions / 24;
- optional conditional agreement among valid comparable classifications, separately
  named with its denominator;
- missing, rejected and invalid rows stay in expected=24 and are reported separately;
- same-error/new-classification-flip/board-fix counts only use valid predictions;
  do not describe an unclassified -1 as a classified modulation confusion;
- independently output correct/24, coverage, gated accuracy and end-to-end accuracy.

Add regression cases expecting 23/24 when one otherwise-matching row is missing or
nonfinite/unusable. Do not change the RF quality gate to make these tests pass.

## S2 — digital baseline lacks same-source/version identity binding

load_digital_baseline reads class IDs/names, predictions and B tensor SHA, but the
judge checks only class IDs/names against the TX manifest. The baseline has no
source_id/version/model binding, and its model_input_sha256 is not used to establish
the reference identity. Both real v1 and v2 baselines have the same 24 class identities:

    V1_BASELINE_V2_CLASS_IDENTITY_ACCEPTED = True

Thus the correct v2 manifest/summary plus a mistakenly selected v1 baseline is not
rejected by the implemented identity checks. Their predictions differ, so such a
mix-up could be misreported as an RF-related new flip.

Bind each frozen baseline to its exact TX manifest SHA, source_id, conversion
version and frozen model identity, using a verified sidecar/frozen baseline record
or an equivalent explicit trusted mapping. Bind its B tensor SHA records to the
reference artifacts. Do not compare RF C tensor bytes with B bytes in device mode.

Required counterexample: use the real v1 digital baseline with v2 manifest/summary;
reject with analysis_ok=false, measurement_valid=false and an explicit baseline
identity error. The correct v2 combination must remain accepted even though its
digital model baseline has one known classification error.

## Final bounded handoff

Fix S1 and S2 in the judger/identity metadata/tests/docs, rerun the existing cases,
rebuild checksums, and return the package for final review. No new board collection
or learning experiment is necessary to close these two findings.
