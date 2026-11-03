# M29 Phase E0 — QAT 可行性硬门禁（调查 + 判定）

> 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`（未变）
> 本阶段结论：**E0 硬门禁不通过 → 不启动 QAT 训练（E0.4 / E1 前提均不满足）。**
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁自动启动 QAT / 禁写 FINAL_*/NPU_PASS 等。

---

## 0. 结论（TL;DR）

**iCraft 3.39（本机已装 SDK）不提供任何 QAT 接口**：解析器不支持 Q/DQ（QuantizeLinear/DequantizeLinear）算子，量化组件是**纯训练后量化（PTQ）**，且量化阶段**强制前向校准并重新计算全部 scale（含输入层），不存在保留外部/QAT 学习 scale 的机制**。

由此直接触发 E0.3 停止条件：**iCraft 会重新校准并覆盖输入 scale → QAT 无法解决输入端信息丢失 → 停止并报告。**

---

## 1. E0.1 — iCraft 3.39 官方 QAT 接口调查（结论：无）

### 1.1 是否接受带 Q/DQ 节点的 ONNX？——**否**

- 解析器（`icraft-parse`）仅支持 **Pytorch .pt** 与 **ONNX opset=11**（`docs/parse`）。
- 官方「所有支持的算子」清单（`docs/start/compilation.html`、`docs/interface/cli_arguments.html`，Abs…Yolo 共 100+ 算子）中**没有 QuantizeLinear / DequantizeLinear**。
- 全安装目录 2305 个 HTML + 全部文本文件（py/toml/txt/h/hpp/cpp/rst/md/json）grep：`QAT/QDQ/QuantizeLinear/DequantizeLinear/量化感知/fake-quant` 命中**仅 1 处**——`docs/quantizer/{zhuge,buyi}.html` 中的一句指针：「量化感知训练的具体使用方法见**《QAT用户手册》**」。该手册**未随 SDK 附带**（无 pdf、无 manual、无 QAT 工具）。

### 1.2 是否保留 QAT 提供的 scale/zero-point？——**否，无此机制**

`icraft-quantize` 全部 CLI 参数（`--help` 实测）为：`json/raw/jr_path/qdtype/bits/target/forward_dir/forward_list/forward_mode/saturation/per/batch/bin_num/autoqset_num/smooth_alpha/input_norm/mix_precision/quant_autotune_config/asymmetric/before_relu/no_transinput/no_imagemake/normalize/precheck/names_file/ftmp_csv/raw_csv/decode_dll`。
**没有任何「保留/导入已学习 scale」的开关。**

### 1.3 是否在 Quantize 阶段重新覆盖 QAT 参数？——**是（必然覆盖）**

`docs/quantizer/zhuge.html` §1.2 明确：量化流程 = 加载浮点网络 → **前向校准（INT8 必做）** → 测量特征图 → 计算归一化系数 → 归一化 → 量化 → 生成。changelog 亦确认：`qdtype=int8` 时 `forward_dir/forward_list/saturation/per` 为**必配项**（即必须重新校准）。

因此，无论输入模型是否由 QAT 产生，**量化阶段都会用校准集重新统计并覆盖所有激活/输入的 scale**。唯一的两个外部钩子是：
- `--ftmp_csv` / `--raw_csv`：导入**特征图/权重的饱和点统计文件**（非 QAT scale 语义，且无 QAT 工具产出此类文件；changelog 仅记录其修复过 Cast 系数导入 bug）。
- `--input_norm`：仅把输入 normratio 设为「与其他特征图相等」，不是自由指定学习值。

### 1.4 真实量化语义（输入/Conv/FC，供记录）

- **输入**：进入首卷积前被 `Cast` 成 int8（per-channel scale，clip=127×scale），scale 由校准 KLD 饱和决定；`no_transinput=true` 关闭图片 [0,255]→[-128,127] 平移（本工程已设）。
- **Conv**：非深度可分离走 MPE+VPE，`cut_scale=m*2^(-n)`（m∈[0,255]，n∈[bits,2*bits+5]），per-channel 时按通道近似且 MPE 首截位强制相等。
- **Matmul（FC）**：参考 conv_const 非深度可分离实现，**暂不支持按通道量化**（per-tensor）。
- **输出层**：`Output` 算子，logits 亦被量化（D.1/D.2 已实证其为 AM-SSB-SC 崩塌的末端贡献者）。

### 1.5 权重 per-channel / 激活 per-tensor、舍入、饱和规则

- **权重**：`per=tensor|channel`；`per=channel` 时 conv 权重 (h,w,ci,co) 的 co 个通道对应 co 个 scale；`per_group=n` 按最后一维分 n 组。
- **激活**：经「归一化」把各层动态范围统一到量化可表达范围，再按归一化系数与饱和点确定 scale；默认**对称**（`zero_points=[]`），`--asymmetric` 可开非对称。
- **舍入**：硬件 scale 强制 `m*2^(-n)`（2 的幂尾数）格式。
- **饱和**：`saturation=kld|ems|null`（KLD=KL 散度最小；EMS=误差平方和最小；null=非饱和取 |max|）。

---

## 2. E0.2 — vendor-faithful 伪量化器（未构建，因 E0.1/E0.3 已否决）

iCraft 唯一提供的「量化前向仿真」是 **HostBackend 的 `fakeQf` 模式**（`docs/hostbackend`）：`setFakeQf(true)` 后前向在 FP32 上执行截位+饱和（`fake quantize forward`），用于对比量化前后输出。它是**运行期仿真/调试**功能，**不是带梯度的训练期伪量化器**。

若要做 QAT，伪量化器须在 PyTorch 手工实现（对称 int8、per-channel 权重、per-tensor 激活、就近舍入、clamp±127，并用 iCraft 产物中的真实 scale）。此路径在 E0.1/E0.3 已否决的前提下**无意义**（scale 不会保留），故不构建。

---

## 3. E0.3 — 输入层专项验证（决定性，触发停止条件）

1. **当前 AM 族输入饱和率**（D.3 Step 1/4 已实测）：AM-SSB-WC 13.6% / AM-SSB-SC 10.7%（最大 100%），其余 22 类 0.000%（clip ±6.334）。
2. **QAT 能否学习/控制输入 scale？** 输入是**固定预处理后的原始 IQ**（禁止改预处理），QAT 只能改权重、不能改输入分布本身；唯一能「控制输入 scale」的途径是让 QAT 学得的输入 scale 被编译期采纳。
3. **iCraft 编译后是否保留该输入 scale？——否。** 量化阶段对 INT8 **强制前向校准**，输入层 scale 由校准集输入特征图分布的 KLD 饱和重新计算（实测：384 基线 0.052646082、DRA 0.049874272，二者均由校准决定，非任何外部注入值）。**无「保留输入 scale」开关。**

**判决（触发 E0.3 停止条件）**：iCraft 会重新校准并覆盖输入 scale → **QAT 不能解决输入端信息丢失** → **停止并报告**。

补充技术论证（强化该结论）：输入端 int8 `Cast` 发生在**任何权重作用之前**，对 AM 族 ~10× 幅度输入先裁 ~6.4×；QAT 仅更新权重，无法阻止该前置裁剪；即使 QAT 权重更新使深层激活更易量化，输入端的信息已在前置 Cast 处永久丢失，无法通过权重补偿找回。

---

## 4. E0.4 — 门禁判定

- **E0 未通过**：无 QAT 接口 + 输入 scale 被重新校准覆盖。
- **不启动 QAT 训练**（E1 前提「E0 全部通过」不满足）。

---

## 5. 前向路径与状态

| 项 | 值 |
|---|---|
| 状态 | `M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`（保持） |
| E0 门禁 | **FAILED**（`M29-QAT-FEASIBILITY=FAILED`） |
| PTQ_CANDIDATES | REJECTED（384 基线 / 实验A / DRA 384 均不晋升） |
| BOARD_DEPLOYMENT | BLOCKED（禁碰板 / 禁写 Flash） |
| QAT 训练 | **未启动**（E0 未通过） |
| closed-set test | 未访问；QAT 未启动，无新 test 访问问题 |

**若仍希望走 QAT**，需向厂商（FMSH）索取随 SDK 缺失的《QAT用户手册》及配套 QAT 工具，并据其重新验证：
1. 该工具是否导出可被量化阶段保留的输入/激活 scale（或直接导出量化 json/raw）；
2. 若其依赖 `ftmp_csv`/`raw_csv` 注入饱和点，需确认格式并验证输入层 scale 是否真的被采纳。

在取得该工具并验证输入 scale 保留路径**之前**，本机 iCraft 3.39 内 PTQ 与 QAT 两条路径均告尽（PTQ 见 D.2/D.3；QAT 见本文）。

---

## 6. 证据清单

- `docs/quantizer/zhuge.html`（量化流程/参数/算子方案；QAT 指针）
- `docs/parse/index.html`（框架支持：Pytorch/.pt + Onnx opset11；无 Q/DQ）
- `docs/start/compilation.html`、`docs/interface/cli_arguments.html`（支持算子清单，无 QuantizeLinear/DequantizeLinear）
- `docs/hostbackend/index.html`（`fakeQf` 模式）
- `docs/changelogs/change_logs.html`（ftmp_csv/raw_csv 仅修 bug，无 QAT 功能引入）
- `icraft-quantize.exe --help`（全部参数，无 scale 保留项）
- 全目录 grep（文本+2305 HTML）无 QAT/量化感知/QDQ 命中
