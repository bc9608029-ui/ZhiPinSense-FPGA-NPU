# M29-RML24-REALRF-FINETUNE-PILOT1 — 环境锁定（ENVIRONMENT）

> 本文件回答评审问题 #9「Python 环境问题（torch 在用户 site-packages，`python -I` 报
> no torch）」。它把「哪个解释器跑哪一段、每个第三方库在哪个 site、精确版本」写死，
> 让离线复现与回传后判读不再依赖隐式环境。**所有版本/路径均为本机实测冻结值。**

## 1. 三套解释器与分工

| 解释器 | 版本 | 用途 | 关键第三方库（实测冻结） |
|---|---|---|---|
| `D:\Anaconda\python` | 3.13.5 | 离线分析 / 判读 / 训练 / 评估 | numpy 2.1.3 · h5py 3.12.1（Anaconda base site）；torch 2.12.0+cpu（用户 site） |
| `D:\radioconda\python` | — | PC TX 服务（只跑 TX SDR） | libiio 0.26 + fix10prep2 依赖链 |
| WSL Ubuntu `g++` | 15.2.0 | C++ host 测试 / 24 帧 e2e 模拟 | 无第三方（iCraft/libiio/SDR-free） |

### 1.1 `python -I`（隔离模式）能看见什么

`-I` 关掉用户 site-packages，所以：

- **可见**（Anaconda base site，`D:\Anaconda\Lib\site-packages`）：
  `numpy==2.1.3`、`h5py==3.12.1` → 判读器、一致性核验、`select_960_sources.py` 用
  `python -I` 可跑。
- **不可见**（用户 site，`C:\Users\shado\AppData\Roaming\Python\Python313\site-packages`）：
  `torch==2.12.0+cpu` → 训练/评估脚本**必须**用 `python`（不带 `-I`）。

> 教训：任何「import torch」的脚本都不许标 `python -I`；任何 numpy-only 的脚本都可以
> 标 `python -I`（更干净、防 CWD 内植 `json.py`）。

### 1.2 精确版本与位置（实测）

```text
Python       3.13.5      D:\Anaconda\python
numpy        2.1.3       D:\Anaconda\Lib\site-packages\numpy
h5py         3.12.1      D:\Anaconda\Lib\site-packages\h5py
torch        2.12.0+cpu  C:\Users\shado\AppData\Roaming\Python\Python313\site-packages\torch
radioconda   —           D:\radioconda\python.exe          （libiio 0.26）
icraft-run   —           C:\Icraft\CLI v3.39.0\bin\icraft-run.exe
WSL g++      15.2.0      wsl.exe -e bash -lc 'g++ --version'
```

## 2. 每段脚本 → 正确命令

| 段 | 脚本 | 正确调用 |
|---|---|---|
| 一致性核验 | `consistency_check.py` | `python -I consistency_check.py` |
| 线 B schema 自测 | `line_b/scripts/selftest_capture_schema.py` | `python -I ...` |
| 线 C 自测 | `line_c/scripts/selftest_line_c.py` | `python -I ...` |
| 24 帧 e2e 模拟 | `line_b/scripts/run_e2e_sim.py` | `python -I line_b/scripts/run_e2e_sim.py`（内部调 WSL g++） |
| 数字基线（Host BF16） | `line_c/scripts/run_digital_baseline.py` | `python -I ... --icraft-run "C:\Icraft\CLI v3.39.0\bin\icraft-run.exe"` |
| 判读器 | `line_c/scripts/judge_realrf_pilot.py` | `python -I ...` |
| 训练（采集后） | `line_c/scripts/train_finetune_pilot.py` | **`python`**（不带 -I，需 torch）`--train ...` |
| 评估（S4 一次） | `line_c/scripts/evaluate_finetune_pilot.py` | **`python`**（不带 -I，需 torch） |
| 训练框架自测 | `line_c/scripts/train_finetune_pilot.py --selftest` | **`python`**（不带 -I，需 torch 加载 checkpoint） |
| PC TX 服务 | `host_tools/pc_tx_radioml_dualsdr.py` | `D:\radioconda\python.exe -I ...`（板端树） |
| C++ host 测试 | `host_tests/build_host_tests.sh` / `run_tests.sh` | `wsl.exe -e bash -lc 'bash host_tests/...'` |

## 3. 外部只读资产（不随本树分发）

| 资产 | 路径 | 用途 |
|---|---|---|
| 训练 checkpoint `best.pt` | `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt` | E0-E3 初始化（SHA `96cd25f8…`） |
| 模型 json / raw | `F:\嵌赛\...\model_rml24_bf16\rml24_adamrv11_bf16.{json,raw}` | 板端 NPU + 数字基线（`28272abc…` / `c1781aec…`） |
| HDF5 | `F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5` | 960 源 IQ 来源（`e3dd0bef…`） |
| 模型定义源码 | `F:\FPGA_Work\sdr_amr_12class_ood_u_v1\models\ad_amr_v1_1_net.py` | `ADAMRV11Net` 类 |

## 4. 复现顺序（离线，全部可重跑）

```sh
cd /d F:\嵌赛\fix10class24_realrf_finetune_pilot1_work
python -I consistency_check.py                         # 17/17
python -I line_b/scripts/selftest_capture_schema.py    # PASS
python -I line_c/scripts/selftest_line_c.py            # PASS（含 judge/训练契约级）
python -I line_b/scripts/run_e2e_sim.py                # 24 帧 e2e 模拟 PASS
python   line_c/scripts/train_finetune_pilot.py --selftest   # 需 torch，验证训练循环可达
```
