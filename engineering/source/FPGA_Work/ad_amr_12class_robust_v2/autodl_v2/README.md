# ad_amr_12class_robust_v2 — AutoDL 包（十二类调制识别 V2 鲁棒性改进）

> V2 训练/搜索/导出/量化全流程包，跑在 AutoDL GPU 镜像上。
> 冻结身份：V1 模型 `12CLASS_CHAIN_VALIDATION_MODEL_V1`，raw SHA `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`。
> 新模型只在门禁全过后才命名 `12CLASS_ROBUST_CANDIDATE_V2`；**绝不覆盖 V1**。

## 冻结契约（读自 V1，训练不可改）

- 十二类标签（权威顺序，见 `v2/contract.py`）：
  `OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`
- 输入 `[1, 2, 1024]` fp32、RMS=1.0（实部/虚部）；输出 12 logits。
- 训练信号/信道域随机化参数冻结于 `configs/v2_base.yaml`（`signal`/`channel` 两块）。
- 冻结源文件逐文件 SHA 见 `PROVENANCE_SHA256.txt`（打包后自动生成）与工程根 `BASELINE_SOURCE_SHA256.txt`。

## 目录结构

```
autodl_v2/
├── v2/                    # V2 新增模块（contract/curriculum/augmentation/losses/
│                          #   dataset_v2/trainer/evaluate/architectures/results/
│                          #   export_onnx/fake_int8/run/pilot/formal/select）
├── models/ datasets/ channel/ training/ evaluation/   # V1 原样拷贝（只读复用）
├── configs/v2_base.yaml           # 冻结 V1 信号/信道/模型 + V2 训练/搜索轴
├── configs/search_space_v2.yaml   # 阶段十搜索空间（训练前锁定）
├── scripts/                       # 入口脚本（见下）
├── docs/                          # 审计/消融/门禁/防泄漏/真实 RF 采集协议
├── tools/                         # 防泄漏检查 / sigmf 工具 / 按 session 切分
├── data/radioml2018/              # 公开数据标签映射与 classes.txt
└── requirements.txt               # numpy/scipy/…/onnx/onnxruntime/pytest/optuna
```

## 入口脚本（`cd autodl_v2` 后执行）

### 离线 CPU 门禁（先跑，全部本地可复现）
| 脚本 | 作用 |
|------|------|
| `bash scripts/run_preflight.sh` | CPU 冒烟：契约/模型 279036 参数/前向/数据集/增广/课程/损失/trainer/评估/Phase-C 候选 |
| `bash scripts/run_data_audit.sh` | 校验冻结信号/信道契约与 V1 一致 |
| `bash scripts/run_leakage_check.sh` | 真实 RF 数据跨切分防泄漏（无 manifest 时 fail-closed 报 OK） |

### GPU 流水线
| 脚本 | 作用 |
|------|------|
| `bash scripts/setup_env.sh` | 装非 torch 依赖（torch 由镜像提供，不重装） |
| `bash scripts/run_baseline_reproduce.sh` | Phase 1：V2 基线下复现 V1 |
| `bash scripts/run_pilot.sh` | Phase A/B 超参搜索（optuna TPE，回退 numpy 种子采样） |
| `bash scripts/run_select.sh` | 用 **validation** 选 Top 候选（绝不看 test） |
| `bash scripts/run_formal.sh` | 完整预算多 seed（2026/2027/2028）正式训练 |
| `bash scripts/run_export_onnx.sh` | 导出 opset-17 ONNX（算子门禁：Conv/BN/Relu/Add/ReduceMean/Gemm） |
| `bash scripts/run_fake_int8.sh` | fake INT8 对称量化精度检查 |
| `bash scripts/run_all.sh` | 一键串行全流程（失败即停） |

## 状态红线

- 有真实 RF 之前：**`NEEDS-REAL-RF-DATA`**；真实 RF 导入且未上板：`READY-FOR-12CLASS-V2-NPU-HARDWARE-TEST`。
- 未实机验证**绝不**写 `FINAL_MODEL_PASS / ROBUST_MODEL_PASS / REAL_RF_PASS / OOD_PASS / PROJECT_COMPLETE`。
- 不使用测试集调参；不根据最终测试结果反复改门限；不把候选模型直接替换进正式板端包。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
