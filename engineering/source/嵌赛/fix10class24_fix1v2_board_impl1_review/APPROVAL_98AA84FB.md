# Offline delivery review approved — 98aa84fb

Disposition: the scoped S1/S2 findings are closed. The cumulative offline delivery
may return to READY-FOR-BOARD-TEST. This is not an aarch64 build approval, RF_PASS,
accuracy guarantee, production-integration approval, or autonomous-listening test.

Accepted archive:

    fix1v2_board_impl1_PATCH.tar.gz
    SHA256 98aa84fbbb6c4f7f89f43adf05dad6d260acff4bad08708e5d1aabf7b1656c64
    81932 bytes; 16 members; one gzip layer; 15 embedded file digests checked.

Independent rechecks:

- Judger self-test rerun: 13/13 PASS.
- Actual v1/v1 and v2/v2 manifest/baseline identity pairs: accepted.
- Actual v1/v2 and v2/v1 mixed pairs: BASELINE_TSV_SHA_MISMATCH.
- Actual v2 baseline B-layer tensor hashes checked against reference bins: 24/24.
- Same-prediction fixture constructed from the real v2 baseline: agreement 24/24,
  same-error count 1, label correctness 23/24. This is an offline fixture, NOT a new
  board measurement. It retains the known AM-DSB-SC baseline error honestly.
- One missing or nonfinite/unusable otherwise-matching classification: primary
  agreement is 23/24, not 100%; conditional scope is separately named.
- Runner and public recovery headers match the prior 4641e014 package digests:
  runner dfca251de30fefff7835b031dbaf7ab0d90df4af9d5e6780423e46cbaa8b875c;
  recovery 41bb2231d82d2d2334211f37fc9c01441e3cc42169efc077bab38e62abf95e7f.

Required execution boundaries:

1. User performs a native single-thread board build, then file-mode validation,
   before real RF. No board or SDR was accessed during this review.
2. Use v2 inputs, v2 manifest, v2 replay baseline, and the accepted frozen identity
   sidecar together. Keep v1 only as an explicitly separated historical control.
3. For the intended device-mode RF-versus-digital comparison, pass BOTH
   --digital-baseline and --baseline-identity even though the generic device CLI
   allows them to be omitted. Always pass --tensor-dir pointing to the returned
   actual board artifacts. Device C bytes must not be required to equal B bytes.
4. Report true-label accuracy and baseline agreement separately. Baseline is 23/24,
   not a promise that RF must reproduce 24 correct labels.
5. Preserve full output directories and logs. Real RF and aarch64 outcomes remain
   pending until actual user-executed build/run results are returned.
