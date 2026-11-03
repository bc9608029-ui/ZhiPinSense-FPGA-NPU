# HDMI 动态显示系统 · 总操作手册（从断电接线开始）

> **状态：全部 `READY-FOR-HARDWARE-TEST`，待你本人按阶段实测。**
> 本文只给逐行步骤、期望画面与 PASS/FAIL 判据。**我（AI）不碰板、不写 Flash、不操作开发板。**
> 未经你实机验证，任何阶段都**不得**标记 `PASS` / `READY` / "显示成功"；只能标记 `READY-FOR-HARDWARE-TEST`。

---

## 0. 阶段与验收门（必须先读）

四个独立验收门，**顺序执行，任一未过不得进入下一阶段、不得宣称后续阶段通过**：

```
[门1] Phase 1A 静态帧 PASS
        ↓
[门2] Phase 1B 动态双缓冲 PASS
        ↓
[门3] Phase 1C 动态图案 + ≥10 分钟稳定性 PASS   （与 1B 同一位流，只换 PS 程序）
        ↓
[门4] Phase 2  完整识别 UI 离屏渲染 PASS         （与 1B 同一位流，只换 PS 程序）
        ↓
[门5] Phase 3  USB 触摸检测/校准/页面切换 PASS   （与 1B 同一位流，只换 PS 程序）
```

| 阶段 | 位流 | PS 程序 | 所在目录 |
|---|---|---|---|
| 1A | v1 单缓冲 `hdmi_framebuffer_720p_top_disable_icap.bit` | `phase1a_fb_test` | `hdmi_framebuffer_ui_v1/` |
| 1B | **v2 双缓冲 `hdmi_framebuffer_720p_top_disable_icap.bit`（共用）** | `phase1b_doublebuf_test` | `hdmi_framebuffer_ui_v2/` |
| 1C | 同上（共用 v2） | `phase1c_dynamic_test` | `hdmi_framebuffer_ui_v2/` |
| 2  | 同上（共用 v2 位流） | `phase2_ui_render`（**v3 三页 UI**） | `hdmi_framebuffer_ui_v3/` |
| 3  | 同上（共用 v2 位流） | `phase3_touch_test`（**v3 触摸翻页**） | `hdmi_framebuffer_ui_v3/` |

> **位流数量说明**：1B/1C/2/3 的 RTL 完全相同（双缓冲），只换 PS 程序，故共用同一 v2 位流。
> **v3 交付范围**：Phase 2（仪器化三页 UI）+ Phase 3（触摸翻页）。`phase1b/1c` 是 v2 已上板验证的资产，
> 在 v3 目录**原样保留但不再构建**（见 `hdmi_framebuffer_ui_v3/REPORT.md` §8）。位流 SHA-256 见 `docs/BUILD_RESULTS.md`，
> 每阶段加载前都先 `sha256sum -c` 校验同一位流，实现"独立校验、独立定位"。
>
> **类别契约（v3）**：UI 是**运行时 8–16 类**渲染器，类别顺序来自 `model_contract.hpp`，不在 UI 代码写死。
> 当前板测用 10 类 `contract_v1_1()`；12 类 `contract_target_12()` 仅预留，不冒充真实模型输出。

---

## 1. 硬件接线（从断电状态开始）

| 项目 | 说明 |
|---|---|
| 电源 | **12V DC 接 J37** |
| 上电 | 拨 **SW8** 上电 |
| PL JTAG | **20 针 U19**（不是 PS JTAG U18） |
| HDMI | 板子 PL 侧 **pHDMI** 输出口 → 屏的 **HDMI 口**（直接接，无需按屏上任何键） |
| 触摸/供电 | 屏的 **touch 口** 用 USB 线接 **板子 USB host 口**：**同一根线同时给屏供电 + 传触摸（USB HID）** |
| 登录 | 板载 Linux 的串口（或网口 SSH），沿用官方 demo 方式 |

**显示器（7" IPS 触摸屏）接线要点**：
- 屏原生 **1024×600**，HDMI 输入吃标准 720p 并由屏内缩放芯片缩到面板——**现有 720p 位流直接可用，不改时序**。
- **屏的 POWER 键不要按**：USB 上电即自动开机；按 POWER 等于关机。
- 若 USB 供电不稳（屏闪烁/重启），再单独给屏的 POWER 供电口接一根电源线。

**指示灯（v1/v2 同款，见 `hdmi_framebuffer_720p_top.sv` 末段）**：

| LED | 引脚 | 含义 | 期望 |
|---|---|---|---|
| led[0] | **J1** | MMCM1&2&3 + PS7 PLL 全部锁定 | **常亮** |
| led[1] | **M6** | 74.25MHz / 2^27 ≈ 0.55Hz | 约每 1.8 秒翻转一次 |

---

## 2. 统一 JTAG 加载流程（每个阶段都走这一步）

> **两条红线**：① 只用临时 JTAG（volatile），**永不写 Flash**；断电即还原。
> ② 加载的是 `*_disable_icap.bit`，**不是**原始 `.bit`。

**本机（Windows）用 Vivado 2020.2 Hardware Manager**（2020.2 只做下载，构建用 2018.3）：

- Phase 1A：`D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/program_phase1a_jtag.tcl`
- Phase 1B/1C（v2）：`D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v2/fpga/program_phase1b_jtag.tcl`
- Phase 2/3（v3）：`D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v3/fpga/program_phase1b_jtag.tcl`

脚本自动：`connect_hw_server` → **枚举全部 JTAG 器件、忽略 arm_dap（PS DAP）、只挑 `PART == xc7z030`（必须恰 1 个）** → `program_hw_devices`（volatile）→ 用 `REGISTER.IR.BIT5_DONE==1` 校验配置完成（不用 `PROGRAMMED` 属性）。
**验收**：打印 `..._JTAG_LOAD_COMPLETE`，且 led[0]（J1）常亮、led[1]（M6）慢闪。

> ⚠️ 若 JTAG 加载导致串口断流/崩溃：先断电→重新上电恢复 Linux，再按"**先起来 Linux，再加载位流**"顺序重来。

---

## 3. 阶段 1A — 静态帧（门 1）

步骤与判据见 `hdmi_framebuffer_ui_v1/docs/PHASE1A_BRINGUP.md`（接线/JTAG/PS 程序/10 分钟判据/回滚已齐全）。
**要点**：跑 `./build_on_board.sh run checker`，屏幕稳定静态棋盘 ≥10 分钟，`PHASE1A_PS_PASS` 打印，读回=写入。
**未 PASS 不得进入 1B。**

---

## 4. 阶段 1B — 动态双缓冲（门 2）

> **v2 资产**：本阶段程序位于 `hdmi_framebuffer_ui_v2/`，不在 v3 交付范围；v3 目录仅原样保留 `phase1b_doublebuf_test.cpp` 供参考、不构建。

**目标**：PS 每帧渲染到**后缓冲**（PL 未在读的那块），写 `0x40080050=后缓冲号`，PL 在下一帧边界原子切读，
屏幕显示**平滑移动的竖条**，全程无撕裂（竖条无水平错位/缺口）。

**步骤**（位流已由步骤 2 加载为 v2；若刚做完 1A，需**重新加载 v2 位流**）：

```
scp -r sw <board>:/tmp/hdmi_v2_sw/
ssh <board>
cd /tmp/hdmi_v2_sw
./build_on_board.sh                  # CMake 构建；失败则 ./build_on_board.sh g++（无需 iCraft，仅 libc）
./build_on_board.sh run phase1b 0 60 # 移动竖条，永久，60fps（Ctrl-C 停）
```

> 程序**不再用 iCraft `Device::Open` / NPU 寄存器**（HDMI-only 位流没有 NPU，旧 `axi://` 路径会卡死 Linux）。
> 改为**安全直连后端**：读 sysfs 得 phys/size → mmap `/dev/udmabuf0`（RGB565）+ mmap `/dev/mem` 单页（frame_ctrl）
> → 版本校验后才写寄存器（每次写都读回校验）。需 root（`/dev/mem`）。

**期望输出**：`[DFB] frame_ctrl version = 0x20230218 (expect ...)` → `[1B-PS] FB0=... FB1=... rd(0x54)=...` → 写 `0x54=fb0>>3`/`0x50=0`（读回一致）→ `PHASE1B_PS_PASS` → 每秒一行 `[1B-PS] frame=... front=0/1`。

**PASS（全满足）**：
1. `PHASE1B_PS_PASS` 打印（版本/对齐/容量/读回全过，软件门）。
2. HDMI 显示**深色底上一条白色竖条从左向右平滑移动**，边界锐利。
3. 连续观察（建议 ≥1 分钟）**无撕裂**（竖条无水平断裂/错位）、无冻屏。
4. led[0] 常亮、led[1] 慢闪。

**FAIL（任一即停）**：任一条 `[DFB] FAIL` / `FAIL` 打印；竖条出现水平撕裂/错位；画面冻住；读回≠写入。

---

## 5. 阶段 1C — 动态图案 + ≥10 分钟稳定性（门 3）

> **v2 资产**：本阶段程序位于 `hdmi_framebuffer_ui_v2/`，不在 v3 交付范围；v3 目录仅原样保留 `phase1c_dynamic_test.cpp` 供参考、不构建。

**目标**：轮换 4 种动态图案（竖条/棋盘/渐变/纯色），连续 ≥10 分钟稳定，程序心跳不卡死，寄存器回读零异常。

```
./build_on_board.sh run phase1c 600 60                 # 默认 600s 自动停；0 表示 Ctrl-C 停
RUN_TIMEOUT=660 ./build_on_board.sh run phase1c 0 60   # 用 timeout --kill-after=5s 兜底防卡死
```

**期望输出**：`PHASE1C_PS_READY` → 每 1 秒一行 `[1C-PS] frame=... elapsed_s=... pattern=... anomalies=0`。
每秒额外回读 `0x54`/`0x50` 校验无漂移；跑满 600s 且异常数为 0 才打印 `PHASE1C_PS_PASS (>=600 s, 0 register/readback anomalies)`。

**PASS**：① ≥10 分钟图案持续轮换、无撕裂/闪烁/冻屏；② 心跳 `frame`/`elapsed_s` 单调、无卡死、无报错；
③ `anomalies == 0` 且打印 `PHASE1C_PS_PASS`；④ led[1] 全程慢闪。
**FAIL**：任何时刻画面冻住/花屏、心跳停更，或 `anomalies > 0`（打印 `PHASE1C_PS_FAIL`）。

---

## 6. 阶段 2 — 仪器化识别 UI（三页，门 4）

**目标**：staging 缓冲 + 标量提交离屏渲染**三页**识别 UI（Overview / All Classes / Diagnostics），双缓冲翻页无撕裂、无 SIGBUS。

```
cd /tmp/hdmi_v3_sw
./build_on_board.sh                  # CMake；失败则 ./build_on_board.sh g++
./build_on_board.sh run phase2 -1 20 -1   # 动态 Top-1、20 fps、三页轮换
```

**期望画面**：顶部标题 `RF SIGNAL RECOGNITION`；三个标签 `OVERVIEW / ALL CLASSES / DIAGNOSTICS`（活动标签高亮）；右上角 `LIVE`/`MOCK` 徽标。
1. **Overview**：Top-1 类名大号 + 置信度带 + **Top-5 置信度条**。
2. **All Classes**：副标题 `FIXED CONTRACT ORDER`；按 `class_count` **动态排布** N 行（序号、`>` 标 Top-1、类名、置信度条、百分比）。
3. **Diagnostics**：FB phys / frame_ctrl 版本 / front buffer / 帧统计 / fps / latency + 事件日志框。

> **类别契约（v3，不写死 10 类）**：UI 是运行时 8–16 类渲染器，类别顺序来自 `model_contract.hpp`。
> 当前板测契约 `contract_v1_1()` = 10 类 **AM-DSB / WBFM / 2FSK / GFSK / BPSK / QPSK / 8PSK / 16QAM / 64QAM / OFDM**；
> 12 类 `contract_target_12()` 仅预留，不冒充真实模型输出。置信度是 MOCK 旋转 softmax（已归一化 sum=100%）。
> Top-1、状态带、Top-5、All Classes 高亮来自**同一份归一化概率向量**，天然一致。

**PASS**：① `PHASE2_UI_PASS` 打印（软件门：版本/寄存器写读回 OK + 首帧 staging→标量提交→翻页）；② 三页文字清晰可读；
③ Top-1 与其置信度条动画无撕裂；④ 置信度 sum=100% 且 Top-1 各页一致。
**FAIL**：文字缺失/错位、花屏、撕裂、冻屏、任何 `[DFB] FAIL` 或 **SIGBUS**。

---

## 7. 阶段 3 — USB 触摸检测/校准/页面切换（门 5）

> **硬件已确认**：7" IPS 触摸屏（原生 1024×600），触摸走 **touch 口 USB → 板子 USB host**（USB HID）。
> 屏的 touch 口 USB 线**同时供电+触摸**；**不要按屏的 POWER 键**（按了=关机）。
> 程序会自动适配单点触摸（`BTN_TOUCH`）与多点协议 B（`ABS_MT_TRACKING_ID`）两种 USB HID 上报方式；
> 触摸设备通过**枚举 `/dev/input/event*`** 自动发现（不硬编码 event 编号），要求名字关键字 + ABS 能力双命中。

```
cd /tmp/hdmi_v3_sw
./build_on_board.sh run phase3 30      # 检测并标定触摸，等待点击翻页（Ctrl-C 停）
```

**期望输出**：先打印 USB 拓扑与 input 设备列表，然后：
- 找到触摸：`TOUCH_FOUND path=/dev/input/eventX name=...` → `TOUCH_AXIS X=[..] Y=[..]` → 打印线性标定公式 → `PHASE3_PS_READY`，等待触摸。
- 找不到触摸：打印 `PHASE3_TOUCH_FAIL: no touch device found ...` 并以**非零码退出**（**不假 PASS、不自动翻页**）。

**手势（有触摸时，画的是三页识别 UI）**：点顶部三个标签 = 直接跳对应页（命中区域 `hit-region=tab (page 0/1/2)`）；点其余区域 = 下一页（`hit-region=next-page`）。
每次点击打印 `[3-PS] tap screen=(...) hit-region=... page -> ...`；第一次成功点击即打印 `PHASE3_TOUCH_PASS`。

**PASS**：① `TOUCH_FOUND` + 标定公式打印清楚；② 至少一次点击成功走通「点击→坐标→命中区域→翻页」并打印 `PHASE3_TOUCH_PASS`；
③ 页面内容/高亮正确切换、无撕裂。
**FAIL**：`PHASE3_TOUCH_FAIL`（找不到触摸设备，非零退出）；或点击后页面切换撕裂/错乱。

> 若 `PHASE3_TOUCH_FAIL`：先检查 touch 口 USB 线是否插到板子 USB host、屏是否亮（USB 供电）；
> 再 `dmesg | grep -i -E 'usb|input|hid'` 看枚举；`ls /dev/input/event*` 看设备节点。
> 本阶段判 FAIL（不假 PASS），修好接线后重跑。

---

## 8. 验收门链与状态声明规则（必须遵守）

1. 每个阶段独立验收：**静态帧 PASS → 动态双缓冲 PASS → 稳定性 PASS → 完整 UI PASS → 触摸 PASS**。
2. 任一阶段 FAIL：**立即停**，收集证据（见下），先定位再继续；**不得跳阶段、不得把后续阶段标 PASS**。
3. 状态词汇：实机验证前一律 `READY-FOR-HARDWARE-TEST`；只有你实测满足"PASS 判据"才由**你**标记 PASS。

**证据收集（每阶段 PASS/FAIL 都要留）**：程序完整 stdout 存 `*.log`；屏幕照片/录像（1C 留 ≥10 分钟段）；
led 状态；JTAG 脚本完整输出；`_disable_icap.bit` 的 `sha256sum` 结果。

---

## 9. 安全回滚

- 任何异常：**先 SW8 断电再上电**，板子回到默认启动流程，PL 位流（易失）消失，无 Flash 改动。
- 全程只有 `program_hw_devices`（volatile），**永不写 Flash**。

---

## 10. 故障排查速查

| 症状 | 最可能原因 | 检查 |
|---|---|---|
| led[0] 不亮 | 时钟/PS7 PLL 未锁或位流未加载 | 200MHz 晶振 C8/C7；JTAG 是否 `LOAD_COMPLETE`；PART 是否 `xc7z030` |
| 有画面但位置/颜色错 | `fb>>3` 或 720p 时序 | 程序打印的 `FB0`、`0x54` 写值；`read_len=230400` |
| 1B/2/3 撕裂 | 双缓冲索引同步 | v2 位流是否真加载（不是 1A 单缓冲）；`read_addr_1=camera_rd_addr+230400` |
| `[DFB] FAIL: open /dev/mem` 或 `/dev/udmabuf0` | 权限 / u-dma-buf 未加载 | `sudo`；`ls /dev/udmabuf0`、`cat /sys/class/u-dma-buf/udmabuf0/phys_addr` |
| 全黑 | 复位/display_en/HP 读 | `frame_ctrl` 复位；`0x40080054` 写对 |
| 3 阶段无触摸 | touch 线没插好 / USB HID 未就绪 | 看 `PHASE3_TOUCH_FAIL` 与 USB 拓扑；查接线与 `dmesg | grep -i hid` |
