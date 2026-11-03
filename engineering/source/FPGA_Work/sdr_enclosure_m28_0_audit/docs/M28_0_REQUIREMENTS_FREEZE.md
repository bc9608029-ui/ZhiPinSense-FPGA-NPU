# M28_0 需求冻结（Requirements Freeze）

任务 id="39e5" · M28-0 · 便携式智能无线电频谱感知终端外壳审计。
本文件冻结**本阶段的需求与边界**，不含任何加工尺寸。

---

## 0. 阶段性质

- 本阶段 = **只读、证据驱动的机械设计审计**，不生成最终可加工外壳。
- 允许输出：概念布局图（必须标注 `CONCEPT ONLY / NOT FOR MANUFACTURING / DIMENSIONS NOT FROZEN`）。
- 不允许：STEP/STL/DXF/DWG、加工图、生产位流、下单采购、修改电子工程、填充假参数。

## 1. 产品定位（冻结）

- 便携式智能无线电频谱感知终端 / 小型智能频谱分析仪。
- 主链：RF → ADALM-PLUTO → USB/IQ → FMQL30TAI PS/Linux → PL DDR → FPGA → NPU → PS/Linux → Qt/QML → HDMI → 7 寸屏。

## 2. 核心硬件清单（冻结，来自任务书）

| 器件 | 说明 |
|---|---|
| FMQL30TAI Lite 开发板 | PS/Linux + FPGA + NPU + PL DDR（**NPU 归属见 §5 冲突**） |
| ADALM-PLUTO SDR | AD9363 + Zynq Z-7010 |
| 7 寸 HDMI 显示屏 | 型号待确认 |
| USB 触摸接口 | 若屏幕支持 |
| SD 卡 | micro-SD（板载 TF 槽） |
| 内部 USB/HDMI/电源线 | — |
| 散热器与风扇 | 型号待确认 |
| SMA 穿板母座 | 50Ω SMA Female Bulkhead，禁 RP-SMA，不优先 BNC |
| 内部电源分配模块 | 后续可能增加 |

## 3. 初始方案基线（冻结，作为审计对象，非无条件遵循）

- 结构：前面板 + 横向主箱体 + 可拆后盖。
- 正面：7 寸屏、POWER 按钮、POWER 指示灯、SYSTEM 指示灯、"智频感知" + "INTELLIGENT RADIO SENSING SYSTEM"。
- 顶部：RF IN/RX、RF OUT/TX（50Ω SMA Female Bulkhead）。
- 侧/后：DC IN、RJ45、1 个用户 USB、风扇与通风。
- 隐藏维护区：UART、JTAG、SD、维护 USB、复位。

## 4. 已确认需求（本次审计证据支撑）

- 板载 **4× USB2.0 Host + 1× mini-USB UART**，Pluto + 触摸 + 用户 USB 无需额外 Hub（详见线缆审计）。
- 板载 **12V DC 输入**（电源座 J37 + TPS259824 eFuse，UVLO 9.6V / Ilim 6A）→ 单 DC 输入可行（详见电源审计）。
- HDMI 输出 **720P@60 原生**、1080P@60 有闪屏风险 → 7 寸屏需 ≤720P 或验证（详见线缆/正面审计）。

## 5. 需求冲突（必须在进入 CAD 前由用户裁决）

| # | 冲突 | 证据 | 影响 |
|---|---|---|---|
| C1 | ~~任务书写"FMQL30TAI Lite"但核心硬件列 NPU，Lite 板无 NPU~~ **已勘误（M28-0.1）** | 板卡已跑通 NPU 模型 | **NPU 功能身份已确认**；改为：载板机械版本及安装尺寸未确认（载板精确型号/PCB 修订版/实际尺寸/安装孔/连接器坐标/最大器件高度） |
| C2 | 板卡安装孔坐标/孔径/板厚/最高元件高度 手册未提供 | 手册文本抽取 | 无法放置螺柱 |
| C3 | 7 寸屏精确型号未知 | 无本地资料 | 无法生成正面开窗 |

> 冲突 C1 已勘误：**不再阻塞"是否 NPU"**，改为阻塞"载板机械版本与安装尺寸"（见 `M28_0_1_ERRATA_REPORT.md`）。C2/C3 仍阻塞。

## 6. 状态红线（冻结）

- 最高可写状态：`M28_0_ENCLOSURE_AUDIT result=CONDITIONALLY_FEASIBLE`（或 `INCOMPLETE`），`CAD_READY=false`。
- 禁止：`ENCLOSURE_PASS / THERMAL_PASS / EMI_PASS / MANUFACTURING_READY / PRODUCTION_READY / PROJECT_COMPLETE`。
- 禁止：凭空定长宽高、用相似板/普通屏替代、把照片估算当加工尺寸、功耗未确认冻结 DC/DC、生成加工图/STEP/STL、下单采购、修改电子工程。
