# ADALM-PLUTO 官方资料整理（本地存档）

> 整理日期：2026-10-05
> 来源：Analog Devices 官方 wiki（wiki.analog.com）+ AD9363 数据手册（经官方产品页/数据手册确认）
> 说明：analog.com 的官方 PDF 服务器在当前网络环境**直连超时**，故本目录改为：① 存档官方 wiki 页面 HTML；② 本文档整理关键信息；③ 附一份第三方介绍 PDF（非官方，仅作快速入门参考）。

---

## 0. 本目录文件清单

| 文件 | 内容 | 来源 | 是否官方 |
|---|---|---|---|
| `wiki/users.html` | 用户指南总目录 | wiki.analog.com | ✅ 官方 |
| `wiki/users_intro.html` | 产品介绍 | wiki.analog.com | ✅ 官方 |
| `wiki/users_transmit.html` | 发射（TX）说明，含回环安全警告 | wiki.analog.com | ✅ 官方 |
| `wiki/hacking_hardware.html` | 硬件接口说明 | wiki.analog.com | ✅ 官方 |
| `ADALM-PLUTO.pdf` | 11 页介绍 PPT（Graham Cottew） | github zendata/SDR | ❌ 第三方 |

---

## 1. 硬件接口（最常用，重点）

ADALM-PLUTO = **AD9363** 射频收发器 + **Zynq Z-7010（XC7Z010）** SoC。

| 接口 | 类型 | 用途 | 接电脑时 |
|---|---|---|---|
| **USB 数据口（OTG）** | micro-USB，板子**中间** | 数据 + 供电 | ✅ **插这个** |
| **USB 供电口** | micro-USB，板子**侧面/边角**（常标 `PWR`） | 仅供电（OTG 接外设时补电） | ❌ 不用管 |
| **RX SMA** | 50Ω 射频口 | 接收 | 回环自测时才用 |
| **TX SMA** | 50Ω 射频口 | 发射 | 回环自测时才用 |
| **按钮 S1** | 轻触开关 | 上电时按住进入恢复模式 | 平时不用 |

> 关键：**两个 micro-USB 口一样大**，接电脑认准**中间那个数据口**（一个口同时供电 + 传数据，侧面供电口不用插）。

---

## 2. 连接电脑

1. 用 **micro-USB 数据线**（能传数据，不是纯充电线）连接 Pluto 的数据口与电脑 USB 口。
2. Windows 10/11 **自带 RNDIS 驱动**，插上自动装（识别为一个虚拟网卡）。
3. 默认走网络协议，Pluto 固定 IP **192.168.2.1**。
4. 通过 USB 访问射频信号，可用：MATLAB/Simulink、GNU Radio、C/C++/C#、Python（**libiio**、**PyADI-IIO**、SoapySDR、gqrx、SDR# 等）。

---

## 3. 关键参数（AD9363 / Pluto）

| 参数 | 数值 |
|---|---|
| 频率范围 | **325 MHz – 3.8 GHz**（官方标称；改固件后约 70 MHz – 6 GHz） |
| ADC / DAC 分辨率 | **12 bit**（ADI HDL 期望 16 bit 输入，低 4 LSB 忽略） |
| 最大采样率 | **61.44 MSPS** |
| 瞬时带宽 | **200 kHz – 20 MHz** |
| 收发 | **全双工**，1 RX + 1 TX |
| 接收通道 | 6 差分 / 12 单端 |
| 发射通道 | 4 差分输出 |

---

## 4. 功率与安全（⚠️ 重要，务必遵守）

| 项 | 数值 | 说明 |
|---|---|---|
| **RX 绝对最大输入** | **+2.5 dBm** | AD9363 数据手册，超过会损坏接收前端/LNA |
| **TX 最大输出** | **≈ +7 dBm** | 2.4 GHz 处 7.0 dBm，800 MHz 处 7.5 dBm |
| **TX 衰减默认值** | **−10 dB** | 官方默认，保证输出级线性 |
| **官方回环警告** | — | **「不要把 TX 衰减设到小于 −10 dB，就把 TX 输出环回 RX 输入」** |

**回环自测安全规则（本机已采纳，写入项目记忆）：**
- 双保险：① 软件先把 TX 衰减拉到 −40 dB 以上（输出 ≤ −30 dBm），从最小功率逐步加、每步读回 RX 功率盯 ≤ −10 dBm；② TX→RX 串 20~30 dB SMA 衰减器作物理保险。
- **绝不满功率裸连。**

---

## 5. 官方用户指南章节索引（在线查看）

wiki.analog.com/university/tools/pluto/users 下的章节：
- 硬件介绍（命名、内部结构、工作温度、范围/速率、收发特性、天线、Volatility PDF）
- **Quick Start（快速开始）**
- **设备驱动安装**（Windows / Linux / MAC）
- 固件升级
- 校准（Calibration）
- 自定义设备
- 软件交互：IIO Oscilloscope、gqrx、MATLAB/Simulink、GNU Radio、SDRangel、SDR#、SoapySDR、Python（libiio / PyADI-IIO）、C 示例
- 附件与 ASEE 论文

---

## 6. 备注

- analog.com 官方 PDF（数据手册、产品亮点）在当前网络环境直连超时，如需官方 PDF 原文件，可在网络可访问时到 **analog.com/products/ad9363** 或 **analog.com 的 ADALM-PLUTO 产品页** 下载；本目录已提供内容等价的官方 wiki 存档 + 本文档。
- `ADALM-PLUTO.pdf` 为第三方介绍 PPT，内容准确但**非官方**，仅作快速入门参考，不作为参数依据。
