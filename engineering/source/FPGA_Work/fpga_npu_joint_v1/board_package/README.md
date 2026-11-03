# FPGA → NPU joint correctness closed-loop — board package

Self-contained package that runs the **full data path in one board program** on
the FMQL30TAI Linux image (aarch64) against the official iCraft 3.39 runtime:

```
frozen IQ (77824 B) → Linux MemChunk → PL DDR → FPGA Mandatory Core
  → 97280 B 5-plane SInt8 tensor → Linux host memory
  → byte-compare vs Golden → per-frame NPU (frames 7..18) → argmax
```

No bitstream is written, no QSPI/SD boot is modified, no system package is
installed, nothing is downloaded, and nothing auto-retries.  The only transfer
is a plain file copy into a writable filesystem.

## What is frozen (do not modify)

1. Six Mandatory Core RTL (never edited)
2. `AI_Mate.edif`, Golden, FMSH patch (never edited)
3. `best.pt`, original ONNX, current tensor values/layout, verified hardware capture
4. FPGA Mandatory Core output contract: SInt8, 5-plane per frame
   (I, Q, power, lag1_real, lag1_imag), 19 frames × 5120 B = 97280 B
5. Dequantization reference: iq × 1/127, physical × 2/127 (symmetric, z=0)

## Contents

| File | Purpose |
|---|---|
| `fpga_npu_joint_smoke.cpp` | the joint smoke program (Phase A + Phase B) |
| `pl_ddr_register_map.hpp` | verified PL-DDR data-path register map (VERSION 0x20260929) |
| `CMakeLists.txt` | board build (finds `icraft-zg330backend` + `icraft-hostbackend`, gnu++17) |
| `build_on_board.sh` | cmake + make, builds `fpga_npu_joint_smoke` |
| `run_joint_test.sh` | runs the joint closed-loop test |
| `iq_input.bin` | frozen IQ input (19 frames × 1024 samples × 4 B = 77824 B) |
| `expected_tensor_plddr.bin` | frozen 19-frame 5-plane SInt8 Golden (97280 B) |
| `model.json` / `model.raw` | final iCraft ZG330 artifact (`rfnet_npu_ZG`) |
| `reference_argmax.txt` | compact `frame_id,argmax_id,argmax_class,ood,ground_truth` |
| `pc_reference_19frames.json/.csv` | PC reference logits/argmax (PyTorch best.pt) |
| `sha256_manifest.txt` | SHA-256 of every file above |

## Reused verified code (not rewritten)

Phase A reuses the board-verified PL-DDR + Mandatory Core data-path smoke
(`pl_ddr_mandatory_core_smoke.cpp`) **verbatim**: `Device::Open` →
`defaultRegRegion()` / `defaultMemRegion().malloc(bytes, false, 64)` → dynamic
physical address from `chunk->begin.addr()` → 64 B alignment asserted in software
and checked by hardware `[5:0]==0` → register configure (IQ_BASE / IQ_BYTES /
TENSOR_BASE / TENSOR_BYTES / FRAME_COUNT) → START → poll DONE/ERROR → read back
tensor via `chunk.read`.  The additions are the byte-compare against
`expected_tensor_plddr.bin` and a `MemChunkGuard` that frees the chunk exactly
once, before `Device::Close`, on every path (normal / timeout / exception).

Phase B reuses the exp4 lifecycle from `npu_diag.cpp`: `Network` created once;
per frame `Device::Open → Session::Create<ZG330Backend,HostBackend> →
forward → waitForReady → read → destroy → Device::Close`, wrapped in an RAII
`DeviceGuard` so the device is closed on every path.  exp4 has been board-run
three times: 12/12 MATCH (frames 7–18), timeout=0, error=0, no one-frame delay
(the earlier `delay_shift=1/11` was a false positive — frames 8 and 9 both
reference 7/OFDM).

## Run order

```sh
# 1. confirm the PL-DDR + Mandatory Core bitstream is loaded (outside this package)
# 2. verify the package: sha256sum -c sha256_manifest.txt
# 3. build
./build_on_board.sh
# 4. run the joint closed-loop test
./run_joint_test.sh
```

## Output format and PASS criteria

Phase A:
```
JOINT_PHASE_A iq_bytes=77824 tensor_bytes=97280 chunk=0x... tensor_addr=0x...
JOINT_PHASE_A fpga_status=0x3 iq_accepted=19456 tensor_accepted=19456
JOINT_PHASE_A tensor_mismatch=0
```
On failure, an extra `JOINT_PHASE_A error=...` / `free_err=...` / `close_err=...`
line identifies the exact fault (exception, `MemChunk::free`, `Device::Close`).

Phase B, one line per frame:
```
JOINT_FRAME frame=7 pred=0(BPSK) ref=0(BPSK) result=MATCH setup=264.3 forward=1.4
```

Summary:
```
JOINT_NPU match=12/12 timeout=0 error=0
JOINT_CORRECTNESS_PASS
REALTIME_NOT_YET_VALIDATED
```

`JOINT_CORRECTNESS_PASS` requires **all** of:
`tensor_mismatch=0`, no Phase A `error`/`free_err`/`close_err`,
`match=12/12`, `timeout=0`, `error=0`.

Any Phase A failure (`tensor_mismatch>0`, an exception, or a `MemChunk::free()` /
`Device::Close()` error) prints `JOINT_STOP phase A failed` and skips the NPU
phase (exit 2).  `REALTIME_NOT_YET_VALIDATED` is **always** printed: Phase B's
exp4 lifecycle is correctness-verified (board-run 3×, 12/12) but is not
real-time, because each frame re-opens the Device/Session (per-frame setup
overhead).

## Forbidden (never called)

`Device::reset()` with unconfirmed level, `setOpWait()`, `clearMMUCache()`,
`icoreCalc()`, private FPGA state registers (STATE_CLEAR / RESET / EXHS_ACK/VLD),
any `/dev/mem` register write.  Frame indices are never offset; no frame is
dropped and no warm-up frame is inserted.
