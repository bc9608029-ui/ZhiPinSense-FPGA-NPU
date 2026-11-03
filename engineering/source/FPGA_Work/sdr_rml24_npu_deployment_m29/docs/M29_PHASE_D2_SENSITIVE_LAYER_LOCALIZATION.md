# M29 Phase D.2 — 有界敏感层定位（中间张量只读分析）

> 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`
> 依据：用户指示 39e5（批准方向 1，禁止 28 层逐层盲跑，采用有界敏感层定位，A 路中间张量分析优先）
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁重训 / 禁换校准集 / 禁写 FINAL_*/NPU_PASS 等

---

## 1. 目标

定位「head 之外量化主干」中**首次明显偏离**的层（导致 AM-SSB-SC 残余 −31.3pp 崩塌），据此给出**最小敏感层集合**，再走 B 路分组 bf16 二分（或直接定向 bf16），最终在完整 validation 上评估一次（规则 C）。

实验 A 结论（含两项勘误）：
1. Top-1 agreement 0.810 < 0.98 → FAIL。
2. 只能确认「head 之外的量化主干导致剩余崩塌」，**不得**断言全由 28 层 Conv 激活量化造成——具体层待本文定位。

---

## 2. 能力确认（已实证）

- `icraft-run --dump_ftmp --dump_format SFB` 每样本导出 **130 个去量化 fp32 中间张量**（从 NCHWc32 瓦片解包，无头部），文件名为张量 `v_id`（如 `14.ftmp`、`924.ftmp`）。
- 输入张量 `0.ftmp` 与喂入的 `[2,1024]` planar I/Q **逐位一致**（`np.array_equal == True`）。
- **关键发现**：raw NCHWc32 张量（v14/v28/…，Conv 输出）解包为 W-major 瓦片序，直接 flatten 与 PyTorch 不对齐（cosine 0.05~0.38）；而**转置后**的 `*C*c32`/`*C` 张量（v510/v514/…/v574、v419/v425/v429）解包为规范 **channel-major `[C,L]` 序**，与 PyTorch `[B,C,L]` 逐元素对齐（cosine > 0.98）。
- BN 已折叠进 Conv（INT8 Conv 输出 = fp32 `bn(conv)` 输出）；ReLU 融合：`conv1`/`stem` 输出含 ReLU，`conv2`（bn2）输出不含，残差 Add 输出含 ReLU（= ResidualUnit 返回值）。

因此 A 路**可行**，无需 B 路兜底来定位（B 路用于定位后的定向 bf16 验证）。

---

## 3. 对齐映射（33 个规范边界，全部 cosine>0.98 已实证）

| 边界名 | INT8 v_id | fp32 hook | 逻辑 shape |
|---|---|---|---|
| input | 0 | 读入 iq bin（逐位） | [2,1024] |
| denoiser.stem_out | 510 | `denoiser.stem.2` | [24,1024] |
| denoiser.block0_conv2 | 514 | `denoiser.blocks.0.bn2` | [24,1024] |
| denoiser.block0_out | 45 | `denoiser.blocks.0` | [24,1024] |
| denoiser.block1_conv2 | 518 | `denoiser.blocks.1.bn2` | [24,1024] |
| denoiser.block1_out | 76 | `denoiser.blocks.1` | [24,1024] |
| denoiser.block2_conv2 | 522 | `denoiser.blocks.2.bn2` | [24,1024] |
| denoiser.block2_out | 107 | `denoiser.blocks.2` | [24,1024] |
| denoiser.correction | 526 | `denoiser.correction` | [2,1024] |
| denoised | 121 | `denoiser`（容器） | [2,1024] |
| feat0_proj | 530 | `features.0.projection.1` | [32,512] |
| feat0_conv2 | 534 | `features.0.bn2` | [32,512] |
| feat0_out | 164 | `features.0` | [32,512] |
| feat1_conv2 | 538 | `features.1.bn2` | [32,512] |
| feat1_out | 195 | `features.1` | [32,512] |
| feat2_proj | 542 | `features.2.projection.1` | [48,256] |
| feat2_conv2 | 546 | `features.2.bn2` | [48,256] |
| feat2_out | 238 | `features.2` | [48,256] |
| feat3_conv2 | 550 | `features.3.bn2` | [48,256] |
| feat3_out | 269 | `features.3` | [48,256] |
| feat4_proj | 554 | `features.4.projection.1` | [64,128] |
| feat4_conv2 | 558 | `features.4.bn2` | [64,128] |
| feat4_out | 312 | `features.4` | [64,128] |
| feat5_conv2 | 562 | `features.5.bn2` | [64,128] |
| feat5_out | 343 | `features.5` | [64,128] |
| feat6_proj | 566 | `features.6.projection.1` | [96,64] |
| feat6_conv2 | 570 | `features.6.bn2` | [96,64] |
| feat6_out | 386 | `features.6` | [96,64] |
| feat7_conv2 | 574 | `features.7.bn2` | [96,64] |
| feat7_out | 417 | `features.7` | [96,64] |
| mean | 419 | `classifier.0` 前向 pre-hook | [96] |
| fc1 | 425 | `classifier.1` | [128] |
| fc2_logits | 429 | `classifier.3` | [24] |

覆盖：denoiser（stem + 3 残差块 + correction + 加性输出）、features 8 残差单元（含 4 投影）、mean、FC1、FC2。**注**：每残差单元内部 conv1 输出未单独列（raw NCHWc32 瓦片序，非必要；conv2 输出已累积 conv1+conv2 误差）。若定位显示某单元为敏感单元，可再对该单元 conv1 单独解包复核（见 §5 备选）。

---

## 4. 分析方法（规则 A）

在**同一固定 1536 诊断子集**（`work/eval_full/subset_index.npz`，64/类，validation 非 test，与实验 A 完全一致）上：

1. **fp32 参考**：PyTorch checkpoint（`96cd25f8…`）eval + `inference_mode`，forward hooks 采集 §3 列出的 33 个边界激活。
2. **int8 实际**：`icraft-run --dump_ftmp --dump_format SFB`（实验 A 模型 `model_24class_ZG.json`+`.raw`，head bf16）逐样本导出 130 张量，按 v_id 取 33 个边界。
3. **逐层逐样本指标**（fp32 vs int8，两向量均 reshape 为 1-D 后计算）：
   - **cosine** = dot(a,b)/(‖a‖‖b‖)
   - **SQNR(dB)** = 10·log10(‖a‖² / ‖a−b‖²)
   - **MAE** = mean|a−b|，及归一化 MAE/‖a‖₂（相对误差）
   - **动态范围**：fp32 与 int8 各自的 min/max/RMS
   - **饱和率**：由 ZG.json 各张量 `QuantizedType.scale`（per-channel 时 axis=-1 对应 C）+ SFB 去量化值反推 `round(value/scale)==±127` 的比例（仅对 int8 张量；bf16 head 记 N/A）
4. **分组统计**：按 AM-SSB-SC（类18）、AM-SSB-WC（类17）、其它类（22 类合并）三组分别累计均值；再给全子集均值。
5. **首次偏离判定**：沿 §3 顺序扫描，找 cosine/SQNR 首次跌破阈值（默认 cosine<0.99 或 SQNR<20dB 视为明显偏离；阈值只做定位提示，不选配置），标出敏感层集合。

**纪律（规则 C）**：不访问 test；不更换校准集；不按单个 AM 样本选配置；只用 1536 子集定位。定位得到最小敏感层集合后**冻结**，再对完整 validation 评估一次。

---

## 5. 备选：conv1 单独解包（如需更细粒度）

raw NCHWc32 conv 输出（v14/v28/…）解包为 W-major：`reshape([W,32]).T → [32,W] → [:C]` 可得规范 `[C,W]`。若 §4 显示某残差单元为敏感单元但需区分 conv1/conv2，用该法复核 conv1 输出。当前默认不展开。

---

## 6. 后续（定位后）

- **B 路定向 bf16**：将 §4 定位的最小敏感层集合（按 4 网络阶段分组：denoiser / feat0-1 / feat2-3 / feat4-7 / head，必要时再细分）置 bf16，每次只改一组，总编译实验 ≤8 次（规则 B）。
- **规则 D 最终报告**：acc/macro-F1/rated/snr0/min_class、AM-SSB-SC 及 AM-SSB-WC 精度、Top-1 agreement、中间层误差、bf16 层数、NPU 映射率、是否 CPU fallback、模型大小、预计/实测延迟与内存。
- **规则 E 晋级门不变**：无单类系统性崩塌、min_class 降幅 ≤5pp、Top-1 agreement ≥0.98（不得静默降低）、无 CPU fallback 冒充 NPU 成功。
- **规则 F 停止条件**：最小敏感层集仍无法恢复 AM-SSB-SC / 混合精度致关键算子 CPU fallback / 资源或延迟明显不可接受 → 停止 PTQ，提交证据后申请 QAT，不自动重训。

---

## 7. 交付物

- 脚本：`scripts/d2_fp32_acts_dump.py`（fp32 33 边界采集）、`scripts/d2_int8_acts_dump.py`（int8 SFB 采集）、`scripts/d2_layer_analysis.py`（对齐+逐层指标+首次偏离）。
- 报告：`docs/M29_PHASE_D2_LAYER_ANALYSIS_RESULT.md`（逐层指标表 + 首次偏离层 + 敏感层集合）。
- 对齐验证：`scripts/d2_align_verify.py`（单样本 33 边界 cosine 全 >0.98 的实证记录）。

红线：全部只读；`model_24class_ZG` 与实验 A 产物保持 REJECTED 不晋升；未碰板/未写 Flash/未访问 test。
