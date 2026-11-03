# 任务 39e5：HDMI DDR 帧缓冲读取链路修复报告

> 目录：`hdmi_framebuffer_ui_v4_fix`（独立修复目录，不覆盖 v2/v3）。
> 状态：**READY-FOR-HARDWARE-TEST**（RTL 修复经仿真 RED/GREEN 实证，位流构建通过；未经实机验证，不写 PASS/READY）。

## 1. 根因定位（审计结论）

### 根因 A（主，RTL）：64→16 位宽转换顺序错误（MSB-first vs LSB-first）

Xilinx FIFO Generator 的**非对称 FIFO（写宽 > 读宽）读侧是 MSB-first（大端）**：
一个 64-bit word 的首次 16-bit 读返回最高 16 位 `din[63:48]`，末次返回最低 16 位
`din[15:0]`（PG057 非对称 FIFO 例子：写入 8-bit `11_00_01_11`，读出顺序为
`11`、`00`、`01`、`11`）。

而 DDR 里 PS 按**小端**写 RGB565 像素：像素 0 落在 `RDATA[15:0]`，像素 3 落在
`RDATA[63:48]`。原设计 `aq_axi_master.v` 把 `RD_FIFO_DATA = M_AXI_RDATA` 直通，
于是 FIFO 读出的每个 4 像素组被逆序（3,2,1,0），屏幕即表现为"一团乱"。

**证据链（确定，非猜测）：**

| 步骤 | 行为模型 | RTL | 结果 |
|---|---|---|---|
| 1. 基线 | LSB-first（旧假设） | 未修复 | PASS（证明敏感测试图/断言本身正确） |
| 2. 复现 | **MSB-first（真实 IP）** | 未修复 | **FAIL，mismatch=28800=720×40（每 4 像素逆序）** |
| 3. 修复 | MSB-first（真实 IP） | 半字反转 | PASS（mismatch=0） |

> 敏感测试图：buffer 0 每行前 40 像素 = 像素索引 0..39（原"全白"对 4 像素
> 逆序不敏感，是导致上一版误 PASS 的盲区）。

### 根因 B（软件）：NEON/SIMD 宽写 → SIGBUS

phase1b/1c 的 render 函数用**非 volatile** `std::uint16_t*` 直接写 u-dma-buf 的
mmap，GCC -O2 自动向量化为 NEON 宽写（st2/str q），而 u-dma-buf 只接受标量宽度
访问 → SIGBUS（v3 `REPORT.md` §2 已确认）。

## 2. 修复（最小可证）

### 2.1 RTL：`aq_axi_master.v` 读数据半字反转

```verilog
// MSB-first 的 FIFO 先读 din[63:48]，而小端 DDR 的像素 0 在 RDATA[15:0]，
// 故把 4 个 16-bit 半字逆序送入 FIFO，使读出的首个半字正是像素 0。
assign RD_FIFO_DATA[63:0] = {M_AXI_RDATA[15:0],
                             M_AXI_RDATA[31:16],
                             M_AXI_RDATA[47:32],
                             M_AXI_RDATA[63:48]};
```

只改读路径 `RD_FIFO_DATA`，写路径（`WR_FIFO_DATA`→`M_AXI_WDATA`）与读控制逻辑
（`RREADY`/`RD_FIFO_WE`/FSM）不动。写路径（`afifo_16i_64o_largebuf`）在本只读
设计中已 tie-off，无需同步修改。

### 2.2 软件：render 参数加 volatile

- `phase1b_doublebuf_test.cpp`：`render_moving_bar(volatile std::uint16_t* px, …)`
- `phase1c_dynamic_test.cpp`：`render_pattern(volatile std::uint16_t* px, …)`

volatile 强制编译器逐像素做标量 16-bit store，禁止向量化成 NEON 宽写。
（`fb.frame_buffer()` 返回 `std::uint16_t*`，向 `volatile` 的限定转换是隐式合法的。）

## 3. 仿真验证（Verilator 5.032，tb_read_path.sv）

最终仿真（MSB-first 行为模型 + 修复后 RTL + 双 buffer 切换）`VERDICT: PASS`：

```
frame_beat[0] = 230400     frame_beat[2] = 230400
frame_beat[1] = 230400     frame_beat[3] = 230400   (buf1，切换后)
valid_px_cnt  = 921600     line_cnt = 720
mismatch_buf0 = 0          mismatch_buf1 = 0
underflow_cnt = 0          drop_we = 0
```

覆盖验收项：1280 px/行、720 行/帧、921600 px/帧、每帧 230400 个 64-bit 读、
64→16 顺序正确、buffer 0/1 切换各读满 230400 words、无 FIFO 上下溢。

行为模型 `afifo_64i_16o_128_beh.v` 已按真实 IP 改为 MSB-first，并移除临时诊断
`$display`。

## 4. 构建结果（Vivado 2018.3）

构建门限全过（详见 `docs/BUILD_RESULTS.md` 与 `SHA256SUMS.txt`）：

| 门限 | 结果 | 结论 |
|---|---|---|
| 时序 WNS / WHS | **+2.308 ns / +0.084 ns**（TNS=THS=0，WPWS=+1.100） | ✅ 全过 |
| DRC | **0 Error / 25 Warning**（REQP-1839×20、PORTPROP-2×2、RTSTAT-10×1、CHECK-1/3×2，全无害） | ✅ 0 Error |
| 位流 `.bit` | 5,980,035 B，`9282f98a…` | ✅ 已生成 |
| 位流 `_disable_icap.bit` | 5,980,619 B，`df8a0c66…` | ✅ 已生成（JTAG 加载目标） |
| FMSH IP patch | Procise 检测 `IP Patch version: 53180205`（与 v2 **文件大小一致、patch 版本一致，但不宣称二进制完全一致**） | ✅ 已应用 |

> 构建过程中 360 U盘保镖（360UDiskPro）实时扫描对 exFAT F 盘锁文件，导致
> `launch_runs` 并发 worker 偶发 `Access is denied`；write_bitstream 最终以
> 「单进程直接跑 run 步骤脚本（含 `write_bitstream_pre/post.tcl`）」完成，
> 保证 FMSH IP patch 与 `_disable_icap.bit` 正确产出。

**状态：`READY-FOR-HARDWARE-TEST`**（RTL 修复经仿真实证、位流构建门限全过、FMSH patch
已应用；但未经实机验证，不写 PASS/READY）。待用户本人按 1A→1B→1C→2→3 顺序上板，
JTAG 只加载 `_disable_icap.bit`。
