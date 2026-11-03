# M27 NPU 多模型调度离线框架交付报告（Delivery Report）

任务 id="39e5" · M27 · 工程 `F:\FPGA_Work\sdr_npu_multimodel_m27\`。

---

## 0. 状态（最高）

| 项 | 状态 |
|---|---|
| M27 框架 | **`M27-NPU-MULTIMODEL-OFFLINE-FRAMEWORK-READY`** |
| 多模型常驻 | `MULTI_MODEL_RESIDENCY_UNSUPPORTED`（单模型常驻，见 §4） |
| 24 类模型 | `24CLASS_EXPERT_MODEL_NOT_TRAINED`（stub） |
| 专家模型 | `EXPERT_MODEL_FRAMEWORK_READY` + `24CLASS_EXPERT_MODEL_NOT_TRAINED` |
| 信道模型 | `CHANNEL_IMPAIRMENT_MODEL_SYNTHETIC_PROTOTYPE` |

**不是** 硬件 READY。不接 Gate 9/10 主链、不调用真 NPU、不写 Flash、不碰板。

---

## 1. 组件清单

| 目录 | 文件 | 职责 | 测试 |
|---|---|---|---|
| `runtime/` | `m27_contract.hpp` | namespace/常量/槽/路由契约、`sha256_valid()` | 62 断言 |
| | `m27_buffer_pool.hpp` | 定长缓冲池、owner 标记、越界/重复释放 fail-closed | ↑ |
| | `m27_runtime_stats.hpp` | 每槽调用/耗时/超时/切换 + p50/p95/p99 水库 | ↑ |
| | `m27_npu_backend_stub.hpp` | 单模型 load / `infer()` 恒等直通 + 超时模拟 | ↑ |
| `registry/` | `m27_model_registry.hpp` | 槽 A=12 类生产（SHA 冻结）；B/C/D/E 禁用实验 | ↑ |
| `router/` | `m27_conditional_router.hpp` | margin/entropy/OOD/稳定性门控，DIRECT/EXPERT/OOD/CHANNEL/ERROR | ↑ |
| `fusion/` | `m27_temporal_fusion.hpp` | 7 算法 12/24 类多帧融合（见契约文档） | ↑ |
| `channel_proto/` | 7 `.py` + 2 `run_*.sh` | 11 类合成信道原型（生成/审计/manifest/模型/训练/ONNX/int8） | 7 用例 |
| `expert/` | `m27_expert_framework.py` | 混淆对/专家组占位/routing_gate/stub/ONNX 审计 | 5 用例 |
| `docs/` | 审计 + 契约 + 本报告 | — | — |
| `scripts/` | build/run/asan/ubsan/test/package | 编排 | — |

## 2. 主机验证（全部离线，本次实跑）

| 项 | 结果 |
|---|---|
| C++ release（WSL g++ 15.2.0, `-O2 -Wall -Wextra -Werror`） | **62/62 断言** |
| C++ AddressSanitizer | 62/62，无报告 |
| C++ UBSan | 62/62，无报告 |
| pytest（channel 7 + expert 5） | **12 passed** |
| 信道 3 路隔离审计 | `CHANNEL_IMPAIRMENT_ISOLATION_OK` |
| 信道生成器捷径审计 | `CHANNEL_IMPAIRMENT_PROTOCOL_OK` |
| `bash -n` 全部 `.sh` | OK |
| `python -m compileall` 全部 `.py` | OK |

编排入口 `scripts/test_m27.sh`，末尾 `== M27_OFFLINE_VERIFICATION_OK ==`。

## 3. 信道原型结果（诚实口径）

`m27_channel_train.py --seed 2026 --samples-per-label 64 --epochs 5`：

- `validation_acc=0.2330`、`final_test_acc=0.2230`（11 类随机基线 ≈ 9.1%）
- `int8_feasible=True`、`unsupported_ops=[]`（算子白名单内，仅可行性，非精度结论）
- 状态固定 `CHANNEL_IMPAIRMENT_MODEL_SYNTHETIC_PROTOTYPE`

这**只是合成数据原型**：证明 11 类信道环境可用 2D-CNN 学到远超随机的结构、且可导出 ONNX 做 int8 可行性检查。**不是**真实信道/真实电磁环境的识别能力声明。

## 4. NPU 运行时能力结论（引自 `M27_NPU_RUNTIME_CAPABILITY_AUDIT.md`）

- **多模型常驻不支持**：ZG330 NPU 运行时只支持**单模型常驻**（一次 load 一个模型）。框架以**单槽激活**方式表达；`NpuStatus::MULTI_MODEL_RESIDENCY_UNSUPPORTED` 是后端返回的真实能力边界，不是 stub 臆造。
- **逐帧 reopen 已定位根因**：历史 263ms 周期尖峰来自设备重开；M24 已以 `npu_rearm_state`（第 2 帧起 `reset(1)`）修复。M27 框架沿用**常驻 + rearm**，不新增 reopen 路径。
- 备选方案（`startup-select` 单模型 / 共享骨干多头）已记录，均**不要求多模型同时常驻**。

## 5. 12 类默认行为（红线）

- 槽 A 的 `model_sha256` 冻结为 `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`，标签序 12 类不变（`OOK,4ASK,AM-DSB,WBFM,2FSK,GFSK,BPSK,QPSK,8PSK,16QAM,64QAM,OFDM`），输入契约 `[N,2,1024]` 不变。
- 框架**默认单模型直通**：不 configure 融合/路由时，输出与单帧 argmax 字节一致。
- 未修改 M20/M22/M23/M24 任何工程或交付物。

## 6. 红线（禁止项，未触碰）

不生成/烧写生产位流；不写 Flash；不碰板；不接 Gate 9/10；不宣称 24 类/专家完成；不把估算写成实测；不写 `NPU_MULTIMODEL_PASS / 24CLASS_PASS / OOD_PASS / HARDWARE_PASS / PERFORMANCE_PASS / PROJECT_COMPLETE` 及 FINAL_* 族。

## 7. 打包

`scripts/build_m27_package.sh` → `dist/m27_npu_multimodel_offline_framework_patch.tar.gz`（32 内容文件）+ `dist/M27_PATCH_SHA256SUMS.txt`（32 行）。无裸 `SHA256SUMS.txt`，不含编译产物（`tests/test_m27{,_asan,_ubsan}`）、`__pycache__`、`.pytest_cache`、`dist/`。确定性 tar（`--sort=name` + 固定 mtime/owner/group）+ `gzip -n`。包 SHA 与解包校验见最终报告。
