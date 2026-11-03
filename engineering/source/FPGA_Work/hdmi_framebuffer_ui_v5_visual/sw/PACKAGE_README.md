# hdmi_v5_visual_sw — Style A 视觉重构软件包（任务 39e5c）

本包只含 **PS 软件**：把 Phase2/Phase3 的 5×7 点阵字体替换为**预栅格化的抗锯齿 DejaVu
位图字图集 + Style A（现代科研仪器风）UI**。基于 v4_fix 的官方 -O2 上板验证版本，
**设备写路径 `DirectFramebufferBackend::submit_frame()`、双缓冲、触摸解析、寄存器、
DDR 布局、RTL/XDC/位流一律未改**（位流仍用 v4_fix 的 `hdmi_framebuffer_720p_top_disable_icap.bit`）。

## 变更要点

- **字体**：5×7 点阵 → DejaVu Sans（Regular/Bold/Mono）8-bit 灰度覆盖率图集，离线
  预栅格化（无板上 FreeType）。固定四档 20/28/40/52px + 粗体 24px；板端只做
  `dst = (dst*(255-a) + fg*a + 127) >> 8` 的 RGB565 整数 alpha blend（逐通道）。
  字符集 = 可打印 ASCII 32..126（95 字模，`font_atlas_data.cpp` 生成）。
- **Style A UI**（现代科研仪器风）：三页统一（Main / Diagnostics / Touch），信息层级
  结果卡→概率两列卡→SNR/延迟/帧/源→底部导航；状态一律「文字+形状+颜色」
  （MOCK/LIVE/STALE/ERROR）。所有文字对比度 ≥ 4.5:1。无阴影/模糊/渐变/透明层。
- **修复（本实现阶段发现并修复）**：
  1. 渲染函数补 `pal.bg` 背景填充（此前 host 侧零初始化导致黑底）。
  2. 设计稿 `text_width` 惰性缓存 bug（首调回退 space 宽，徽标/右对齐文字右移 21px）。
  3. 诊断错误文案破折号 `—`(U+2014) → ASCII 连字符 `-`（图集只含 ASCII）。
- **视觉/语义修复（2026-10-05，按用户 6 项要求，仍 `READY-FOR-HARDWARE-VISUAL-RETEST`）**：
  1. 状态图形移到文字**左侧**并留 **≥10px 间距**，不再覆盖 LIVE/STALE/ERROR/MOCK
     （几何单一来源 `status_badge_shape_cx()`，C++ 与设计稿 `make_mockups.py` 同步改）。
  2. Phase2/Phase3 演示状态 `Live`/`SDR` → `Mock`/`MOCK`（Phase2 演示必须显示 MOCK/MOCK）。
  3. 12 类在 1280×720 与 1024×600 均**完整显示**：卡片网格 `card_grid()` 自适应两列
     （8..16 类都落在信息条上方，底部两行不再裁切）；契约标签 `GFSK/GMSK` → `GFSK`。
  4. Error 主识别页**保留信息栏 + 底部导航**，允许进入 Diagnostics/Touch（去掉提前 `return`）。
  5. 新增主机测试 `test_ui_render`：8/10/12/16 边界、文字/图标不重叠、Error 导航存在、
     Mock 不可冒充 Live。
  6. 重生成 1024×600 截图、软件包与 SHA。**未改 backend/submit_frame/RTL/XDC/位流**。
- **构建**：`build_on_board.sh` g++ 兜底已加 `font_atlas.cpp font_atlas_data.cpp ui_render.cpp`
  链接，并修 `run` 模式 `./` 路径（`elif [ -x "./$BIN" ]`）。`CMakeLists.txt` 增加
  `ui_render` 静态库，Phase2/3 链接 `direct_framebuffer_backend + ui_render`。

## 证据（主机侧，无板）

- `host_screenshot.cpp`（`-O2 -Wall -Wextra` 零告警）用**与板端完全一致**的图集 + blend
  渲染 14 张 1280×720 BMP（Main/Diag/Touch × normal/lowconf/stale/error + 12 类目标 +
  状态图例）；`tools/convert_host_out.py` 转 PNG + Pillow BILINEAR 1024×600 模拟缩放预览
  + `host_out/index.html` 画廊。
- **像素级比对**：与已确认 Style A 设计稿（`design_mockups/output/style_A/`，565 空间对齐）
  的逐像素差 **mean ≤ 0.03、max = 9**（仅 AA 边缘 `//255` vs `>>8` 舍入差，不可见）。
- `test_direct_framebuffer_backend` 主机 mock 测试全 PASS（退出 0）。
- `test_ui_render` 主机渲染测试全 PASS（8/10/12/16 边界、文字/图标不重叠、Error 导航、
  Mock 不冒充 Live）。
- `objdump_evidence/`（自 v4_fix 保留，后端未改）证明 submit 循环只有 `ldrh`+`strh`
  标量，无宽存储。

## 板上用法（root，权威 -O2 构建）

```bash
sha256sum -c SHA256SUMS.txt                 # 先校验
./build_on_board.sh g++                     # g++ -std=gnu++17 -O2 -Wall -Wextra（权威 -O2）
./build_on_board.sh run phase2 -1 20        # Style A 主识别页，动态 top-1（状态徽标=MOCK）
./build_on_board.sh run phase3 30           # 三页触摸切换
./build_on_board.sh run phase1b 0 60        # 双缓冲回归（未改，仍应 PASS）
```

复测判据与逐条命令见 `docs/BOARD_TEST_39E5C.md`。

## 状态

**READY-FOR-HARDWARE-VISUAL-RETEST** —— 待 -O2 上板复测：Phase2/3 无 SIGBUS + 显示
（抗锯齿文字平滑、三页统一、状态徽标正确右对齐）+ 触摸切换正常后，由测试者标记
`HARDWARE_VISUAL_PASS`。
