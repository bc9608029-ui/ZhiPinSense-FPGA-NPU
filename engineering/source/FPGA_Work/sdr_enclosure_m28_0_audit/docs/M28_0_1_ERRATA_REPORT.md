# M28_0.1 勘误报告（Errata Report）

任务 id="39e5" · M28-0.1 · 对 M28-0 外壳审计做**只读复审与勘误**。
不修改电子工程，不生成 STEP/STL/DXF。

---

## 0. 勘误性质

本轮勘误的触发事实：**用户实际使用的板卡已成功运行 NPU 模型**，因此"板卡是否有 NPU"不再是未知项。M28-0 把"Lite 与 NPU 身份矛盾"列为 CRITICAL 阻塞项，此判断需修正。

---

## 1. 勘误记录表（修改记录）

| 编号 | 位置 | 原文 | 修正后 | 理由 |
|---|---|---|---|---|
| E-1 | REQUIREMENTS_FREEZE §5 C1 / DESIGN_AUDIT §2 P1 | "任务书'Lite'与'NPU'自相矛盾，阻塞级" | "NPU 功能身份**已确认**；载板机械版本及安装尺寸**尚未确认**" | 板卡已跑通 NPU，NPU 存在不再是矛盾点 |
| E-2 | DESIGN_AUDIT §3 风险#1 / FINAL Q17 | "板卡身份未定（CRITICAL）→ 内部尺寸全变" | "载板机械版本与安装尺寸未确认（CRITICAL）→ 螺柱/连接器坐标无法定位" | 未知项从"是否 NPU"收窄为"机械版本" |
| E-3 | EVIDENCE_REGISTER 结论 / DIMENSION_REGISTER | "关键缺失：板卡身份二选一未定" | "关键缺失：载板精确型号 / PCB 硬件修订版 / 实际机械尺寸 / 安装孔 / 连接器坐标 / 最大器件高度" | 按任务书 §一 重新界定未知项 |
| E-4 | LAYOUT_FEASIBILITY §4 / DIMENSION_REGISTER | "最小底板 ≥ 主控板外形（202×150 或 233×139）" | "主板平面概念包络 = **233 × 150 mm**（二者并集）；仅作 PCB 概念占用区，**不得直接作为外壳尺寸**" | 引入最大兼容包络 |
| E-5 | CAD_READINESS_GATE G1 | "板卡身份已裁决" | "NPU 功能身份已确认；载板机械版本 + 安装尺寸待实测" | 门禁条件收窄 |

---

## 2. 事实修正：NPU 身份确认

| 项 | 状态 |
|---|---|
| NPU 存在 | ✅ **已确认**（用户板卡已成功运行 NPU 模型） |
| FMQL30TAI + ZG330 NPU 功能链 | ✅ **已确认** |
| 载板精确型号 | ⬜ 未确认 |
| PCB 硬件修订版 | ⬜ 未确认 |
| 实际机械尺寸 | ⬜ 未确认（手册值需实测复核） |
| 安装孔 | ⬜ 未确认 |
| 连接器坐标 | ⬜ 未确认 |
| 最大器件高度 | ⬜ 未确认 |

> 结论：**NPU 功能身份已确认；当前未确认的仅为"载板机械版本及安装尺寸"**（对应任务书 §八 第 1、2 问）。

---

## 3. 最大兼容包络（233 × 150 mm）

### 3.1 定义

- 已知两种外形：`202 × 150` 与 `233 × 139`。
- 二者**并集包络** = `max(202,233) × max(150,139)` = **`233 × 150 mm`**。

### 3.2 定性

- `233 × 150 mm` **只能作为主板 PCB 平面概念占用区**，用于占位布局。
- **不得直接作为外壳尺寸**。外壳还需在四边/高度方向额外叠加（全部 TBD，不得猜值）：

| 附加空间 | 状态 |
|---|---|
| HDMI 插头 | TBD_MEASURE |
| USB 插头 | TBD_MEASURE |
| RJ45 插头 | TBD_MEASURE |
| 电源插头 | TBD_MEASURE |
| SD 卡插拔行程 | TBD_MEASURE |
| UART/JTAG 维护空间 | TBD_MEASURE |
| 线缆弯折半径 | TBD_MEASURE |
| 散热器高度 | TBD_MEASURE |
| 风道高度 | TBD_MEASURE |
| 壁厚 | TBD_MEASURE |
| 装配公差 | TBD_MEASURE |
| 螺钉操作空间 | TBD_MEASURE |

---

## 4. 状态更新

```
M28_0_1_REVIEW result=CONDITIONALLY_FEASIBLE
CONCEPT_LAYOUT_READY=true
PARAMETRIC_CAD_READY=false
MANUFACTURING_CAD_READY=false
CAD_READY=false
```

- `CONCEPT_LAYOUT_READY=true`：仅指可用 233×150 占位包络开展概念布局（非加工）。
- `PARAMETRIC_CAD_READY=false` / `MANUFACTURING_CAD_READY=false` / `CAD_READY=false`：屏幕型号、安装尺寸、风扇/连接件仍缺失，继续保持不可进入任何级别 CAD。
