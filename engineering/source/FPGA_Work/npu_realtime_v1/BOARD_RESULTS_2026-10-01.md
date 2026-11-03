# ZG330 persistent-Device continuous inference board result

Date: 2026-10-01 (host), board log clock: 2026-03-13

## Outcome

PASS with the documented `Device::reset(1)` re-arm before every frame after
the first.  Each 100-frame sequence invocation opened the Device exactly once
and closed it once.  The frozen model, tensor payload, and reference argmax
files were unchanged.

## Re-arm sweep

- `none`: 2/12, one-frame-stale signature reproduced, FAIL.
- `setready`: 2/12, one-frame-stale signature reproduced, FAIL.
- `reset1`: 12/12, delay shift 0/10, timeout 0, error 0, PASS.
- `reset1_apply`: results correct, but iCraft reports that an applied Session
  cannot be applied again; this mode is not selected.
- `reopen`: 12/12 correctness control, PASS, but about 263 ms per frame.

Selected mechanism: `reset1` (no repeated `Session::apply()`).

## Direct continuous runs

1. 100/100, delay shift 0/90, timeout 0, error 0,
   forward avg/max 0.666/1.052 ms, setup avg/max 0.045/0.123 ms.
2. 100/100, delay shift 0/90, timeout 0, error 0,
   forward avg/max 0.672/1.058 ms, setup avg/max 0.045/0.116 ms.
3. 100/100, delay shift 0/90, timeout 0, error 0,
   forward avg/max 0.673/1.059 ms, setup avg/max 0.045/0.120 ms.

Each sequence log contains exactly one `Device initialization successful`.

## Full-logits stale-output test

- Alternating frame 7 and frame 10, 24 iterations.
- stale = 0
- argmax mismatch = 0
- timeout = 0
- error = 0
- worst logits difference = 0.0000e+00
- forward avg/max = 0.675/0.915 ms
- PASS

The alternating test log contains three Device initializations: two known-good
reopen baselines plus one persistent-Device test instance.

## Board artifacts

- Directory: `/home/work/npu_realtime_v1`
- Executable SHA-256:
  `1c3804d56f6e2da46ce692fcecabcb95300521acdca2fd4db04a427422754773`
- `rt_seq_1.log`:
  `6927bcaf7a091b1de006f41f8887d695558deb48fb009b33a42dcdf70b0ba448`
- `rt_seq_2.log`:
  `9429d681a62694193a42bddfefd2f2ae656503ab4f3d3b9686055e852488fadd`
- `rt_seq_3.log`:
  `1704db7a96221c6eb38041024f8d8604693f3df15dd4c4a42ccd3f165de7992d`
- `rt_alt.log`:
  `9f0af5139183ae1f1cc4b4e7adb26b7f2264b5ee7b3af10fed8cdf12cf3822bd`

## Test-harness compatibility fixes

- Changed the helper argument from `const Device&` to `Device&`, because
  iCraft 3.39 declares `Device::reset(int)` as non-const.
- Excluded adjacent inputs with the same expected class from the argmax-only
  delay heuristic; full-logits alternating validation remains the authoritative
  stale-output check.

No frozen Mandatory Core RTL, Golden data, compiled model, bitstream, EDIF, or
FMSH patch was modified.  No QSPI or SD-card programming was performed.
