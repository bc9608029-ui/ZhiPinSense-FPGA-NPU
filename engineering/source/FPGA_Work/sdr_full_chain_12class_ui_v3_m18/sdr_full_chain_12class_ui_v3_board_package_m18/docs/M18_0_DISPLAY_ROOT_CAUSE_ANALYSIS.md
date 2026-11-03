# M18-0 决定性根因分析：HDMI 竖纹 + 动态横带

> 状态：**分析完成，未下结论（根因均未达 CONFIRMED，待板测）。**
> 本文档回答 M18-0 纠正指令的 8 个问题，并交付诊断工具 A–D 的设计、三条板测步骤与判定矩阵。
> 依据：只读审计来源工程 `sdr_full_chain_12class_combined_v1` 的 RTL 与 M18 工作区的软件。
> 本阶段**不修改 RTL、不启动 Vivado、不改任何正式换帧/缓存/时钟/地址逻辑**；诊断工具是纯新增，不改变既有软件行为。

---

## 0. 结论摘要

把「竖纹 + 动态横带」拆成两个**不同机制**的缺陷，避免再用"软件优化后重建观察"的方式混在一起迭代：

| 症状 | 最可能机制 | 现状 |
|---|---|---|
| **开机竖纹**（固定、常伴随黑场/花屏） | 位流加载后 PL 以 `display_en=1`、`camera_rd_addr=0x7E00000` 扫描**未初始化 DDR**，直到软件写 rd_addr 前一直扫垃圾 | RTL 结构上**已实锤**（见 Q7），但"屏幕上的竖纹是否就是它"仍需板测 A 确认 |
| **运行期动态横带**（滚动/闪烁的水平带） | ① 换帧无硬件 ACK → 软件 front/back 跟踪可能漂移 → 覆盖正在扫描的 buffer（写入追赶扫描行）；② 读 FIFO 下溢未记录 | **假设**，需板测 B/C/D 区分 |

RTL 层面**已确认的事实**（不需要上板即可从代码证明）：

- 没有 vblank / flip-ACK / frame_valid / mmcm_locked 状态寄存器（Q2）。
- buffer-select 在**帧起始**（VSYNC 边沿 → read_req → S_ACK）锁存，不在任何具体像素周期（Q3）。
- 读 FIFO 下溢 `rd_rfifo_err`、写 FIFO 上溢 `wr_wfifo_err` **结构性未被记录**（Q6）。
- 位流加载后扫描的初始 DDR 地址/内容 = `0x3F000000`（字节地址，`camera_rd_addr=0x7E00000`）处的**未初始化内容**，且 `display_en` 复位为 1（Q7）。

**未确认、必须上板区分**的（Q4/Q8）：运行期动态横带到底来自"换帧竞态覆盖 front buffer"还是"DDR/FIFO 读侧"。

---

## 1. Q1：M17 改了哪些显示项？为什么没能消除条纹？

M17 与显示相关的是三个软件改动（其余 Task A/B/C/H 属于 Gate10 采样、生命周期、dump、触摸，与显示条纹无关）：

1. **Task D — 帧缓冲 vblank 只读审计**：审计结论是"**没有**可轮询的 vblank 状态寄存器"，因此换帧仍是"写到 `camera_wr_addr[0]`（0x50）即视为翻转"的 fire-and-forget。
2. **Task E/G — `FlipScheduler` 事件驱动翻转**：把 UI 空转时不必要的翻转去掉，降低翻转频率。它只能降低"翻转竞态"的**概率**，无法消除。
3. **Task F — 启动消隐 `set_display_enable`**：在 UI 进程 `init()` 后先 `disable_hdmi=1` 消隐、清帧、写 rd_addr、再 `disable_hdmi=0` 解除消隐。

为什么这些软件改动**注定不能消除**这两类条纹：

- **开机竖纹**：Task F 的消隐只覆盖"UI 进程运行后"的那一段窗口。而 `display_en` 在 RTL 复位就是 1（`frame_ctrl.v:821/834`），从**位流加载完成 → FSBL/Uboot → Linux 引导 → 用户态 UI 进程被拉起 → `init()` 完成** 的整段时间，PL 一直在扫复位地址 `0x3F000000` 的垃圾。这一段在**软件可运行的层级之下**，任何用户态程序都够不着，只有 RTL（复位默认消隐、或等待 `ddr3_init_done`+软件显式使能）才能关掉。
- **运行期动态横带**：Task E/G 的翻转调度是在**没有硬件翻转 ACK、没有 FIFO 下溢标志**（Q2/Q6）的前提下做的，软件对"硬件此刻到底在扫哪个 buffer、是否下溢"是**盲**的。降低翻转频率只是减少暴露，不是修复。

结论：M17 的软件修复方向没有错在"优化"，而是错在**把两个位于软件层级之外（或软件不可观测）的硬件缺陷当作软件问题迭代**。这正是 M18-0 要求先做根因分析的原因。

---

## 2. Q2：当前硬件是否存在真正的 vblank 信号和 flip ACK？

**不存在。** 证据：

- `frame_ctrl.v` 的状态寄存器 `slv_reg22`（偏移 0x58，`frame_ctrl.v:733`）只有 `{29'h0, wr_wfifo_err, rd_rfifo_err, camera_wr_done}` 三个标志位；没有任何 vblank / frame_valid / flip_done / mmcm_locked 位。
- `direct_framebuffer_backend.hpp` 的 Config 里，`disable_hdmi_offset=0x78`、`h_sync=0x94`、`v_sync=0xA4`、`vtc_enable=0xB4` 都只是**只读**配置/使能寄存器，是 720p 时序的**常数**，不是"当前是否处于 vblank"的实时状态。
- "翻转" = 软件写 `camera_wr_addr[0]`（0x50 bit0，`frame_ctrl.v:691-699`）。`write_reg` 只做**寄存器回读一致**校验（`direct_framebuffer_backend.cpp:244-260`），它证明的是"写进 AXI-Lite 寄存器的值读回来一致"，**不是**"PL 已锁存到下一帧的 buffer-select"。

因此：**不存在可用来做用户态翻转同步的 vblank 信号，也不存在 flip ACK。** 这是"运行期动态横带"无法靠软件精确消除的根因之一。

---

## 3. Q3：buffer-select 究竟在哪个像素周期生效？

**在帧起始锁存，不在任何具体像素周期。** 数据链：

1. 软件写 `camera_wr_addr[0]`（0x50，gp_clk 域）。
2. `fb_read_720p.sv:183-191`：`read_buf_sel` 经 `buf_sel_sync1 → buf_sel_sync2` **两级 FF 同步**到 hp_clk 域。
3. `fb_read_720p.sv:219`：`read_addr_index = {1'b0, buf_sel_sync2}`，选择 buffer 0（`camera_rd_addr`）或 buffer 1（`camera_rd_addr + 230400`）。
4. `video_rect_read_data.v` 在**垂直同步边沿**（`pos_vs` 上升沿）置 `read_req`。
5. `frame_fifo_read.v` 的 `S_ACK` 状态**每帧只锁存一次** `rd_burst_addr`（从 `read_addr_index_d1` 来），随后整帧地址计数器从该基址自增。

所以：一次翻转写入要经过"两级 FF 同步（~2 个 hp_clk）+ 等到下一个帧起始的 `read_req → S_ACK`"才真正生效，**至多延迟一帧**。翻转**不会**在帧中间切换地址；帧中地址是连续自增的。这意味着"一次干净的单次翻转"本身**不该**产生帧中撕裂——如果出现横带，更可能是**写入追赶扫描行**（见 Q4）或**读侧下溢**（见 Q6），而不是翻转地址在帧中突变。

---

## 4. Q4：UI 是否可能写入正在扫描的 front buffer？

**稳态下不应写入，但没有硬件 ACK，软/硬件 front-back 跟踪可能漂移，从而可能写入。** 机制：

- 软件约定：`submit_frame` 总是渲染到 `front ^ 1`（后 buffer），拷贝+sync 完成后才翻转。`front` 是软件内部跟踪的变量，**没有任何硬件回读来确认**。
- 由于 Q2/Q3：翻转是 fire-and-forget、帧起始才锁存、至多延迟一帧。若软件在一次翻转尚未被 PL 锁存时又发下一次翻转（两次快速翻转被合并，`camera_wr_addr[0]` 只保留最后写值），软件的 `front` 变量与 PL 实际锁存的 buffer-select 就**可能错位**。
- 一旦错位，软件"以为"的后 buffer 其实就是 PL 正在扫描的 front buffer；软件对它做 1.8MB 的标量拷贝时，PL 的扫描行会**追着写指针跑**，于是在某一行读出"上一行已更新、下一行未更新"的混合内容 → **水平横带**。

这是"动态横带"的头号候选机制，但属于**假设**，必须靠板测 B/C 区分（见 §7）。Tool C（低频红蓝切换）正是为隔离"翻转本身是否干净"而设计。

---

## 5. Q5：udmabuf 驱动的同步是否覆盖完整 buffer？

（补充回答，虽不在 8 问主序，但直接影响 Tool D 的 CRC 判定可信度。）

- `submit_frame` 的同步路径是：标量 volatile 16-bit 写 → `flush()`（`msync(MS_SYNC)`，EINVAL 容忍；再写 `/sys/.../sync_for_device`）。`direct_framebuffer_backend.cpp:262-286`。
- `sync_for_device` 节点由 u-dma-buf 驱动实现，语义是"整个 udmabuf 缓冲"一次同步，**覆盖完整 buffer**（非按页/按段）。这由 Tool D（提交前后 CRC）实证：若 CRC 一致，则写+同步链路可信，屏幕仍异常就指向 PL 读侧；若 CRC 不一致，则写/同步链路本身有问题。

---

## 6. Q6：是否存在 FIFO empty/underflow 但没有被记录？

**存在，且结构性未被记录。** 证据链（这是本文档最强的一条 CONFIRMED）：

1. 读链路最底层的 `frame_read_write_largebuf.v` 会在 `read_en && rd_buf_empty` 时断言 `rd_rfifo_err`（写侧 `write_en && wr_buf_full` 断言 `wr_wfifo_err`）。
2. 但 `fb_read_720p.sv:243-244` 把这两个输出**空接（tie-off）**：
   ```systemverilog
   .wr_wfifo_err      (),
   .rd_rfifo_err      (),
   ```
3. 顶层 `ps_ai_peripheral_combined.sv:630-631` 声明的 `wire wr_wfifo_err / rd_rfifo_err` 只被 `frame_trans` 实例（`:971-972`）消费，用于喂给 `frame_ctrl` 的 `slv_reg22`，但**没有任何东西驱动这两根线**（`fb_read_720p` 实例 `:858-912` 根本没有连接这两个端口）。
4. 于是 `frame_ctrl.v:733` 的 `slv_reg22 = {29'h0, wr_wfifo_err, rd_rfifo_err, camera_wr_done}` 里两个错误位读回的是**悬空/未驱动的值**（综合后通常为 0）。

**结论：即便读 FIFO 真的下溢（横带的候选机制之一），0x58 寄存器也看不到，软件无从得知。** 这正是"诊断工具 E（仅加计数器的诊断位流）"存在的原因——若 RTL 不可观测，只有加计数器重出位流才能证明/排除下溢。

---

## 7. Q7：位流加载后扫描的初始 DDR 地址和内容是什么？

**地址 `0x3F000000`（字节），内容 = 未初始化 DDR。** 证据：

- `frame_ctrl.v:705`：`camera_rd_addr` 复位 `27'h7E0_0000` → `fb_read_720p.sv:215` 把它当 `read_addr_0`，字节地址 = `0x7E00000 × 8 = 0x3F000000`。
- `frame_ctrl.v:821`：`disable_hdmi` 复位 0 → `:834` `display_en = ~disable_hdmi_2 = 1`。即**位流一加载，PL 就使能 HDMI 扫描**，扫的是 0x3F000000 的 DDR。
- 软件直到 UI 进程 `init()` + 写 `rd_addr = phys>>3`（`0x54`）才把扫描基址改到 udmabuf0。这之前的 DDR 内容 = 上次掉电残留 / 本次 boot 的任意分配，**未初始化**。

**结论：开机竖纹 = PL 在软件介入前扫描未初始化 DDR 的强候选机制。** 唯一的软件补救（Task F 消隐）覆盖不到软件运行之前，故该缺陷只能靠板测 A 确认 + RTL 最小修复（复位默认消隐，或等待 `ddr3_init_done` + 软件显式使能）。

---

## 8. Q8：动态横带出现时使用的是哪个 buffer 地址？

**无法从 RTL 静态判断，必须靠板测 +（若 RTL 不可观测）诊断位流观察。** 因为：

- 软件侧能知道"自己 flip 到了哪个 index"（写 0x50 的值），但**不知道 PL 此刻实际锁存的是哪个**（无 ACK，Q2）。
- 硬件侧 `read_buf_sel` 在每个帧起始锁存 `camera_wr_addr[0]`，但当前锁存值**没有回读寄存器**。

因此横带时"PL 在扫 buffer 0 还是 buffer 1"当前**不可观测**。Tool C（红蓝双 buffer 低频切换）用"红=0、蓝=1"的颜色把 buffer 身份**可视化**：横带出现时是哪一色被撕裂，就能定位到具体 buffer。若仍不可判定，则升级到诊断位流（加计数器/回读寄存器）——这是 E 的触发条件。

---

## 9. 诊断工具 A–D（先交付，不是修复版本）

新增独立诊断程序 `board_package/board_display_diagnostic.cpp`（复用 `direct_framebuffer_backend`，**不修改**生产 UI `board_ui_live_12class` 的换帧逻辑）。为支持 B/D，向后端**新增两个只读/只增方法**（不改变既有 `submit_frame` 行为）：

- `submit_frame_no_flip(...)`：拷贝 + 同步，但**不写** `wr_addr`（供 Tool B 单 buffer 锁定）。
- `read_frame_words(...)`：把某帧的 device 映射**读回**普通缓冲（供 Tool D CRC 校验）。

| 工具 | 做什么 | 回答哪一问 | 需要人眼看屏 |
|---|---|---|---|
| **A 黑清静态** | 消隐→清两帧→写 rd_addr→解除消隐→静止保持黑色 | Q7：竖纹是否=未初始化内容 | 是 |
| **B 单 buffer 锁定** | 固定图案写满 buffer 0，**全程不发翻转**，静止保持 | Q4/Q6：无翻转时是否还有横带 | 是 |
| **C 红蓝低频切换** | 帧0=红、帧1=蓝，低频（默认 1Hz）只翻转不重渲染 | Q3/Q8：翻转本身是否干净、撕裂在哪个 buffer | 是 |
| **D 提交前后 CRC** | 渲染已知图案→算 staging CRC→提交→读回 device→算 CRC→比对 | Q5：写+同步链路是否可信 | 否（自动打印） |

编译产物：`bin/board_display_diagnostic`（`build_display_diagnostic.sh`，纯 g++，无 iCraft/libiio）。运行入口：`scripts/run_display_diagnostic.sh {a|b|c|d}`。

---

## 10. 三条板测（用户只做这三个短测试）

> 前提：`./board_package/build_display_diagnostic.sh g++` 编译后，`./scripts/run_display_diagnostic.sh a|b|c|d`（root）。每个测试观察屏幕即可，工具会打印关键事实。

1. **测试 1（Tool A，黑清静态）**：看屏幕是否变成**干净纯黑**。
2. **测试 2（Tool B，单 buffer 锁定、无翻转）**：看静态图案是否**干净稳定**，还是仍有横带/竖纹。
3. **测试 3（Tool C，红蓝低频切换）**：看红↔蓝切换是否**干净整帧切换**，还是切换瞬间出现撕裂/横带。
4. （顺带）**Tool D（CRC）**：不依赖人眼，自动打印 pre/post CRC 是否一致。

---

## 11. 判定矩阵（≥1 项达 CONFIRMED 前，不修 RTL、不建 Vivado、不宣称已修复）

| 板测结果 | CONFIRMED 根因 |
|---|---|
| A 黑清后屏幕**干净纯黑**（竖纹消失） | **未初始化 buffer**（Q7） |
| A 黑清后竖纹**仍在** | 竖纹在**扫描侧**（地址/步距/端序/像素映射），非内容 |
| B 单 buffer 稳定、仅 C 切换异常 | **换帧/CDC/同步**问题（Q2/Q4） |
| B 单 buffer 也异常 +（若诊断位流）下溢计数上升 | **DDR/FIFO 读侧**问题（Q6） |
| D CRC 一致但屏幕异常 | **RTL 扫描侧**问题 |
| D CRC 不一致 | **写/同步链路**问题（Q5） |
| 换帧或黑清后 MMCM 失锁 | **HDMI 时序**问题 |

对应的**最小修复**方向（**只在 CONFIRMED 后**才做，且一次只改一处）：

- 未初始化 buffer → RTL 复位默认消隐 / 等 `ddr3_init_done` + 软件显式使能。
- 换帧/CDC → 增加 flip ACK 或回读"当前锁存 buffer"寄存器，软件据此同步。
- DDR/FIFO → 补上 `rd_rfifo_err` 真实接线（从 `fb_read_720p` 引出），或加大 FIFO 深度。
- RTL 扫描侧 → 逐像素读侧映射审计（半字反转/步距/时序）。

**在至少一个根因达到 CONFIRMED 之前：不修改换帧、缓存、时钟、地址中的任何一项；不启动多轮 Vivado 构建；不用降刷新率或延时掩盖。**

---

## 12. 附：关键 RTL 证据索引

| 事实 | 位置 |
|---|---|
| `camera_rd_addr` 复位 0x7E00000（→字节 0x3F000000） | `frame_ctrl.v:705` |
| `camera_wr_addr` 复位 0x7C00000（bit0=0 → 默认 buffer 0） | `frame_ctrl.v:695` |
| `disable_hdmi` 复位 0、`display_en=~disable_hdmi_2`=1 | `frame_ctrl.v:821,834` |
| 状态寄存器 0x58 = `{…, wr_wfifo_err, rd_rfifo_err, camera_wr_done}` | `frame_ctrl.v:733` |
| 读/写 FIFO 错误输出空接（tie-off） | `fb_read_720p.sv:243-244` |
| 顶层错误线未驱动（`fb_read_720p` 实例不连） | `ps_ai_peripheral_combined.sv:630-631,858-912,971-972` |
| buffer-select 2-FF 同步 | `fb_read_720p.sv:183-191` |
| `read_addr_index={1'b0,buf_sel_sync2}` | `fb_read_720p.sv:219` |
| buffer1 = buffer0 + 230400（一帧 64-bit 字数） | `fb_read_720p.sv:215-216` |
| 半字反转（DDR 小端 ↔ 读 FIFO MSB-first） | `aq_axi_master.v:436-439` |
| 读请求在 VSYNC 边沿 | `video_rect_read_data.v`（read_req） |
| 每帧地址只在 S_ACK 锁存一次 | `frame_fifo_read.v`（S_ACK） |
| 软件翻转 = 写 0x50 + 回读校验（非 ACK） | `direct_framebuffer_backend.cpp:244-260,336` |
| 软件启动消隐序列 | `board_ui_live_12class.cpp:340-363` |
