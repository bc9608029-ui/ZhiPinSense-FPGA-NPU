# M29 fix10class24-dualsdr-rf-adapt-prep1 — 真实 RF 采集手册

状态：`M29-RML24-FIX10CLASS24-DUALSDR-RF-ADAPT-PREP1-READY-FOR-DATA-CAPTURE`（仅审计文档持有该令牌）。
本手册是**未来真实双 SDR RF 采集**的操作指南。本任务只准备脚手架，**不采集、不训练、不量化**。

> 红线（采集时同样适用）：**不改 0.100 残差门、不改恢复器、不改标签、不生成生产替换模型**。
> 采集/上板动作由用户在板端执行；本任务不碰板、不碰 SDR。

---

## 1. 采集总目标

为「真实双 SDR RF 域适配」准备 960 个**计划槽位**（Pilot 240 + Formal 720），每个槽位一条
物理捕获，由生产恢复链产出 `[2,1024]` fp32 模型输入。计划与划分由
`contracts/rml24_dualsdr_rf_dataset_v1.py` 冻结，任何下游工具都从该合同读取，**不手工造数**。

| 阶段 | 每类 offset | 每类样本 | 总计 | session 要求 |
|---|---|---|---|---|
| Pilot | 0..9 | 10 | 240 | ≥1 session |
| Formal | 10..39 | 30 | 720 | ≥2 sessions |

Formal 确定性划分（按 offset，无泄漏）：`train=10..27`（18/类）、`val=28..33`（6/类）、
`test=34..39`（6/类）。Pilot 不进入 train/val/test（仅探索真实门禁分布 + 校准采集参数）。

## 2. C4 冻结 RF 采集配置

| 字段 | 值 |
|---|---|
| center_freq_hz | 2400000000 |
| sample_rate_hz | 2560000 |
| rx_gain | 35 |
| rx_bw_hz | 18000000 |
| tx_bw_hz | 18000000 |
| tx_atten_db | -40 |
| tx_target_rms | 2048 |
| rf_path | direct-cable |

链路：`raw RX → coarse-CFO → 分数定时 → 广线性 iqrfrec → int16 → PreprocessChain → D2 恢复
→ 分类窗 → [2,1024] fp32`。**禁止**用期望 payload 代替、禁止 NumPy 近似重建、禁止手工修正。

- 双 SDR（`link=dual`）：PC-TX / 板-RX，仅 TCP 39010 传控制 + 身份 + SHA。
- 单 SDR（`link=single`）：本地 cyclic TX 自发自收（loopback=0）。

## 3. sample_id 与 source_index

- `sample_id = c{raw24:02d}_{offset:03d}`，如 `c00_010`。
- `source_index = raw24_class_index * 500 + intra_class_offset`，全局唯一，`offset ∈ [0,499]`。
- 计划槽位只覆盖 `offset ∈ [0,39]`；`offset ≥ 40` 的捕获会被 builder **拒绝**（不是计划槽位）。
- 24 类原始标签序见 `rml24_dualsdr_rf_dataset_v1.py::SOURCE_LABEL_ORDER_24`。

## 4. 捕获落地目录布局（builder 输入契约）

每个捕获一个子目录，放在 `--capture-root` 下：

```
<capture-root>/
  c00_010/
    capture_meta.json      # 必填：source_index, link, gate_status, capture_session_id
    model_input.f32        # 必填：8192 字节 [2,1024] fp32 LE（生产链输出，非近似）
    model_input_wl.f32     # 可选：广线性变体（同形状，若存在则一并入库）
  c00_011/ ...
```

`capture_meta.json` 必填字段：`source_index`(int)、`link`(single|dual)、
`gate_status`(PASSED|DIAGNOSTIC_PROVISIONAL|REJECTED)、`capture_session_id`(str)。
可选：`payload_training_residual`、`corr`、`cfo_hz`、`wide_linear_ratio`、
`capture_attempts`、`raw_rx_iq_sha256`、`frozen_raw24_pred`。

## 5. 门禁处置（0.100 门本身不变）

| gate_status | 含义 | 处置 |
|---|---|---|
| `PASSED` | 残差 ≤ 0.100 | 进入主集（train/val/test 只收 PASSED） |
| `DIAGNOSTIC_PROVISIONAL` | 门拒（0.10 < 残差 ≤ 上限） | 仅保留进 pilot，**永不**进 train/val/test |
| `REJECTED` | 硬失败（clip/CFO/corr 超限） | ≤3 次有界重捕获后仍失败则记录并丢弃 |

builder 的 fail-closed 规则（任一违规即中止、不落部分结果）：
`source_index` 必须在计划内且全局唯一；train/val/test 只收 `PASSED`；provisional 只进 pilot；
`model_input.f32` 必须存在、恰好 8192 字节、全有限 fp32。

## 6. 建议采集流程

1. **Pilot 先行**：每类 offset 0..9，共 240 槽，≥1 session。目的=确认真实 RF 门禁分布、残差
   典型值、是否需要重捕获；Pilot 数据不参与训练。
2. **Formal**：每类 offset 10..39，共 720 槽，**必须 ≥2 个 session**（`capture_session_id`
   至少两个不同值）。按 offset 自动落入 train/val/test。
3. 每个槽位记录 `capture_meta.json` + `model_input.f32`（+ 可选 wl）。
4. 校验：`python -I scripts/build_fix10class24_dualsdr_rf_dataset.py --capture-root <dir>
   --out-dir datasets/rml24_dualsdr_rf_v1 --allow-provisional`，读 `build_report.json`。
5. 只有 `PASSED` 且 `split_role ∈ {train,val,test}` 的样本进入适配训练；F1(clean24_smoke)、
   F2(单SDR)、F3(双SDR历史) 是冻结评估集，**永不进入训练**。

## 7. 训练/评估/导出（采集完成后，在训练环境）

- 训练：`scripts/train_fix10class24_rf_adapt.py --checkpoint <FP32 best.pt> --model-def <mod>
  --candidate <…> --lr <…> --seed <…> --data-mix <…> --dataset datasets/rml24_dualsdr_rf_v1`
  （预注册 36 组合：candidate×data_mix×seed×lr；**仅 val 选模，永不 test**）。
- 评估：`scripts/evaluate_fix10class24_rf_adapt.py`（F1 清洁回归 / F2 单SDR / F3 双SDR 开放
  测试 / F4 三种子统计；`--f4-stats` 纯 stdlib 本环境可跑）。
- 导出/编译：`export_fix10class24_rf_adapt_onnx.py` → `compile_…_bf16.py` / `compile_…_tf32.py`
  （**门禁在 go/no-go**：只有 FP32 候选在独立 test 上超过原模型才允许编译，否则 fail-closed）。
