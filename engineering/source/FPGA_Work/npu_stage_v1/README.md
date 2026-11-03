# NPU-stage v1 — pre-board preparation (complete) + board execution order

This directory holds everything needed to run the **first NPU-only on-board
test** of the frozen TimePowerPhase RF partition on FMQL30TAI (ZG330).

All preparation is done. The remaining work is the board run itself, in the
fixed order below.

## What is frozen (do not modify)

1. Six Mandatory Core RTL (never edited)
2. `AI_Mate.edif`, Golden, FMSH patch (never edited)
3. `best.pt`, original ONNX, current tensor values/layout, verified hardware capture
4. The FPGA Mandatory Core output contract: SInt8, 5-plane per frame
   (I, Q, power, lag1_real, lag1_imag), 19 frames x 5,120 B = 97,280 B
5. Dequantization reference: iq x 1/127, physical x 2/127 (symmetric, z=0)

## Compile & reference summary

| Artifact | Location | Status |
|---|---|---|
| iCraft 3.39 compile | `compile/` (parse→optimize→quantize→adapt→generate) | PASS, all 5 stages |
| Final ZG330 model | `compile/jsonraw/rfnet_npu_ZG.{json,raw}` | SHA-256 in `compile/compile_report.md` |
| Compiled-model gate (13 items) | `compiled_model_gate/` | PASS |
| PC reference (19 frames) | `reference/pc_reference_19frames.{json,csv}` | generated (PyTorch best.pt) |
| NPU smoke program | `npu_program/npu_only_smoke.cpp` | FP32 input, ZG330Backend + HostBackend, fresh Session per frame |
| NPU diagnostic harness | `npu_program/npu_diag.cpp` | experiments 0-5 to localize the same-process one-frame delay |
| Board package | `board_package/` | 12 files, self-contained |

### Key contract finding

The compiled ZG330 network takes **FP32** inputs (`iq [1,2,1024]`,
`physical_features [1,3,1024]`) and outputs **FP32** `logits [1,8]`; it
quantizes to SInt8 *inside* the NPU (iq scale 0.0071911365, physical
0.011158751).  The host adapter therefore dequantizes the FPGA SInt8 with the
frozen reference (x 1/127, x 2/127) before feeding the NPU.  This is a pure
host-side adapter step — no Mandatory Core / Golden change.

## Board execution order (11 steps)

The next session is **only** the board run. Do not re-run any preparation step.

1. **Connect the board.** Power, JTAG, UART, and SD/network as used in the
   previously PASSed PL-DDR + Mandatory Core big-loop test.
2. **Confirm the bitstream** is the already-verified PL-DDR + Mandatory Core
   image (not a new build). Do not regenerate it.
3. **Confirm the iCraft 3.39 runtime** is present on the board Linux image
   (`/usr/cmake/icraft-zg330backend*.cmake` and the ZG330 device driver).
4. **Copy `board_package/` to the board.** Do not auto-write QSPI or modify SD
   boot; a plain file copy into a writable filesystem is the only transfer.
5. **Verify the package** on the board: `sha256sum -c sha256_manifest.txt`.
6. **Build on the board**: `./build_on_board.sh` (cmake + make, gnu++17).
7. **Single-frame inference**: `./run_frame7.sh` — frame 7 (BPSK +20 dB), the
   *first meaningful* case. Frame 0 is OOD/degenerate and is not used.
8. **Check single-frame result**: `argmax=0 class=BPSK`, and
   `reference_argmax=0 (BPSK) MATCH`. Any error → stop and report.
9. **Correctness baseline (frames 7-18)**: `./run_process_baseline.sh` — one
   independent process per frame, aggregate 12 return codes + MATCH, exit 0
   only if 12/12. **This is the correctness baseline only, NOT the real-time
   path.** Same-process continuous inference still shows a fixed one-frame
   delay (see `run_diagnostic.sh` for the localization experiments).
10. **Compare vs PC reference**: class-match is reported for valid frames
    (7-18) only; frames 0-6 are OOD (logits recorded, not scored).
11. **Record and save** board console output, timing, and any log under
    `board_package/` (do not overwrite the SHA-256 manifest or the model files).

## Known item — 1 GHz BUFG Min-Period (preserved, not waived)

The existing FPGA implementation carries one known timing item that is
**intentionally left as-is** in this NPU stage:

```
BUFG 1 GHz min-period path: Required 1.409 ns / Actual 1.000 ns / Slack -0.409 ns
```

No waiver, no false path, no `AI_Mate.edif` change, and no downclock are applied
for it. It is recorded here so the NPU board run is not blocked by it.
