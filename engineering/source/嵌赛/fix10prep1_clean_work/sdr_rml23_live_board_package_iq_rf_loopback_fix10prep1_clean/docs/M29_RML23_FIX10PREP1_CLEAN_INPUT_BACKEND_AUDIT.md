# M29 RML23 fix10prep1 — clean-input/backend diagnostic audit

## Purpose and status ceiling

This patch repairs the generated-clean diagnostic path and turns it into a
fail-closed deployment-consistency test.  It does **not** retrain or modify the
model, weights, preprocessing, labels, RF recovery, or the C++ 24-to-23 merge.

Highest permitted state after host verification:

`M29-RML23-FIX10-CLEAN-INPUT-BACKEND-DIAGNOSTIC-READY-FOR-BOARD-TEST`

Board execution is still required.  Host success is not an accuracy result and
does not prove the NPU model domain.

## Confirmed defects repaired

1. The Python baseline producer converted `argmax(logits24)` through a class
   lookup.  This is not equivalent to the deployed C++ merge: raw classes 17
   and 18 must first be combined with `logaddexp`, then the 23-way argmax is
   taken.  The producer now mirrors `rml23_merged.hpp` and fails on non-finite
   logits.
2. The old runtime returned process success whenever `scored > 0`, even with
   prediction disagreement.  The gate now requires every holdout row to be
   scored, zero exclusions, complete baseline identity, complete tensor/logit
   evidence, and prediction agreement for every scored sample.
3. The clean generator routed raw24 class 22 (GMSK) to the OQPSK generator.
   Class 22 now uses `_gmsk_signal`; class 23 alone uses `_oqpsk_signal`.  A
   deterministic constant-envelope/distinct-waveform regression test prevents
   recurrence.
4. Generated-clean manifests left `original_sha256` empty, which is rejected
   by the cumulative h5 loader.  It is now the SHA-256 of canonical little-
   endian complex64 samples before D2 quantization.  Quantized CI16 and recovered
   tensor identities remain separately recorded.

## Evidence boundary

For each accepted sample, the board writes before inference:

- exactly 8192 bytes: `[2,1024]` float32 NPU input tensor;
- exactly 96 bytes: 24 float32 NPU output logits;
- SHA-256 for both files;
- tensor reference SHA, equality, max absolute error, and RMS error;
- raw24 top-1 plus merged23 top-1/top-2/margin.

Writes use a same-directory temporary file, flush/close checks, and atomic
rename.  A short tensor, short logits vector, NaN/Inf, failed write, missing
baseline key, incomplete scoring, any exclusion, or any prediction mismatch is
fatal.

`scripts/analyze_clean_board_tensor_backend.py` replays the exact board-dumped
tensor through the frozen PyTorch checkpoint and emits one diagnosis:

- `PYTORCH_NPU_BACKEND_DIVERGENCE`
- `BASELINE_MERGE_CONTRACT_ERROR`
- `BASELINE_INPUT_DOMAIN_MISMATCH`
- `FULL_DEPLOYMENT_AGREEMENT`

Thus the previous 22/24 observation is not labeled a model defect by guesswork.
The two mismatches (clean sample 9 and 21) are classified only after comparing
the same tensor through both backends.

## Dataset identity

Regenerate the deterministic generated-clean set with the repaired generator;
do not combine rows from the earlier GMSK/OQPSK-corrupted manifest.  The
generator freezes the seed, modulation algorithms, D2 parameters, and all
three identities (`original`, quantized CI16, recovered tensor).  The baseline
must be regenerated from that exact manifest and tensor directory.

## Board acceptance

The clean diagnostic passes only when:

- `baseline_identity_ok=1`;
- `scored == holdout` and `excluded=0`;
- `prediction_agreement == scored`;
- `tensor_dumps == scored` and `logit_dumps == scored`;
- final token is `ROUTE_F_FIX10_CLEAN_IQ_DIAGNOSTIC_PASS`;
- `GATE_RESULT ... result=PASS`.

The printed model-domain token remains
`ROUTE_F_FIX10_CLEAN_IQ_MODEL_DOMAIN_NOT_PROVEN` until the exact tensor/backend
comparison has been performed.  Label accuracy is reported but is not used to
hide a deployment-consistency failure.

## Host verification

- generated-clean self-test: 8/8;
- Python baseline/merge self-test: 9/9;
- tensor/backend analyzer self-test: 4/4;
- clean C++ host test: 35/0;
- cumulative h5 host suite: all passed;
- Gate 7/9/10 and RML23 Gate 9 syntax checks: passed.

