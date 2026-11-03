# 下一位 AI 唯一入口：纯净生成 v2 RadioML IQ 双 SDR 测试

## 1. 用户目标

在不修改模型、不修改现有接收恢复算法、不使用逐样本补偿的前提下，测试：

> 电脑 TX Pluto 发射纯净生成的 24 类 RadioML 格式 IQ，经同轴线进入板端 RX Pluto，板端使用现有公共训练帧恢复和冻结 NPU 模型完成 24 类识别。

本轮只做 24 帧（每类一帧），先判断此前 S1/S2 数据集 IQ 的 95% 能否泛化到纯净生成 IQ。

## 2. 必须先理解的口径

- 新测试载荷不是 RadioML HDF5 数据集样本，也不是 pilot1 的 S1/S2。
- 新载荷来自：
  `F:\嵌赛\fix10class24_waveform_correct_v2_work\replay_out\layers\1..24.orig.tensor.bin`
- 这是物理定义修正后的 v2 生成波形，24 类各一条、每条 1024 个复数采样点。
- TX 套用和已成功 228/240 测试相同的公开帧：静默 2048 + 公共训练 2048 + 载荷重复 8 次 + 公共尾段 2048 + 静默 2048，共 16384 complex。
- 24 帧全部使用同一个固定尺度 `68.46059377833956`；审计已证实没有任何样本触发峰值限幅或逐样本缩放。
- RX 板端只收到 `seq`，收不到标签、类别、源 IQ、生成种子、尺度或理想恢复参数。
- 现有模型权重完全不变；现有板端 CPU/Python 恢复算法完全不变；本轮无新增 FPGA 算法。
- 数字直送基线是 23/24，不应强行要求 RF 得到 24/24。唯一数字固有错：source 21、AM-DSB-SC（class 20）被预测为 256QAM（class 16）。

## 3. 工作目录与依赖

本轮准备目录：

```text
F:\嵌赛\amr_rescue_clean_v2_test_prep1
```

外部只读依赖：

```text
F:\嵌赛\fix10class24_waveform_correct_v2_work
F:\AMR_Rescue_20261025
```

板端既有部署目录：

```text
/root/amr_rescue_20261025
```

主要文件：

- `verify_clean_v2_inputs.py`：测试前 fail-closed 审计。
- `pc_clean_v2_tx.py`：实际 TX 服务；私有真值只保存在电脑。
- `start_clean_v2_tx.ps1`：电脑一键启动入口。
- `score_clean_v2.py`：固定 24 分母离线判分。
- `clean_v2_common.py`：共同合同与帧构造。
- `frozen_receiver_sha256.json`：冻结接收链身份。
- `BOARDTEST_CLEAN_V2.md`：人类版完整手册。
- `input_audit.json`：已经生成的通过证据。

## 4. 已完成的验证

以下均已在本机执行通过：

1. 24 个源张量的大小、有限性、SHA、类别顺序与 manifest 绑定：PASS。
2. 24/24 类覆盖：PASS。
3. 固定幅度 24/24，无逐样本峰值缩放：PASS。
4. 数字基线 23/24，唯一错误严格匹配 source 21：PASS。
5. 冻结接收端五个文件 SHA：PASS。
6. TX `--dry-run`：24 帧 PASS。
7. 判分器正常合成输入：23/24、与数字基线一致 24/24：PASS。
8. 判分器缺一帧反例：返回 rc=2，`INCOMPLETE_MEASUREMENT`：PASS。

不得重新生成波形、修改模型、调门限或修改接收算法后再称为同一次对照测试。

## 5. 实际板测步骤

### 5.1 硬件与网络

- TX Pluto：接电脑 USB。
- RX Pluto：接板子 USB。
- TX/RX 射频口用同轴线连接，保持此前成功测试的接法及衰减条件。
- 电脑有线网卡：`192.168.126.50/24`。
- 板子：`192.168.126.49/24`。
- 先确认双方可 ping。

### 5.2 电脑先做只读审计

Windows PowerShell：

```powershell
cd F:\嵌赛\amr_rescue_clean_v2_test_prep1
D:\radioconda\python.exe -I .\verify_clean_v2_inputs.py --out-json .\input_audit.json
```

只有看到 `"result": "PASS"` 才能继续。

### 5.3 电脑启动 TX

```powershell
cd F:\嵌赛\amr_rescue_clean_v2_test_prep1
.\start_clean_v2_tx.ps1
```

若自动扫描发现不止一台 Pluto，显式指定电脑 TX URI（以现场扫描为准，不可盲信旧编号）：

```powershell
.\start_clean_v2_tx.ps1 -TxUri 'usb:1.8.5'
```

记录第一行打印的：

```text
Private truth/output directory: F:\...\runs\clean_v2_...
```

该目录内 `expected_private.json` 是之后判分所需私有真值。保持窗口运行，等待：

```text
CLEAN_V2_TX_LISTENING ...
```

### 5.4 板端启动 RX

串口执行：

```bash
bash /root/amr_rescue_20261025/run_board.sh 192.168.126.50
```

不要重新构建、不要换模型、不要修改 `pilot_recovery.py`。完成后应看到 24 条处理记录和：

```text
BOARD_RX_COMPLETE 24
RESULT_DIR=/tmp/amr_rescue_run.XXXXXX
```

记录实际 `RESULT_DIR`。

### 5.5 把板端原始结果复制回电脑

Windows PowerShell（把占位路径替换成板端实际打印值）：

```powershell
scp root@192.168.126.49:/tmp/amr_rescue_run.XXXXXX/capture/results.json `
  F:\嵌赛\amr_rescue_clean_v2_test_prep1\board_results.json
```

如需完整留证，再复制整个结果目录；主判分只需要 `capture/results.json`。

### 5.6 电脑离线判分

将 `--expected` 替换为 5.3 记录的实际私有目录：

```powershell
cd F:\嵌赛\amr_rescue_clean_v2_test_prep1
D:\radioconda\python.exe -I .\score_clean_v2.py `
  --board-results .\board_results.json `
  --expected .\runs\clean_v2_实际目录\expected_private.json `
  --out-json .\clean_v2_score.json
```

## 6. 固定判定规则

- 分母始终为 24；缺帧、恢复失败和无法分类都算错。
- `20–24/24`：`CONTINUE`。说明同一通用恢复器对纯净生成波形也具有较好泛化；需同时报告相对数字基线 23/24 的 RF 新增错误。
- `16–19/24`：`INVESTIGATE_ONE_DAY`。只允许基于保存的 raw/input/logits 做一次限时定位，不立即训练。
- `<16/24`：`CLEAN_SIGNAL_TARGET_NOT_MET`。此前 S1/S2 的 95% 不得外推到纯净生成信号。
- 若结果不足 24 条：`INCOMPLETE_MEASUREMENT`，先重测，不能据此评价准确率。

## 7. 下一位 AI 的职责边界

下一位 AI 应：

1. 先读本文件和 `input_audit.json`。
2. 指导用户执行实际双 SDR 测试，避免把 PowerShell 命令贴进板端 Bash，或反过来。
3. 收到 `board_results.json` 后运行冻结判分器。
4. 如实报告 `correct/24`、接收失败数、相对数字基线一致数和 RF 新增错误。

下一位 AI 不应：

- 把 S1/S2 数据集 IQ 冒充为纯净生成 IQ。
- 在 RX 端使用类别、源 IQ、逐样本缩放或理想补偿参数。
- 为提高分数更改模型、接收器、门限、帧结构、波形或样本集合。
- 只报告门内准确率而剔除失败帧。
- 在本测试完成前开启训练或 FPGA 迁移。

## 8. 当前诚实状态

状态：`READY_FOR_24_FRAME_CLEAN_V2_RF_TEST`。

离线准备已完成；尚未执行本轮真实双 SDR 发射接收，因此不能写 RF PASS，也不能预报最终准确率。
