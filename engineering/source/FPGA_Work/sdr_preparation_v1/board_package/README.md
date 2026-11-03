# continuous_joint_stress — board package

Continuous **joint** stress program for the FMQL30TAI + ZG330 NPU: it runs the
already-board-PASS FPGA path and NPU path back-to-back in one process on **one
persistent Device**, to prove that the two can share a single Device lifetime
and that `Device::reset(1)` does not disturb the PL-DDR / Mandatory Core path
between cycles. This is the last offline deliverable before the SDR arrives; it
does **not** touch the SDR itself.

## What one cycle does

```
fixed IQ (iq_input.bin, loop replay)
  -> Linux MemChunk (dynamic PL-DDR address, 64 B aligned)
  -> PL DDR -> FPGA Mandatory Core (START + poll DONE)
  -> 97280 B 5-plane SInt8 tensor read back
  -> byte-compare vs expected_tensor_plddr.bin   (mismatch != 0 => FAIL)
  -> NPU inference on frames 7..18               (Device::reset(1) re-arm)
  -> argmax vs reference_argmax.txt
  -> next cycle
```

Per cycle: 19 FPGA frames + 19 tensor Golden compares + 12 NPU inferences.

## Device / Session / memory lifetime (the point of this program)

- `Device::Open` — once, before the loop.
- `defaultMemRegion().malloc(175104, false, 64)` — once; the same chunk is reused
  every cycle (address is written into `IQ_BASE` / `TENSOR_BASE` each cycle).
- `Network::CreateFromJsonFile` + `lazyLoadParamsFromFile` — once.
- `Session::Create<ZG330Backend, HostBackend>` + `apply()` — once.
- `Device::reset(1)` — before every NPU frame except the global first, to re-arm
  the FPGA completion state (board-confirmed in `npu_realtime_v1`).
- `MemChunk::free` then `Device::Close` — once, at the end, RAII-guarded on every
  path.

There is **no** per-frame or per-cycle `Device` reopen and **no** repeated
`Session::apply()`.

## Files

| File | Role |
|------|------|
| `continuous_joint_stress.cpp` | Main program (FPGA + NPU on one Device). |
| `iq_source.hpp` / `iq_source.cpp` | IQ source contract + `SdrIqSource` placeholder (throws; SDR unspecified). |
| `file_iq_source.cpp` | `FileIqSource`: replays the frozen IQ byte-exactly. |
| `pl_ddr_register_map.hpp` | Verified PL-DDR register map (`VERSION=0x20260929`). |
| `CMakeLists.txt` | gnu++17; links `Icraft::ZG330Backend Icraft::HostBackend pthread dl`. |
| `build_on_board.sh` | Board-side build. |
| `run_smoke.sh` / `run_basic.sh` / `run_stress.sh` | 1 / 10 / 100 cycles. |
| `model.json`, `model.raw` | Compiled model (unchanged, frozen). |
| `iq_input.bin` | Frozen IQ (77824 B, 19 × 1024 complex int16). |
| `expected_tensor_plddr.bin` | Frozen Golden tensor capture (97280 B). |
| `reference_argmax.txt` | Frozen reference argmax per frame. |

## Build and run (on the board, aarch64 Linux)

```sh
./build_on_board.sh
./run_smoke.sh     # 1 cycle   (quick correctness)
./run_basic.sh     # 10 cycles (stability)
./run_stress.sh    # 100 cycles (full stress)
```

Or directly:

```sh
./build/continuous_joint_stress \
    --model model.json --raw model.raw \
    --iq iq_input.bin \
    --expected-tensor expected_tensor_plddr.bin \
    --reference reference_argmax.txt \
    --reg-base 0x400C0000 --first 7 --last 18 --cycles 100
```

## PASS rules (`STRESS_RESULT=PASS`)

1. Every cycle's tensor byte-compare vs Golden = **0 mismatch**.
2. Every NPU frame (7..18) argmax **matches** `reference_argmax.txt`.
3. No stale / drop / duplicate / reorder signature: delay shift = 0.
4. `timeout = 0`, `error = 0`.
5. `Device::reset(1)` does not break the next PL-DDR / Core cycle: every
   `version_pre` / `version_post` VERSION read = `0x20260929`, `version_fail = 0`.
6. `Device::Open` happens once (one `STRESS_SETUP` line), all `cycles` complete.

## Output lines

- `STRESS_SETUP` — one line: device open, chunk/tensor address, VERSION.
- `STRESS_CYCLE id=.. version_pre=.. fpga_status=.. iq_accepted=.. tensor_accepted=.. mismatch=.. fpga_ms=..`
- `STRESS_NPU cycle=.. frame=.. pred=..(..) ref=..(..) result=.. delay=.. forward=..`
- `STRESS_VHEALTH id=.. version_changed=..` (only if a VERSION read changed).
- `STRESS_SUMMARY` / `STRESS_THROUGHPUT` / `STRESS_RESULT=PASS|FAIL`.

## Constraints respected

No private FPGA registers, no `setOpWait`/`getOpWait`, no `clearMMUCache`, no
`icoreCalc`, no `/dev/mem`, no new driver, no frame drop/shift/warm-up, no
hardcoded DDR address, and no model / tensor / Golden / bitstream / RTL change.
