# PL DDR data-path preparation

This directory is deliberately independent of both the frozen Mandatory Core
hardware baseline and `vivado_projects/ps_pl_ctrl_smoke`.  Nothing here has yet
been integrated into a Vivado block design or downloaded to hardware.

## 1. Verified official interface contract

The contract below was read from the original `fpai_demo_fpga` and
`fpai_demo_app` distributions in the workspace, principally:

- `rtl/ps_ai_peripheral.sv`
- `rtl/ai7030_edif_top.v`
- `rtl/utils/demo_clkrst_wrapper.v`
- `rtl/adder_op/dma.v`
- `examples/1_single_input+ai/PLin+SingleNet+HDMI/src/adder_demo.cpp`

`User_Ddr_*` is a 512-bit, ready/valid, single-beat PL-DDR interface in the
official `hp_clk` domain.  The official wrapper assigns `hp_clk = ddr_clk`, and
the example connects the user logic's `sys_clk_200m` to `hp_clk`.

| Direction relative to user logic | Signal | Width | Acceptance |
|---|---|---:|---|
| output | `User_Ddr_awwaddr` | 32 | write accepted with `awwvalid && awwready` |
| output | `User_Ddr_awwdata` | 512 | 64 data bytes |
| output | `User_Ddr_awwinfo` | 72 | `{reserved, byte_enable[63:0], info[5:0], last}` |
| output/input | `User_Ddr_awwvalid/ready` | 1/1 | complete write request handshake |
| output | `User_Ddr_araddr` | 32 | read request accepted with `arvalid && arready` |
| output | `User_Ddr_arinfo` | 32 | `{25'h0, info[5:0], last}` |
| output/input | `User_Ddr_arvalid/ready` | 1/1 | read request handshake |
| input | `User_Ddr_rdata` | 512 | read response payload |
| input | `User_Ddr_rinfo` | 32 | `{25'h0, info[5:0], last}` |
| input/output | `User_Ddr_rvalid/rready` | 1/1 | read response acceptance |

The official single-beat encodings are:

```text
write info = {1'b0, 64'hffff_ffff_ffff_ffff, 6'b0, 1'b1}
read info  = {25'h0, 6'b0, 1'b1}
```

Official `dma.v` increments byte addresses by 64.  Official `adder_demo.cpp`
allocates with `defaultMemRegion().malloc(..., 0, 64)`, uses
`mem_chunk->begin.addr()`, and transfers bytes through `MemChunk.write/read`.
The adapters therefore require 64-byte-aligned base addresses and sizes.

## 2. Buffer layout

No absolute PL-DDR address is assumed.  Linux allocates one 64-byte-aligned
`MemChunk`, and the hardware receives its runtime address through registers.

| Chunk offset | Size | Contents |
|---:|---:|---|
| `0x00000` | `0x13000` = 77,824 B | 19 x 1024 IQ words, `{Q[15:0],I[15:0]}` |
| `0x13000` | `0x17c00` = 97,280 B | 19 channel-major Tensor frames |
| total | `0x2ac00` = 175,104 B | one aligned allocation |

Each 5,120-byte Tensor frame contains five 1,024-byte planes:

```text
frame + 0x000: IQ-I INT8
frame + 0x400: IQ-Q INT8
frame + 0x800: Power INT8
frame + 0xc00: Lag-Re INT8
frame + 0x1000: Lag-Im INT8
```

This is the exact channel-major meaning of the frozen `tensor_packer` ports.
Every 64 samples become five full, aligned 512-bit writes.  No sparse byte
writes are required.

## 3. CDC and adapters

```text
Linux MemChunk / PL DDR (official hp_clk, about 200 MHz)
  -> user_ddr_iq_reader (one outstanding read, 64 B per request)
  -> 512-bit Gray-pointer asynchronous FIFO
  -> iq_beat_unpacker (Mandatory Core 50 MHz)
  -> sixteen 32-bit IQ ready/valid samples per beat
  -> frozen Mandatory Core (not instantiated in this preparation directory)
  -> tensor_plane_beat_packer (64 samples -> five 64 B plane writes)
  -> 544-bit {address,data} Gray-pointer asynchronous FIFO
  -> user_ddr_tensor_writer (official hp_clk)
  -> PL DDR / MemChunk.read()
```

Both async FIFO pointers cross through two `ASYNC_REG` synchronizer stages.
Payload is transferred only through dual-port storage.  Backpressure is
preserved end to end.  The input reader intentionally permits only one
outstanding request until an official maximum-outstanding contract is found.

The output packer pulses the real two-bit `buffer_release` one core cycle after
accepting a frame's final Mandatory Core transaction.  By then all five output
bytes have been copied into adapter-owned registers.  Completion reported to
Linux must use the DDR writer's accepted-beat count, not merely this release.

## 4. Proposed control register contract

Only relative offsets are defined in `linux/pl_ddr_register_map.hpp`.  The
absolute base must be taken from the future integrated BD Address Editor.

| Offset | Name | Purpose |
|---:|---|---|
| `0x00` | VERSION | integrated data-path version |
| `0x04` | CONTROL | bit0 START, bit1 CLEAR |
| `0x08` | STATUS | bit0 BUSY, bit1 DONE, bit2 ERROR |
| `0x0c` | IQ_BASE | runtime MemChunk IQ address |
| `0x10` | IQ_BYTES | must be `0x13000` |
| `0x14` | TENSOR_BASE | runtime MemChunk Tensor address |
| `0x18` | TENSOR_BYTES | must be `0x17c00` |
| `0x1c` | FRAME_COUNT | must be 19 for the first test |
| `0x20` | IQ_ACCEPTED | accepted 32-bit IQ transactions |
| `0x24` | TENSOR_ACCEPTED | accepted core Tensor transactions |
| `0x28` | ERROR_CODE | alignment/count/protocol error |

Linux owns the allocation while idle.  After writing input and issuing START,
PL owns both ranges until DONE or ERROR.  Linux must not change input or read
output while BUSY.  On DONE, it reads the Tensor range with `MemChunk.read()`.

## 5. Unit and full-chain verification completed

Vivado Simulator 2018.3 was run with independent 200 MHz DDR and 50 MHz core
clocks plus ready/backpressure stalls:

- input: 1,216 read beats, all 19,456 IQ samples in order;
- output: 19,456 core Tensor transactions, 1,520 full DDR write beats;
- buffer release: 19 correctly sequenced pulses;
- no drop, duplicate, protocol error, or deadlock.

The conversion-tool round trip generated a 97,280-byte five-plane image,
converted it back to capture CSV, and passed the existing frozen comparator:

```text
reference rows: 19,456
checked fields: 330,752
mismatches: 0
```

In addition to the two adapter unit tests, the real frozen RTL was then placed
between the adapters in one end-to-end simulation:

```text
PL-DDR model
  -> pl_ddr_iq_input_adapter
  -> six frozen Mandatory Core RTL modules
  -> pl_ddr_tensor_output_adapter
  -> PL-DDR write sink
  -> existing compare_board_capture.py
```

This test uses the independent 200 MHz DDR and 50 MHz core clocks, the frozen
`iq_input.hex`, deterministic DDR response latency, and output backpressure.
It completed all 19 frames and all 19,456 IQ/Tensor transactions.  The emitted
97,280-byte DDR image is byte-identical to the image packed from
`expected_core.csv` (SHA-256
`7f4bce133fd00cbd6161eb278ad4f2506e12d74fc223fbda0afb664fc8fe2af5`).
The frozen comparator checked 330,752 fields with zero mismatches.

Run locally with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_unit_sims.ps1
```

## 6. Files

- `rtl/async_fifo_gray.sv`: generic dual-clock ready/valid FIFO
- `rtl/user_ddr_iq_reader.sv`: conservative official-interface read engine
- `rtl/iq_beat_unpacker.sv`: 512-to-32 IQ serializer
- `rtl/pl_ddr_iq_input_adapter.sv`: complete input CDC path
- `rtl/tensor_plane_beat_packer.sv`: real five-plane Tensor packer
- `rtl/user_ddr_tensor_writer.sv`: official-interface write engine
- `rtl/pl_ddr_tensor_output_adapter.sv`: complete output CDC path
- `tb/tb_pl_ddr_mandatory_core_e2e.sv`: complete DDR/core/DDR simulation
- `tb/`: full 19-frame independent adapter unit testbenches
- `tools/iq_hex_to_plddr.py`: frozen IQ hex to little-endian DDR image
- `tools/plddr_tensor_to_csv.py`: DDR Tensor image to existing capture CSV
- `linux/pl_ddr_mandatory_core_smoke.cpp`: future MemChunk application skeleton

## 7. Required gates before integration

Do not integrate this directory until the existing PS->PL smoke test proves on
real hardware:

1. the current bitstream's actual User_Reg base is reachable;
2. VERSION and SCRATCH read/write work with runtime 3.39;
3. START/DONE/RUN_COUNT work across the official GP clock/reset path;
4. the chosen C++ `Device::Open` URL and `ZG330Device` cast work on this image;
5. the copied official project remains the correct BD/address-map baseline.

During integration, additionally re-confirm the generated BD address map,
connect `User_Ddr_*` only in the official `hp_clk` domain, synchronize START
and stable configuration into both clock domains, constrain the asynchronous
clock groups/FIFO paths correctly, and run synthesis/P&R/STA before hardware.
