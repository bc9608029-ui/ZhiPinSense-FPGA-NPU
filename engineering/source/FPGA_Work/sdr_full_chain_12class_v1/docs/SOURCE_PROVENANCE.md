# 来源溯源（SOURCE_PROVENANCE）

本工程 `sdr_full_chain_12class_v1` 为任务 39e5 十二类 SDR→FPGA/NPU→UI 完整链路（Gate 6–9）
的**离线交付**。本文说明：哪些资产是**只读复用**（已冻结、未改动），哪些是**本工程新建**，
以及如何校验「未修改任何上游资产」。

---

## 1. 只读复用资产（冻结清单见 `SOURCE_PROVENANCE_SHA256.txt`）

| 类 | 来源工程 | 用途 | 校验 |
|---|---|---|---|
| §A 十二类 ONNX + 报告 | `ad_amr_data_v3_12class_ff2b3fb3_run` | 链路上唯一推理模型源（opset17，`[1,2,1024]→[1,12]`） | SHA |
| §B 类别契约 | `sdr_preparation_v3_logging_fix` + `sdr_pluto_board_integration_v1` | `cat::target_12()` 权威顺序 | SHA 两处一致 |
| §C FPGA↔NPU 寄存器 | `sdr_preparation_v3_logging_fix` | `pl_ddr_register_map.hpp` | SHA |
| §D 现有位流 | `hdmi_framebuffer_ui_v4_fix` / `pl_ddr_mandatory_core_v1` | 权威上板位流（禁写 Flash） | SHA |
| §E UI 渲染核心 | `hdmi_framebuffer_ui_v5_visual` | 十二类 UI 三页渲染 | SHA |
| §F 八类参考模型 | `npu_stage_v1` | 仅资产审计，**不接入**十二类 | SHA |
| §G Gate 1–5 源码 | `sdr_pluto_board_integration_v1` | 复用 SDR 原语/安全状态机/采样率协商 | SHA 逐文件 |

**校验方法**（在 WSL，从本工程根目录）：

```
# 每类路径在清单里是绝对路径；逐类核对（示意）：
sha256sum -b <上游文件路径> | awk '{print $1}'   # 与清单该行首列 SHA 比对
```

`SOURCE_PROVENANCE_SHA256.txt` 由 `tools/make_source_provenance.sh` 生成（只 `sha256sum` 读，
**绝不写**上游）。本工程对上游的「只读」= 只取 SHA 与复制源码到 `sdr_adapter/`，且复制后的
源码与上游逐字节一致（SHA 相同，见 §G）。

## 2. 本工程新建资产

| 路径 | 说明 |
|---|---|
| `board_package/chain_common.hpp` | 十二类 SDR→tensor 链 + ResultFrame 填充（iCraft/libiio-free，可主机测） |
| `board_package/npu_classifier.hpp` | iCraft-only 十二类 NPU 推理封装 |
| `board_package/board_gate{6,7,8,9}_*.cpp` | 逐门板端程序 |
| `board_package/board_calibrate_rec_scale.cpp` | §九 receiver_scale 定标器 |
| `board_package/build_on_board.sh` / `build_npu_on_board.sh` / `CMakeLists.txt` | 板端构建 |
| `model_12class/` | 编译产物 + 部署契约（`12CLASS_CHAIN_VALIDATION_MODEL`） |
| `deployment_golden/` | 240 条黄金输入 + 期望 argmax/logits |
| `tools/gen_12class_calibration.py` / `gen_deployment_golden.py` | 校准/黄金集生成（只读源工程） |
| `host_tests/` | 主机测试（WSL g++ -Werror，64/64 通过：43 C++ + test_board_build.sh 21 项板端构建依赖+目录隔离测试） |
| `scripts/` | run_gate{6,7,8,9} + 定标 + 打包脚本 |
| `docs/` | 本文 + 板测指南 + 验收 + 定标 + 修正 |
| `SOURCE_PROVENANCE_SHA256.txt` | 上游冻结清单 |
| `SHA256SUMS.txt` | 本包自校验清单（`sha256sum -c`） |

## 3. 模型溯源链

```
源 ONNX (f7758715…, opset17)
  → iCraft v3.39 CLI (parse→optimize→quantize→adapt→generate, 全 exit 0)
  → model_12class/model_12class.json (51364bdf…, 222,804 B)
  → model_12class/model_12class.raw  (2ae95275…, 2,851,472 B)
```

量化：int8 对称 per-channel（`zero_points: []`）、KLD 饱和、`no_transinput=true`（输入 fp32
不量化）。校准集 252 条、黄金集 240 条，均只读源工程冻结 train split 生成（RNG 复刻
`SeedSequence([seed, split_code, 0, index])`）。详见 `model_12class/MODEL_DEPLOYMENT_CONTRACT.md`。

## 4. 状态

- 离线（未上板）交付，状态 **`READY-FOR-GATE6-9-HARDWARE-TEST`**。
- 模型标签 **`12CLASS_CHAIN_VALIDATION_MODEL`**；OOD = **NO_GO**。
