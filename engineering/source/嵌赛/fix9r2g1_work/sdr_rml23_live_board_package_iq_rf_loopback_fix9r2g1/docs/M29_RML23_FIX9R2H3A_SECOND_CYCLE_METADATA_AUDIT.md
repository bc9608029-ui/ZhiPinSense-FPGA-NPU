# fix9r2h3a second-cycle diagnostic metadata hotfix

## Board evidence

The fix9r2h3 R8 capture recovered BPSK successfully with `valid=1`, residual
0.081245, no clipping, and an absolute timing offset of 63489.  The cyclic frame
period is 59904, so the full-capture search selected the equivalent preamble in
the second captured period.  All eight waveform slices were saved successfully,
but the legacy fix9r2d metadata check then rejected the capture solely because it
asserted `timing_offset < period`; the runner returned before classification.

That assertion was false: timing is an absolute index in the captured buffer.
The capture is valid whenever the training, payload, and complete frame slices
fit inside the buffer.  `linear_offset` retains the absolute index and
`circular_offset = timing_offset % period` retains the within-period position.

## Minimal correction

`compute_capture_meta()` removes only the false `timing_offset < period`
condition.  All real fail-closed bounds remain: capture SHA must exist, at least
two periods must be present, and training/payload/full-frame ends must be within
the captured buffer.

The host regression now proves that `period + 100` is accepted with linear offset
`period + 100` and circular offset `100`, while a frame whose end exceeds the
capture remains rejected.

No RF recovery math, retry policy, model, threshold, label mapping, FPGA, frame
layout, TX safety setting, or fix10/generated-clean code is changed.
