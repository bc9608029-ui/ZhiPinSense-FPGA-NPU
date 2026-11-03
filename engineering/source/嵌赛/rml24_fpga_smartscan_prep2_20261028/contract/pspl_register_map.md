# Smart-Scan PS/PL 寄存器映射（SS_ 前缀，冻结）

版本：2026-10-29。本文件是 `SHARED_CONTRACT_PARALLEL_20261029.md` §6 的 B 线定版回填，
为唯一的 SS_ 寄存器映射权威来源。命名约定：数据/控制/状态三组；宽度与 `smart_scan_top`
端口一致（IQ `{Q,I}` 32-bit、`rd_bank`+`rd_addr`、`rd_data` 64-bit、状态 `8+32+1+1+1+1`）。

## 0. 接口域

- 寄存器通道 `User_Reg_*`：32-bit，`gp_clk` 域。写协议 `awwvalid && awwready`（`awwready` 恒 1）；
  读协议 `arvalid && arready`（`arready = !rvalid`），单待处理读，`rdata` 于 `rvalid` 周期有效，
  `rvalid` 在 `rvalid && rready` 后清 0。地址取 `awwaddr/araddr[17:0]`。
- IQ 输入：经 `User_Ddr_*` 512-bit DMA 读（`hp_clk` 域）→ 异步 FIFO → 解包为 `{Q,I}` 流（`core_clk` 域）。
- PSD 回读：经本寄存器通道（非 DDR 写回），见 §4。

## 1. 数据组

| 寄存器 | 地址 | 访问 | 位 | 说明 |
|--------|------|------|----|------|
| `SS_IQ_BASE`  | `0x00000` | RW | [31:0] | IQ 缓冲 DDR 字节基址，须 64 字节对齐（`[5:0]==0`） |
| `SS_IQ_BYTES` | `0x00004` | RW | [31:0] | IQ 字节数，须为 4096 整数倍（整帧 = 1024 样本 × 4 字节），非零 |

## 2. 控制组

| 寄存器 | 地址 | 访问 | 位 | 说明 |
|--------|------|------|----|------|
| `SS_CTRL` | `0x00008` | W | [0] START（写 1 触发一次扫描，自清）<br>[1] CLEAR（清 done/error/计数，空闲时） | 配置不合法 → done+error+`SS_ERR_CODE.BAD_CONFIG`，不启动 |

## 3. 状态组

| 寄存器 | 地址 | 访问 | 位 | 说明 |
|--------|------|------|----|------|
| `SS_VERSION`     | `0x0000C` | R | [7:0] | 扫描核版本 `8'h01`（冻结，`smart_scan_psd_buffers.VERSION`） |
| `SS_STATUS`      | `0x00010` | R | [0] busy<br>[1] done<br>[2] error<br>[3] committed_valid<br>[4] committed_bank<br>[5] protocol_error<br>[6] overflow<br>[7] rd_ready | 见错误分类 §5 |
| `SS_FRAME_ID`    | `0x00014` | R | [31:0] | 最近提交帧世代（帧 N 完成后 = N+1） |
| `SS_IQ_ACCEPTED` | `0x00018` | R | [31:0] | 核实际接受的 IQ 样本数（应 == `SS_IQ_BYTES/4`） |
| `SS_ERR_CODE`    | `0x0001C` | R | [0] BAD_CONFIG<br>[1] INPUT_DDR_ERROR<br>[2] FFT_PROTOCOL_ERROR<br>[3] FFT_OVERFLOW<br>[4] SAMPLE_COUNT_MISMATCH | 完成时锁存 |

## 4. PSD 回读组（寄存器通道，防撕裂）

| 寄存器 | 地址 | 访问 | 位 | 说明 |
|--------|------|------|----|------|
| `SS_RD_CTRL`    | `0x00020` | W | [9:0] bin 地址<br>[10] bank | 写触发一次读，`rd_ready` 清 0 |
| `SS_RD_DATA_LO` | `0x00024` | R | [31:0] | 上次读结果低 32 位 |
| `SS_RD_DATA_HI` | `0x00028` | R | [31:0] | 上次读结果高 32 位（`[63:54]` 恒 0，54-bit 功率合同） |

**读时序（PS 侧协议）：**
1. 读 `SS_STATUS`（`committed_valid`/`committed_bank`/`protocol_error`/`overflow`）与 `SS_FRAME_ID`。
2. `committed_valid==0` → 无数据。`protocol_error/overflow==1` → 拒收并回退。
3. 以 `bank = committed_bank` 写 `SS_RD_CTRL`；轮询 `SS_STATUS.rd_ready`（或等固定周期），
   读 `SS_RD_DATA_LO/HI`。写 `SS_RD_CTRL` 会清除 `rd_ready`。
4. 读完整帧前后**各**重读 `SS_FRAME_ID` + `committed_bank`：任一变化 → 重试；仍变化 → 拒收回退。
   仅读 `committed_bank` 不能防被下一轮覆盖（合同 §5）。

**BRAM 读延迟：** 真实两库各为 1024×64 块 RAM（OOC 已确认），读延迟 1 个 `core_clk` 周期。
引擎回读桥已按「寄存器地址 + 1 周期等待 + 捕获」实现，仿真（组合读）与硬件（1 周期延迟）均正确。

## 5. 错误分类 → `auto` 回退

任一成立 → `software/fpga/auto` 切软件 FFT，不得展示过期 FPGA 结果（合同 §4）：
- `protocol_error`（tlast 异常 / 输入 starvation / 输出失步）
- `overflow`（FFT `data_halt` 锁存）
- 帧未提交（`committed_valid==0` 或读完整帧世代变化）
- 版本不符（`SS_VERSION != 8'h01`）
- 读超时（`rd_ready` 超时未置位）
- `SS_ERR_CODE` 任一位非零（BAD_CONFIG / DDR 错误 / 样本计数不符）

## 6. 完成语义

`done` 在「DDR 读完成 **且** 最后一帧已提交（`frame_id >= SS_IQ_BYTES/4096`）」时置位。
`error`/`SS_ERR_CODE`/`SS_IQ_ACCEPTED` 与 `done` 同拍锁存。`START` 会经 `job_domain_controller`
复位 IQ 适配器与扫描核（清 `frame_id`/粘性错误），故每次扫描从干净状态开始。
