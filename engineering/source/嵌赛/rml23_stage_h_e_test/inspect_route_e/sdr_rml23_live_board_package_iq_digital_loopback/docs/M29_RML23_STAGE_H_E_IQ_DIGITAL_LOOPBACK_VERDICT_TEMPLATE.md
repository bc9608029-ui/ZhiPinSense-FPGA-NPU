# M29 RML23 Stage H-E / Route E — 同设备调制 IQ 数字回环 判决报告模板

> 本文件是**模板**：所有 `<…>` 占位符与「待上板」标记由**用户板端实测**填写。
> host 自洽测试**不能**填写任一判决；host 只能声明 `…-READY-FOR-BOARD-TEST`。

---

## 0. 最高状态（host 交付后即冻结）

```
M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST
```

板上实测前**不得**写：
`RML23_LIVE_HARDWARE_PASS / NPU_PASS / UI_HARDWARE_PASS / UI_VISUAL_PASS /
 RF_PASS / HARDWARE_PASS / PROJECT_COMPLETE / FINAL_*`
以及任何「Route E 分类通过 / RF 安全已证明 / 数字回环保真已证明 / 项目完成」。

---

## 1. 输入身份（板端实测时填写）

| 字段 | 值 |
|---|---|
| input-kind | `generated-2p56m` / `radioml-reconstructed-2p56m`（**分别跑，不混合**） |
| frozen-dir | `<Stage G 工件目录>` |
| frozen 文件数 / SHA | `<来自 iq_loopback_manifest.tsv 或 roundtrip_manifest.tsv>` |
| 模型 json / raw / params_md5 | `d43a2284…` / `2425d990…` / `7966a482…`（冻结，不得变） |
| 位流 / HDF5 / 24 类标签序 | `22fec95c…` / `e3dd0bef…` / `3e1382d1…`（冻结，不得变） |

Route E **只读** frozen 文件与 Route D 已有 i16 文件；缺失即报
`STAGE_G_FROZEN_IQ_REQUIRED`，**禁止重新生成**（硬要求 4）。

---

## 2. 基础设施判决（硬要求 11 第一项：设备配置 / TX / RX / 同步 / 捕获 / 恢复）

由 `GATE_RESULT gate=gate9_full_chain_rml23` 行与 `RF_LEAKAGE_NOT_PROVEN` 行得出：

| 判据 | 期望 | 实测 | PASS/FAIL |
|---|---|---|---|
| requested rate | 2560000 | `<…>` | |
| rx / tx readback | `abs(actual-2560000) <= 5 Hz` | rx=`<…>` tx=`<…>` | |
| 回读误差 Hz / ppm | 记录，2559999 可接受 | `<…>` | |
| 3840000 等回退 | fail-closed | 未出现/出现 | |
| loopback 回读 | 1（数字） | `<…>` | |
| TX attenuation 写入/回读 | 最大衰减 `-89.75` | req=`<…>` readback=`<…>` | |
| 天线 / 同轴 | 均不接 | none / none | |
| ENSM | 未管理（本代码不改） | `ensm=not_managed_by_this_code` | |
| 每文件 capture_ok | 全 OK | `<…>` | |
| restore_result | PASS | `<…>` | |

基础设施 PASS **不**要求分类正确（反之亦然）。

---

## 3. 信号保真判决（硬要求 11 第二项：观测 token，仅板端可终判）

每文件 `IQ_DIGITAL_LOOPBACK … fidelity=…` 行：

| 文件 | fidelity | NMSE | EVM% | corr | CFO Hz | delay | gain dB | phase deg |
|---|---|---|---|---|---|---|---|---|
| `<…>` | `<PRESERVES_IQ / DISTORTS_IQ / SYNC_OR_WRAP_INCONCLUSIVE / CAPABILITY_NOT_PROVEN / INSUFFICIENT_EVIDENCE>` | | | | | | | |

```
arbitrary_modulated_iq_fidelity = BOARD_REQUIRED     （除非板端实测报
  DIGITAL_LOOPBACK_PRESERVES_IQ / DIGITAL_LOOPBACK_DISTORTS_IQ）
```
host 音调已证 TX DMA→内部 loopback→RX DMA 结构，**未证**任意调制 IQ 保真；
保真只能由本板测给出。**RF_LEAKAGE_NOT_PROVEN 持续保留**，不得宣称绝对无 RF。

---

## 4. 分类判决（硬要求 11 第三项：测量-only，无准确率门，两类输入不混合）

| input-kind | frames | correct | 恢复率 | frozen 率 | verdict |
|---|---|---|---|---|---|
| generated-2p56m | | | | | `<CLASS_CONSISTENT_WITH_FROZEN_REFERENCE / CLASS_FLIPPED_PREPROCESS_DIVERGENCE / CLASS_MAJORITY_DEPLOYED / CLASS_DIVERGENT / INSUFFICIENT_EVIDENCE>` |
| radioml-reconstructed-2p56m | | | | （无 frozen ref） | `<…>` |

分类错误**不得**把基础设施判 FAIL；基础设施错误也不得把分类判通过。
两类输入**不得混合汇总**（硬要求 9）。

---

## 5. 独立主机复核

```
python3 -I scripts/analyze_iq_digital_loopback.py \
    --log <板端 producer stdout> \
    --frozen-dir <Stage G 工件目录> \
    --input-kind <generated-2p56m|radioml-reconstructed-2p56m> \
    --json <out.json>
```
三判决必须与本模板一致；frozen SHA 复核必须 `all_ok=True`。

---

## 6. 结论（板端实测后填写）

- 基础设施：`PASS / FAIL`（含原因）
- 信号保真：`arbitrary_modulated_iq_fidelity = <…>`（只能板端写）
- 分类：`<verdict>`（测量-only）
- RF 泄漏：`RF_LEAKAGE_NOT_PROVEN`（保持）
- 最高状态：`<…>`（板端实测后仍不得写 *_PASS / FINAL_* / 项目完成）
