# hdmi_board_bringup_v1 — 上板前准备包 (FMQL30TAI 悟净)

**最终状态：`pending-vivado-build` + `pending-qt-build`**

HDMI 上板前全部准备。本轮未连接/未烧录/未操作开发板；位流未综合，Qt 板端 C++ 未交叉编译。

## 目录

| 路径 | 内容 |
|---|---|
| `REPORT.md` | **九段式完整报告**（先读这个） |
| `SAFETY_GATE.md` | 上板安全门 G0–G4 |
| `fpga/` | 720p 色条最小工程 + 构建 Tcl + 时钟方案 |
| `linux/display_backend.md` | 板上 Linux **无 DRM/fbdev**，显示 = pHDMI DDR→PL 通路 |
| `qt/` | Qt 显示后端计划 + 主机 offscreen 渲染冒烟测试 |
| `touch/` | USB 触摸准备（硬件未确认） |
| `scripts/00–07` | 分阶段上板脚本 + JTAG 临时加载 Tcl |
| `SHA256SUMS.txt` | 全包文件哈希清单 |

## 一分钟结论

1. HDMI 是 **PL 侧 "IO 模" TMDS (pHDMI)**，720p@60 可靠、1080p 会闪屏；引脚
   AC17/AA15/Y16/W16，`TMDS_33`（取自官方 demo XDC）。
2. 板上 Linux **没有 framebuffer/DRM**，Qt UI 必须 **offscreen 渲染 RGB565 → 写
   DDR → 写寄存器 `0x40080054`**。
3. 最小色条工程已就绪（含解决 200 MHz 无法直接产生 74.25 MHz 的两级 MMCM 时钟方案），
   但位流**尚未综合** → `pending-vivado-build`。
4. 提供的主机/交叉环境**无 Qt 头/qmake/平台插件**，板端 Qt C++ 交叉编译当前不可行
   → `pending-qt-build`；主机侧 QML offscreen 渲染可先验证。
5. USB 触摸**硬件未确认**（手册/DTS 均无触摸屏）。

## 下一步（等你确认后才做）

- 跑 `fpga/build_hdmi_colorbar_720p.tcl` 综合位流 + Procise 后处理。
- 之后才允许连接开发板做色条测试。

详见 `REPORT.md`。
