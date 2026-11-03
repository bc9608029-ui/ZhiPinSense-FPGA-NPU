# M28_0 外壳审计最终结论（Final Audit Conclusion）

任务 id="39e5" · M28-0 · 便携式智能无线电频谱感知终端外壳审计。
本文回答 21 个审计问题，逐条给出证据与结论。**全部结论不超红线，不输出任何 PASS/加工尺寸。**

---

## 状态总览

```
M28_0_1_REVIEW result=CONDITIONALLY_FEASIBLE
CONCEPT_LAYOUT_READY=true
PARAMETRIC_CAD_READY=false
MANUFACTURING_CAD_READY=false
CAD_READY=false
```

---

## Q1 任务书核心硬件是否存在自相矛盾？

**已勘误。** 原判断"Lite+NPU 自相矛盾（阻塞级）"**撤回**：用户板卡已成功运行 NPU 模型，**NPU 功能身份已确认（FMQL30TAI + ZG330 功能链）**。当前未确认的仅为**载板机械版本及安装尺寸**（载板精确型号 / PCB 硬件修订版 / 实际机械尺寸 / 安装孔 / 连接器坐标 / 最大器件高度）。详见 `M28_0_1_ERRATA_REPORT.md`。

## Q2 主控板的权威机械尺寸是多少？

- 悟净 **Lite**：**202 × 150 mm**（手册 V1.0，SHA `1f537678…`，CONFIRMED_DATASHEET）。
- 悟净 **整机/FPAI**：**233 × 139 mm**（手册 V1.0，SHA `c50d3c99…`，CONFIRMED_DATASHEET）。
- 两者均有官方手册，但**身份二选一未定**。

## Q3 ADALM-PLUTO 的权威机械尺寸是多少？

**117 × 79 × 24 mm，114 g**（ADI/Mouser，CONFIRMED_MANUFACTURER_WEB）。塑料外壳，无屏蔽。CAD 前需对当前 ADI 产品页复核（本环境无法直连 analog.com）。

## Q4 屏幕尺寸是否已确认？

**否。** 7 寸屏型号/PCB 外形/有效显示区/厚度/安装孔/接口位置全部 TBD_MEASURE。**屏幕型号未确认前禁止生成屏幕开窗**（红线）。

## Q5 哪些参数可以从现有资料确认，哪些必须实物测量？

- **已确认**：板卡外形（2 选 1）、板载接口清单、12V 电源、Pluto 外形/接口/RF 电平。
- **必须实测**：板卡身份、安装孔坐标/孔径/板厚、最高元件高度、屏幕全套、风扇、SMA 穿板座、面板件孔径、各接口边沿坐标、功耗。详见 `M28_0_USER_MEASUREMENT_CHECKLIST.md`。

## Q6 内部布局采用哪种方案？

**方案 A（单层水平 + RF 分区）为首选**，方案 B（双层叠放）备用。理由：结构简单、RF 路径最短、契合可拆后盖维护基线。详见 `M28_0_LAYOUT_FEASIBILITY.md`。

## Q7 Pluto 如何固定？

**P1 保留原壳（卡槽/压条）为首选**。拆壳（P2）仅当用户明确要求且补测接地/散热后再评估。理由：不破坏原壳、不引入接地/散热未知数。

## Q8 RF 路径是否可行？

**可行方向，但有关键前提。** Pluto RX/TX → 短同轴 → 顶部 SMA Female Bulkhead；穿板座须由面板锁紧螺母承担机械力并接地；Pluto 塑料壳无屏蔽需布局分区 + 局部屏蔽。详见 `M28_0_RF_PATH_AND_EMI_AUDIT.md`。

## Q9 USB 接口是否够用，需不需要额外 Hub？

**够用，无需 Hub。** 板载 4× USB2.0 Host + 1× UART；需求 = Pluto + 触摸 + 用户 USB = 3 口，冗余 1 口。详见线缆审计。

## Q10 供电方案如何？

**单 12V DC 输入可行**（J37 + TPS259824，UVLO 9.6V / 6A）。屏幕/风扇取电方式待功耗实测后定（Q1 板载取电优先 / Q2 加 DC/DC 备选）。**功耗确认前不冻结 DC/DC 与适配器参数**。

## Q11 POWER 按钮与安全关机如何设计？

**K1：瞬时按钮 → GPIO → Linux 安全关机**（长按 ≥4s 强制断电兜底）。避免直接断电损坏 SD 卡。按钮型号/孔径待测，GPIO 接线资源待板卡按键确认。

## Q12 散热方案如何？

**T1 主动风冷为基线**，气流方向底/前入 → 顶/后出，掠过主板散热器。风扇型号/孔距/电压待测。**不输出 THERMAL PASS**。

## Q13 是否存在 EMI/EMC 硬伤？

**存在风险但非硬伤。** Pluto 无屏蔽、SMA 接地路径未定义是主要风险；金属外壳并非 EMI 通过充分条件。策略：布局分区 + 局部屏蔽（S1），金属壳仅在有证据时启用（S3）。**不输出 EMI PASS**。

## Q14 材料与制造方式如何选？

**调试=亚克力激光切割 / 比赛= PETG 3D 打印 / 若需 EMI=铝**。紧固件 M2.5/M3 待安装孔实测。**不生成 STEP/STL/DXF/DWG/加工图**。

## Q15 可维护性是否满足？

**满足。** 前面板独立（屏幕不连带主板）+ 可拆后盖使 SD/JTAG/UART 可达。详见装配/维护审计。

## Q16 是否发现原则性错误？

**4 项**：P1（Lite+NPU 自相矛盾）、P2（默认 Pluto 拆壳未经证据）、P3（RF 接地路径未定义）、P4（安全关机未定义）。详见设计审计 §2。

## Q17 最严重的三个结构风险是什么？

1. 载板机械版本与安装尺寸未确认（CRITICAL）→ 螺柱/连接器坐标无法定位。（原"板卡身份未定"已勘误）
2. 无安装孔坐标（CRITICAL）→ 螺柱无法定位。
3. 屏幕型号未定（CRITICAL）→ 正面开窗无法生成。

## Q18 能否进入正式参数化 CAD？

**否。** `CONCEPT_LAYOUT_READY=true`（可用 233×150 占位包络开展概念布局），但 9 项门禁（G1 机械版本~G9）仍未满足，`PARAMETRIC_CAD_READY=false`、`MANUFACTURING_CAD_READY=false`、`CAD_READY=false`。详见 `M28_0_CAD_READINESS_GATE.md`。

## Q19 本阶段允许输出什么、禁止输出什么？

- **允许**：概念布局图（标注 `CONCEPT ONLY / NOT FOR MANUFACTURING / DIMENSIONS NOT FROZEN`）、审计/登记/清单文档。
- **禁止**：STEP/STL/DXF/DWG/加工图、生产位流、下单采购、修改电子工程、填充假参数、输出虚假 PASS。

## Q20 本轮是否触碰了 M20~M27 或板端/模型/位流？

**否。** 本轮仅在 `F:\FPGA_Work\sdr_enclosure_m28_0_audit\` 新增 M28-0 目录；未覆盖/删除/修改任何历史工程、RTL/XDC/位流、NPU 模型、训练目录、UI 工程、历史交付包、原始手册/图片。

## Q21 下一步建议（M28-1 前置）

1. 用户裁决板卡身份（Q1）。
2. 用户按 `M28_0_USER_MEASUREMENT_CHECKLIST.md` 实测 G2~G9。
3. 复核 Pluto 尺寸（ADI 当前页）。
4. 回填 `M28_0_DIMENSION_REGISTER.csv` MISSING 项。
5. 重跑 CAD 门禁 → 全满足后进入 M28-1 参数化 CAD。

---

## 最终判定

```
M28_0_1_REVIEW result=CONDITIONALLY_FEASIBLE
CONCEPT_LAYOUT_READY=true
PARAMETRIC_CAD_READY=false
MANUFACTURING_CAD_READY=false
CAD_READY=false
```

外壳方案方向可行（单层 + RF 分区 + Pluto 保壳 + 主动风冷 + 安全关机 + 塑料调试壳 + 通用主板托盘）；NPU 功能身份已确认，233×150 包络可作概念占位，但载板安装尺寸、屏幕型号、风扇/连接件仍缺失，**保持 CAD_READY=false**。
