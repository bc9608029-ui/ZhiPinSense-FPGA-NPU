# fix9r2h3 bounded payload-training capture retry

## Board evidence and decision

fix9r2h2 reduced the payload-training residual, but two independent R8 captures
showed a stable BPSK payload scale error of 5.261% and 5.494%, above the unchanged
5% diagnostic limit.  Both samples otherwise had valid recovery, zero exclusions,
and exact frozen-baseline prediction agreement.  The 64-sample/symbol pilot is
therefore rejected because its narrower spectrum no longer represents the BPSK
payload gain closely enough.

The pilot is restored to the fix9r2h1 value of 32 samples/symbol.  In the earlier
46-sample board evidence, its only failures were transient residual crossings at
0.100015, 0.100805, and 0.100978; repeating the affected capture produced 0.065667
and 0.063893.  This supports bounded reacquisition rather than a threshold change.

## Retry contract

- `kPayloadTrainingResidualMax` remains exactly 0.10.
- At most three total capture attempts are allowed per file (initial plus two
  retries).
- A retry is allowed only when the final typed recovery failure is exactly
  `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH` and the folded RF verdict is
  `RF_DISTORTS_IQ`.
- Clip, infrastructure, synchronization, correlation, CFO, SRO, interruption,
  and every other failure are immediately final.
- Retry selection uses no label, prediction, expected payload, modulation class,
  or payload truth.
- Only the final attempt contributes per-file fidelity/classification counters,
  diagnostic waveforms, recovery admission, and model inference.  Earlier failed
  attempts remain visible in transfer/timing instrumentation and are explicitly
  logged by `IQ_RF_LOOPBACK_FIX9R_CAPTURE_RETRY`.

## Red lines

No model, label mapping, preprocessing, NPU binary, FPGA/bitstream, TX ceiling,
frame layout, payload scale contract, synchronization math, or numeric gate is
changed.  fix10 and generated-clean work remain untouched.

## Board stop point

Run the two-sample BPSK/4ASK R8 smoke test first.  Proceed to the 46-sample run
only after R8 reports two valid/scored samples, zero exclusions, prediction
agreement 2/2, payload-training residual at or below 0.10, and payload scale error
at or below 5%.
