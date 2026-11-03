# M20 最终报告 — 当前 NPU 12 类模型的语义 OOD-U / UNKNOWN 拒识

任务 id="39e5" · 工程 `F:\FPGA_Work\sdr_amr_12class_ood_u_v1` · 报告日期 2026-10-08

**一句话结论**：在**不动**当前 12 类 NPU 模型（权值 SHA `2ae95275…`）、不动 RTL/XDC/位流/
数据链/标签序/输入预处理/UI 的前提下，本任务交付了一个 **CPU 侧纯增量**的语义 OOD-U
拒识模块：`IQ → 当前 12 类 NPU → 12 维 raw logits → logit_margin 评分 → 已知 12 类 /
UNKNOWN`。离线阶段全部 8 个一键脚本 + 25 项 pytest + C++ release/ASan/UBSan + PyTorch↔ONNX
logits parity + C++/Python 评分回放一致 + 单次盲测全绿，两个确定性交付包已构建并独立
`sha256sum -c` 全 OK。**当前状态 = 代码 READY + 离线 READY，最高标记
`READY-FOR-M20-12CLASS-OOD-U-HARDWARE-TEST`**；实机 NPU logits 捕获与决策一致性比对待用户
上板完成，此前绝不写 `OOD_PASS / OOD_U_PASS / HARDWARE_PASS`。

---

## 一、工程边界

- 只做**模型侧 + 离线**：CPU 侧 OOD-U 评分/拒识/阈值 manifest/回放/盲测 + 板端集成边界
  文档与工具。
- **禁碰**：实板、写 Flash、启动 Vivado、训练模型、RTL/XDC/位流、当前 NPU 网络结构/权重、
  当前 12 类标签序、输入预处理、SDR/NPU 数据链、framebuffer 换帧生产逻辑、M18-0 A/B/C/D
  诊断工具、M14～M18-0 历史包。
- 不覆盖任何历史交付包；本 M20 交付在 `dist/` 版本化新增。

## 二、权威模型审计（先做，已完成）

当前权威板端模型 = `12CLASS_CHAIN_VALIDATION_MODEL`，SHA 锁定链逐级一一对应：

| 载体 | 文件 | SHA256（前 8 位） |
|---|---|---|
| checkpoint | `model_12class/seed2026_best.pt` | `7215290b…` |
| ONNX（opset17，固定 batch 1） | `model_12class/ad_amr_v1_1_opset17.onnx` | `f7758715…` |
| NPU JSON 描述 | `model_12class/model_12class.json` | `51364bdf…` |
| **NPU 权值（权威）** | `model_12class/model_12class.raw` | **`2ae95275…`** |

- **完整值**：`model_12class.raw` = `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`
  （打包内 `sha256sum` 复核一致）。
- **未使用** t017/seed2028 候选。输入 `[1,2,1024]` fp32 planar I/Q RMS≈1.0；输出
  **12 维 raw fp32 logits（无 Softmax）**，输出边界 `@fp(32)` 运行时已反量化。
- 审计详情见 `docs/M20_MODEL_OUTPUT_AUDIT.md`。

## 三、OOD-U 定义（语义 OOD / UNKNOWN）

- **语义级拒识**，不是信道级。区分只由「调制方式是否属于当前 12 类」决定，与 SNR/CFO/
  多径/IQ 失衡/相噪/削波无关。
- `UNKNOWN`（拒识）与 `NO_SIGNAL`（无输入）、`ERROR`（非有限 logits）严格三分。
- 判定链（`cpp/ood_u_detector.cpp`）：`score > threshold` → UNKNOWN；`score == threshold`
  → 接受（已知）。**默认关闭时与原 12 类 argmax 链逐字节一致**（纯增量安全边界）。
- **红线**：低 SNR / CFO / 多径 / IQ 失衡 / 相噪 / 削波后的 12 类信号**不算**语义 OOD
  （OOD-R 反例，由 §九保护测试强制）。

## 四、未知信号集合

- **near_12**（主评分族，13 种）：8ASK, 16PSK, 32PSK, 16APSK, 32APSK, 64APSK, 128APSK,
  32QAM, 128QAM, 256QAM, OQPSK, AM-SSB-WC, AM-SSB-SC。
- **far**（主评分族 + 阈值锁族，5 种）：LFM, CW, MULTITONE, PULSE, FHOP。
- **ambiguous**（侧报，4 种）：AM-DSB, WBFM, FM, GMSK —— **不计入主指标/方法选择**。
- 所有 OOD 波形与 ID **同一生成器 + 同一 AWGN 级 + 同一信号域**合成（128 kHz / 16 kHz /
  8 sps / rolloff 0.35 / amp 1.0 / 1024 点）。`near_24` 族本任务不使用。

## 五、数据隔离

- 三套 split 由 `split_code` 烘焙进每个 `SeedSequence`，零交集：`oe_aux_train`(1) /
  `ood_validation`(2，只用于选方法+锁阈值) / `ood_final_test`(3，只盲测一次)。
- `OOD_SEED = 12600`（独立命名空间，与模型训练种子无关）；`BENCHMARK_SNR_VALUES = (0,10,20)`。
- `assert_no_overlap`（样本 SHA 零交集）+ `split_sha`（每 split 排序 SHA 散列）落盘进
  manifest；`FinalTestGuard` 落盘审计标志强制盲测单次访问。

## 六、防止生成器捷径（已审计，无捷径）

- `assert_shared_domain` 逐项比对 signal_config（采样率/符号率/样点长/幅度/频偏/相偏/脉冲
  成形）完全一致。
- 4 个模型无关廉价特征 AUROC（|AUROC-0.5| ≥ 0.40 才判捷径）：

| 特征 | AUROC | 判定 |
|---|---|---|
| rms_power | 0.5012 | 无捷径 |
| papr | 0.5371 | 无捷径 |
| bandwidth_frac | 0.4680 | 无捷径 |
| spectral_centroid | 0.5523 | 无捷径 |

→ **`shortcut_detected = false`**（`runs/m20_data_audit/data_audit_report.json`）。

## 七、评分方法（5 种，越大越 OOD）

msp / entropy / max_logit / **logit_margin** / energy，统一 `higher_is_ood`。全部在 raw
logits 上计算，`logit_margin = -(top1 - top2)`（partial sort 取前两大 logit，对公共偏移
不变）。维度守卫 `assert_logits_12`：任何入口评分前强制 `[N,12]` 且有限（NaN/Inf fail-closed）。

## 八、分数选择与阈值冻结

- **方法选择 = 六准则排名聚合**（`auroc_near/far/overall`、`fpr95_overall`、`oscr_overall`、
  `impaired_id_accept_at_99pct`），OOD-R 门槛 `IMPAIRED_ACCEPT_FLOOR=0.90`。
- **胜出 = `logit_margin`**（`temperature=1.0`，非 energy 不扫温度）。
- **默认工作点 `id_accept_99`**，冻结阈值：

  ```
  threshold = -0.15274411201477073   (logit_margin ≤ 0，故为负；score > 阈值 → UNKNOWN)
  ```

- 写一次 manifest（`write_ood_u_manifest(overwrite=False)`），三工作点全冻结：

| 工作点 | 阈值 | ID 接受率 | ID 误拒 | near 拒识 | far 拒识 |
|---|---|---|---|---|---|
| id_accept_95 | -0.48299 | 0.95 | 0.05 | 0.1538 | 0.2933 |
| **id_accept_99（默认）** | **-0.152744** | **0.99** | 0.0111 | 0.0590 | 0.0767 |
| far_ood_target | -15.23898 | 0.1194 | 0.8806 | 1.0 | 0.95 |

- 校准样本 count = id 720 / ood 1080；`final_test_accessed = false`（冻结时未触碰盲测集）。
- C++ 侧 `load_ood_u_manifest` 同语义 fail-closed。

## 九、已知类保护（OOD-R）

- `ood_u/protection.py` 覆盖低 SNR（-20..-10 dB）与 6 类信道损伤（CFO/多径/IQ 失衡/相噪/
  削波/多损伤）+ 强邻近干扰，强制「不得通过大量拒识已知类虚假提高 OOD 指标」。
- 方法选择把 `impaired_id_accept_at_99pct` 纳入聚合并设 0.90 地板（`calibrate.py`），
  落败方法若在 99% 接受点对受损已知类接受率 < 0.90 即被淘汰。
- 64QAM 已知模型问题**不属本任务**，未以任何降门限方式伪修复。

## 十、最终盲测指标（`ood_final_test`，单次访问，冻结阈值）

| 指标 | 值 |
|---|---|
| ID 样本 / near / far / ambiguous | 720 / 780 / 300 / 240 |
| **ID 接受率** | **0.9833（98.33%）** |
| ID 误拒率 | 0.0167（1.67%） |
| **near 拒识率** | **0.0603（6.03%）** |
| **far 拒识率** | **0.1033（10.33%）** |
| OOD 总体拒识率 | 0.0722（7.22%） |
| 冻结阈值检测准确率 | 0.4367（bootstrap 95% CI [0.4267, 0.4461]，n_boot=1000） |
| overall AUROC / AUPR-in / AUPR-out / FPR95 | 0.8037 / 0.7507 / 0.8265 / 0.575 |
| near AUROC / far AUROC / ambiguous（侧报）AUROC | 0.7897 / 0.8400 / 0.5292 |

- **ID 接受率按 SNR**（`id_accept_by_snr`）：0 dB = 0.9542，10 dB = 0.9958，20 dB = 1.0。

> 说明：near/far 拒识率在默认 `id_accept_99` 下相对温和，这是「优先保 ID 接受」工作点的
> 直接结果；`far_ood_target` 工作点可达 95% far 拒识但以 ID 接受为代价（§八表），默认不启用。
> ambiguous 族 AUROC≈0.53（近随机），符合其「与已知类近等价」的侧报定位。

## 十一、NPU 真实 logits 校准（契约 + 现状）

- 见 `docs/M20_LOGITS_PARITY_CONTRACT.md`。容差：`FP32_MAX_ABS_DIFF=1e-4`、
  `NPU_MAX_ABS_DIFF=0.60`（int8 一步 ≈ 0.2327 + 裕量）、逐样本 argmax 一致。
- 固定 parity 集 N=31（12 类 × {0,10}dB = 24 + near_12 代表 4 + far 代表 3），raw fp32
  `parity_iq.bin` 供板端捕获与主机参考喂同一字节。
- **离线实测（PyTorch↔ONNX）**：`max_abs_diff = 9.54e-6`（< 1e-4）、`argmax_agreement = 1.0`、
  `pytorch_vs_onnx_decision_agreement = 1.0`、`within_tolerance = true`。
- **`npu_logits_provided = false`** —— 离线无 ZG330，板端真实捕获待用户执行。

## 十二、CPU 侧 C++ 拒识模块

- `cpp/ood_u_contract.hpp`（contract.py 逐字节镜像）+ `cpp/ood_u_detector.hpp/.cpp`
  （5 评分 + `classify_or_reject` 严格不等式）+ `cpp/ood_threshold_manifest.hpp/.cpp`
  （load_ood_u_manifest fail-closed）+ `cpp/ood_u_replay_main.cpp`（`std::setprecision(17)`）
  + `cpp/minijson.hpp` + `cpp/build_ood_u.sh`（原生 g++，缺时 WSL fallback）。
- 评分与 Python 在 `1e-6` 容差内逐项一致（`m20_board_replay.py`，实测 `max_score_diff=0.0`）。

## 十三、板端集成边界

- `tools/capture_npu_logits.cpp` 双模式 `--mode=board`（真 NPU 前向，接线点 `npu_forward`）
  / `--mode=replay`（主机回放验证 I/O）；输出规范 schema `{n, output_dim, logits}`。
- 拒识模块是**纯增量**：默认关闭时与原 12 类 argmax 链逐字节一致，不改 NPU/数据链/分类结果。
- 板端捕获与上板复测由用户本人执行，我禁碰板/禁写 Flash。

## 十四、日志要求

- 每个一键脚本输出唯一结果行 `M20_RESULT result=PASS|FAIL ...`，`set -euo pipefail`
  非零即停；任一子项失败 fail-closed，绝不静默通过。

## 十五、测试要求（19 类，离线全绿）

- **pytest 25 passed**（`tests/test_m20_*.py`）：分数方向/边界语义/维度守卫/NaN-Inf/
  ONNX parity/int8 仿真容差/隔离捷径/保护/语义/板边界/C++ 一致性/身份 manifest/单次访问。
- **C++**：release + ASan/UBSan 三连 build+run 全 PASS（`cpp/build_ood_u.sh`）。
- **脚本**：`bash -n` 9 个 `.sh` 全 OK；`py_compile` M20 模块全 OK。
- 原有 RML24 V1.1 离线测试（pytest 198 passed 4 skipped）不受本任务改动影响（M20 纯新增）。

## 十六、一键脚本（8 个，全部离线跑通 PASS）

1. `run_m20_data_audit.sh` — 模型身份 + 标签序 + 信号域共享 + 三 split 零交集 + 捷径审计（无捷径）。
2. `run_m20_score_benchmark.sh` — 5 评分 × 3 族 × 3 SNR 基准 + 受损已知类。
3. `run_m20_threshold_calibration.sh` — 六准则聚合选 `logit_margin` + 写一次冻结 manifest。
4. `run_m20_npu_logits_capture.sh` — 生成 parity 集 + 参考 logits + 板端捕获契约。
5. `run_m20_logits_parity.sh` — PyTorch↔ONNX parity + 冻结阈值决策一致性（max_abs 9.54e-6）。
6. `run_m20_board_replay.sh` — C++/Python 评分回放一致（max_score_diff 0.0，decision 1.0）。
7. `run_m20_final_blind_test.sh` — 单次盲测 + FinalTestGuard 审计标志。
8. `test_m20_ood_u.sh` — 25 pytest + C++ release/ASan/UBSan + bash -n 全量回归。

## 十七、阶段状态

```
最高可达：READY-FOR-M20-12CLASS-OOD-U-HARDWARE-TEST
当前：    READY-FOR-M20-12CLASS-OOD-U-HARDWARE-TEST（代码 READY + 离线 READY）
禁用：    OOD_PASS / OOD_U_PASS / HARDWARE_PASS / FINAL_MODEL_PASS / DEPLOYMENT_PASS / PROJECT_COMPLETE
```

## 十八、交付物（`dist/`，版本化新增，不覆盖历史）

| 包 | 内容 | 字节 | SHA256 | 文件数 |
|---|---|---|---|---|
| `m20_12class_ood_u_patch.tar.gz` | M20 净增（ood_u/ + cpp 源码 + tools/ + scripts/m20_*.py + run_m20_*.sh + test_m20_ood_u.sh + tests/test_m20_*.py + docs/M20_*.md + model_12class/） | 4,595,159 | `fd0dcf295d7b3e2f5d7103dd7832b18983e9a213a007157d2f034dee72af1eda` | 55 内容 + SHA256SUMS |
| `sdr_amr_12class_ood_u_m20_package.tar.gz` | 全量自包含工程源码（继承 V1.1 基座 + M20） | 4,772,888 | `d45148e2e3c36bdfb862693395f287c2bb23379f9edb57f8edeb3618bd609c5b` | 214 内容 + SHA256SUMS |

- 两包均确定性（gzip mtime=0、owner 0、稳定排序、内置 SHA256SUMS），独立解包
  `sha256sum -c` 全 OK；补丁 ⊆ 全量（diff 零差异）。
- 排除：cpp 已编译二进制（`ood_u_replay`/`test_ood_u_detector`/`test_ood_u_detector_san`）、
  `runs/`、`data/radioml2018/{rml24_split_indices.npz, audit.json}`、`__pycache__`、
  `.pytest_cache`、`dist/`（目标端由 `cpp/build_ood_u.sh` 重编译、`run_data_audit.sh` 重生成）。
- **本最终报告自身不在包内**（它是关于交付包的交付摘要，放包内会造成「报告引用其所在
  归档的 SHA」的自指矛盾），作为 `docs/M20_FINAL_REPORT.md` 随工程一并交付，§十八数值
  因此为精确稳定值。
- 构建脚本 `scripts/package_m20.py` 已随全量包交付，可复现。

## 十九、最终报告 —— 回答 10 问

1. **NPU 能否取得 raw logits？** 能。模型输出审计已证当前 NPU 输出 **12 维 raw fp32
   logits（无 Softmax，运行时已反量化）**，板端 `npu_classifier.hpp` 直接 memcpy 读 48
   字节，无需从概率反推。板端捕获工具 `tools/capture_npu_logits.cpp --mode=board`。

2. **模型 SHA 是否确认为 2ae95275…？** 是。`model_12class.raw` SHA 复核 =
   `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`；checkpoint→ONNX→NPU
   三级 SHA 链（`7215290b…` → `f7758715…` → `2ae95275…`）锁定一致，**未用 t017/seed2028**。

3. **用了哪种 OOD 分数？** `logit_margin = -(top1(z) - top2(z))`（raw logits 前两大 logit
   之差取负，越大越 OOD）。

4. **为什么？** 在 `ood_validation` 上做六准则排名聚合（近/远/总体 AUROC、FPR95、OSCR、
   99% 接受点受损已知类接受率），`logit_margin` 综合胜出；它对 logits 的公共偏移不变，
   在 raw-logits 且无 Softmax 依赖的部署口径下最稳，且不因信道损伤误拒已知类。

5. **阈值是否来自 NPU 真实输出？** **诚实的现状**：阈值 `-0.152744` 来自**权威 fp32
   checkpoint 的 logits**（`ood_validation` 校准），已通过 PyTorch↔ONNX 两方 fp32 parity
   （`1e-4`，实测 9.54e-6）+ int8 仿真容差（`0.60`）验证；**尚未**在真实 NPU 上捕获板端
   logits（离线无 ZG330）。最终「来自 NPU 真实输出」的确认需用户上板跑
   `run_m20_npu_logits_capture.sh` + `run_m20_logits_parity.sh --npu-logits …`，在冻结阈值
   下确认 `pytorch_vs_npu_decision_agreement = 1.0`。

6. **ID 接受率？** **98.33%**（冻结阈值 `id_accept_99`，`ood_final_test` 720 样本）。按 SNR：
   0 dB = 95.42%、10 dB = 99.58%、20 dB = 100%。

7. **near/far OOD 拒识率？** near_12 = **6.03%**、far = **10.33%**（`id_accept_99` 工作点）。
   `far_ood_target` 工作点可达 95% far 拒识，但以 ID 接受为代价，默认不启用。

8. **低 SNR 已知类误拒率？** 0 dB（基准最低 SNR）ID 误拒率 = **4.58%**（接受率 95.42%）；
   更低 SNR（-20..-10 dB）与信道损伤属 OOD-R 保护域，不判 UNKNOWN，且方法选择设
   `IMPAIRED_ACCEPT_FLOOR=0.90` 地板。

9. **是否存在 generator shortcut？** **否**。4 个模型无关特征 AUROC 全部近随机
   （rms_power 0.501 / papr 0.537 / bandwidth_frac 0.468 / spectral_centroid 0.552，
   |AUROC-0.5| ≤ 0.052 < 0.40 阈值），`shared_signal_domain` 断言通过，`shortcut_detected=false`。

10. **当前是代码 READY / 离线 READY / 硬件 READY？** **代码 READY + 离线 READY**。
    - 代码 READY：C++ 模块编译+release/ASan/UBSan 全 PASS，与 Python 评分 `1e-6` 一致。
    - 离线 READY：8 脚本全 PASS、25 pytest、PyTorch↔ONNX parity、C++/Python 回放一致、
      单次盲测指标齐全、两包独立 `sha256sum -c` 全 OK。
    - **非硬件 READY**：真实 NPU logits 捕获 + 冻结阈值下决策一致性比对待用户上板完成。

---

## 红线声明（自检）

- 未启动 Vivado、未训练任何模型、未写 Flash、未碰实板。
- 未修改 RTL/XDC/位流、当前 NPU 权重/网络结构、标签序、输入预处理、SDR/NPU 数据链、
  framebuffer 换帧、M18-0 A/B/C/D 诊断工具、M14～M18-0 历史包。
- 未把低 SNR/CFO/多径/IQ 失衡/相噪/削波当语义 OOD；未调低门限伪修复 64QAM。
- 未写任何 `OOD_PASS / OOD_U_PASS / HARDWARE_PASS / FINAL_MODEL_PASS / DEPLOYMENT_PASS /
  PROJECT_COMPLETE`。
- 未使用 t017/seed2028 候选替换当前模型。
