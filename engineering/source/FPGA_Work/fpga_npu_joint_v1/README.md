# FPGA → NPU joint correctness closed-loop (`fpga_npu_joint_v1`)

This project closes the loop between the FPGA Mandatory Core (PL DDR data path)
and the ZG330 NPU in **one board program**, so the two independently verified
halves are proven correct end-to-end against the frozen Golden and PC reference.

Everything here is **pre-board preparation only**. Nothing has been run on the
board; no bitstream, model, Golden, RTL, EDIF, or FMSH patch has been modified.

## Directory layout

```
fpga_npu_joint_v1/
└── board_package/               # self-contained, board-ready
    ├── fpga_npu_joint_smoke.cpp # the joint smoke program (Phase A + Phase B)
    ├── pl_ddr_register_map.hpp  # verified register map (VERSION 0x20260929)
    ├── CMakeLists.txt
    ├── build_on_board.sh
    ├── run_joint_test.sh
    ├── README.md
    ├── sha256_manifest.txt
    ├── iq_input.bin              # frozen IQ, 77824 B
    ├── expected_tensor_plddr.bin # frozen Golden tensor, 97280 B
    ├── model.json / model.raw    # frozen iCraft ZG330 model
    ├── reference_argmax.txt      # frozen reference (frame_id, argmax_id, ...)
    └── pc_reference_19frames.{json,csv}
```

## Data flow

```
fixed IQ ──▶ Linux / MemChunk ──▶ PL DDR ──▶ FPGA Mandatory Core
                                             │
                                             ▼
        classification result ◀── NPU ◀── Linux host memory ◀── 97280 B tensor
```

- **Phase A** (FPGA/DDR → host mem): reuse the board-verified
  `pl_ddr_mandatory_core_smoke.cpp` path verbatim — dynamic MemChunk address,
  64 B alignment, register configure, START + poll DONE, tensor read-back — plus
  a byte-exact compare vs `expected_tensor_plddr.bin`. `mismatch != 0` stops the
  run before the NPU is touched.
- **Phase B** (per-frame NPU): frames 7..18, each with the exp4 lifecycle
  (`Device::Open → Session/Tensor → forward/wait/read → destroy → Device::Close`),
  dequantized iq × 1/127 / physical × 2/127, argmax vs `reference_argmax.txt`.

## Build & run (on board)

```sh
cd board_package
sha256sum -c sha256_manifest.txt
./build_on_board.sh
./run_joint_test.sh
```

See `board_package/README.md` for the full output format and PASS criteria.

## Status

- Preparation complete; **board run is the only remaining step**.
- Phase B's exp4 lifecycle is **board-verified**: three board runs, 12/12 MATCH
  (frames 7–18), timeout=0, error=0, no one-frame delay (the earlier
  `delay_shift=1/11` was a false positive from frames 8/9 both referencing
  7/OFDM).  It is correctness-verified but **not real-time** (per-frame
  Device/Session reopen), so `REALTIME_NOT_YET_VALIDATED` is still emitted.
