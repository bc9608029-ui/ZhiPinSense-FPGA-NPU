# BOARD_TEST_39E5C.md — 任务 39e5c（v5_visual）上板验证权威指南

> 目录：`hdmi_framebuffer_ui_v5_visual`（**独立软件目录**，不改 v4_fix / v2 / v3 / NPU / 模型工程）。
> 状态：**`READY-FOR-HARDWARE-VISUAL-RETEST`**。已确认 Style A（现代科研仪器风）设计稿、完成像素级一致的 C++ RGB565 实现 + 主机 14 张截图全对；待 **-O2** 上板复测：Phase2/3 无 SIGBUS + 抗锯齿文字平滑、三页统一、状态徽标右对齐、触摸翻页正常后，才由**你**标 `HARDWARE_VISUAL_PASS`。
> **红线**：只临时 JTAG 加载（volatile），**永不写 Flash**；只加载 `*_disable_icap.bit`，**绝不加载原始 `.bit`**；我（AI）不碰板、不写 Flash、不操作开发板。
> **位流/JTAG/接线复用 v4_fix**（本目录只有 PS 软件，位流与 FPGA 工程未动、未重新生成）。

---

## 1. 唯一有效上板位流（沿用 v4_fix，先校验 SHA）

| 项目 | 值 |
|---|---|
| **上板位流（绝对路径）** | `F:/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit` |
| 文件大小 | **5,980,619 B** |
| **SHA-256（完整）** | `df8a0c669812835f7e6698ae0db0bb8524e6681bb211dfd1255bffe4ad1551b7` |
| FMSH IP patch | `53180205`（证据 `v4_fix/fpga/logfiles/procise.log`） |

> ⚠️ 上板前先在本机校验（Windows Git Bash）：
> `cd /f/FPGA_Work/hdmi_framebuffer_ui_v4_fix && sha256sum fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit`
> 必须与上表 **逐字符一致**，否则**立即停**。原始 `.bit`（5,980,035 B，`9282f98a…`）**不上板**。
> 旧 `0XFFFFFFFF` 位流已 `REVOKED_DO_NOT_PROGRAM`（见 `v4_fix/deprecated_manual_no_patch/README.md`），**严禁加载**。
> **本目录不含 fpga/ 工程与位流**——软件重构不重生成位流，一切以 v4_fix 的 `_disable_icap.bit` 为准。

---

## 2. 硬件接线顺序（板断电状态下接线；与 v4_fix 完全一致）

**先断电（SW8 拨下）→ 接所有线 → 最后上电。**

1. **12V DC 电源 → J37**。
2. **PL JTAG 下载线 → 20 针 U19**（是 PL JTAG **U19**，不是 PS JTAG U18）。
3. **HDMI**：板子 PL 侧 **pHDMI 输出 → 7" 屏 HDMI 口**（直接接，不按屏上任何键）。
4. **触摸/供电 USB**：屏 **touch 口 → 板子 USB host 口**（同根线给屏供电 + 传触摸 USB HID；Phase 1B/2 可暂不接，Phase 3 必需）。
5. **串口（或网口）**：接板载 Linux 调试串口（登录用）。
6. 全部接好后 **SW8 上电**。

> 屏 POWER 键**不要按**：USB 上电自动开机，按 POWER=关机。

---

## 3. 临时 JTAG 加载（Vivado 2020.2 Hardware Manager；脚本在 v4_fix）

板已上电、PL JTAG U19 已接。用 **Vivado 2020.2 只做下载**（构建用 2018.3）。

```
D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/program_phase1b_jtag.tcl
```

**Program Device 成功判据**（三条同时满足）：
- `PROGRAMMING_COMMAND_COMPLETE`
- `HW_DEVICE_DONE=1`（真实 DONE 状态寄存器，非 `PROGRAMMED` 属性）
- `PHASE1B_JTAG_LOAD_COMPLETE`

（脚本已做器件过滤：只保留 `PART` 匹配 `*xc7z030*` 的 FPGA，`arm_dap_0` 自动排除。）

**加载后灯态**：`led[0]`（引脚 **J1**）**常亮**（MMCM1&2&3 + PS7 PLL 全锁）；`led[1]`（引脚 **M6**）约每 1.8s 翻转一次。

> **明确：不写 Flash。** 全程只有 `program_hw_devices`（volatile），**永不 `program_flash`**。

---

## 4. 串口登录 Linux

板载 Linux 起好后登录，确认三样存在：

```
uname -a
ls /dev/udmabuf0
cat /sys/class/u-dma-buf/udmabuf0/phys_addr
cat /sys/class/u-dma-buf/udmabuf0/size
```

三者缺一即 FAIL（PS 程序会提示先加载 u-dma-buf，需 root）。

---

## 5. 板端软件传输 / 编译 / 运行

**传输**（本机 → 板子，`<board>` 换成板子 IP/主机名）：

```
scp sw/hdmi_v5_visual_sw.tar.gz <board>:/tmp/
ssh <board>
mkdir -p /tmp/hdmi_v5_visual && cd /tmp/hdmi_v5_visual
tar xzf /tmp/hdmi_v5_visual_sw.tar.gz
sha256sum -c SHA256SUMS.txt        # 先校验，全部 OK 再继续
```

**编译（权威 -O2，务必用 g++ 回退；CMake Release 会落 -O3，勿用）**：

```
./build_on_board.sh g++             # g++ -std=gnu++17 -O2 -Wall -Wextra（权威 -O2 构建）
```

**运行**（需 root；`<phase>` ∈ `phase1b|phase1c|phase2|phase3`）：

```
./build_on_board.sh run <phase> [args]
```

---

## 5A. 本次变更核心：5×7 点阵 → 抗锯齿 DejaVu 字图集 + Style A UI（纯软件）

**相对 v4_fix 改了哪些**：
- **字体**：5×7 点阵 → 离线预栅格化的 DejaVu Sans（Regular/Bold/Mono）**8-bit 灰度覆盖率图集**（`font_atlas_data.cpp`，ASCII 32..126 共 95 字模；固定 20/28/40/52px + 粗体 24px，**无板上 FreeType、无运行时缩放**）。板端只做 RGB565 逐通道整数 alpha blend：`dst = (dst*(255-a) + fg*a + 127) >> 8`。
- **UI 层级**（Style A，现代科研仪器风）：结果/置信度/状态优先 → 10/12 类概率两列卡 → SNR/延迟/帧/源 → 底部导航；状态一律「文字+形状+颜色」（MOCK/LIVE/STALE/ERROR）；三页（Main/Diagnostics/Touch）同一视觉语言；底部导航 90px（≥72px，命中 ≥60px）；所有文字对比度 ≥4.5:1；无阴影/模糊/渐变/透明层。

**完全未改（与 v4_fix 逐字节一致，SHA 相同）**：
- `direct_framebuffer_backend.cpp/.hpp`（`submit_frame()` 唯一设备写路径 = `volatile uint16_t*` 标量 `strh`，无宽存储；AArch64 objdump 证据在 `sw/objdump_evidence/`，与 v4_fix 相同哈希）。
- `phase1b_doublebuf_test.cpp`、`phase1c_dynamic_test.cpp`、`test_direct_framebuffer_backend.cpp`、`collect_logs.sh`（哈希与 v4_fix 一致）。
- 触摸解析（枚举/ABS/多协议-B/标定/命中区域/翻页链），仅底导航命中高度 80px→90px 以匹配新导航布局。
- RTL/XDC/位流/寄存器/DDR 布局/双缓冲。

**主机验证（已过，无板）**：
- `host_screenshot.cpp`（-O2 -Wall -Wextra 零告警）用**与板端完全一致**的图集+blend 渲染 14 张 1280×720 BMP（Main/Diag/Touch × normal/lowconf/stale/error + 12 类目标 + 状态图例），`sw/tools/convert_host_out.py` 转 PNG + 1024×600 BILINEAR 模拟缩放 + `sw/host_out/index.html` 画廊。
- 与已确认 Style A 设计稿（`design_mockups/output/style_A/`，565 空间对齐）逐像素比对 **mean ≤ 0.03、max = 9**（仅 AA 边缘 `//255` vs `>>8` 舍入差，不可见）。
- `test_direct_framebuffer_backend` 主机 mock 测试全 PASS（退出 0）。
- `test_ui_render` 主机渲染测试全 PASS（8/10/12/16 类边界、文字/图标不重叠、Error 页导航存在、Mock 不冒充 Live）。
- 12 类在 1280×720 与 1024×600 均完整显示（程序化验证：12 张卡片全部渲染、底部两行不裁切、不溢出信息条）；契约标签为 `GFSK`（非 `GFSK/GMSK`）。
- 参考画廊：浏览器打开 `design_mockups/index.html`（A/B/C 三套）与 `sw/host_out/index.html`（C++ 实际渲染）。

**四像素顺序权威判据已升级**：v4_fix 用 5×7 点阵逐像素判镜像；本版用**抗锯齿字图集**判——AA 边缘是**逐像素**覆盖率变化，比 5×7 更敏感。文字平滑无镜像/无花屏 = 四像素顺序正确。

---

## 5B. 六项视觉/语义修复（2026-10-05，Style A 方向确认后）

| # | 修复 | 实现 |
|---|---|---|
| 1 | 状态图形放文字**左侧**、留 **≥10px 间距**，不覆盖 LIVE/STALE/ERROR/MOCK | `status_badge_shape_cx()`（几何单一来源）；C++ 与 `make_mockups.py` 同步 |
| 2 | Phase2 演示必须显示 **MOCK/MOCK**（禁止 LIVE/SDR） | `phase2_ui_render.cpp` / `phase3_touch_test.cpp` 演示状态 `Mock`+`MOCK` |
| 3 | 12 类在 1280×720 与 1024×600 **完整显示**，修复底部两行裁切；`GFSK/GMSK`→`GFSK` | `card_grid()` 自适应两列网格（8..16 类不溢出信息条）；`CLASSES_12[5]="GFSK"` |
| 4 | Error 页**保留信息栏 + 底部导航**，可进 Diagnostics/Touch | `render_main` Error 分支去掉提前 `return`，补 `draw_info_strip`+`draw_nav` |
| 5 | 新增 4 类测试 | `sw/test_ui_render.cpp`（8/10/12/16 边界、文字/图标不重叠、Error 导航存在、Mock 不可冒充 Live） |
| 6 | 重生成 1024×600 截图、软件包、SHA | `host_screenshot`→`convert_host_out.py`；`hdmi_v5_visual_sw.tar.gz` + `SHA256SUMS.txt` |

> **红线不变**：未改 `backend`/`submit_frame`/RTL/XDC/位流；修复后状态仍 `READY-FOR-HARDWARE-VISUAL-RETEST`。

---

## 6. 测试 0 — 位流加载成功 + 信号（先于一切 PS 程序）

先确认屏**有 HDMI 信号**（不显示"无信号"）、`led[0]` 常亮、`led[1]` 慢闪。此时屏可能**噪点/黑屏/随机色**——**正常**（PL 读未初始化 DDR，不是 FAIL）。

---

## 7. 测试 1 — 静态诊断图案（回归，未改）

```
./build_on_board.sh run phase1b 1 60
```

**PASS**：静态竖条稳定、边界锐利、无花屏；打印 `PHASE1B_PS_PASS`。
> 注：静态 40px 竖条对"4 像素组内逆序"不敏感；**四像素顺序权威判据在测试 3（AA 文字）**。

---

## 8. 测试 2 — Phase 1B 双缓冲动态（回归，未改）

```
./build_on_board.sh run phase1b 0 60
```

**PASS**：`PHASE1B_PS_PASS`；白色竖条平滑移动、边界锐利、**≥1min 无撕裂**、无冻屏。

---

## 9. 测试 3 — Phase 2 静态 UI（Style A；**四像素顺序 + 抗锯齿权威判据**）

```
./build_on_board.sh run phase2 0 20       # 固定 Top-1（AM-DSB），20fps
```

**期望画面（Style A）**：
- 顶部标题 `RF SIGNAL RECOGNITION`（大号抗锯齿）+ 右上角 **MOCK 状态徽标**（灰色**空心方块**+文字 `MOCK`，形状在文字**左侧**、留 ≥10px 间距，右对齐、距右缘有留白、不贴边）。
- 结果卡（Top-1 类名 + 置信度 + 状态）→ 10 类概率两列卡（**AM-DSB / WBFM / 2FSK / GFSK / BPSK / QPSK / 8PSK / 16QAM / 64QAM / OFDM**）→ SNR/延迟/帧/源行 → 底部三栏导航。
- 深色背景（RGB≈15,20,27）、卡片圆角、置信度条为细色条。

**PASS**：① 打印 `PHASE2_UI_PASS`；② **文字抗锯齿平滑**（无 5×7 锯齿、无镜像/错位、无花屏）；③ 10 类名+百分比正确（和=100%）；④ 状态徽标 `MOCK`（空心方块+文字）右对齐、形状在文字左侧不重叠、颜色形状正确；⑤ 布局（结果卡→两列卡→指标→底部导航）层级正确、无撕裂。
**FAIL**：文字镜像/错乱、AA 边缘成密集细竖条纹理、花屏、徽标贴边错位、撕裂 → **立即停**。

> ⚠️ **四像素顺序核心判据**：AA 字图集逐像素变化；若 DDR 64→16 四像素仍逆序，每个 4 像素组内左右镜像，文字会明显错乱，AA 边缘会出现每 4 像素周期的细竖条。文字平滑清晰 = 根因 A 修复生效。
> 说明：板上 phase2 演示状态恒为 `Mock`（真实 SDR 才动态切状态）；`LIVE/STALE/ERROR` 三种徽标已由 `host_screenshot` 主机渲染 + 像素比对验证（`sw/host_out/png/`），板上只需验证 `MOCK`。

---

## 10. 测试 4 — Phase 2 动态 UI（Top-1 轮换）

```
./build_on_board.sh run phase2 -1 20      # 每 ~2s 轮换 Top-1，20fps
```

**PASS**：`PHASE2_UI_PASS`；Top-1 类名/结果卡/置信度条动画轮换平滑一致、无撕裂；文字始终抗锯齿清晰。

---

## 11. 测试 5 — Phase 3 触摸（检测/校准/翻页；三页 Style A）

> 前置：屏 touch 口 USB 已接板子 USB host，屏已亮。

```
./build_on_board.sh run phase3 30
```

**期望输出**：`TOUCH_FOUND path=/dev/input/eventX X=[..] Y=[..]` → 线性标定公式 → `PHASE3_PS_READY`。找不到触摸则 `PHASE3_TOUCH_FAIL` 非零退出（不假 PASS）。

**期望画面**：三页统一 Style A——点底部 90px 导航（tab1/2/3）直接跳页；点其余区域翻下一页（`hit-region=next-page`）；每次翻页打印 `hit-region=tabN|next-page` → `page -> N`。

**PASS**：① `TOUCH_FOUND` + 标定公式；② 至少一次「点击→坐标→命中区域→翻页」走通并打印 `PHASE3_TOUCH_PASS`；③ 三页风格统一、翻页无撕裂。
**FAIL**：`PHASE3_TOUCH_FAIL`（非零退出）或翻页撕裂 → **立即停**，查 touch USB 接线。

---

## 12. 39e5c 视觉专项验证重点（逐条对照）

| 关注项 | 判据 | 对应测试 |
|---|---|---|
| 文字抗锯齿平滑（优于 5×7） | AA 字边缘平滑、无 5×7 锯齿、无镜像/花屏 | 测试 3/4 |
| 三页视觉统一（Style A） | Main/Diag/Touch 同背景/卡片/配色/字体 | 测试 3/5 |
| 状态徽标「文字+形状+颜色」且形状在文字左侧 ≥10px | `MOCK` 灰色空心方块+文字，右对齐不贴边、形状不压文字；`LIVE/STALE/ERROR` 已主机验证 | 测试 3（+ 主机截图） |
| 12 类完整显示 + `GFSK` 契约 | 12 类两列卡在 1280×720/1024×600 完整、底部两行不裁切、标签为 `GFSK` | 主机截图 |
| Error 页保留信息栏 + 底部导航 | Error 主识别页仍有 SNR/延迟/帧/源 + 三栏导航 | 主机截图 |
| 主机渲染测试 | `test_ui_render` 8/10/12/16 边界、文字/图标不重叠、Error 导航、Mock 不冒充 Live 全 PASS | 主机 |
| 对比度 ≥4.5:1 | dim 次要文字（SNR/延迟/帧/源）在屏上清晰可读 | 测试 3 |
| 底部导航 ≥72px、命中 ≥60px | 底部三栏导航 90px，点击命中正确 | 测试 5 |
| 无 SIGBUS（-O2） | -O2 构建不打印 `SIGBUS`/不崩溃（rc=135 即 SIGBUS） | 测试 1/2/3/4/5 |
| 双缓冲无撕裂 | 移动竖条与 UI 动画无水平断裂 | 测试 2/4 |

---

## 13. 失败即停 + 每种故障收集什么

**规则：任一阶段 FAIL 立即 STOP，不跳阶段、不把后续标 PASS。** 每阶段留证据。

| 症状 | 收集 |
|---|---|
| 文字镜像/密集细竖条 | Phase 2 UI **高清照片**（重点拍文字与置信度条）；程序 stdout；位流 `sha256sum` |
| 文字锯齿/不清晰（5×7 状） | 照片；确认是否用 `./build_on_board.sh g++`（权威 -O2）而非误用旧二进制 |
| 徽标贴边/错位 | 右上角状态徽标高清照片；对照 `design_mockups/output/style_A/main_normal_1280.png` |
| 花屏/黑屏 | 屏照片；`led[0]/led[1]`；JTAG 输出（`HW_DEVICE_DONE` 是否=1）；`frame_ctrl` 打印 |
| SIGBUS | 程序完整 stdout（含崩溃信号行）；`uname -a`、`dmesg` 尾部 |
| 撕裂 | 移动竖条/UI 动画录像；`frame=` 心跳日志 |

统一采集：`./collect_logs.sh <phase> [stdout.log]`（板上自动收 system/dmesg/USB/input/binary.sha256/bitstream.sha256）。

---

## 14. 安全回滚

任何异常：**先 SW8 断电再上电**，板回默认启动流程，PL 位流（易失）消失，**无 Flash 改动**。全程只有 `program_hw_devices`（volatile），**永不写 Flash**。

---

## 15. 逐阶段 PASS/FAIL 汇总

> ⚠️ 所有 Phase 程序必须用 **-O2 构建**（`./build_on_board.sh g++`，见 §5A）。

| 步骤 | 命令 | 核心判据 |
|---|---|---|
| 0 加载成功 | （JTAG 脚本，v4_fix） | `PROGRAMMING_COMMAND_COMPLETE` + `HW_DEVICE_DONE=1` + `PHASE1B_JTAG_LOAD_COMPLETE`；led[0] 常亮 |
| 1 静态诊断 | `run phase1b 1 60` | 静态竖条稳定、无花屏 |
| 2 动态双缓冲 | `run phase1b 0 60` | `PHASE1B_PS_PASS` + 移动竖条 ≥1min 无撕裂 |
| 3 静态 UI（Style A） | `run phase2 0 20` | `PHASE2_UI_PASS` + 抗锯齿文字清晰 + 徽标右对齐 + 布局正确（**四像素顺序判据**） |
| 4 动态 UI | `run phase2 -1 20` | Top-1 轮换无撕裂、文字清晰 |
| 5 触摸 | `run phase3 30` | `PHASE3_TOUCH_PASS` + 三页统一、翻页正确 |
| （可选）1C 稳定性 | `run phase1c 600 60` | ≥10min 无异常、`PHASE1C_PS_PASS` |
