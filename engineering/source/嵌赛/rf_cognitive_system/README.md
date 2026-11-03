# 智频感知：FPGA-NPU 异构宽带射频智能认知系统

面向 2026 全国大学生嵌入式芯片与系统设计竞赛 FPGA 创新设计赛道、
复旦微 FMQL30TAI 悟净平台的科研级 PC 阶段工程。

当前版本完成可在 PC 上可信验证的第一阶段：合成 IQ、无线信道域随机化、
通信可视化、轻量 1-D CNN、训练与 SNR 评价、RadioML 接口，以及未来 FPGA
DSP 的浮点/定点 Golden Reference。数据默认在线生成，避免在移动硬盘保存
大量重复样本。

> 当前没有悟净开发板和真实 SDR。仓库中的 Accuracy、时延和定点误差仅来自
> PC 软件实验，不代表 NPU/FPGA/真实射频性能。

## 系统边界

计划中的最终数据流为：

```text
真实 RF / SDR -> 数字 IQ -> 悟净 FPGA 实时 DSP
              -> 悟净 NPU AI 推理 -> 悟净 CPU 调度、决策和可视化
```

当前数据流为：

```text
Synthetic IQ -> ChannelPipeline -> [I,Q,L] -> BaselineCNN -> PC evaluation
                         |
                         +-> float/fixed FPGA Golden Reference
```

`TODO-HARDWARE`：真实 SDR 接入、AXI/DMA、Procise RTL、Icraft 模型转换、
NPU 量化与上板推理、FPGA 逐点对比、功耗/资源/时延/吞吐率实测。

## 环境

正式推荐 Python 3.10 或 3.11。Windows PowerShell 示例：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PyTorch 会自动使用 CUDA；没有 CUDA 时回退到 CPU。若需要特定 CUDA 版本，
应按照 PyTorch 官方索引安装匹配的 wheel，再安装其余依赖。

当前验证机只有 Python 3.13.5 和 `torch 2.12.0+cpu`，因此本次 smoke test
使用该现有环境；代码自身限制和推荐目标仍是 Python 3.10/3.11。

## 快速验证

分别运行：

```powershell
python -m pytest -q
python -m evaluation.dataset_audit --config configs/baseline.yaml
python generate_dataset.py --config configs/synthetic.yaml --save-count 8
python -m scripts.golden_demo
python train.py --config configs/smoke.yaml
python -m evaluation.evaluate --config configs/smoke.yaml
python -m evaluation.snr_sweep --config configs/smoke.yaml
```

或执行完整、有界的一键流程：

```powershell
python -m scripts.run_smoke
```

## 正式 baseline

```powershell
python train.py --config configs/baseline.yaml
python -m evaluation.evaluate --config configs/baseline.yaml
python -m evaluation.snr_sweep --config configs/baseline.yaml
```

`baseline.yaml` 默认在线生成 25,200/5,040/8,400 条 train/validation/test
样本，训练上限 40 epoch，并以 8 epoch patience 启用 early stopping。三套数据
都在 8 类调制和 -20 至 20 dB（步进 2 dB）的 21 个 SNR 上精确分层。正式
SNR sweep 每个 SNR 使用 2,000 条记录，即每类 250 条、总计 42,000 条。

按本机 CPU smoke 吞吐量估算，正式训练上限约 45-60 分钟，early stopping
可能缩短到约 30-50 分钟；峰值内存预计 0.5-1.5 GB。实际时间取决于 CPU、
磁盘杀毒扫描和 CUDA 环境。开始长训练前应保留本次 smoke 输出作为对照。

`robust.yaml` 开启多径、衰落、相噪、SFO、IQ 失衡、削顶和两类干扰，用于后续
鲁棒性实验，不建议在 baseline 尚未收敛前直接使用。

## 合成调制

`datasets/modulation_generator.py` 支持：

- BPSK、QPSK、8PSK；
- 归一化 16QAM、64QAM；
- 连续相位 2FSK、CPFSK；
- 64 点、48 个有效子载波、16 点循环前缀的 OFDM（均可配置）。

PSK/QAM 使用单位能量 RRC 成形；OFDM 使用 256 点 IFFT、48 个有效子载波和
64 点 CP，其约 24 kHz 占用带宽接近 RRC 单载波的约 21.6 kHz。所有类别都从
更长的连续波形中随机选择记录起点，RRC 类别还会跳过完整启动瞬态。

输出统一为 `complex64` 基带
`x[n] = I[n] + jQ[n]`，并携带生成参数 metadata。训练集按 `(seed, epoch,
index)` 在线确定性生成：同一配置可复现，不同 epoch 不重复固化数据。
Validation/Test 使用不同 split key 且忽略 `set_epoch`，因此固定不变。

`evaluation/dataset_audit.py` 自动输出 class/SNR/modulation×SNR 计数、平均
功率、RMS、PAPR、边界功率、随机截取偏移、split 指纹交集和 shortcut 风险。

## ChannelPipeline

所有损伤均可通过 YAML 独立启停并配置概率/范围：AWGN、Rayleigh、Rician、
多径、CFO、随机相位、Wiener 相噪、插值近似 SFO、IQ 失衡、DC、幅度缩放、
幅度削顶、窄带干扰和突发干扰。AWGN 位于管线末端，其目标 SNR 以进入噪声
模块前的期望信号分量功率定义，并记录目标值、实测值、信号功率和噪声功率。
窄带/突发干扰使用独立 SIR，不能抬高 AWGN 的参考功率。

## 模型与评价

BaselineCNN 输入为 `[N, 2, L]`，三层 Conv1D 加 BatchNorm/ReLU、池化、
全局平均池化和线性分类头。训练支持 Adam/AdamW、cosine 或 plateau 调度、
early stopping，仅覆盖保存 `best.pt` 与 `last.pt`。

输出包括：

- `outputs/logs/training_history.csv`：epoch、loss、accuracy、Macro-F1、LR、时间；
- `outputs/tables/test_metrics.json` 和 per-class CSV；
- `outputs/tables/dataset_audit.json`、审计 Markdown 和分布/统计 CSV；
- `outputs/figures/confusion_matrix.png`；
- `outputs/tables/snr_metrics.csv`；
- `outputs/figures/snr_accuracy.png`、`snr_f1.png`。

Smoke 配置样本极少，SNR 曲线会有统计抖动，只用于确认整个 pipeline 连通。

## FPGA Golden Reference

`dsp/golden_reference.py` 实现 DC removal、RMS normalization、65-tap FIR、
FFT、power spectrum、framing 和 energy detection，并提供 int16/Q1.15 定点
FIR 模型。接口与位宽分析见 `docs/fpga_interface.md`。

当前建议是 16 位 IQ 输入、Q1.15 系数、40 位 FIR 累加器；1024 点 FFT 若不
缩放至少需要约 26 位，24 位路径必须配合逐级或块浮点缩放。功率计算建议至少
50 位内部精度。最终位宽必须由 OFDM 峰均比、RTL 饱和计数和板上数据决定。

## RadioML 2018.01A

项目不会自动下载数据。将官方获取的 HDF5 文件放置为：

```text
data/radioml/GOLD_XYZ_OSC.0001_1024.hdf5
```

`datasets/radioml_dataset.py` 按 `X/Y/Z` 键读取 IQ、one-hot 标签和 SNR。
文件不存在时只给出 warning 并回退到 synthetic smoke dataset；文件存在时需
额外安装 `h5py`。

## 磁盘管理

可以安全删除并重新生成的内容：

- `outputs/checkpoints/*`
- `outputs/figures/*`
- `outputs/logs/*`
- `outputs/tables/*`

清理命令：

```powershell
python -m scripts.clean_outputs
```

脚本只清理以上四个白名单目录（保留 `.gitkeep`），以及项目内部的
`__pycache__`/`.pytest_cache` 临时缓存。RadioML、原始 SDR 采集和其他本地
数据不会被该脚本触碰。CSV 日志每次训练覆盖写入，不会无限追加；checkpoint
始终只有 best/last 两份。

## 已知限制

- 当前 baseline 不是最终多域融合或 open-set 模型。
- SFO 是短记录上的插值近似，不等价于真实异步 ADC 全链路。
- 平坦 Rayleigh/Rician 当前为单记录块衰落；时变 Doppler 留待下一阶段。
- 当前星座/信道是通信仿真模型，尚未经过真实前端带宽、AGC、ADC 和本振标定。
- 本次没有 Icraft、Procise 或 FMQL30TAI 性能结论。
