# M29 RML24 fix10class24-tf32-ab1 — FP32→TF32 NPU 24类 A/B 审计

任务：验证「FP32 输入 → TF32 NPU 内部计算 → FP32 24维 logits」相比当前 BF16 能否提升
真实 RF 24 类准确率（不训练、不改门、不改恢复链）。覆盖单 SDR 自发自收 + 双 SDR
PC-TX/板-RX。最高允许状态 `M29-RML24-FIX10CLASS24-TF32-AB1-READY-FOR-BOARD-TEST`。
禁写 RF_PASS / PROJECT_COMPLETE / FINAL_*。

## Phase A — 冻结 FP32 源模型（✅ PASS）

| 字段 | 值 |
|---|---|
| 状态 | `SOURCE_MODEL_FOUND_AND_VERIFIED`（非 BLOCKED） |
| checkpoint `best.pt` SHA256 | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` |
| ONNX `rml24_24class_opset17.onnx` SHA256（全量） | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` |
| 标签合同 SHA256 | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` |
| 输入 / 输出 | `[1,2,1024]` fp32 / `[1,24]` fp32 raw logits |
| 标签序 | raw24 精确（`rml24_raw_contract.py::SOURCE_LABEL_ORDER_24`，无 24→23 合并） |
| 与 BF16 源身份 | 一致（同一 checkpoint 96cd25f8…，BF16 源即此 checkpoint） |

从 BF16 JSON/RAW 反推 FP32 = 禁止，未发生。已由 ONNX 正确 checkpoint 导出，标签序/网络身份一致。

## Phase B — TF32 编译 + 网络审计 + Host 前向（✅ PASS）

### 编译（iCraft 3.39.0，qdtype=tf32，target=zhuge）

quantize / adapt / generate 三阶段 exit 0（`F:/FPGA_Work/_tmp_24class_expE_full_tf32_384_20261019/`，
配置 SHA `360e6e2e…`）。产品复制/改名为 `model_rml24_tf32/rml24_adamrv11_tf32.{json,raw}`。

### 冻结身份

| 字段 | 值 |
|---|---|
| model json SHA256 | `8d00a1c31835611f18064389e5b9ecab755afefa5bacd78a983119757e65fa37`（189612 B） |
| model raw SHA256 | `f8366a109576ea53c9b3ddfd2e7b690590515ff3dfb33c6af7cf6ccafcdb392e`（1423004 B） |
| params_md5 / params_bytes | `e48e59f5a2da56a99875ade883d508da` / 1423004 |
| network name / ai_target | `model_24class` / `@zhuget(330)` |
| icraft | v3.39.0 |

### 网络映射审计（`scripts/audit_rml24_tf32_network.py`，fail-closed，重算非缓存）

- op 清单：1 Input + **118 HardOp** + 1 Output（TF32 比 BF16 少 4：Cast 6→3、Reshape 39→37，多 1 Transpose）
- compile_target：`{@hostt:2, @zhuget(330):118}` → **118 NPU + 2 host**，主计算全在 NPU
- HardOp 节点：`{Cast:3, Reshape:37, Transpose:34, Conv2d:28, Add:12, Mean:1, Matmul:2, PruneAxis:1}`
  （计算节点 Conv2d 28 + Add 12 + Matmul 2 + Mean 1 + PruneAxis 1 与 BF16 完全一致）
- 输入 `[1,2,1024]` @fp(32) / 输出 `[1,24]` @fp(32)
- 激活 dtype：**117 @tf(32)**（0 bf16）；权重：**59 @tf(32)** + 118 @uint(64)（0 bf16）
- **零 INT8 / 零 BF16 / 零 FP16**（无静默 BF16 回退；fp16 在 FMQL30TAI 不支持）
- 结论：`DEPLOYABLE_FULL_NETWORK_TF32`（主计算 @zhuget(330)，非 Host）

### Host 前向验证（`scripts/run_tf32_host_forward.py`，icraft-run --backends Host）

- 3 次前向 **逐字节一致**（ftmp SHA256 `b10bdf003d97b2a0214d151c67e6cedbd8f6cdbad270b5344ece8102c20c5309`）
- 24 logits **全部有限**（无 NaN/Inf），argmax 稳定（合成输入 argmax=2）
- 24 logits 示例：`[-165.25, -99.56, -23.63, -124.13, -81.69, -76.5, -131.75, -94.0, -64.25, -122.63, -79.06, -129.5, -63.44, -146.75, -37.34, -70.38, -68.81, -34.81, -41.16, -152.13, -142.25, -185.0, -153.25, -79.5]`

### Phase B 交付物（`model_rml24_tf32/`）

- `rml24_adamrv11_tf32.json` / `rml24_adamrv11_tf32.raw`
- `SHA256SUMS.txt`（json+raw 两条）
- `compiler_metadata.json`（量化方案 full_network_tf32、census、源身份、I/O）
- `network_mapping_report.json` / `network_mapping_report.md`（审计脚本重算生成）

## Phase C — 离线硬门禁（✅ 完成，`results/tf32_ab1_phase_c/`）

工具 `scripts/audit_fix10class24_tf32_ab1_phase_c.py`（fail-closed：模型 SHA + 输入 8192 字节 +
24 维有限 logits 均校验）。**关键修复**：icraft-run Host 后端按扩展名解析输入，`.f32` 会被误走
`Image2Tensor` 图片路径（`out_shape.size()==4` 断言失败）；统一把输入暂存为 `.bin` 后走原始
`[1,2,1024]` fp32 张量路径，三输入集一致。

| 输入集 | TF32 正确 | TF32 vs BF16 argmax | 说明 |
|---|---|---|---|
| C1 clean24_smoke（24 干净张量） | **24/24** | agree **24/24**（diff 0） | 干净 IQ 上两者无差异 |
| C2 单 SDR scalarwl（24×2=48） | WL **23/24**（scalar 同） | diff wl=**0** scalar=**0** | 与单 SDR BF16 参考 23/24 一致 |
| C3 双 SDR full24 门拒（9） | **8/9** | flips **0** | BF16 forced 亦 8/9 |

**数值差异证据**：C2 上 TF32 与 BF16 logits 最大绝对差 **wl=8.875 / scalar=8.25**——证明 TF32 量化
**真实生效**（logits 数值不同，非静默等同 BF16），但 argmax 排序不变。

**C3 覆盖边界（诚实标注）**：双 SDR full24 的 15 个门内样本（`gated=1`）由板端 NPU 直接分类，
主机侧 `files_present=0`（无 model_input、无原始捕获），**离线不可覆盖**；C3 仅覆盖 9 个门拒样本
（主机 BF16 强制分类导出）。这 15 个样本被 C1（干净）+C2（单 SDR 全 24 真实 RF）+C3（双 SDR 门拒
退化样本）三面包夹，且 81 个输入零翻转，argmax 不受残差区间影响。

**合计 81 个输入（24 干净 + 48 单 SDR + 9 双 SDR 门拒）：TF32 与 BF16 argmax 零翻转。**

> 旧 `results/tf32_phaseC_smoke/` 是 n=2 的早期烟测残留，已被本目录取代，不作为判定依据。

## Phase D — Go/No-Go 判定（✅ `TF32_AB1_NO_GO_NO_ACCURACY_GAIN`）

| # | 条件 | 结果 |
|---|---|---|
| 1 | TF32 网络身份有效且纯 TF32（0 bf16/int8/fp16 回退） | PASS（Phase A/B） |
| 2 | TF32 Host 前向确定且有限 | PASS（3 次逐字节一致） |
| 3 | C1 干净张量：TF32 正确率与 BF16 无差异 | PASS（24/24，diff 0） |
| 4 | C2 单 SDR 真实 RF：TF32 与 BF16 argmax 无差异 | PASS（48/48，diff 0） |
| 5 | C3 双 SDR 门拒：TF32 与 BF16 forced 无差异 | PASS（9/9，flips 0） |
| 6 | TF32 数值上确实异于 BF16（量化真实生效） | PASS（max\|Δ\|=8.875） |
| 7 | **TF32 是否带来准确率增益？** | **否 → NO-GO**（81 输入零翻转，增益=0） |

**结论**：FP32→TF32 NPU 在全部可离线覆盖的真实 RF 输入上**不改变任何 argmax**，因此对 24 类
真实 RF 准确率**增益为零**。TF32 更高的尾数精度未越过任何 logit 排序边界。→
**`TF32_AB1_NO_GO_NO_ACCURACY_GAIN`**。不做 Phase E/F/G 板测预备（仅 Phase D 通过才继续）。

## 红线（逐字节不变，本阶段未触碰）

payload_training_residual ≤0.100、恢复/CFO/分数定时/WL 逻辑、≤3 次有界重捕获、TX -40 上限、
canonical 三组件、24 类标签序、分类窗口与预处理链、当前 BF16 JSON `28272abc…`/RAW `c1781aec…`
+ baseline、旧 mixed 模型、24→23 合同、训练数据/代码。TF32 是**新模型**（独立 json/raw），
不覆盖、不替换任何现有模型。
