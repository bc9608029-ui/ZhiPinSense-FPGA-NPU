# 首次上板测试指南 —— HDMI 720p 色条 (FMQL30TAI 悟净 Lite)

> **本指南只指导"临时 JTAG 加载 + 观察色条"，绝不写 QSPI / eMMC / SD 等任何永久启动
> 存储。** 加载是易失性的：**断电即回退**到出厂状态，这是本轮的默认安全回滚方式。
>
> 在开始之前，你必须已经**逐行读完整份本文件**，并在心理上确认每一步的目的。

---

## 0. 一分钟结论（先看这个）

| 项目 | 值 |
|---|---|
| 板卡 | 悟净 Lite，主芯片 **JFMQL30TAI676H**（Vivado 器件 = `xc7z030ffg676-2`） |
| 本测试目标 | HDMI OUT 输出 **1280×720@60Hz** 固定 8 色条，无需 Linux/Qt/DDR/模型 |
| 加载方式 | **临时 JTAG 易失加载**（断电即回退，不写永久存储） |
| JTAG 接口 | **PL JTAG = 20pin 插座 U19**（不要与 PS JTAG=U18、PS UART、USB 混淆） |
| 器件名（Hardware Manager） | **`xc7z030_0`**（已由 `mandatory_core_board_validation` 实机验证） |
| 加载的位流 | `hdmi_colorbar_720p_top_disable_icap.bit`（Procise 后处理产物） |
| 电源 | 12V 适配器 → DC 座 **J37** → 拨码开关 **SW8** |
| 期望画面 | 8 条竖彩条：白/黄/青/绿/品红/红/蓝/黑（左→右），稳定无闪 |
| 板上状态灯 | `led[0]`(J1) 常亮 = 两级 MMCM 锁定；`led[1]`(M6) ~1Hz 闪烁 = 像素时钟在跑 |

---

## A. 前置条件（不满足就先停下，不要上电）

1. **显示器已用已知 720p60 HDMI 源验证过**：用另一台确定能输出 720p60 的设备（笔记本 /
   盒子）接到**同一台显示器、同一根 HDMI 线**，确认能显示 720p60。若这台显示器接 PC 都
   黑屏/无信号，**先解决显示器问题**，不要继续。
2. **显示器供电稳定 5V**：显示器请用其自带的稳定 5V 电源（不要从开发板 USB 口取电）。
3. 触摸屏（USB 触摸）本轮**可选**，不接不影响色条测试。
4. 主机已安装 Vivado 2020.2（`D:\Xilinx\Vivado\2020.2`），且本交付包的位流已生成
   （见 `SHA256SUMS.txt` 与 `build_summary.txt`）。
5. 确认手中有一条 **PL JTAG (20pin) 下载线**（连接 U19 的那种 20pin 排线/转接板）。

---

## B. 断电接线顺序（严格按此顺序，最后再上电）

> 全部在**断电**状态下接线。板卡电源开关 SW8 先置于 OFF。

1. **开发板断电**（SW8 = OFF，12V 适配器先不插）。
2. **HDMI OUT → 显示器 HDMI 输入**（开发板 HDMI 口是 PL 侧 pHDMI 输出）。
3. **显示器上电**（显示器先亮，等待它进入"无信号/待机"状态）。
4. **接 12V 适配器到 DC 座 J37**（先不拨 SW8）。
5. **PL JTAG (U19) → PC**（20pin 下载线，接到 PC 的下载器/延长线上）。
6. （可选）**PS UART → PC**：MINI USB 串口线（CP2103），本轮可不接。
7. （可选）**触摸屏 USB**：本轮可不接。
8. **最后**：拨动 **SW8** 给开发板上电。

> 顺序要点：**"板最后上电"**。任何时候闻到焦味 / 发烫 / 异常电流声，立即断电（拨 SW8
> 或拔 12V）。

---

## C. Vivado Hardware Manager 步骤（GUI）

1. 打开 **Vivado 2020.2**。
2. 菜单 **Flow → Open Hardware Manager**（或启动后选 "Open Hardware Manager"）。
3. **Open Target → Auto Connect**。
4. 观察 Hardware 面板。**预期出现器件 `xc7z030_0`**（FMQL30TAI 的 PL 被识别为
   `xc7z030`）。如果出现多个器件，请选中 **PL 器件（`xc7z030_0`）**，不要选 ARM DAP /
   PS 相关器件。
5. 在器件上右键 → **Program Device…**。
6. **Bitstream file** 选择本包内的：
   ```
   hdmi_colorbar_720p_top_disable_icap.bit
   ```
   （**不要**在 Program Device 对话框勾选 "Program flash" 之类的持久化选项；只做普通
   JTAG Program。）
7. 点击 **Program**。等待进度条走完，出现 "Program operation completed successfully"。
8. `.ltx`（探针文件）：**本设计没有 ILA/调试核，不需要也不生成 `.ltx`**，Program 对话框
   的 Debug probes file 留空即可。

### 等效 Vivado Tcl（不猜器件名）

> 以下 Tcl 直接套用 `mandatory_core_board_validation/vivado.jou` 里已被实机验证过的
> 器件名 `xc7z030_0`。把 `<BIT>` 替换为本包内 `hdmi_colorbar_720p_top_disable_icap.bit`
> 的绝对路径。

```tcl
open_hw
connect_hw_server
open_hw_target
set_property PROGRAM.FILE {<BIT>} [get_hw_devices xc7z030_0]
current_hw_device [get_hw_devices xc7z030_0]
refresh_hw_device -update_hw_probes false [lindex [get_hw_devices xc7z030_0] 0]
set_property PROBES.FILE {} [get_hw_devices xc7z030_0]
set_property FULL_PROBES.FILE {} [get_hw_devices xc7z030_0]
program_hw_devices [get_hw_devices xc7z030_0]
refresh_hw_device [lindex [get_hw_devices xc7z030_0] 0]
```

> 若 `xc7z030_0` 不存在，先用 `puts [get_hw_devices]` 打印实际器件列表，再按列表中
> `xc7z030` 的完整名字替换。**不要凭空猜器件名**。

---

## D. 结果判定

**期望画面**：8 条**等宽竖彩条**，从左到右依次为
**白 / 黄 / 青 / 绿 / 品红 / 红 / 蓝 / 黑**，每条宽约 160 像素，整幅 1280×720。显示器
OSD 信息应显示约 **720p / 60Hz**。

**板上状态**：
- `led[0]`(J1) **常亮** = 两级 MMCM（200MHz→27MHz→74.25/371.25MHz）都锁定。
- `led[1]`(M6) **约 1Hz 闪烁** = 74.25MHz 像素时钟正常在跑。

| 判定 | 条件 |
|---|---|
| **PASS** | 8 彩条清晰、颜色顺序正确、**稳定无闪**，`led[0]` 亮、`led[1]` 闪，且 **≥10 分钟**持续稳定 |
| **FAIL** | 黑屏 / 无信号 / 彩条顺序错 / 花屏 / 闪烁 / 只有部分颜色 / LED 不亮 / 中途掉配置 |

**注意**：PASS 判定要求 **至少稳定运行 10 分钟**（排除偶发掉配置）。期间若出现发烫/焦味/
异常，立即断电按 FAIL 处理并进入 E 节收集信息。

---

## E. 失败信息收集（务必完整，缺一项都会拖慢定位）

失败后，**保持现场**（先别断电、别拔线），逐项收集：

1. **Hardware Manager 截图**（含器件树、Program 结果/报错）。
2. **Program 日志**（Vivado 底部 Tcl Console 或 `.jou` 文件全文）。
3. **屏幕照片 / 短视频**（拍清楚是黑屏 / 花屏 / 彩条 / 无信号，最好连显示器 OSD 一起拍）。
4. **显示器型号 + 供电方式**（5V 适配器还是 USB 取电）。
5. **HDMI 线**（长度/版本，换一根再试一次）。
6. **PC 侧 720p 复测**：把 PC 接回同一显示器/线，确认 PC 能输出 720p60（排除显示链路问题）。
7. **本包报告**：`timing_summary`、`DRC_report`、`clock_report`、`utilization_report`、
   `build.log`（本包内已随附）。
8. **板上 LED 状态**：`led[0]`/`led[1]` 是亮/灭/闪。
9. 是否闻到焦味 / 器件发烫 / 电流异常。

> 用本包内的 `collect_results.ps1` 可自动打包第 7 项到结果目录。

---

## F. 安全回滚（默认路径，永远先选这个）

**本轮是易失加载，最简单的回滚 = 断电重启。**

1. **断电**：拨 SW8 到 OFF（或拔 12V）。
2. 可选：拔掉 PL JTAG 下载线。
3. **重新上电**：开发板回到出厂/上一次的配置状态（临时色条配置自动消失）。

> **禁止**本指南范围内的任何"固化到 Flash / 写 QSPI / 写 SD / 写 eMMC"操作。若后续确实
> 需要永久固化，那是**另一轮**单独授权的动作，不在此指南内，也不在本轮交付范围。

---

## 附：本轮明确不做什么

- 不构建/运行 Qt UI；不修改 `hdmi_ui_v1_1`。
- 不操作模型 / NPU / SDR / 训练。
- 不写任何永久启动存储（QSPI / eMMC / SD）。
- 不实际烧录开发板（本指南是**等你本人**上板时使用；编写本指南本身不等于已上板验证）。
