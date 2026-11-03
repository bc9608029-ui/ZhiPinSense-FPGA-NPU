# R1–R7 recheck: package c908e2c0

Decision: NOT APPROVED for READY yet. This is a bounded recheck, not a request
for a new model, waveform generator, FPGA migration, or RF matrix.

## Verified improvements and checks

- SHA256 c908e2c0ead721d5013b784b9a7ca0a20d724a28c5c36d1dabca30c351563bc6.
- 61943 bytes, 14 archive members, single-layer gzip. All 13 embedded file
  checksums independently matched archived bytes.
- Python simulated-device suite rerun: pass=36 fail=0.
- Actual restore now writes existing attribute .value and verifies readbacks;
  STOPPED false is propagated. Public PC entry point has been renamed.
- Capture is now at least two cyclic frames and the integer timing search includes
  positive offsets. Raw/logit persistence and repeated inference have been added.
- IMPORTANT correction to the delivery summary: actual C++ residual_rel uses
  sqrt(error_energy / received_energy), not the squared expression stated in the
  message. Gain normalization is implemented. It should not be reported as the
  exact unchanged production estimator: the production payload residual divides by
  modeled signal energy. Preserve an explicit mathematical contract/comparison.
- A review-only C++ executable instantiated and ran the full file-mode runner on
  all 24 v2 frames. It did not access libiio or hardware (device factory throws).
  This exposed issues missed by the original helper-only 8-check tests.
- No full board/aarch64 build or real RF was performed.

## Remaining blocking items

### B1: clipping uses the wrong ADC rails and health flags do not gate inference

runner.hpp kClipRail is 32766. The actual adapter read_rx uses channel conversion
and returns signed 12-bit ADC values, approximately [-2048,2047], as documented
and implemented in sdr_adapter/pluto_device_libiio.cpp. Even 100% samples at +2047
produce clip_ratio=0 under the new helper.

recover_and_classify_one records capture_ok and rx_clipped but its `gated`
predicate only uses no_sync, finite coefficients, invertibility and residual.
Thus a valid-looking training block with capture_ok=false or rx_clipped=true can
still invoke NPU inference. Correct the rails using adapter format information
and enforce the agreed capture/clip quality policy in both gate and classification.
Add counterexamples for the real decoded ADC rails and each failed health flag.

### B2: negative-control capture failure can be counted as PASS

The TX-off branch ignores capture_contiguous's return value and continuity/health
results. It sets negative_control_pass only from a low sync score. An empty or
failed capture can therefore resemble no signal and pass. Require a successful,
nonempty, finite, healthy measured window; persist its evidence and refuse the run
when the negative-control measurement fails. Do not treat absence of data as noise.

### B3: full file mode cannot report success; summary records a stale pass value

Observed full-run output:

    FILE_RUN completed=1 processed=24 readback=0 negative=0 functional_pass=0

File mode never sets rx_readback_ok or negative_control_pass, yet the unconditional
final predicate requires both. Represent device-only checks as not-applicable in
file mode and compute the corresponding functional outcome correctly.

Additionally the summary TSV is written BEFORE rep.functional_pass is calculated,
so its pass field contains the initial false value even when device-mode success
would subsequently be computed. Calculate final status before serialization, and
test returned status, stdout and persisted summary for agreement.

### B4: documented commands still do not execute the intended configuration

- PowerShell does not use ^ as a continuation (that is cmd.exe syntax). Use a
  PowerShell argument array or a single-line invocation with the call operator.
- BOARDTEST pre-creates OUT and OUT_FILE, but the runner explicitly refuses any
  existing output directory. The review executable reproduced that rejection.
  Keep logs outside the fresh runner-owned directory until it exists, or provide
  a wrapper that moves the log after execution. Preserve no-overwrite semantics.
- Device command omits --rx-gain=35. The reused scripts/run_gate9_rml23.sh inserts
  --rx-gain=10, overriding the new runner's internal 35 default. Put the explicit
  requested gain in the real invocation and validate requested versus actual values.
- The named build_npu_on_board.sh still executes make -j"$(nproc)"; a single target
  is not a single build job. Supply a genuinely single-thread native build command.
- Preserve/inspect the producer exit code across tee, and stop on failed build/run.

### B5: board judging remains disconnected

The current producer emits 21 columns. The separate v2 board-vs-baseline judger
requires an exact 11-column header, and the fix1 judger accepts only --kind digital.
BOARDTEST now explicitly admits no device-arm judger and only instructs reading
the summary. This does not deliver the previously required independent RF-versus-
digital-baseline comparison and C-layer input verification.

Supply one compatible board-result entry point using the actual 21-column output,
persisted model inputs and frozen v2 baseline. Independently recompute label accuracy,
baseline agreement, coverage, gate and failed/missing count over the fixed 24 sources;
verify recorded tensor SHA and report same-wrong versus new flips without claiming
RF causation. Test the actual producer output, including duplicates, missing rows,
invalid health flags, finite=0 and tampered tensors. No new RF acquisition required.

## Required next step

Fix B1–B5 only, add executable counterexample regressions through the full runner
and actual board-result loader, update docs and rebuild the package/checksums.
Keep the validated model/waveform assets and existing source trees unchanged.
An offline approval means ready for USER native board build/test, not RF_PASS or
proof that the device path has already run on aarch64.
