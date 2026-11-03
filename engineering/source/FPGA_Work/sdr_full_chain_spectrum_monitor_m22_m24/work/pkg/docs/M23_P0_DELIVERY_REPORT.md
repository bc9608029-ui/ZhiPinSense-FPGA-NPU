# M23 P0 — 交付报告（离线预研：D 信号存在 + H 参数估计 + C OOD-U 可关闭接线）

> 状态：**`M23-P0-OFFLINE-MODULES-READY`**
> 本报告如实记录离线预研成果、测试误差、精确 diff 与未完成事项。**最高状态仅此一项**；不得写 `M23_P0_PASS` / `HARDWARE_PASS` / `PROJECT_COMPLETE`。本交付为**补丁包**，非可上板验收全量包。

## 1. 结论摘要

M23 P0 三线（D 信号存在检测 / H 参数估计 / C OOD-U 可关闭接线）的**隔离模块、单元测试、IQ 回放工具、契约文档**已离线完成并验证：

- **纯 CPU 参考实现**，header-only + 2 个 .cpp，iCraft/libiio/板卡/位流全部无关。
- **不修改 M22 交付物**：对 M22 基线只有**新增**，零改动（diff 见 §6）。
- **每项参数输出实际数值误差**，不写裸 PASS（误差表见 §5）。
- OOD-U **默认关闭**，启用路径 fail-closed，UI 语义 `UNKNOWN_EXPERIMENTAL`。
- 已知局限性如实披露（occupied-BW 跨度定义、SNR 谱域近似、CFO 阶数依赖）。

## 2. 交付物清单

工程根：`F:\FPGA_Work\sdr_full_chain_spectrum_monitor_m22_m24\work\pkg\`

### 2.1 新增源码模块（`sdr_adapter/`）

| 文件 | SHA-256 | 说明 |
|---|---|---|
| `m23_contract.hpp` | `057814468957ed0575413af5651ed52c2874c80fb2c5103e421dff3e2b20372d` | 冻结 token/常量（NO_SIGNAL/SIGNAL_PRESENT/UNKNOWN_EXPERIMENTAL/ERROR、OOD_MODEL_SHA256、PARAM_STALE_AFTER_FRAMES=5、OOD-U 参考阈值） |
| `m23_cfo.hpp` | `c8e9d6a638e0b2b23a92f0e39573be16f185682dbdcf0ae332d22fd79af8152c` | CFO 一阶自相关 + 调制阶非线性剥离（order 1/2/4） |
| `m23_params.hpp` | `836b4c0546a14185836151e158b7080fe12c0951a36bab6176e47ce0cdf49d1c` | `ParamEstimate` / `M23Params` / `estimate_params()` / `M23ParamState`（valid/stale） / `render_param` |
| `m23_verdict.hpp` | `5768edf706009b083911a0d7cb810c85afe9a2c23e26a3e3cf3526fe49608c17` | 四态裁决 `Verdict` + `compose()` |
| `m23_ood_u_switch.hpp` | `8b2fdb135e729018bac2c96a965adbd599549041d6f4a6b05738cc849455ba0d` | 可关闭 OOD-U 开关（禁用=纯 argmax） |
| `m23_iq_synth.hpp` | `3208911e574c0ca7ea2d5312eb79f72215792fe35bebfab1f81b24aa4a8669a0` | 确定性合成 IQ（tone/BPSK/QPSK/two-tone，携带真值） |
| `ood_u_contract.hpp` | `439954e24efa2dde3ac10c30bb41c4450e81ef0d41f30bdf76d62575fbbe7b64` | 自 M20 逐字节拷贝 |
| `ood_u_detector.hpp` | `191e535097bda06acc01c0482641bbe0524d9712195b90e562835ec4595f5a3d` | 自 M20 逐字节拷贝 |
| `ood_u_detector.cpp` | `160f26289422cec7396bf3129a77d6d4cce8a13f0c080b8867db3286a4ae4711` | 自 M20 逐字节拷贝 |
| `ood_threshold_manifest.hpp` | `8e40bafa370add5fd2dc80adcbbab8d3529ac7c9aeb360190b754d2aaa8bbd74` | 自 M20 逐字节拷贝 |
| `ood_threshold_manifest.cpp` | `2ca598ae8505588379a78d948aa22ff23053533471d46319b5964e0de7478192` | 自 M20 逐字节拷贝 |
| `minijson.hpp` | `6f1cec365e5f2d78df220fda117451104d9f6dd3824275cfe4b5bab2afb8ce58` | 自 M20 逐字节拷贝 |

### 2.2 主机测试（`host_tests/`）

| 文件 | SHA-256 | 说明 |
|---|---|---|
| `test_m23_p0.cpp` | `9c000ef01f67deeca1951b560cd19e666938ce8d946e70e52e410abd7d2e2856` | 59 断言单元测试 |
| `build_m23_p0.sh` | `0846a293ea2534c967d35c38a311dc586313918d1c31b0893f6512456b228adc` | 独立构建 |
| `run_m23_p0.sh` | `355d2c3f5c6d2edb87d5388e7f7073d6b6bb556580e8106b8f4fda31bdeb2a05` | 独立运行 |

### 2.3 IQ 回放工具（`host_tools/`）

| 文件 | SHA-256 | 说明 |
|---|---|---|
| `m23_iq_replay.cpp` | `a80fbb20daf225dbe65e811b5a9b26122aacabc955bbd14362e1c10e246b85aa` | CLI：`--synth tone/bpsk/qpsk/two-tone` 或 `--file int16/f32` |
| `build_m23_iq_replay.sh` | `a73bcd1ad34c63a2ea726075a947121cc991ff14fa69501527e5cd902a269fa7` | 独立构建 |

### 2.4 文档（`docs/`）

| 文件 | 说明 |
|---|---|
| `M23_P0_PARAMETER_ESTIMATION_CONTRACT.md` | 六项参数定义/公式/单位/valid-stale/误差预期/局限性 |
| `M23_P0_INTEGRATION_INTERFACE.md` | 后续接入 M22 的接口约定与串口纪律 |
| `M23_P0_DELIVERY_REPORT.md` | 本报告 |

（所有文件含三份文档的 SHA 以补丁包内 `SHA256SUMS.txt` 为准。）

## 3. 构建与测试方法

- 工具链：WSL g++ 15.2.0（Git Bash 无原生 g++），`-std=gnu++17 -O2 -Wall -Wextra -Werror`。
- 测试：`host_tests/build_m23_p0.sh && host_tests/run_m23_p0.sh`。
- 回放工具：`host_tools/build_m23_iq_replay.sh`。
- 两构建脚本均 `set -euo pipefail`，独立于 M22 `run_tests.sh`。

## 4. 测试结果

- `test_m23_p0`：**59/59 断言通过**（`-Werror` 零告警）。
- 覆盖：CFO order 1/2/4 数值误差、CFO 无参考→invalid、中心频率、功率/RMS、SNR、占用带宽、estimate_params 标志、存在检测迟滞（confirm=3/lost=5）、四态裁决、OOD-U 默认关 argmax、OOD-U 启用接受/拒识/错误、OOD-U `+1e30` 安全边界、valid/stale 渲染 `"--"`。

## 5. 实测误差表（不写裸 PASS）

| 参数 | 真值条件 | 实测误差 | 容差 |
|---|---|---|---|
| `center_freq_hz` | 单音 16000 Hz | −1.469 Hz | ≤ 20 Hz |
| `cfo_hz` order1 | 单音 cfo +250 Hz | +0.454 Hz | ≤ 5 Hz |
| `cfo_hz` order2 | BPSK cfo −120 Hz | +0.251 Hz | ≤ 20 Hz |
| `cfo_hz` order4 | QPSK cfo +80 Hz | −0.520 Hz | ≤ 50 Hz |
| `power_dbfs` | 单音 amp 1000（真值 −6.227 dBFS） | 0.000 dB | ≤ 0.05 dB |
| `rms` | 单音 amp 1000 | 0.000 counts | ≤ 1 count |
| `snr_db` | 单音+AWGN 20 dB | +1.658 dB | ≤ 5 dB |
| `occupied_bw_hz` | 双音 snr=0 16 kHz | +125 Hz | ≤ 250 Hz |

## 6. 精确 diff（相对 M22 基线）

**只新增，零修改、零删除。** M22 既有文件（`sdr_adapter/dsp_measure.hpp`、`signal_presence.hpp`、Gate 9/10 主链、模型、UI、位流、打包脚本等）均未触碰。

新增 21 文件：

```
sdr_adapter/m23_contract.hpp
sdr_adapter/m23_cfo.hpp
sdr_adapter/m23_params.hpp
sdr_adapter/m23_verdict.hpp
sdr_adapter/m23_ood_u_switch.hpp
sdr_adapter/m23_iq_synth.hpp
sdr_adapter/ood_u_contract.hpp
sdr_adapter/ood_u_detector.hpp
sdr_adapter/ood_u_detector.cpp
sdr_adapter/ood_threshold_manifest.hpp
sdr_adapter/ood_threshold_manifest.cpp
sdr_adapter/minijson.hpp
host_tests/test_m23_p0.cpp
host_tests/build_m23_p0.sh
host_tests/run_m23_p0.sh
host_tools/m23_iq_replay.cpp
host_tools/build_m23_iq_replay.sh
docs/M23_P0_PARAMETER_ESTIMATION_CONTRACT.md
docs/M23_P0_INTEGRATION_INTERFACE.md
docs/M23_P0_DELIVERY_REPORT.md
scripts/build_m23_p0_package.sh
```

M20 拷贝源（逐字节一致，未改）：`F:\FPGA_Work\sdr_amr_12class_ood_u_v1\cpp\ood_u_*.{hpp,cpp}` + `minijson.hpp`。

## 7. 未完成事项 / 已知限制

1. **occupied-BW 跨度定义脆弱**：`DspMeasure` 用 `max_bin−min_bin+1`，带外一个噪声/量化谱线即可使跨度横跨整谱。更稳健定义（99% 功率带宽 / 最大连通区域）留待 M23 集成期，本轮不改 `DspMeasure`（不碰 M22）。
2. **SNR 谱域近似**：对宽带调制偏保守（+1.66 dB），只作近似读数。
3. **CFO 阶数依赖**：BPSK=2 / QPSK=4 / 单音=1，阶数选错不报错。
4. **OOD-U 未取真实 NPU logits**：阈值来自 M20 fp32 冻结值，本包只做可关闭接线，未接 12 类模型/上板捕获。
5. **未接入 M22 主链**：阶段门禁要求 M22 板测通过后方可集成（见集成接口文档）。

## 8. 状态红线

- 最高状态：`M23-P0-OFFLINE-MODULES-READY`。
- 禁止：`M23_P0_PASS` / `HARDWARE_PASS` / `PROJECT_COMPLETE` / `FINAL_*`。
- 我禁碰板 / 禁写 Flash；不启动 M23 主链集成；不生成冒充可上板验收的全量包。
- 冻结权威值不变：`model_sha256 = 2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`、combined bitstream `22fec95c…`。
