# BOARD_TEST_39E5.md — 任务 39e5 上板验证权威指南

> 目录：`hdmi_framebuffer_ui_v4_fix`（独立修复目录，不覆盖 v2/v3）。
> 状态：**`READY-FOR-HARDWARE-RETEST`**。已定位并修复 Release(-O2) SIGBUS（纯软件层，见 §5A），待 -O2 上板复测：Phase2/3 无 SIGBUS + 显示/触摸正常后，才由**你**标 `HARDWARE_PASS`。本文是**唯一权威上板指南**（39e5 以此为准，`MASTER_MANUAL.md` 仅作阶段模型参考）。
> **红线**：只临时 JTAG 加载（volatile），**永不写 Flash**；只加载 `*_disable_icap.bit`，**绝不加载原始 `.bit`**。
> **状态词**：软件修复 + 主机验证通过 = `READY-FOR-HARDWARE-RETEST`；只有你以 **-O2** 上板实测满足"PASS 判据"（无 SIGBUS + 显示/触摸正常）才由**你**标 `HARDWARE_PASS`。我（AI）不碰板、不写 Flash、不操作开发板。

---

## 1. 唯一有效上板位流（务必先校验 SHA）

| 项目 | 值 |
|---|---|
| **上板位流（绝对路径）** | `F:/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit` |
| 文件大小 | **5,980,619 B** |
| **SHA-256（完整）** | `df8a0c669812835f7e6698ae0db0bb8524e6681bb211dfd1255bffe4ad1551b7` |
| FMSH IP patch | `53180205`（证据 `fpga/logfiles/procise.log`，行 `IP Patch version: 53180205`） |

> ⚠️ 上板前先在本机校验（Windows Git Bash）：
> `cd /f/FPGA_Work/hdmi_framebuffer_ui_v4_fix && sha256sum fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit`
> 结果必须与上表 SHA-256 **逐字符一致**，否则**立即停**，不得加载。
> 原始 `.bit`（5,980,035 B，`9282f98a…`）是构建产物，**不上板**。
> 此前 `write_bitstream_manual.tcl` 生成的 `0XFFFFFFFF` 位流已作废（`REVOKED_DO_NOT_PROGRAM`），见 `deprecated_manual_no_patch/README.md`，**严禁加载**。

---

## 2. 硬件接线顺序（板断电状态下接线）

**先断电（SW8 拨下），再接所有线，最后上电。** 顺序：

1. **12V DC 电源 → J37**（先不接，或接好但不上电）。
2. **PL JTAG 下载线 → 20 针 U19**（⚠️ 是 PL JTAG **U19**，不是 PS JTAG **U18**）。
3. **HDMI 线**：板子 PL 侧 **pHDMI 输出口 → 7" 屏的 HDMI 口**（直接接，无需按屏上任何键）。
4. **触摸/供电 USB 线**：屏的 **touch 口** → **板子 USB host 口**（同一根线同时给屏供电 + 传触摸 USB HID）。
5. **串口线（或网口）**：接板载 Linux 的**调试串口**（登录用；若有网口 SSH 则按官方方式）。
6. 全部接好后 **SW8 上电**。

### 各线缆是否必需

| 线缆 | 必需？ | 用途 |
|---|---|---|
| 12V 电源（J37） | **必需** | 板子供电 |
| PL JTAG（U19，20 针） | **必需** | 临时加载 `_disable_icap.bit` |
| HDMI（pHDMI） | **必需** | 显示输出（PASS/FAIL 主判据） |
| 触摸/供电 USB | Phase 1B/2 **不需要**；**Phase 3 必需** | 屏供电 + 触摸（但屏供电其实靠 USB，若屏不亮需接） |
| 串口（或 SSH） | **必需** | 登录 Linux 跑 PS 程序、看打印 |

> 屏 POWER 键**不要按**：USB 上电自动开机，按 POWER=关机。

---

## 3. 临时 JTAG 加载（Vivado 2020.2 Hardware Manager，逐步）

**用 Vivado 2020.2 只做下载**（构建用 2018.3，两者不同）。板已上电、PL JTAG U19 已接。

1. 打开 Windows 终端，执行（**一次性，脚本自动完成加载与校验**）：

   ```
   D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/program_phase1b_jtag.tcl
   ```

2. 脚本会依次打印（关键行）：
   - `HW_DEVICE_COUNT=2`（链上两个器件：`arm_dap_0` 的 PS DAP + `xc7z030_1` 的 FPGA）。
   - `HW_DEVICE=arm_dap_0 PART=...`（PART **不含** xc7z030 → 被**忽略**）。
   - `HW_DEVICE=xc7z030_1 PART=xc7z030...`（PART **含** xc7z030 → 被选中）。
   - `FPGA_DEVICE_COUNT=1`（**必须恰 1**，否则脚本报错退出，不可能误编程）。
   - `PROGRAMMING_PART=xc7z030...`（确认选中的是 FPGA，不是 ARM DAP）。

3. **如何确认选了 xc7z030 而非 ARM DAP**：看到 `FPGA_DEVICE_COUNT=1` 且 `PROGRAMMING_PART=...xc7z030...`，即确认。脚本逻辑是**枚举全部器件、只保留 PART 匹配 `*xc7z030*` 的那个**，`arm_dap_0`（PS DAP）因 PART 不含 xc7z030 被自动排除。

4. **Program Device 成功判据**（三条同时满足）：
   - `PROGRAMMING_COMMAND_COMPLETE`
   - `HW_DEVICE_DONE=1`（真实 DONE 状态寄存器，非易错的 `PROGRAMMED` 属性）
   - `PHASE1B_JTAG_LOAD_COMPLETE`

5. **加载后灯态判据**：`led[0]`（引脚 **J1**）**常亮**（MMCM1&2&3 + PS7 PLL 全锁定）；`led[1]`（引脚 **M6**）约每 1.8 秒翻转一次（74.25MHz/2^27≈0.55Hz）。

> **明确：不写 Flash。** 全程只有 `program_hw_devices`（volatile，断电即还原 PL 到默认启动流程），**永不 `program_flash` / 不写 QSPI / 不改 Flash 内容**。

---

## 4. 串口登录 Linux

板载 Linux 起好后，用**调试串口（或网口 SSH）**登录（登录方式/波特率沿用官方 demo，本文不另造）。登录后确认：

```
uname -a                       # 确认 aarch64 Linux
ls /dev/udmabuf0               # 帧缓冲设备
cat /sys/class/u-dma-buf/udmabuf0/phys_addr
cat /sys/class/u-dma-buf/udmabuf0/size
```

三者都要存在（`/dev/udmabuf0`、phys_addr、size），否则 PS 程序会 FAIL（提示先加载 u-dma-buf）。

---

## 5. 板端软件传输 / 编译 / 运行

**传输**（本机 Windows → 板子，`<board>` 换成板子 IP/主机名）：

```
scp -r sw <board>:/tmp/hdmi_39e5_sw/
ssh <board>
cd /tmp/hdmi_39e5_sw
```

**编译**（二选一）：

```
./build_on_board.sh                 # CMake 构建（首选）
# 若 CMake 不可用：
./build_on_board.sh g++             # 直接 g++ 编译（仅 libc，无 iCraft/NPU 依赖）
```

**运行**（每个测试的具体命令见下；程序需 root，因为要 mmap `/dev/mem`）：

```
./build_on_board.sh run <phase> [args]
```

---

## 5A. 软件修复：Release(-O2) SIGBUS 根因 + 复测要求（本次变更核心）

**背景**：上一版 Release(-O2) 上板，Phase2/Phase3 **立即 SIGBUS（rc=135）**；改 -O0 能跑。根因：GCC -O2 自动向量化把"非 volatile `uint16_t*` 直写 u-dma-buf mmap"变成 **NEON/SIMD 宽存储**，该映射拒绝宽写 → SIGBUS。（DDR 64→16 的硬件修复本身有效，与此无关。）

**修复（仅改 PS 软件；RTL/XDC/位流未动、未重新生成位流）**：
- 后端 `direct_framebuffer_backend` 新增**普通内存 staging 缓冲**：所有 Phase 程序把 UI 画进 staging（向量化无害），再统一走**唯一设备写路径** `submit_frame(frame_index, staging_data, pixel_count)`。
- `submit_frame()` 严格顺序：校验 `frame_index`/`pixel_count` → `volatile uint16_t*` 逐元素标量写 → `flush()`(msync + sync 节点，确认成功) → **最后**才切换显示缓冲寄存器；禁止在提交/同步完成前翻页（防撕裂/半帧）。
- 强制标量：函数加 `noinline` + `optimize("no-tree-vectorize","no-tree-slp-vectorize")` + `volatile` 三保险；应用层**拿不到**非 volatile mmap 指针。
- 覆盖 **Phase1B/1C/2/3**，全部走同一 submit 路径。

**AArch64 objdump 证据（无宽存储）**：`sw/objdump_evidence/submit_frame_aarch64_disasm.txt` —— 提交循环只有 `ldrh`（16-bit 读 staging）+ `strh`（16-bit 标量写设备），**无 st1/st2/st3/st4/str q/str d**；全文见 `submit_frame_aarch64_full.txt`。

**主机验证（已过）**：`test_direct_framebuffer_backend` 全 PASS（含越界 / 帧大小 / frame_index / 金丝雀 canary 测试）；ASan/UBSan 全 PASS；四个 Phase 程序 -O2 -Wall -Wextra 编译干净。

**权威编译（务必 -O2）**：CMake 的 `Release` 会落到 -O3，**复测请用显式 -O2 的 g++ 回退**：

```
./build_on_board.sh g++      # g++ -std=gnu++17 -O2 -Wall -Wextra …（权威 -O2 构建）
```

**复测命令 + 判据**（每步都必须是 **-O2 构建**；任一步 SIGBUS/崩溃/显示异常即 STOP）：

| 步骤 | 命令（root，-O2 构建） | PASS 判据 |
|---|---|---|
| R1 动态双缓冲 | `./build_on_board.sh run phase1b 0 60` | 打印 `PHASE1B_PS_PASS`；**无 SIGBUS**；竖条平滑 ≥1min 无撕裂 |
| R2 静态 UI | `./build_on_board.sh run phase2 0 20` | 打印 `PHASE2_UI_PASS`；**无 SIGBUS**；文字 ≥scale2 清晰可读、无镜像/错位 |
| R3 动态 UI | `./build_on_board.sh run phase2 -1 20` | `PHASE2_UI_PASS`；**无 SIGBUS**；Top-1 轮换无撕裂、文字清晰 |
| R4 触摸 | `./build_on_board.sh run phase3 30` | `TOUCH_FOUND` + 标定公式；点击翻页走通 `PHASE3_TOUCH_PASS`；**无 SIGBUS** |

> **字号修复（本次一并）**：去掉 scale=1；类名/状态栏/百分比 ≥ scale=2，标题 scale=3，边框 2px；经 1024×600 降采样后仍清晰；避免过细单像素线。Phase3 触摸页本就用 scale≥5 大数字，无需改。

---

## 6. 测试 0 — 位流加载成功 + 信号（先于一切 PS 程序）

跑任何 PS 程序前，先确认：屏**有 HDMI 信号**（屏不显示"无信号"）、`led[0]` 常亮、`led[1]` 慢闪。
此时 DDR 尚未被 PS 写入，屏可能显示**噪点/黑屏/随机色**——这是**正常**的（不是 FAIL），因为 PL 读的是未初始化的 DDR。

**PASS**：屏有信号、两 LED 状态正确、JTAG 日志三条成功判据齐。
**FAIL**：屏无信号 / led[0] 不亮 / JTAG 日志缺成功判据 → **立即停**，先查接线与位流 SHA。

---

## 7. 测试 1 — 静态诊断图案（39e5 基础稳定检查）

**命令**（渲染 1 帧静态竖条后定格）：

```
./build_on_board.sh run phase1b 1 60
```

**期望画面**：屏幕显示**一条 40px 宽白色竖条（在左部）+ 深色背景**，**静止、边界锐利、无闪烁、无花屏、无密集竖条纹理**。

**PASS**：静态画面稳定、竖条边界清晰锐利、无花屏/噪点纹理；程序打印 `PHASE1B_PS_PASS`。
**FAIL**：花屏、竖条边界呈密集细竖条/锯齿纹理、画面闪烁 → **立即停**。

> ⚠️ **39e5 专项提示（重要）**：此静态竖条宽 40px（4 的倍数）且左边界 4 像素对齐，
> **对"4 像素组内逆序"不敏感**（组内 4 像素同色，逆序不变）。这是历史"误 PASS"的盲区之一。
> 因此**"4 像素顺序正确"的权威肉眼判据在测试 3（Phase 2 静态 UI 的 5×7 文字点阵）**，见 §10。
> 本步只负责验证"静态图案稳定、信号正常、无花屏"。

---

## 8. 测试 2 — Phase 1B 双缓冲动态（无撕裂）

**命令**：

```
./build_on_board.sh run phase1b 0 60     # 移动竖条，永久，60fps（Ctrl-C 停）
```

**期望画面**：深色底上一条白色竖条**从左向右平滑移动**，边界锐利。

**PASS（全满足）**：
1. 打印 `PHASE1B_PS_PASS`（版本/对齐/容量/读回全过，软件门）。
2. 白色竖条平滑移动、边界锐利。
3. 连续观察 **≥1 分钟无撕裂**（竖条无水平断裂/错位）、无冻屏。
4. `led[0]` 常亮、`led[1]` 慢闪。

**FAIL（任一即停）**：任一条 `[DFB] FAIL`/`FAIL` 打印；竖条水平撕裂/错位；画面冻住；读回≠写入。

---

## 9. 测试 3 — Phase 2 静态 UI（固定 Top-1；**4 像素顺序权威判据**）

**命令**：

```
./build_on_board.sh run phase2 0 20      # 固定 Top-1（静态 UI），20fps
```

**期望画面**：
- 顶部标题 `RF SIGNAL RECOGNITION`；
- 状态行 `SNR / TOP-1 / CONF / LAT / FRAME`；
- 中部 10 个分类行（**AM-DSB / WBFM / 2FSK / GFSK / BPSK / QPSK / 8PSK / 16QAM / 64QAM / OFDM**），每行一条置信度条 + 百分比；
- 底部 `RESULT >` 高亮 Top-1 类名。

**PASS**：① 打印 `PHASE2_UI_PASS`；② 标题/状态/分类行**文字清晰可读（无镜像、无错位）**；③ 10 类名与百分比显示正确（置信度 sum=100%）；④ 边框/置信度条位置正确、无撕裂。
**FAIL**：文字缺失/**镜像错乱**/错位、花屏、撕裂、冻屏 → **立即停**。

> ⚠️ **这是"四像素顺序"的核心肉眼判据**：5×7 文字点阵是**逐像素**变化的，若 DDR 64→16 的
> 4 像素仍逆序，每个 4 像素组内会左右镜像，文字会**明显错乱/镜像**；置信度条与边框也会出现
> 每 4 像素周期的细竖条错位。文字清晰可读 = 四像素顺序正确（根因 A 修复生效）。

---

## 10. 测试 4 — Phase 2 动态 UI（Top-1 轮换）

**命令**：

```
./build_on_board.sh run phase2 -1 20     # 动态度：Top-1 每 ~2s 轮换，20fps
```

**期望画面**：同测试 3 的完整 UI，但 **Top-1 类名/高亮框/置信度条动画轮换**，全程无撕裂。

**PASS**：① `PHASE2_UI_PASS`；② Top-1 轮换平滑、与其置信度条动画一致；③ 无撕裂/闪烁/冻屏；④ 文字始终清晰可读。
**FAIL**：Top-1 与其置信度条不一致、撕裂、花屏、文字错乱 → **立即停**。

---

## 11. 测试 5 — Phase 3 触摸（检测/校准/翻页）

> 前置：屏 touch 口 USB 已接板子 USB host（同一根线供电+触摸），屏已亮。

**命令**：

```
./build_on_board.sh run phase3 30         # 检测并标定触摸，等待点击翻页（Ctrl-C 停）
```

**期望输出**：
- 找到触摸：`TOUCH_FOUND path=/dev/input/eventX X=[..] Y=[..]` → 打印线性标定公式 → `PHASE3_PS_READY` 等待触摸。
- 找不到触摸：`PHASE3_TOUCH_FAIL: no touch device found ...` 并**非零退出**（不假 PASS、不自动翻页）。

**手势**：点底部 80px 标签栏 = 选页 1/2/3（`hit-region=tabN`）；点其余区域 = 下一页（`hit-region=next-page`）。

**PASS**：① `TOUCH_FOUND` + 标定公式清晰；② 至少一次「点击→坐标→命中区域→翻页」走通并打印 `PHASE3_TOUCH_PASS`；③ 页面数字/颜色/图案正确切换、无撕裂。
**FAIL**：`PHASE3_TOUCH_FAIL`（非零退出）；或点击后翻页撕裂/错乱 → **立即停**，查 touch USB 接线。

---

## 12. 39e5 专项验证重点（逐条对照）

| 关注项 | 判据 | 对应测试 |
|---|---|---|
| DDR 64-bit → RGB565 四个 16-bit 像素顺序正确 | Phase 2 UI 文字清晰、无镜像/错位 | 测试 3 |
| 无 4 像素组反转 | 文字点阵/置信度条无每 4 像素周期镜像 | 测试 3/4 |
| 无原始"密集竖条"或 UI 错位 | 无密集细竖条纹理；UI 文本/边框/概率条位置正确 | 测试 1/3 |
| 无 SIGBUS（-O2） | -O2 构建下程序不打印 `SIGBUS`/不崩溃退出（rc=135 即 SIGBUS）；`PHASE1B_PS_PASS` 等正常打印 | 测试 1/2/3/4 |
| 静态图案稳定 | 测试 1 静态竖条稳定、无花屏 | 测试 1 |
| 双缓冲动态无可见撕裂 | 测试 2/4 移动竖条与 UI 动画无水平断裂 | 测试 2/4 |
| UI 文本/边框/概率条位置正确 | 测试 3 布局正确、置信度 sum=100% | 测试 3 |

---

## 13. 失败即停 + 每种故障收集什么

**规则：任一阶段 FAIL 立即 STOP，不跳阶段、不把后续阶段标 PASS。** 每阶段 PASS/FAIL 都要留证据。

| 症状 | 收集哪些日志/照片 |
|---|---|
| **花屏** | 屏幕**照片/录像**；程序完整 stdout（存 `.log`）；`dmesg` 尾部；位流 `sha256sum` 结果 |
| **四像素顺序错误（文字镜像/密集竖条）** | Phase 2 UI **高清照片**（重点拍文字与置信度条）；程序 stdout；`sha256sum` |
| **黑屏** | 屏是否"无信号"照片；`led[0]/led[1]` 状态照；JTAG 完整输出（`HW_DEVICE_DONE` 是否=1）；`frame_ctrl` 寄存器打印（`FB0`、`0x54` 写值） |
| **SIGBUS** | 程序 stdout 完整（含崩溃信号行）；`uname -a`、`dmesg` 尾部；是否用 `./build_on_board.sh` 而非手改编译选项 |
| **撕裂** | 移动竖条/UI 动画**录像**（慢动作更好）；程序 `frame=` 心跳日志 |

统一采集：`sw/collect_logs.sh <phase> [程序stdout.log]`（板上自动收 system/dmesg/USB/input/binary.sha256/bitstream.sha256）。

---

## 14. 安全回滚

任何异常：**先 SW8 断电再上电**，板回到默认启动流程，PL 位流（易失）消失，**无 Flash 改动**。全程只有 `program_hw_devices`（volatile），**永不写 Flash**。

---

## 15. 逐阶段 PASS/FAIL 汇总

> ⚠️ **软件修复后，所有 Phase 程序必须用 -O2 构建**（`./build_on_board.sh g++`，见 §5A）再复测；
> 复测四步 R1–R4 的命令/判据见 §5A。下方为完整步骤链。

| 步骤 | 命令 | 核心判据 |
|---|---|---|
| 0 加载成功 | （JTAG 脚本） | `PROGRAMMING_COMMAND_COMPLETE` + `HW_DEVICE_DONE=1` + `PHASE1B_JTAG_LOAD_COMPLETE`；led[0] 常亮 |
| 1 静态诊断 | `run phase1b 1 60` | 静态竖条稳定、无花屏 |
| 2 动态双缓冲 | `run phase1b 0 60` | `PHASE1B_PS_PASS` + 移动竖条 ≥1min 无撕裂 |
| 3 静态 UI | `run phase2 0 20` | `PHASE2_UI_PASS` + 文字清晰/布局正确（**4 像素顺序判据**） |
| 4 动态 UI | `run phase2 -1 20` | Top-1 轮换无撕裂、文字清晰 |
| 5 触摸 | `run phase3 30` | `PHASE3_TOUCH_PASS` + 翻页正确 |
| （可选）1C 稳定性 | `run phase1c 600 60` | ≥10min 无异常、`PHASE1C_PS_PASS` |
