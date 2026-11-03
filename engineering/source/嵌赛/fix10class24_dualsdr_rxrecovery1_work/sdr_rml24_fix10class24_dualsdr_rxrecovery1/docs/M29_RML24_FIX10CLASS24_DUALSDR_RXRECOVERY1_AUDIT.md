# fix10class24-dualsdr-rxrecovery1 — gated wide-linear IQ compensation + bounded payload-training recapture

**Status:** `M29-RML24-FIX10CLASS24-DUALSDR-RXRECOVERY1-READY-FOR-BOARD-TEST`
**Scope:** two additive capabilities to the dual-SDR RX recovery core (`iqrfrec`). Host
BF16 / API-only. Never touches the board, the SDR, the BF16 model, labels, canonical
assets, or any existing validity gate.

---

## 1. What was added

Two capabilities, both fail-closed and label-free:

1. **Wide-linear IQ compensation** — model the CFO-corrected payload-training block as
   `xc[k] = a*rk[k] + b*conj(rk[k])`, fit `(a, b)` by complex least squares on the FIRST
   HALF (512 samples), validate on the SECOND HALF (512 samples). Enable the compensation
   only when it generalizes (second-half residual < 99% of the same-window scalar fit) and
   the image ratio is physically plausible. Otherwise reject and keep the scalar path
   byte-identical.

2. **Bounded recapture** — for `Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH` only, repeat
   the payload-training capture up to `kPayloadTrainingCaptureMaxAttempts = 3` total
   attempts per source_index (initial + two retries). No other failure retries.

---

## 2. Ambiguity resolutions (the five open questions, now closed)

### A1 — "retry the capture" = full PREPARE→START→CAPTURE→CAPTURED→STOPPED cycle, per source_index

The board cannot re-capture RX without the PC re-emitting the burst (the PC stops TX after
every CAPTURED). So a retry re-runs the complete control-channel cycle for the same
`source_index`/`file_name`/`payload_sha_pre`, bounded by `capture_attempts`.

**This session's key verification** — the PC-side state machine explicitly permits a second
PREPARE for the same sample after CAPTURED→STOPPED:

- `fix10_tx_protocol.py` `PcTxServerSession._dispatch` transitions
  `WAIT_CAPTURED --CAPTURED--> WAIT_PREPARE` and clears `current_sample = None` (lines 460-468).
  There is **no** duplicate/seen-sample guard — `current_sample` merely tracks the in-flight
  PREPARE for the START/CAPTURED identity check.
- `pc_tx_sdr_fix10.py` `on_prepare` → `prepare_from_cache` → `require_cached_burst` is a
  **cache hit** (idempotent), not a one-shot: re-preparing the same sample rebuilds `_current`
  and returns the same `payload_sha_post`/`burst_sha`/`tx_scale`. No "already prepared" rejection.
- `on_start` re-applies the burst config and re-starts cyclic TX; `on_captured` stops + restores.

Therefore the recapture loop wiring is correct as-is. A retry's `send_prepare` cannot fail on
the "same sample" basis, and `control_fatal` is only set on genuine protocol/infra failure.

### A2 — fit reference is the payload-training block, never the payload or a label

`estimate()` step 6.6 fits against `stretched_pt(k)` (SRO-stretched
`iqrftrain::payload_gain_training_complex()`), the deterministic modulated training block
placed immediately before the payload and derived from the exact int16 TX samples
(bit-identical to what was transmitted). It is a known fixed sequence — not payload data,
not a class label, not an expected-payload recovery target. Payload samples and labels never
enter the `(a, b)` fit nor the validation.

### A3 — "existing gates untouched" = the only exception to the recovery-core red line

The recovery core (`iq_rf_sync_recovery.hpp`) is modified **additively**. The red-line
contract "do not change the recovery core's existing behavior" is met by:

- `kPayloadTrainingResidualMax = 0.10` unchanged (asserted by `test_residual_gate_unchanged`).
- The scalar `apply()` path is **byte-identical** to pre-rxrecovery1 when
  `wide_linear_enabled == false` (asserted by `test_clean_capture_rejects_wide_linear`'s
  re-apply byte-identity check).
- Every existing validity gate (training corr/residual, CFO, SRO, clip, negative control)
  is unchanged and still fires exactly as before.

### A4 — wide-linear runs in the same CFO-corrected domain and REPLACES the scalar gain when enabled

The scalar path outputs component-RMS `target_rms/tx_scale` via
`a_inv = (1/mag)/tx_scale * exp(-j*phase)`. The wide-linear inverse
`(conj(a)*xc - b*conj(xc))/(|a|^2-|b|^2)` recovers the native TX reference (RMS σ_native,
which `a`/`b` absorbed). To match the scalar output amplitude the branch multiplies by

```
norm_scale = |a| / (mag * payload_tx_scale)
           = target_rms / (sigma_native * tx_scale)
```

so the model sees an identical amplitude whether or not the compensation is enabled. The
CFO derotation and SRO resample in the wide-linear branch mirror the scalar branch
sample-for-sample (same `src`, same interpolation, same phase ramp), only the gain step
differs. When `wide_linear_enabled` is true the wide-linear path fully replaces the scalar
gain; when false (or the denominator is unsafe) control falls through to the unchanged
scalar path.

This `norm_scale` was the one real bug found and fixed in review: without it the wide-linear
path output the native (un-normalized) reference, breaking the scale contract the model
expects. The corrected scale is exercised by `test_distorted_capture_enables_wide_linear`.

### A5 — the second-half validation is the negative control against noise re-fitting

Fitting `(a, b)` on the first half and measuring the residual on the **unseen** second half
is exactly the "no re-fitting of noise" control: a genuine image term generalizes (second-half
residual drops), while a `(a, b)` that merely fits first-half noise does not. The additional
`physical` gate (`|b| <= |a|` and `|b| > |a|*1e-4`) rejects degenerate/singular fits, and
`wide_linear_fit` returns the zero pair on a singular determinant (rejected fail-closed). A
clean capture therefore never enables the compensation (image ratio < 1e-3 asserted).

---

## 3. Review findings (this task, checked in full)

- **Cramer's rule** in `wide_linear_fit` (normal equations `[S0 conj(S2); S2 S0]·[a;b]=[d0;d1]`,
  `det = S0^2 - |S2|^2`) verified algebraically correct.
- **`should_retry_payload_training_capture`** returns true only for
  `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH` with `0 < completed_attempts < 3` — attempts 1 and 2
  retry, attempt 0 (initial) and 3 (cap) do not. Matches the fix9r2h3 contract exactly.
- **`failure_rf_verdict`** maps `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH -> "RF_DISTORTS_IQ"`; the
  runner's retry predicate additionally requires `should_retry_payload_training_capture(...)`,
  so the `RF_DISTORTS_IQ` verdict alone is never sufficient to retry — only the exact residual
  failure retries.
- **Recapture loop structure** (board runner): negative control runs once per file *outside*
  the loop; the loop re-initializes `rx_int16`/`rx`/`ccr`/CFO vars and `rec_cfg` each attempt;
  CFO aggregation and the CFO/RECOVERY/CAPTURE_ATTEMPTS diagnostics run once per file on the
  final attempt (not per-attempt). Shadowing of the file-scope `rx_int16`/`rx` was removed;
  `rec_cfg` is file-scope so `dump_failed_rx_sample` sees the final attempt's config.
- **Under-indentation** of the step 2-7 body inside the `for(;;)` (body at the `for`'s own
  indent level) was **empirically confirmed** to compile clean under
  `-Wall -Wextra -Werror -Wmisleading-indentation` (g++ 15.2.0): a minimal reproduction
  compiled with rc=0 and ran correctly. `-Wmisleading-indentation` does not fire on a braced
  block body. (This matters because the runner header is board-only and is **not** compiled by
  the host regression — see §4.)

## 4. Evidence

- `host_tests/test_dual_sdr_wide_linear.cpp` — 25 checks, all pass:
  (a) exact `(a,b)` recovery + singular fail-closed; (b) clean capture rejects wide-linear,
  scalar path byte-identical; (c) distorted capture enables wide-linear, wide-linear residual
  < 50% of scalar, second-half validation improved; (d) retry primitive (only
  `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`, attempts 1/2 retry, 0/3 do not, cap == 3); (e) 0.10
  gate unchanged.
- Full host regression `build_host_tests.sh && run_tests.sh`: BUILD_RC=0, RUN_RC=0, ALL HOST
  TESTS PASSED (includes the byte-equality `test_fix10class24_failed_rx_force_classify` and the
  new `test_dual_sdr_wide_linear`).
- Note: `iq_pc_tx_board_rx_24class_bf16_fix10.hpp` is board-only (included only by
  `board_gate9_full_chain_rml23.cpp`); its recapture loop is compile-verified by the §3
  indentation reproduction plus the full structural re-read, not by the host binary build.

## 5. Red lines

No BF16 model JSON/RAW, label order, 24→23 contract, canonical three components,
`0.10` residual gate, training corr/CFO/SRO/clip gates, TX −40 dB ceiling, training or
quantization assets, FPGA bitstream, or NPU model changed. `apply_provisional` in
`host_tools/replay_fix10class24_failed_rx_force_classify.hpp` is untouched. No label,
expected payload, class, or payload truth participates in the fit, the gate, or the retry
decision.

## 6. Board stop point

Run the standard two-sample BPSK/4ASK board smoke first. Only proceed to a full run after
both samples report valid recovery, zero exclusions, and (if `RF_DISTORTS_IQ` is ever seen)
an explicit `FIX10CLASS24_BF16_CAPTURE_RETRY`/`FIX10CLASS24_BF16_CAPTURE_ATTEMPTS` trace
showing attempts <= 3 and a final typed failure.
