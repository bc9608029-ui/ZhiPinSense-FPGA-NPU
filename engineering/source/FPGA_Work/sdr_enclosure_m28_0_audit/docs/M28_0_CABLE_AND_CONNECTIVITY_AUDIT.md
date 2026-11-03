# M28_0 线缆与连通性审计（Cable & Connectivity Audit）

任务 id="39e5" · M28-0 · 审计内部线缆、接口数量与连通性，判断"单 DC 输入、无额外 USB Hub"是否成立。

---

## 1. 接口与线缆需求盘点

### 1.1 板载接口（证据，来自 E1）

| 接口 | 数量 | 说明 |
|---|---|---|
| USB2.0 Host | 4（USB2514，每口 +5V） | 可接 Pluto + 触摸 + 用户 USB |
| mini-USB UART | 1（CP2103GM） | 维护/调试 |
| HDMI | 1（720P@60 原生） | 接 7 寸屏 |
| RJ45 | 1（YT8521，10/100/1000M） | 网络/维护 |
| DC 12V | 1（J37 桶型座） | 主供电 |
| micro-SD | 1（板载 TF） | 系统盘 |
| JTAG | 2（20-pin） | 调试 |
| SFP / 2×SDI / PCIe x1 / MIPI CSI / XADC | 各若干 | 本外壳基线不引出 |

### 1.2 内部线缆清单（概念）

| 线缆 | 从 → 到 | 说明 |
|---|---|---|
| USB 数据线 | 主板 USB Host → Pluto 数据口（中间 micro-USB） | USB2.0，尽量 <0.5m，无中继 |
| 触摸/USB 线 | 主板 USB Host → 屏幕触摸口（若 USB 触摸） | 待屏 C-6 确认 |
| HDMI 线 | 主板 HDMI → 屏幕 HDMI | 720P@60，短软排/短线 |
| DC 线 | 面板 DC 座 → 主板 J37 | 12V，线径按 6A eFuse 上限留裕量 |
| RF 同轴 | Pluto RX/TX SMA → 顶部 SMA 穿板 | 见 RF 审计 |
| 风扇线 | 主板/独立电源 → 风扇 | 待风扇电压（D-1） |
| POWER 按钮线 | 面板按钮 → 主板按键/GPIO | 见电源审计 |
| LED 线 | 主板 LED → 面板指示灯 | 见电源审计 |

---

## 2. 关键判断

### 2.1 USB 数量是否够（无需额外 Hub）

- 需求：Pluto（1）+ 触摸（1）+ 用户 USB（1）= **3 口**。
- 板载 **4× USB2.0 Host** → **够用，无需额外 Hub**。
- 保留 1 口冗余（接 USB 键盘/鼠标调试等）。
- 注意：4 口均为 USB2514 hub 下游，Pluto 走 USB2.0 无带宽瓶颈（Pluto 本身 USB2.0）。

### 2.2 单 DC 12V 输入是否可行

- 板载 12V DC（J37 + TPS259824，UVLO 9.6V / Ilim 6A）→ **单 DC 输入可行**。
- 屏幕/风扇若需 5V/其他电压，需确认板卡是否对外供电或另配 DC/DC（**待功耗确认，见电源审计**）。
- 红线：**功耗确认前不冻结 DC/DC 与适配器参数**。

### 2.3 HDMI 分辨率限制

- 板载 HDMI 720P@60 原生，1080P@60 有闪屏风险。
- 7 寸屏应选 **≤720P（如 1024×600 / 800×480 / 1280×720）** 或实测 1080P 稳定性。
- 触摸 USB 与 HDMI 若屏幕为 HDMI+USB 一体，则两根线并行。

---

## 3. 走线原则（概念）

- USB/HDMI 数据线远离 RF 同轴线（串扰）。
- DC/电源线远离 RX SMA（噪声）。
- 线缆固定：用线夹/扎带座固定，避免松脱与振动；预留弯曲半径。

---

## 4. 状态

```
M28_0_ENCLOSURE_AUDIT result=CONDITIONALLY_FEASIBLE
CAD_READY=false
reason=missing_verified_dimensions
```

USB 4 口够用（Pluto+触摸+用户 USB，冗余 1），单 12V DC 输入可行；屏幕 5V/风扇供电方式待功耗确认；HDMI 需 ≤720P 屏。
