# M28_0 证据登记表（Evidence Register）

任务 id="39e5" · M28-0 · 每条证据记录：路径/链接、SHA256、版本、页码/图号、提取值、单位、可信等级、是否允许用于 CAD。

> **勘误（M28-0.1）**：板卡已跑通 NPU 模型 → **NPU 功能身份已确认（FMQL30TAI + ZG330 功能链）**。E1"Lite 无 NPU"与 E2"整机有 NPU"的**芯片事实仍为真**；勘误的是**解释**：用户板卡属于带 NPU 的 FPAI 族，但其**载板精确型号 / PCB 硬件修订版 / 实际机械尺寸 / 安装孔 / 连接器坐标 / 最大器件高度**仍未确认。

> 证据等级（§5.3）：`CONFIRMED_CAD` / `CONFIRMED_DATASHEET` / `CONFIRMED_MANUFACTURER_WEB` / `CONFIRMED_PHYSICAL_MEASUREMENT` / `ESTIMATED_PHOTO_ONLY` / `CONFLICTING_SOURCES` / `TBD_MEASURE`。

---

## E1 悟净开发板 Lite（轻量版）硬件使用手册 V1.0

| 项 | 值 |
|---|---|
| 路径 | `F:\嵌赛\03_FMQL30TAI-悟净开发板手册\悟净开发板Lite（轻量版）硬件使用手册V1.0.pdf` |
| SHA256 | `1f53767846907b6f64c2e25aa990c504ce34b2c082140d00cc2027f14daf5e7b` |
| 版本 | V1.0 · 深圳市创芯瑞天科技有限公司 |
| 页码 | §1（P4）、§2（P5）、§4.13（P21）、§4.21（P31）等 |
| 提取值 | 整板尺寸 **202 mm × 150 mm**；芯片 **JFMQL30TAI676H**（PSOC，对标 XC7Z030FFG676-2I，**无 NPU**）；供电 **DC 12V**（J37 + TPS259824，UVLO 9.6V / 6A）；**4× USB2.0 Host**（USB2514，各 +5V）+ **1× mini-USB UART**（CP2103GM）；**HDMI 720P@60 原生**、1080P@60 闪屏风险；**micro-SD**；**2× 20-pin JTAG**；1× RJ45（YT8521）；1× SFP；2× SDI 输入；PCIe x1；MIPI CSI；5× XADC；5 LED / 4 键 |
| 单位 | mm / V / 个 |
| 可信等级 | **CONFIRMED_DATASHEET**（厂商官方手册） |
| CAD 可用 | **是**（仅板卡外形 202×150；**不含**安装孔/板厚/元件高度，这些仍是 TBD） |

## E2 悟净开发板硬件使用手册 V1.0（整机 / FPAI 版）

| 项 | 值 |
|---|---|
| 路径 | `F:\嵌赛\03_FMQL30TAI-悟净开发板手册\悟净开发板硬件使用手册V1.0_嵌赛.pdf` |
| SHA256 | `c50d3c99b90e065ae6bddbe7c982a6b5b7c1cb76cf9c8289d9a29706e51cff93` |
| 版本 | V1.0 · 深圳市创芯瑞天科技有限公司 |
| 页码 | §1（P4，整板尺寸）、§4.1（P7，芯片概述）、§4.21（电源） |
| 提取值 | 整板尺寸 **233 mm × 139 mm**；芯片 **FMQL30TAI**（FPAI 系列：4 核 PS + **"诸葛架构"NPU**（原生支持 Transformer）+ **125K PL** + eMMC AT70B32G）；供电 **DC 12V**；2× 千兆以太网（PS+PL 各 1）；4× USB2.0 Host；HDMI 720P@60；eMMC + SD |
| 单位 | mm / V |
| 可信等级 | **CONFIRMED_DATASHEET**（厂商官方手册） |
| CAD 可用 | **是**（仅板卡外形 233×139；安装孔等 TBD） |

## E3 悟净 Lite 手册 DOCX 版

| 项 | 值 |
|---|---|
| 路径 | `F:\嵌赛\悟净开发板Lite（轻量版）硬件使用手册V1.0.docx` |
| SHA256 | `4f60e3b9baf0876009ed0f0fe2d3987ef230b558553e490a6941ae326198f40d` |
| 版本 | V1.0（与 E1 同内容，Word 源） |
| 提取值 | 同 E1（202×150mm 等） |
| 可信等级 | CONFIRMED_DATASHEET |
| CAD 可用 | 是（同 E1） |

## E4 悟净整机手册（嵌赛根目录副本）

| 项 | 值 |
|---|---|
| 路径 | `F:\嵌赛\悟净开发板硬件使用手册V1.0_嵌赛.pdf` |
| SHA256 | `6f2d808001ba15ac601e556a80e52e0a965a0b305ec2c904fb5908862fb7d87a` |
| 提取值 | 与 E2 内容一致（233×139mm），但字节与 E2 不同（`c50d3c99…` vs `6f2d8080…`） |
| 可信等级 | **CONFLICTING_SOURCES**（两副本字节不同，疑为修订差异；关键值一致） |
| CAD 可用 | 否（以 E2 为准，需确认版本差异） |

## E5 ADALM-PLUTO 外形尺寸

| 项 | 值 |
|---|---|
| 来源 | ADI 产品页 / Mouser / ADI `ADALM-PLUTO Product Highlight` PDF（网络检索交叉一致） |
| 链接 | https://www.analog.com/en/design-center/evaluation-hardware-and-software/evaluation-boards-kits/ADALM-PLUTO.html |
| 提取值 | **117 × 79 × 24 mm**（4.62 × 3.11 × 0.95 in），**114 g**；塑料外壳；工作温度 +10~+40°C |
| 单位 | mm / g |
| 可信等级 | **CONFIRMED_MANUFACTURER_WEB** |
| CAD 可用 | **是**（外形；但 **CAD 前应对当前 ADI 产品页复核**，本环境无法直连 analog.com） |

## E6 ADALM-PLUTO 官方资料整理（本地存档）

| 项 | 值 |
|---|---|
| 路径 | `F:\FPGA_Work\pluto_tools\docs\ADALM-PLUTO_官方资料整理.md` |
| 提取值 | AD9363 + Zynq Z-7010；**micro-USB 数据口在板中间（数据+供电）、micro-USB 供电口在侧面**；**RX SMA + TX SMA（50Ω）**；按钮 S1；塑料壳**无屏蔽**；频率 325MHz–3.8GHz（AD9364 固件改 70MHz–6GHz）；RX 绝对最大 +2.5 dBm、TX 最大 ≈ +7 dBm、TX 默认 −10 dB |
| 可信等级 | CONFIRMED_MANUFACTURER_WEB（ADI wiki 存档） |
| CAD 可用 | 部分（接口类型/位置方向，不含坐标） |

## E7 ADI wiki 页面存档（4 份 HTML）

| 项 | 值 |
|---|---|
| 路径 | `F:\FPGA_Work\pluto_tools\docs\wiki\{users,users_intro,users_transmit,hacking_hardware}.html` |
| 提取值 | 接口/操作说明；**未含**精确外形尺寸数字（尺寸在未存档的 hardware 子页） |
| 可信等级 | CONFIRMED_MANUFACTURER_WEB |
| CAD 可用 | 否（无尺寸数字） |

## E8 ADALM-PLUTO.pdf（第三方介绍 PPT）

| 项 | 值 |
|---|---|
| 路径 | `F:\FPGA_Work\pluto_tools\docs\ADALM-PLUTO.pdf` |
| SHA256 | `fb968d7d56443acbf48ea4192b2eb0459d2dab32ef789609df9760c01932ad21` |
| 提取值 | AD9363 + Zynq XC7Z010；**塑料壳、无屏蔽**；无 TXCO（±25 ppm）；主要教学用途 |
| 可信等级 | **ESTIMATED_PHOTO_ONLY**（第三方，非官方） |
| CAD 可用 | 否 |

## E9 待确认项（本地无权威资料 → TBD_MEASURE）

| 项 | 状态 |
|---|---|
| 7 寸 HDMI 屏精确型号/PCB 外形/有效显示区/厚度/安装孔/HDMI-触摸-供电位置/触摸禁压区 | **TBD_MEASURE** |
| 板卡安装孔坐标/孔径/板厚/最高元件高度/散热器尺寸 | **TBD_MEASURE**（手册未给） |
| 风扇型号/外形/孔距/电压电流 | **TBD_MEASURE** |
| SMA 穿板母座型号/面板孔径/尾部深度 | **TBD_MEASURE** |
| DC 插座型号/孔径；POWER 按钮型号/孔径；LED 孔径 | **TBD_MEASURE** |
| RJ45/USB 面板延长件型号；铜柱/螺钉/热熔螺母规格 | **TBD_MEASURE** |

---

## 结论

- **已确认（可用 CAD）**：两块候选板的外形（202×150 / 233×139）、Pluto 外形（117×79×24）、板载接口清单与电源（12V / 4USB+1UART / HDMI720P）；**NPU 功能身份已确认**（板卡已跑通 NPU 模型）。
- **概念包络（可用占位，非加工）**：主板平面并集包络 **233 × 150 mm**（仅 PCB 概念占用区，不得直接作为外壳尺寸）。
- **关键缺失（阻塞 CAD）**：载板精确型号 / PCB 硬件修订版 / 实际机械尺寸 / 安装孔坐标 / 连接器坐标 / 最大器件高度、屏幕型号、风扇/连接器型号。
