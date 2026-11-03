# HDMI 720p 色条位流 — 构建与验证报告

**状态：READY-FOR-HARDWARE-COLORBAR-TEST（可上板色条测试）**

> 本报告只陈述**软件/位流侧**事实：真实 Vivado 2018.3 完成综合、布局布线、位流生成，
> 时序、DRC、时钟频率三项硬性门全部通过。**是否"上板成功"仍需你本人按本报告第 6 节
> 实机验证**——本报告编写完成本身不等于已上板验证。

---

## 1. 一句话结论

1280×720@60Hz 固定 8 色条的 PL 侧 HDMI（pHDMI）测试位流已由**真实 Vivado 2018.3**
构建完成并全部通过验证门：**WNS=+4.794ns / WHS=+0.125ns，DRC 0 Error，两级 MMCM
输出 74.25MHz（像素）+ 371.25MHz（TMDS×5）精确匹配**。防 ICAP 位流经 FMSH hook 与
Procise 两条独立路径产出，**md5 逐字节一致**。

---

## 2. 构建环境

| 项 | 值 |
|---|---|
| Vivado 版本 | **2018.3 (win64) Build 2405991**（FMSH JFM patch 官方配对版本） |
| 器件（Vivado） | `xc7z030ffg676-2` |
| 器件（Procise/FMSH 库） | `7z030aiffg676-2` ↔ 板上 **JFMQL30TAI676H** |
| FMSH IP PATCH | **5.3.1.8**，userID `32'h53180205` |
| Procise | 2025.1.1（SVN 32494，仅用于 disable_icap 后处理） |
| 顶层模块 | `hdmi_colorbar_720p_top` |
| 设计类型 | 纯 PL，无 PS/Linux/Qt/DDR 依赖 |

---

## 3. 验证结果（三项硬性门，全通过）

### 3.1 综合 / 实现
- 综合：`synth_design Complete!`（0 errors, 0 critical warnings, 1 warning）
- 实现：`write_bitstream Complete!`（place → route → write_bitstream 全通过）

### 3.2 时序（setup / hold 均无违例）
| 指标 | 值 |
|---|---|
| **WNS**（最差 setup 余量） | **+4.794 ns** ✅ |
| **WHS**（最差 hold 余量） | **+0.125 ns** ✅ |
| TNS / THS | 0.000 / 0.000 |

### 3.3 DRC
**0 Error，3 Warning**（均逐条核对为无害，非降级/删约束通过）：

| 规则 | 条数 | 说明 |
|---|---|---|
| PORTPROP-2 | 2 | `sys_clk_p/n` 的 `DIFF_TERM` 在 `DIFF_SSTL15` 下不支持片内端接，被忽略（官方 XDC 属性，无影响，时钟照常进 MMCM） |
| ZPS7-1 | 1 | 未实例化 PS7 block——纯 PL 设计本就无需 PS7（Zynq 器件对纯 PL 设计的常规提示） |

> 附注（如实披露）：write_bitstream 阶段 FMSH patch 会额外输出
> `DRC CHECK-1 Report disabled checks: REQP-44/46/52/56`，这是 **FMSH 官方
> `write_bitstream_pre.tcl` 的行为**（针对 Zynq PS 配置引脚的规则），不是本工程改的，
> 与纯 PL HDMI 设计无关。本包主 DRC 报告 `reports/routed_drc.rpt` 是在 route 完成后、
> write_bitstream 之前生成的完整报告，结论见上表。

### 3.4 时钟频率（两级 MMCM，精确匹配）
| 时钟 | 周期(ns) | 频率 | 期望 |
|---|---|---|---|
| `sys_clk_p` | 5.000 | 200 MHz | 板上晶振 C8/C7 ✅ |
| `clk_27m` | 37.037 | 27 MHz | MMCM1 ✅ |
| `clk_74m25` | 13.468 | **74.25 MHz** | MMCM2 像素时钟 ✅ |
| `clk_371m25` | 2.694 | **371.25 MHz** | MMCM2 TMDS×5 ✅ |

---

## 4. 位流文件

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `hdmi_colorbar_720p_top.bit` | 5,980,032 B | `d7184fd6cdf3e1407f002a6d848204a430667bac26e31542bae4da556142d571` |
| `hdmi_colorbar_720p_top_disable_icap.bit`（上板用） | 5,980,616 B | `81fc863b2c05ab17284cf48367b678b4c924a366884c54375807c3de53585458` |

> `_disable_icap.bit` 经**两条独立路径**生成并 md5 一致（`4937fd42…`）：
> ① FMSH hook 在 write_bitstream 后自动产出；② 手动跑 Procise
> `call_procise_disable_icap.bat` 重跑产出。二者逐字节相同，产物可信。

---

## 5. 交付包清单（`hdmi_720p_colorbar_test/`）

```
BOARD_TEST_GUIDE.md                    上板测试指南（逐行步骤，必读）
TROUBLESHOOTING.md                     按现象排查表
BUILD_REPORT.md                        本报告
SHA256SUMS.txt                         包内所有文件 SHA-256 清单
build.log                              Vivado 完整构建日志
build_summary.txt                      构建摘要（TOP/PART/状态/WNS/WHS/位流路径）
hdmi_colorbar_720p_top.bit             普通位流
hdmi_colorbar_720p_top_disable_icap.bit  上板加载用位流（防 ICAP）
collect_results.ps1                    上板结果/失败现场打包脚本
reports/
  routed_drc.rpt                       DRC 报告（0 Error）
  routed_clocks.rpt                    时钟频率报告（74.25/371.25MHz）
  routed_clock_networks.rpt            时钟网络报告
  routed_clock_interaction.rpt         时钟交互报告
  routed_timing_summary.rpt            布线后时序报告
  routed_utilization.rpt               资源利用率报告
  routed_route_status.rpt              布线状态报告
  routed_methodology.rpt               方法学检查报告
  post_synth_utilization.rpt           综合后利用率
  post_synth_timing_summary.rpt        综合后时序
  timing_gate.txt                      时序门结果（WNS/WHS）
src/
  build_hdmi_colorbar_720p.tcl         构建脚本
  report_clocks_post.tcl               时钟报告脚本
  constrs/hdmi_colorbar_720p.xdc       约束（HDMI 引脚 + 时钟 + 复位）
  rtl/*.v / *.vhd                      6 个 RTL 源文件
```

整包压缩：`hdmi_720p_colorbar_test.zip`，其 SHA-256 见上级目录 `dist/PACKAGE_SHA256.txt`（打包时生成，因包内含本报告文件，避免自指）。

---

## 6. 上板测试步骤（逐行，只做临时 JTAG 加载）

> 全程**不写 QSPI / eMMC / SD**，断电即回退。详细版见 `BOARD_TEST_GUIDE.md`。

1. 开发板断电（SW8 = OFF，12V 适配器先不插）。
2. HDMI OUT → 显示器 HDMI 输入。
3. 显示器先上电，等它进入"无信号/待机"。
4. 12V 适配器插 DC 座 J37（先不拨 SW8）。
5. PL JTAG（**20pin 插座 U19**）→ PC 下载器。**不要接 PS JTAG=U18 / PS UART**。
6. 拨 SW8 给开发板上电。
7. PC 打开 Vivado 2020.2 → **Open Hardware Manager** → Open Target → **Auto Connect**。
8. 确认出现器件 **`xc7z030_0`**；若多器件，只选 PL 器件 `xc7z030_0`。
9. 右键器件 → **Program Device…**，Bitstream file 选本包
   `hdmi_colorbar_720p_top_disable_icap.bit`，**不勾** "Program flash" 类持久化选项。
10. 点 Program，等 **"Program operation completed successfully"**。
11. 观察：`led[0]`(J1) **常亮**（MMCM 锁定）、`led[1]`(M6) **约 1Hz 闪**（像素时钟在跑）。
12. 观察屏幕：**8 条等宽竖彩条**（白/黄/青/绿/品红/红/蓝/黑，左→右），显示器 OSD 约
    **720p / 60Hz**，稳定无闪。
13. **持续 ≥10 分钟稳定** → 判 **PASS**。否则按 FAIL，用 `collect_results.ps1` 打包现场。

---

## 7. 边界声明

- 本报告及交付包**不构成"已上板"声明**；上板结论待你本人实测。
- 出现焦味/发烫/异常电流：**立即断电**，按 FAIL 处理并收集现场信息。
- 本轮**不**固化 Flash，不构建 Qt UI，不操作模型/NPU/SDR/训练。
