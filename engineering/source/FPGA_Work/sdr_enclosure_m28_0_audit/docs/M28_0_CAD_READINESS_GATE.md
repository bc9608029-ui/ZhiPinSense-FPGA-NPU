# M28_0 CAD 就绪性门禁（CAD Readiness Gate）

任务 id="39e5" · M28-0 · 判断**能否进入正式参数化 CAD（M28-1）**。

---

## 1. 门禁条件（全部满足才 `CAD_READY=true`）

| # | 门禁条件 | 当前状态 | 证据 |
|---|---|---|---|
| G1 | NPU 功能身份已确认；载板机械版本 + 安装尺寸待实测 | ❌ 机械版本未确认 | 勘误 E-1/E-2 |
| G2 | 板卡安装孔坐标/孔径/板厚已实测 | ❌ 缺失 | A2-2/A2-3 |
| G3 | 板卡最高元件高度（含散热器）已实测 | ❌ 缺失 | A2-5 |
| G4 | 屏幕型号 + 有效显示区 + 安装孔已实测 | ❌ 缺失 | C-1/C-3/C-4 |
| G5 | 风扇型号/孔距/电压已实测 | ❌ 缺失 | D-1 |
| G6 | SMA 穿板座型号/孔径已实测 | ❌ 缺失 | D-2 |
| G7 | 面板件（按钮/LED/DC/RJ45/USB）型号/孔径已实测 | ❌ 缺失 | D-3~D-6 |
| G8 | 屏幕/风扇功耗已实测（锁定 DC/DC 与适配器） | ❌ 缺失 | 电源审计 |
| G9 | 各边沿接口中心坐标已实测 | ❌ 缺失 | A2-7 |

---

## 2. 判定

```
M28_0_1_REVIEW result=CONDITIONALLY_FEASIBLE
CONCEPT_LAYOUT_READY=true
PARAMETRIC_CAD_READY=false
MANUFACTURING_CAD_READY=false
CAD_READY=false
```

**结论：`CONCEPT_LAYOUT_READY=true`（可用 233×150 占位包络开展概念布局）；但 9 项门禁（G1 机械版本~G9）仍未满足，`PARAMETRIC_CAD_READY=false`、`MANUFACTURING_CAD_READY=false`、`CAD_READY=false`。** 在逐项实测补齐前，只能输出概念布局图（标注 `NOT FOR MANUFACTURING`）。

---

## 3. 进入 M28-1 的前置动作（按序）

1. 用户实测 **G1** 载板机械版本 + 安装尺寸（**NPU 身份已确认，无需再裁决有无 NPU**）。
2. 用户实测 **G2~G9**（见 `M28_0_USER_MEASUREMENT_CHECKLIST.md`）。
3. 复核 Pluto 尺寸（ADI 当前产品页）。
4. 回填 `tables/M28_0_DIMENSION_REGISTER.csv` 的 MISSING 项。
5. 重新跑本门禁 → 全部满足后，方可建正式参数化 CAD。

---

## 4. 阻塞项分级（M28-0.1 §六）

区分每个缺失项阻塞到**哪一层**，避免"一把尺子量死全部 CAD"：

| # | 缺失项 | 阻塞外壳总体概念布局 | 阻塞主板专用托盘 | 阻塞前面板 | 阻塞接口面板 | 阻塞最终加工 |
|---|---|---|---|---|---|---|
| 1 | 7寸屏具体型号 | ✖ | — | ✔ | — | ✔ |
| 2 | 屏幕 PCB 尺寸 | ✖ | — | ✔ | — | ✔ |
| 3 | 屏幕有效显示区 | ✖ | — | ✔ | — | ✔ |
| 4 | 屏幕安装孔 | ✖ | — | ✔ | — | ✔ |
| 5 | 屏幕 HDMI/USB/电源接口位置 | ✖ | — | ✖ | — | ✔ |
| 6 | 主板最大器件高度 | ✔ | ✔ | — | — | ✔ |
| 7 | 风扇型号 | ✖ | — | — | ✖ | ✔ |
| 8 | SMA 穿板座 | ✖ | — | — | ✔ | ✔ |
| 9 | 电源按钮/DC 接口 | ✖ | — | ✔ | ✔ | ✔ |
| 10 | 插头与线缆包络 | ✔ | ✖ | — | ✔ | ✔ |

图例：✔=阻塞，✖=不阻塞，—=无关。

- **外壳总体概念布局**：仅被「主板最大高度」「插头/线缆包络」阻塞 → 可用 233×150 占位包络先行（`CONCEPT_LAYOUT_READY=true`）。
- **主板专用托盘**：被「安装孔/实际尺寸/连接器坐标/最大高度」阻塞 → 待载板机械版本实测。
- **前面板**：被「屏幕型号/PCB/AA/安装孔/接口位置/按钮」阻塞 → 待屏幕型号。
- **接口面板**：被「风扇/SMA/DC/按钮/线缆包络」阻塞 → 待连接件型号。
- **最终加工**：被全部 10 项阻塞 → 待全部实测。

## 5. 状态

```
M28_0_1_REVIEW result=CONDITIONALLY_FEASIBLE
CONCEPT_LAYOUT_READY=true
PARAMETRIC_CAD_READY=false
MANUFACTURING_CAD_READY=false
CAD_READY=false
```
