# NPU-only board test package

Self-contained package for the NPU-only on-board test of the frozen
TimePowerPhase RF partition.  Everything here runs on the FMQL30TAI Linux image
(aarch64) against the official iCraft 3.39 runtime.  No bitstream is written,
no QSPI/SD boot is modified, no system package is installed, nothing is
downloaded, and nothing auto-retries.

## Current NPU-only status (honest, not "PASS")

| Mode | Result |
|---|---|
| Single frame 7 (one process) | **PASS** — argmax=0 BPSK, MATCH vs PC reference |
| Frames 7-18, one independent process per frame | **PASS 12/12** — every frame MATCH |
| Frames 7-18, same process (fresh Session + fresh tensors per frame) | **FAIL** — fixed one-frame delay, class_match=2/12 |

The 12/12 independent-process result proves the board, NPU, compiled model,
tensor layout and SInt8→FP32 dequantization are all correct.  The remaining
defect is confined to *same-process* continuous inference: even with a fresh
`Session` per frame, iCraft 3.39 keeps process-/device-level state across
forwards, so a forward returns the previous frame's logits.  This is **not**
a single-session `ready_` short-circuit — the fix must be at device/sync level,
and is localized by the diagnostic experiments below.

## Contents

| File | Purpose |
|---|---|
| `model.json` / `model.raw` | final iCraft ZG330 artifact (`rfnet_npu_ZG`) |
| `expected_tensor_plddr.bin` | frozen 19-frame 5-plane SInt8 FPGA capture (97,280 B) |
| `pc_reference_19frames.json/.csv` | PC reference logits/argmax (PyTorch best.pt) |
| `reference_argmax.txt` | compact `frame_id,argmax_id,argmax_class,ood,gt` for C++ compare |
| `npu_only_smoke.cpp` | NPU-only smoke program (FP32 input, ZG330Backend + HostBackend, fresh Session per frame) |
| `npu_diag.cpp` | diagnostic harness (experiments 0-6) to localize the one-frame delay |
| `CMakeLists.txt` | board build (finds `icraft-zg330backend` + `icraft-hostbackend`, gnu++17); builds both binaries |
| `build_on_board.sh` | cmake + make, builds `npu_only_smoke` + `npu_diag` |
| `run_frame7.sh` | single frame 7 (first meaningful: BPSK +20 dB) |
| `run_process_baseline.sh` | correctness baseline: 12/12 via one process per frame |
| `run_diagnostic.sh` | runs `npu_diag` experiments 0-6, saves logs, prints summary table |
| `sha256_manifest.txt` | SHA-256 of every file above |

## Compiled contract (the reason the adapter dequantizes)

The compiled network input is **FP32** `[1,2,1024]` (iq) + `[1,3,1024]`
(physical_features); output is **FP32** `[1,8]`.  The FPGA emits SInt8, so the
smoke program dequantizes with the frozen reference on the host:

```
iq_fp32        = iq_int8        * (1/127)
physical_fp32  = physical_int8  * (2/127)
```

The NPU then re-quantizes internally with its own learned scales.  This host
dequantization is a pure adapter step; it does not touch the Mandatory Core or
Golden.  The raw SInt8 tensor is preserved byte-for-byte in
`expected_tensor_plddr.bin` for a bit-exact check.

## Diagnostic experiments (one variable each)

| Exp | Change vs baseline | Official API used |
|---|---|---|
| 0 | single Session reused across all frames | `Session::Create`, `apply`, `forward` |
| 1 | fresh Session + fresh tensors per frame (current scheme) | `Session::Create` per frame |
| 2 | Network re-created from JSON + raw per frame | `Network::CreateFromJsonFile` + `lazyLoadParamsFromFile` |
| 3 | fresh host device per frame | `HostDevice::Init()` |
| 4 | Device closed + reopened per frame (session destroyed before Close) | `Device::Open` / `Device::Close` |
| 5 | two pre-created Sessions alternated | `Session::Create` x2, `forward` alternating |
| 6 | log-only: `layerCount()` before/after forward | `Device::cast<ZG330Device>()` + `layerCount()` (read-only) |

**Forbidden (never called):** `setOpWait()`, `Device::reset()` with unconfirmed
level, `clearMMUCache()`, `icoreCalc()`, `FPGA_STATE_CLEAR_REG`,
`FPGA_RESET_REG`, `EXHS_ACK/VLD`, and any `/dev/mem` register write.  `getOpWait()`
is also not read because its `reg_idx` semantics are unconfirmed.  Frame indices
are never offset; no frame is dropped and no warm-up frame is inserted.

## Output format and PASS criteria

Per frame (one line):
```
DIAG_FRAME exp=<N> frame=<F> pred=<P> ref=<R> result=<MATCH|MISMATCH|NO_REF|TIMEOUT|ERROR> \
delay=<y|n|-> setup=<ms> forward=<ms> wait=<OK|TIMEOUT|ERR> rc=<0|1> [layer_b=.. layer_a=..] [err=..]
```

Per experiment summary:
```
DIAG exp=<N> match=X/12 delay_shift=Y/11 timeout=Z error=E
DIAG_RESULT=PASS|FAIL
```

A scored experiment passes **only** when all of:
`match=12/12`, `delay_shift=0/11`, `timeout=0`, `error=0`.

Passing by dropping the first frame, shifting the result stream, or adding a
fake warm-up frame is explicitly disallowed.  Experiment 6 is log-only and is
never scored.

## Run order

```sh
# 1. confirm the bitstream is loaded (outside this package)
# 2. verify the package: sha256sum -c sha256_manifest.txt
# 3. build both programs (npu_only_smoke + npu_diag)
./build_on_board.sh

# 4. first meaningful single-frame test (frame 7, NOT frame 0)
./run_frame7.sh

# 5. correctness baseline: 12/12 via one process per frame
./run_process_baseline.sh

# 6. localize the same-process one-frame delay (read-only)
./run_diagnostic.sh     # full logs in diag_logs/exp{0..6}.log
```

Expected success: `run_frame7.sh` prints `argmax=0 class=BPSK` and
`reference_argmax=0 (BPSK) MATCH`; `run_process_baseline.sh` prints
`BASELINE_RESULT=PASS (12/12, one process per frame)` and exits 0.
`run_diagnostic.sh` prints one `DIAG exp=N ...` line per experiment plus a
`DIAG_RESULT=` verdict; the experiment that clears the delay is the one that
reaches `DIAG_RESULT=PASS`.

Frames 0-6 are OOD/degenerate; they are not part of any continuous run.
