# v5_visual 静态设计稿（design mockups）

本目录是 **Phase2/Phase3 视觉重构** 的静态设计稿，**尚未进入 C++ 实现**。
在确认某一套风格之前，`hdmi_framebuffer_ui_v4_fix/sw` 的正式 Phase2/Phase3 代码
**一律不改**。

## 字体（真正的抗锯齿字体图集）

- 字体：**DejaVu Sans**（Regular / Bold / Mono），Bitstream Vera 许可，允许随程序再分发
  （需保留版权与许可声明，见 `assets/fonts/LICENSE-DejaVu.txt`）。
- 板端不依赖 FreeType：设计稿用电脑端把字形预栅格化为 **8-bit 灰度覆盖率**，板端只做
  **RGB565 整数 alpha blend**（`dst = (dst*(255-a) + fg*a + 127) >> 8`，逐通道）。
- 固定字号 4 档：**20 / 28 / 40 / 52 px**（粗体 + 常规 + 等宽数字）。**禁止运行时缩放 5x7。**
- 1280x720 输出 → 屏幕 1024x600（约 0.80 水平 / 0.83 垂直）。缩放后：正文 20→16px、
  次要数据 28→23px、主要数据 40→32px、识别结果 52→42px。

## 三套风格

### Style A — 现代科研仪器风（推荐）
- background `#0F141B` · surface `#1A212B` · textPrimary `#E7ECF2` · textSecondary `#8B98A8`
- primary `#4A90E2`（仅当前选中 + 关键结果）· success `#3DDC84` · warning `#E8A93C` · error `#E5605F` · outline `#2A3542`

### Style B — 比赛展示风
- background `#0D1526` · surface `#17243A` · textPrimary `#F2F5FA` · textSecondary `#93A2B8`
- primary `#3D8BFF`（仅当前选中 + 关键结果）· success `#38D47A` · warning `#F2B33D` · error `#F0655E` · outline `#2E3D57`

### Style C — 浅色实验仪器风
- background `#EFF2F6` · surface `#FFFFFF` · textPrimary `#18212B` · textSecondary `#576273`
- primary `#2563EB`（仅当前选中 + 关键结果）· success `#166534` · warning `#9E460C` · error `#B91C1C` · outline `#D5DBE3`

## 信息层级（主识别页，自上而下）

1. **识别结果 / 置信度 / 信号状态** — 顶部结果卡（52px 类名 + 40px 置信度 + 状态 chip）。
2. **10/12 类概率** — 两列卡片，简洁排行，非全宽描边。
3. **SNR / 延迟 / 帧号 / 数据源** — 底部信息条（28px）。
4. **延迟分解 + 详细计数** → 移到 Diagnostics 页。
5. 底部触摸导航高度 **90px 原始（→75px 物理）**，命中区 ≥60px 物理。
6. **MOCK / LIVE / STALE / ERROR** 一律「文字 + 形状 + 颜色」三通道表达（见 legend_status.png）。

## 布局网格

- 水平按 **5px**、垂直按 **6px** 对齐：1280→1024 是 0.8 倍（5→4 整数），720→600 是 5/6（6→5 整数），
  避免非整数缩放导致的发糊。
- 不使用阴影、模糊、渐变、透明图层。

## 文件清单

- `output/style_*/{main,diag,touch}_{normal,lowconf,stale,error}_{1280,1024}.png` — 每套 24 张。
- `output/style_*/legend_status.png` — 状态图例（4 值）。
- `output/comparison/old_vs_*_1280.png / _1024.png` — 新旧并排对比。
- `tools/make_mockups.py` — 生成器（numpy + Pillow，无其它依赖）。

> 状态：**DESIGN-DRAFT-ONLY**。确认风格后才会写像素级一致的 C++ RGB565 版本。
