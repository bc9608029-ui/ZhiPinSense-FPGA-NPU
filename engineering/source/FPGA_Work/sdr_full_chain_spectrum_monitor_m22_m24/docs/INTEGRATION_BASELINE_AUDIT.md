# M22–M24 集成基线审计（INTEGRATION_BASELINE_AUDIT）

任务 id="39e5" · M22–M24（运行时性能修复 + P0/P1 频谱监测能力落地）首个交付物。
本文件确定**唯一集成基线**、M19/M20 迁移文件、冲突、权威 SHA 与 12 类模型身份。
原则：**先确认唯一集成基线，不允许直接拼接不兼容工程。**

---

## 1. 结论摘要（单点真相）

| 项 | 判定 |
|---|---|
| 唯一集成基线 | `F:\FPGA_Work\sdr_full_chain_12class_ui_v3_m19\work\pkg\`（当前最新稳定 12 类板端软件） |
| 权威合并位流 | `combined_npu_hdmi_disable_icap.bit`（5,980,628 B，SHA `22fec95c…`，**不改/不重编**） |
| 权威 12 类模型 | `model_12class/model_12class.raw`（2,851,472 B，SHA `2ae95275…`，**冻结**） |
| 模型标签 | `12CLASS_CHAIN_VALIDATION_MODEL`（通路验证模型，OOD=NO_GO） |
| 12 类标签序 | `cat::target_12()`：OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM |
| 24 类模型 | **NOT_READY**（未训练，见 §8；M24 只允许 stub + 标记 `24CLASS_MODEL_NOT_READY`） |
| M20 OOD-U | 仅作实验功能，默认 OFF，near/far 6.03%/10.33% 不得宣传为可靠 UNKNOWN |

---

## 2. 集成基线判定（为何是 M19 `work/pkg/`）

**排除的候选**：

| 候选 | 排除原因 |
|---|---|
| `sdr_full_chain_12class_combined_v1` | 是「源软件基线」与位流/Vivado 工程的宿主，**冻结只读**；软件增量都在 ui_v3 链上，不直接在此改 |
| `sdr_full_chain_12class_ui_v3` / `_m17*` / `_m18*` | ui_v3 链的历史里程碑，均已被 M19 吸收（PROVENANCE §4 状态红线逐条列出吸收关系） |
| `sdr_amr_12class_ood_u_v1`（M20） | 独立 OOD-U 后处理工程，**非** 12 类主链；其核心需「迁移」进本工程，而非整体作基线 |

**选定理由**：

1. M19 = ui_v3 链**最新**版本（`ls -dt` 确认无更新候选），PROVENANCE 溯源完整（M0→M19，359 拷贝 + 逐里程碑登记）。
2. M19 `work/pkg/` 是**完整自洽的板端软件包**：含 `board_package/`（Gate 6/7/9/10 + UI live + 触摸/控制）、`sdr_adapter/`（DSP/RF/Pluto/resampler/signal_presence/dsp_measure）、`ui_sw/`（framebuffer/渲染/主题/布局）、`model_12class/`（契约+json+raw+sha256）、`deployment_golden/`（240 黄金输入/期望）、`scripts/`、`host_tests/`。
3. M19 全量包 `sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package.tar.gz` = 3,310,229 B，SHA `3d6d793c5a89ab983dfd6c381032192401bc3678dc43ae1b3e7139e3e76a31cd`（实测）；补丁 `m19_ui_polish_patch.tar.gz` = 305,496 B，SHA `6a33a8f5292c0a09c7b27d8229ae0b3e12921fb92ebc0773bf49c9e092cc9c85`。
4. PROVENANCE §1 明确：**源基线 = `combined_v1`（smoke_v1 位流 + smoke_v2 触摸软件）**，权威位流与模型「保持不变」，本工程链只加软件/DSP/板端程序。

> 基线 = 「M19 软件（`work/pkg/`） + 冻结位流 `22fec95c…` + 冻结模型 `2ae95275…`」三者的联合。
> 位流与模型只读复用，**本 M22–M24 工程只在新工程内改动软件/DSP/板端程序**，绝不碰位流/模型/RTL/XDC/Flash。

---

## 3. 冻结资产与权威 SHA（实测）

| 资产 | 路径 | 字节 | SHA256 |
|---|---|---|---|
| 权威合并位流 | `combined_v1/outputs/smoke_v1/bitstream/combined_npu_hdmi_disable_icap.bit` | 5,980,628 | `22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9` |
| （废弃位流，勿用） | `combined_npu_hdmi_raw.bit` | 5,980,044 | `bc58f4f1…` |
| （废弃位流，勿用） | `combined_npu_hdmi_raw_pre_fix.bit` | 5,980,044 | `d62c3d4e…` |
| 权威 12 类模型 raw | `work/pkg/model_12class/model_12class.raw` | 2,851,472 | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |
| 12 类模型 json | `work/pkg/model_12class/model_12class.json` | 222,804 | `51364bdf49d280944094f7af89ea4c759b3ae4d0d350be5f8c43e0c5849ab834` |
| 12 类模型 sidecar | `work/pkg/model_12class/model_12class.sha256` | 84 | `fbdaf1ac…` |
| 源 ONNX（仅审计，不在板上运行） | `…/formal/export/onnx/ad_amr_v1_1_opset17.onnx` | — | `f77587152b52cda9a467b28790bc62d0eb0c639db2c39da82642c00ca8deda5a` |
| 部署契约 | `work/pkg/model_12class/MODEL_DEPLOYMENT_CONTRACT.md` | — | `ef4c32b4…` |
| 位流设计说明 | `work/pkg/docs/COMBINED_BITSTREAM_DESIGN.md` | — | `0e9987ff…` |
| M19 全量包 | `ui_v3_m19/dist/sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package.tar.gz` | 3,310,229 | `3d6d793c5a89ab983dfd6c381032192401bc3678dc43ae1b3e7139e3e76a31cd` |
| M19 补丁 | `ui_v3_m19/dist/m19_ui_polish_patch.tar.gz` | 305,496 | `6a33a8f5292c0a09c7b27d8229ae0b3e12921fb92ebc0773bf49c9e092cc9c85` |

**关键运行脚本 SHA（基线，改动需登记）**：

| 脚本 | SHA256 |
|---|---|
| `scripts/run_gate7.sh` | `8a19cd32…` |
| `scripts/run_gate9.sh` | `7ecc0d1a…` |
| `scripts/run_gate9_ui.sh` | `4b4b5bc7…` |
| `scripts/run_ui_live.sh` | `d1763ed0…` |
| `scripts/common.sh` | （M17 加 BITSTREAM_SHA，见 PROVENANCE） |

**关键板端源文件 SHA（基线，M22 生命周期改动的目标文件）**：

| 文件 | SHA256 |
|---|---|
| `board_package/npu_classifier.hpp` | `f7e24f79…` |
| `board_package/producer_12class.hpp` | `a44eeb8c…` |
| `board_package/board_gate9_full_chain_12class.cpp` | `3debe094…` |
| `board_package/board_ui_live_12class.cpp` | `d02a2d77…` |

---

## 4. 12 类模型身份（冻结，单点真相）

来源 = `model_12class/MODEL_DEPLOYMENT_CONTRACT.md`（全部本机实测核验）。

| 项 | 值 |
|---|---|
| 模型标签 | **`12CLASS_CHAIN_VALIDATION_MODEL`**（通路验证，非「最终鲁棒/准确率 PASS/OOD PASS」） |
| 类别数 | 12（frozen 顺序，§5） |
| OOD 门 | **NO_GO**（源 `acceptance.json` OOD gate 未过；本模型仅验证链路通路） |
| 网络 | ADAMRV11Net 变体（opset17，12 类） |
| 输入 | 单输入 `iq` `[1,2,1024]` fp32（ch0=I，ch1=Q；训练域 RMS=1.0；无 FPGA 特征/无反量化） |
| 输出 | 单输出 `logits` `[1,12]` fp32（**raw logits，无 softmax**；argmax 在 CPU 侧） |
| 算子 | Add(12)/Conv(28)/Gemm(2)/ReduceMean(1)/Relu(24) |
| 编译 | iCraft CLI v3.39.0，目标 `@zhuget(330)`（FMQL30TAI NPU），`parse→optimize→quantize→adapt→generate` 五阶段 |
| 量化 | **INT8**（非 FP16）：per-channel 对称无零点、KLD 饱和、`no_transinput=true`（输入保持 fp32）、输出自动反量化 |
| 参数量 / MAC | 279,036 / 46,544,384（12 类；24 类 280,584 / 46,545,920，见 §8） |
| 部署黄金集 | 240 样本（12 类 × 20，SNR 10dB），argmax 与标签自洽 236/240（98.3%） |

**冻结约束（M22–M24 全程遵守）**：不删/不换模型算子、不改数学、不静默 HostBackend 回退、
非图像输入（no_transinput/no_imagemake 关闭）、校准集仅取冻结 train split、**不用 t017/seed2028 替换**。

---

## 5. 类别契约（12 类权威序）

来源 = `sdr_adapter/categories.hpp`（M19 pkg 内，SHA 见 SOURCE_PROVENANCE_SHA256.txt）。

| idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 类 | OOK | 4ASK | AM-DSB | WBFM | 2FSK | GFSK | BPSK | QPSK | 8PSK | 16QAM | 64QAM | OFDM |

- 三层契约并存：`frozen_8`（Mandatory Core 8 类，部署早期）/ `current_10`（V1.1 AMR 10 类）/ `target_12`（12 类权威）。
- **本工程 12 类链只用 `cat::target_12()`**（模型契约 §3 明确「板端程序只从 `cat::target_12()` 取序，不另写」）。
- ⚠️ **待办（低优先级文档勘误）**：`categories.hpp` 头注释仍写 `target_12` 为「RESERVED, not a real output today」，与 12 类模型已部署事实（模型契约 §3）冲突。此注释为 12 类模型部署前遗留；**以模型契约为准**。M22 不强制改（避免无谓触碰共享头），但审计留痕。

---

## 6. M19 集成基线目录清单

`work/pkg/` 顶层子目录（483 文件，`SHA256SUMS.txt` 覆盖 438 条）：

| 目录 | 内容要点 |
|---|---|
| `board_package/` | Gate 6/7/9/10 板端程序、UI live、触摸/控制客户端、npu_classifier、producer、rearm 状态机、delay_gate |
| `sdr_adapter/` | categories、signal_presence、dsp_measure、auto_level_control、resampler、NCO、receiver_scale、pluto、mock_iio、pipeline、result_frame、ui_report |
| `ui_sw/` | direct_framebuffer_backend、ui_render、ui_theme（M19 语义色）、ui_layout（M19 8px 网格）、font_atlas |
| `model_12class/` | MODEL_DEPLOYMENT_CONTRACT、model_12class.json/raw/sha256 |
| `deployment_golden/` | 240 input_*.bin + expected_logits/argmax + manifest |
| `contracts/` | pluto_config、rx_iq_format、sampling_and_iq |
| `scripts/` | run_gate6/7/8/9/10、run_ui_live、run_*_acceptance、package_*、common、process_guard |
| `host_tests/` | 全量主机测试 + build/run_tests/syntax_check/test_board_build |
| `host_tools/` | compare_64qam_threeway.py 等 |
| `docs/` | 全套契约/验收/审计文档 |
| `artifacts/` | ui_m19 快照 PPM |

---

## 7. M20 OOD-U 迁移集

勘察（只读）结论：M20 = `F:\FPGA_Work\sdr_amr_12class_ood_u_v1`，其 OOD-U 板端 CPU 模块全部集中在
`cpp/`（8 文件）+ `tools/`（1 文件），**与 M19 基线零文件名冲突**。

### 7.1 迁移最小集（板端 CPU 拒识模块，7 文件）

| # | 源文件 | 用途 |
|---|---|---|
| 1 | `cpp/ood_u_contract.hpp` | 冻结契约：`MODEL_SHA256=2ae95275…`、`MODEL_NAME=12CLASS_CHAIN_VALIDATION_MODEL`、`LABEL_ORDER_12`（12 类序）、`OUTPUT_DIM=12`、`DIRECTION=higher_is_ood`、`SCORE_METHODS` 五选一 |
| 2 | `cpp/ood_u_detector.hpp` | `OodDecision{known,valid,class_index,score,threshold,score_method,class_name}` |
| 3 | `cpp/ood_u_detector.cpp` | 五评分（msp/entropy/max_logit/logit_margin/energy）+ `classify_or_reject` |
| 4 | `cpp/ood_threshold_manifest.hpp` | `OodThresholdManifest` 结构 |
| 5 | `cpp/ood_threshold_manifest.cpp` | `load_ood_u_manifest` fail-closed（校验 model SHA/score_method/direction/temperature 有限正/threshold 有限/label_order 逐位/final_test_accessed==false） |
| 6 | `cpp/minijson.hpp` | manifest 加载器的 JSON 解析依赖 |
| 7 | `runs/m20_threshold_calibration/ood_u_threshold_manifest.json` | 冻结阈值（运行期数据） |

### 7.2 建议同迁（验证回路，可选）

`cpp/ood_u_replay_main.cpp`（logits 回放一致性）、`cpp/test_ood_u_detector.cpp`+`cpp/build_ood_u.sh`（主机单测/构建）、`tools/capture_npu_logits.cpp`（板端 NPU logits 捕获，`npu_forward` 板端接线占位）。

### 7.3 零冲突确认 + 模型工件一致

- M20 全部 9 个 C/C++ 文件名与 M19 `board_package/`（31 文件）+ `sdr_adapter/`（42 文件）**无任何同名**。
- M19 与 M20 的 `model_12class.raw`（`2ae95275…`）、`model_12class.json`（`51364bdf…`）**字节完全一致**——OOD-U 契约对 M22–M24 基线的模型同样成立，模型工件无需迁移。

### 7.4 冻结阈值与语义（M20 单源真相）

| 项 | 值 |
|---|---|
| 评分方法 | **logit_margin** = `-(top1 - top2)` |
| 方向 | higher_is_ood（分数越高越 OOD） |
| temperature | 1.0 |
| 阈值（默认工作点 id_accept_99） | **-0.15274411201477073** |
| 判决 | `score > threshold → UNKNOWN`；`score <= threshold → argmax 已知类`（`==` 判接受） |
| 非有限 logits | `ERROR`（valid=false，绝不静默判 UNKNOWN） |
| 无输入 | `NO_SIGNAL` |
| near/far 拒识 | 6.03% / 10.33%（冻结模型能力天花板，**不得宣传为可靠 UNKNOWN**） |

### 7.5 接线点与「默认关闭」安全边界

- **插入位置**：NPU 产出 12 维 raw fp32 logits 之后、argmax 之前（M19 `producer_12class.hpp:245` `classify()` 返回 logits 后、`:246` `argmax_index()` 前）。`classify_or_reject(logits,12)` 自带 argmax，包裹原 argmax 步骤。
- **默认关闭**：阈值设 `+1e30`（logit_margin 恒 ≤ 0，永不触发），CPU 模块输出与原 12 类 argmax 链**逐字节一致**（`tests/test_m20_board_boundary.py:91` 锁定）。即拒识为**纯增量**：不改 NPU/数据链/原分类结果。
- **接线工程量（M23 阶段）**：`npu.infer()` 返回 logits 后调用 `classify_or_reject`，`class_index` 喂 `engine_.update(stats, present, argmax)`（UNKNOWN 时 argmax=-1，对齐 NO_SIGNAL 通路）；`chain_common.hpp fill_result` 在 UNKNOWN 时输出 UNKNOWN 哨兵。M20 未提供板端胶水代码（只给纯模块 + 捕获占位），具体胶水属 M23 实现。

---

## 8. 24 类模型就绪状态

勘察（只读）结论：**24 类模型未训练（无正式 checkpoint/ONNX/INT8/NPU 产物）**，M24 只允许
stub + 标记 **`24CLASS_MODEL_NOT_READY`**。工程 `sdr_amr_rml24_ood_v1_1` 状态 =
`READY-FOR-AUTODL-RML24-OOD-V1.1-CUDA-PREFLIGHT`（离线训练/评估**尚未执行**）。

### 8.1 训练前就绪条件现状矩阵

| # | 条件/产物 | 状态 | 证据 |
|---|---|---|---|
| 1 | 离线单 batch 过拟合 smoke 门 | ✅ 已满足（本地 CPU，acc=1.0，finite_gradients） | `v1/runs/rml24_smoke/overfit_probe.json` |
| 2 | 离线测试套件 | ✅ 已满足（本地 CPU 143 passed / V1.1 198 passed 4 skipped） | v1_1 `PROVENANCE.md` |
| 3 | HDF5 数据审计（SHA+切分+manifests） | ❌ 缺失（本地无 21GB HDF5，须 AutoDL `run_data_audit.sh`） | `README_AUTODL.md` |
| 4 | CUDA preflight（8 子检查） | ❌ 缺失（未执行，需 GPU） | `scripts/cuda_preflight.py` |
| 5 | 已训练 checkpoint（`*.pt/*.pth`） | ❌ 缺失（`find` 为空） | 两工程全量检索 |
| 6 | ONNX 导出产物（`*.onnx`） | ❌ 缺失 | `find *.onnx` 为空 |
| 7 | INT8 / fake-INT8 量化产物 | ❌ 缺失（仅 `v2/fake_int8.py` 仿真代码） | — |
| 8 | NPU/iCraft 编译产物（`.json/.raw`） | ❌ 缺失 | — |
| 9 | OOD 基线 / 阈值锁定 | ❌ 缺失（依赖 frozen checkpoint） | — |
| 10 | 最终评估 / 12-vs-24 选择 | ❌ 缺失 | — |

> 训练前门禁落盘实现 = `autodl_rml24/run_all.sh`（17 步）+ `scripts/cuda_preflight.py`（8 子检查）。
> 12 类导入契约 `contracts/12class_import_contract.json` 的 `checkpoint_path`/`model_sha256` 仍 `PENDING_*`。

### 8.2 参数量 / MAC 核实（代码推导，任务值正确）

`ADAMRV11Net`（`models/ad_amr_v1_1_net.py`）解析：合计 = 277,488 + 129·n 参数 / 46,542,848 + 128·n MAC。

- n=12 → **279,036 参数 / 46,544,384 MAC** ✓
- n=24 → **280,584 参数 / 46,545,920 MAC** ✓（差 = +1,548 参数 / +1,536 MAC，仅末层 Linear(128→n)）

### 8.3 12/24 标签序关系 —— **重要修正：非前缀、非子集**

- 12 类序（`cat::target_12`）：`OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`
- 24 类序（`OFFICIAL_CLASS_ORDER`，四处逐字节一致）：`OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK, 16APSK, 32APSK, 64APSK, 128APSK, 16QAM, 32QAM, 64QAM, 128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC, AM-DSB-WC, AM-DSB-SC, FM, GMSK, OQPSK`
- **非前缀**：24 类序前 12 个与 12 类序完全不同。
- **非子集**：12 类有 5 类**不在** 24 类内（AM-DSB、WBFM、2FSK、GFSK、OFDM = 24 类视角的 near-OOD）。
- **精确同名交集 = 7 类**：OOK, 4ASK, BPSK, QPSK, 8PSK, 16QAM, 64QAM。
- 近义/歧义对（不进主 OOD 指标）：WBFM↔FM、GFSK↔GMSK、2FSK↔GMSK、AM-DSB↔AM-DSB-WC、AM-DSB↔AM-DSB-SC。

**结论**：两套标签序**独立冻结**；12/24 策略对比只能按 `contracts/LABEL_ONTOLOGY.md` 的
COMMON / AMBIGUOUS / near-OOD 语义对齐，**不能按前缀/子集直接对齐**。

---

## 9. 迁移边界与红线（M22–M24 全程）

**绝不修改 / 只读复用**：
- 12 类 NPU 权重（`model_12class.raw` 2ae95275…）、12 类标签序、输入预处理（`[1,2,1024]` fp32 RMS1.0）。
- 稳定 RTL/XDC/位流（`22fec95c…`）、framebuffer 地址（0x40080000/0x80080000）与显示时序、触摸语义。
- 历史交付包（M14–M19 全量包/补丁，`dist/` 版本化不覆盖）。

**M22 阶段门禁**：M22（运行时生命周期/时延修复 + 可复现性能基线工具 + 根因定位）**未通过前，不得开始 M23 集成**；M23 未通过前不得开始 M24 正式集成。

**状态红线**：严禁提前写 `OOD_U_PASS / 24CLASS_PASS / PERFORMANCE_PASS / PROJECT_COMPLETE`；
最高离线状态按阶段推进（M22→`M22-RUNTIME-*`、M23→`M23-P0-*`、M24→`M24-P1-*`）。

---

## 10. 待确认项（UNKNOWN）

1. NPU 运行时实测利用率 / 精确 infer_us / 端到端分段时延（待 M22 板端回传）。
2. DDR 实际速率口径（手册 1600MHz vs 时序报告 800MHz，尚待验证）。
3. 多模型驻留/并行能力（NPU 运行时是否支持，尚待验证）。
4. `icraft::xrt::Tensor::mallocOn`/`.to()` 内部是否真实触发 heap/驱动分配（SDK 内部，代码不可见）。
5. `UnixSocketSink` 阻塞 `::send`（fd 无 O_NONBLOCK）在 UI 消费端慢时是否实测阻塞主推理循环（板端未在本仓体现）。
6. M20 板端胶水代码（`classify_or_reject` 接入 producer 的具体改法）——M20 只提供纯模块，胶水属 M23 实现。

---

*本审计基于 M19 PROVENANCE + MODEL_DEPLOYMENT_CONTRACT + categories.hpp + 实测 SHA，未改动任何源工程。*
