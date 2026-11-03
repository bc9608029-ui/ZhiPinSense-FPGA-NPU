# M26–M27 最终报告（§十六 · 15 问必答）

任务 id="39e5" · FPGA-DSP 流式加速与 NPU 多模型调度离线预研。
两工程：`F:\FPGA_Work\sdr_fpga_dsp_accel_m26\` 与 `F:\FPGA_Work\sdr_npu_multimodel_m27\`。

最高状态：M26 = **`M26-FPGA-DSP-OFFLINE-MODULES-READY`**；M27 = **`M27-NPU-MULTIMODEL-OFFLINE-FRAMEWORK-READY`**。二者均为**离线模块 READY，不是硬件 READY**（见 Q15）。

---

## 逐问回答

### Q1 哪些 DSP 模块已经完成 RTL

**全部 16 个 RTL 模块均已完成**（`m26/rtl/*.sv`，namespace `m26`）：

- 流式前端：`m26_dc_removal`、`m26_energy_rms`、`m26_signal_presence`、`m26_nco`、`m26_fir`、`m26_decimator`、`m26_stream_frontend_top`。
- 频谱链：`m26_hann`、`m26_fft_1024`、`m26_fftshift`、`m26_mag_sq`、`m26_noise_floor`、`m26_cfar`、`m26_candidate_merge`、`m26_spectrum_top`。
- 公共：`m26_fxp_pkg`（定点包）。

另有 5 个 SV 自检查测试台（`m26/sim/*.sv`：stream_frontend / spectrum / cfar / median / fir）。**本环境无 Vivado/xsim/iverilog，RTL lint/行为仿真/OOC 综合为待运行**（脚本 `m26/synth/*.tcl` 已交付）。

### Q2 哪些只有黄金模型

**没有「只有黄金模型、无 RTL」的模块**。黄金模型（`m26/golden/m26_golden.hpp`、`m26_fixed_model.hpp`、`m26_verify.cpp`）是**与 RTL 逐位对齐的参照**，而非替代 RTL：能量 RMS、noise_floor 位串中值、CFAR 无除法判决、candidate_merge 99% 带宽均有 RTL 实现。黄金模型职责 = 离线验证 RTL 的定点语义（`m26_verify` **36/36 断言通过**）。

### Q3 每个模块实际消耗多少 DSP/BRAM/LUT

**诚实声明：Vivado 未运行（只读），没有「实际」综合后数字。** 下列为**结构级分析估算**（来源 `docs/M26_RESOURCE_AND_TIMING_BUDGET.md`），任何下游引用不得写成实测：

| 模块 | LUT | FF | BRAM | DSP |
|---|---|---|---|---|
| dc_removal | ~250 | ~200 | 0 | 0 |
| energy_rms | ~500–4000 | ~120 | 0 | 2 |
| signal_presence | ~30 | ~20 | 0 | 0 |
| nco | ~200 | ~200 | 1×B18 | 4 |
| fir | ~400 | ~1100 | 1×ROM | 32（并行） |
| decimator | ~50 | ~70 | 0 | 0 |
| hann | ~50 | ~40 | 1×B18 | 2 |
| fft_1024 | ~300 | ~200 | 2×B18 | 4 |
| fftshift | ~50 | ~40 | 1×B18 | 0 |
| mag_sq | ~30 | ~40 | 0 | 2 |
| noise_floor | ~400 | ~34,000（D） | 0（D） | 0 |
| cfar | ~300 | ~34,000（D） | 4 | 4 |
| candidate_merge | ~500 | ~35,000（D） | 0（D） | 0 |

`D` = distributed RAM（寄存器阵列）。离线 D 版三个谱消费者各持 1024×32 功率缓冲 → 功率缓冲即 ~98k FF，**不能与现有 71k FF 设计同板共存**；生产路径已给出（合并为单份 BRAM 功率缓冲，FF <5k，见预算文档 §2）。DSP 与 BRAM 占用很小、在富余预算内（基线 DSP 空闲 ~376、BRAM 空闲 ~123.5）。

### Q4 是否实现每周期一采样或满足实际输入速率

**满足。** 流式前端每模块稳态 1 样本/周期（decimator 为 1 输出/D 输入，满占空比 1 周期 1 输入）。频谱链按帧吞吐：FFT ~22,528 周期/帧、CFAR ~9,217、中值 ~1,057、合并变长（可限界），在 100 MHz 下每帧预算 **800,000 周期**，模型端 128 kHz 帧率（8 ms/帧）**远未触及**。因此每模块均满足 128 kHz 实时率。这是**结构推导**，最终需 OOC 综合 + 上板确认。

### Q5 是否存在溢出、精度或时序风险

**存在，且已明示**（不掩盖）：

- **精度**：定点契约 16-bit Q1.15，逐级对称饱和 + round-half-away，FFT 每级 1/2 缩放（P_golden = P_rtl·2^20）。CFAR 黄金与定点边界舍入有 4/1024 bin 差异（预期，非缺陷）。无溢出风险（饱和 + 缩放）。
- **时序风险点**（需 OOC 收敛，**不伪造 false path**）：① energy_rms 组合 16 段开方（→ 生产改 1 段/周期流水）；② noise_floor 1024 输入 popcount（~11 级加法树）；③ cfar 64×64 交叉乘（→ 强制 DSP 或分拍）；④ 全并行 FIR 16 项加法树（→ 生产转置单 MAC 时分）。
- **资源风险**：离线 D 版寄存器阵列 FF >150k 超预算（见 Q3），生产必须迁 BRAM。

### Q6 是否接入现有主链

**否。** M26/M27 均未接入 Gate 9/10 主链、未改 RTL/XDC/位流、未接 FPGA 数据通路。M26 以 AXI-Stream `{I[15:0],Q[15:0]}` 独立顶、逐模块可旁路；M27 为 header-only C++ 框架 + Python 原型，与真 NPU 之间只有 `m27_npu_backend_stub`。集成接口（异步 FIFO、地址时分、启动时序）见 `M26_INTEGRATION_INTERFACE.md`，仅文档、未实施。

### Q7 是否生成生产位流

**否。** 未运行 Vivado 实现/布线，未生成或烧写任何 `.bit`，未写 Flash，未碰板。仅交付可综合源码 + 待运行的 lint/sim/OOC 脚本 + 独立 DCP 生成脚本（未执行）。

### Q8 NPU 是否支持多模型常驻

**否，单模型常驻。** ZG330 NPU 运行时一次只 load 一个模型；`NpuStatus::MULTI_MODEL_RESIDENCY_UNSUPPORTED` 是真实能力边界。M27 以**单槽激活**表达（registry 槽 A 为 12 类生产，B–E 禁用实验），并记录备选（startup-select / 共享骨干多头），均不要求多模型同时常驻。

### Q9 是否仍存在逐帧 reopen

**框架层面不引入；历史根因已定位。** 263ms 周期尖峰 = 设备重开，M24 已以 `npu_rearm_state`（第 2 帧起 `reset(1)`）修复。M27 采用**常驻 + rearm**，无逐帧 reopen 路径。真 NPU 上的 reopen 是否彻底消除，需上板实测——**本离线环境不宣称已消除**。

### Q10 当前 12 类默认行为是否保持不变

**是。** 槽 A 的 `model_sha256` 冻结 `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`；12 类标签序不变；输入契约 `[N,2,1024]` 不变；融合/路由默认关闭时输出与单帧 argmax 字节一致。未修改 M20/M22/M23/M24 工程、模型、标签、预处理、RTL/XDC/位流、UI。

### Q11 24 类和专家模型是否仍为 stub

**是。** 24 类正式模型未训练（`sdr_amr_rml24_ood_v1_1` 停在 CUDA-PREFLIGHT，无 checkpoint），M27 槽 B/C 禁用；专家模型为 `ExpertStub`，专家组 `PLACEHOLDER_EXPERT_GROUPS` 未冻结，`routing_gate()` 恒返回 `24CLASS_EXPERT_MODEL_NOT_TRAINED`。**未用 stub 宣称任何 24 类/专家能力完成。**

### Q12 信道模型是否只有合成数据结果

**是，只有合成数据。** 11 类信道环境（CLEAN/CFO/PHASE_NOISE/IQ_IMBALANCE/MULTIPATH/CLIPPING/CW_INTERFERENCE/MULTITONE/PULSE/SWEEP/MULTI_IMPAIRMENT）由 `m27_channel_generator.py`（numpy 基带合成 + 显式损伤）生成，`SeedSequence` 三路隔离；模型为 torch 2D-CNN，ONNX 可导出、int8 白名单可行。原型训练 acc ≈ 22%（11 类随机 ≈ 9.1%）仅证明「可学到结构」，**不是真实电磁环境识别声明**。

### Q13 多帧融合是否支持 12/24 类

**是，模型无关，12/24 通用。** `m27::TemporalFusion` 以 `n`（仅 12 或 24）为维度，7 算法（LogitsMean/ProbMean/EMA/MajorityVote/MarginWeighted/SnrWeighted/Hysteresis），不跨 `model_sha` 融合，NO_SIGNAL/UNKNOWN 直通，突发换类有界响应。12/24 切换在 host 测试中有专门断言覆盖。

### Q14 NPU 利用率是实测还是估算

**估算，不是实测。** 未上板、未跑真 NPU。M27 的 `RuntimeStats` 只是统计框架，其耗时字段在 stub 后端下为 0/占位；任何「真实 NPU 利用率 / 延迟」数字**本工程一律不产出、不宣称**。同理，M26 的 FPGA 功耗/时序/最高频率均为结构估算（Q3/Q5 已注明）。

### Q15 当前到底是离线模块 READY 还是硬件 READY

**离线模块 READY，不是硬件 READY。** 两工程交付的是：可综合 RTL + 黄金模型 + 待运行综合/仿真脚本（M26），以及 header-only 调度框架 + 合成信道/专家 stub 原型（M27）。均已通过**离线**主机验证（M26 golden 36/36；M27 C++ 62/62×3、pytest 12、审计 OK、bash -n/compileall OK）。未运行 Vivado、未生成位流、未上板，因此**不构成** `FPGA_DSP_PASS / TIMING_PASS / NPU_MULTIMODEL_PASS / HARDWARE_PASS / PERFORMANCE_PASS / 24CLASS_PASS / OOD_PASS / PROJECT_COMPLETE`。

---

## 交付物与校验

| 交付物 | 路径 | SHA256 | 文件数 | manifest 行数 |
|---|---|---|---|---|
| M26 补丁 | `m26/dist/m26_fpga_dsp_offline_modules_patch.tar.gz` | `7262b1ae611f63a6872a4733ef0da6b7082c7a0d95f74e43a133d01354fe6f00` | 37 | 37 |
| M26 清单 | `m26/dist/M26_PATCH_SHA256SUMS.txt` | — | — | 37 |
| M27 补丁 | `m27/dist/m27_npu_multimodel_offline_framework_patch.tar.gz` | 见包外交付说明（自引用） | 32 | 32 |
| M27 清单 | `m27/dist/M27_PATCH_SHA256SUMS.txt` | — | — | 32 |

- 两包均 **unpack 后 `sha256sum -c` 全 OK**；均**不含**裸 `SHA256SUMS.txt`、不含编译产物（`m26_verify` 二进制、`test_m27{,_asan,_ubsan}`）、`__pycache__`、`.pytest_cache`。
- 注：M27 补丁包内包含本报告，故其归档 SHA 若写进本表即构成自引用；归档 SHA 以**包外交付说明**为准（`dist/` 同名 `.tar.gz` 的 `sha256sum` 输出，记录于本会话交付摘要与记忆）。M26 补丁不含本报告，其 SHA 无自引用、上表即为最终值。
- 两清单均只列内容文件、不含自身，`sha  path` 文本格式。

## 红线复核

未修改/覆盖 M20/M22/M23/M24 历史工程与交付物、当前 12 类模型与标签序、输入预处理、RTL/XDC/位流、UI、Gate 9/10、24 类训练目录、历史 `SHA256SUMS.txt`。未生成生产位流、未写 Flash、未碰板。工程根无 `FINAL_*`、无上述 `*_PASS` 禁词。
