# 任务4：MemChunk 动态地址 / 64B 对齐 / 77824B IQ / 97280B Tensor 核对

核对对象：`pl_ddr_mandatory_core_smoke.cpp` + `pl_ddr_register_map.hpp` + `pl_ddr_mandatory_core_regs.sv` + `v2_tensor_contract.json` + `iq_beat_unpacker.sv` + `tensor_plane_beat_packer.sv`。**全部一致，无矛盾。**

## 1. MemChunk 动态地址

```cpp
// pl_ddr_mandatory_core_smoke.cpp:93
auto chunk = fpai_device.defaultMemRegion().malloc(kAllocationBytes, false, 64);
const std::uint64_t chunk_addr = chunk->begin.addr();   // 运行期返回的物理地址
const std::uint64_t tensor_addr = chunk_addr + kTensorOffset;  // +77824
```
- 地址由 iCraft XRT `MemRegion::malloc` 在**运行期动态分配**（非编译期固定），`chunk->begin.addr()` 取物理地址。
- 写入寄存器 `IQ_BASE=chunk_addr`、`TENSOR_BASE=tensor_addr`（见 smoke 116/117 行）。
- 一次性分配 `kAllocationBytes = 77824 + 97280 = 175104 B`，IQ 在前、Tensor 在后（offset 77824）。

## 2. 64B 对齐（三层双重校验）

| 层 | 位置 | 校验 |
|---|---|---|
| 分配 | smoke:93 `malloc(..., false, 64)` | 请求 64 字节对齐 |
| 软件 | smoke:99 `(chunk_addr & 63)==0 && (tensor_addr & 63)==0` | 运行期断言，否则抛错 |
| 硬件 | regs.sv:62-63 `iq_base_addr[5:0]==0 && tensor_base_addr[5:0]==0` | `config_valid` 必要条件，否则 ERROR_BAD_CONFIG |

## 3. 77824 B IQ 输入

- `EXPECTED_IQ_BYTES = 32'd77824`（regs.sv:6）。
- `kIqBytes = 19 帧 × 1024 采样 × 4 B = 77824`（smoke:22）。
- 4 B/采样 = {Q[15:0], I[15:0]}（`iq_beat_unpacker.sv:25-26`：`iq_i=word[15:0]`、`iq_q=word[31:16]`）。
- 数据文件 `data/iq_input.hex`：19456 行 × 32-bit word = 77824 B ✅（脚本已实测转换 19456 word / 77824 B）。
- smoke 入口 `read_exact(argv[3], kIqBytes)` 要求输入恰为 77824 B，否则报错。

## 4. 97280 B Tensor 输出

- `EXPECTED_TENSOR_BYTES = 32'd97280`（regs.sv:7）。
- `kTensorBytes = 19 帧 × 5 plane × 1024 = 97280`（smoke:24，`kTensorFrameBytes=5*1024`）。
- 布局（`tensor_plane_beat_packer.sv` channel-major，与 contract `pl_ddr_frame_layout` 一致）：

| plane | 名称 | 帧内 offset | 字节 |
|---|---|---|---|
| 0 | I | 0 | 1024 |
| 1 | Q | 1024 | 1024 |
| 2 | power | 2048 | 1024 |
| 3 | lag1_real | 3072 | 1024 |
| 4 | lag1_imag | 4096 | 1024 |

- Golden `data/expected_tensor_plddr.hex`：97280 行 × 1 B = 97280 B ✅（脚本已实测 97280 B，其中 79978 非零）。
- 回读 `chunk.read(tensor.data(), kTensorOffset, kTensorBytes)`，写 `tensor_output.bin`（smoke:147-148）。

## 5. 寄存器映射一致性

`pl_ddr_register_map.hpp` 与 `pl_ddr_mandatory_core_regs.sv` 完全一致：
VERSION=0x00 / CONTROL=0x04 / STATUS=0x08 / IQ_BASE=0x0C / IQ_BYTES=0x10 / TENSOR_BASE=0x14 / TENSOR_BYTES=0x18 / FRAME_COUNT=0x1C / IQ_ACCEPTED=0x20 / TENSOR_ACCEPTED=0x24 / ERROR_CODE=0x28；
`VERSION_VALUE=0x20260929`；CONTROL bit0=START、bit1=CLEAR；STATUS bit0=BUSY、bit1=DONE、bit2=ERROR。绝对基址 `0x400C0000`（由 ps_pl_ctrl_smoke 及 BD 地址编辑器确认）。

## 结论

MemChunk 动态地址、64B 对齐（三层双重）、77824 B IQ、97280 B Tensor 四项全部核对通过，软硬件与 golden 数据尺寸一致，无任何失配。
