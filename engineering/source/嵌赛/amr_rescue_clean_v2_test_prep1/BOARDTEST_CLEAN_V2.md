# 纯净生成 v2 IQ：双 SDR 24 类测试

## 测试口径

- 载荷：`fix10class24_waveform_correct_v2_work/replay_out/layers/*.orig.tensor.bin`，即物理定义修正后的 24 类生成波形，不读取 RadioML HDF5 或 pilot1 S1/S2。
- 帧：公共静默段 + 公共训练段 + 8 次 1024 点载荷 + 公共尾段 + 静默段。
- 接收：完全复用 `F:\AMR_Rescue_20261025` 已验证接收链及原冻结模型；SHA 不符即停止。
- 隔离：板端只收到 `seq`，不收到类别、源 IQ、生成种子、尺度或理想恢复参数。
- 分母固定 24；缺帧、恢复失败、非分类均算错。

## 0. 离线审计（Windows PowerShell）

```powershell
cd F:\嵌赛\amr_rescue_clean_v2_test_prep1
D:\radioconda\python.exe -I .\verify_clean_v2_inputs.py --out-json .\input_audit.json
```

必须看到 `"result": "PASS"`、`class_coverage: 24/24`、数字基线 `23/24`。唯一已知数字误分类应为 source 21：AM-DSB-SC → 256QAM。

## 1. 连接

- TX Pluto 接电脑 USB；RX Pluto 接板子 USB；两台 Pluto 用同轴线连接。
- 电脑有线网卡：`192.168.126.50/24`；板子：`192.168.126.49/24`。
- 本测试只有 24 帧，约数分钟；无需重新构建板端程序，也不上传新模型。

## 2. 先启动电脑 TX

Windows PowerShell：

```powershell
cd F:\嵌赛\amr_rescue_clean_v2_test_prep1
.\start_clean_v2_tx.ps1
```

若发现多台 Pluto，显式指定：

```powershell
.\start_clean_v2_tx.ps1 -TxUri 'usb:1.8.5'
```

保持窗口打开，看到 `CLEAN_V2_TX_LISTENING` 后再启动板端。

## 3. 启动板端 RX

串口执行：

```bash
bash /root/amr_rescue_20261025/run_board.sh 192.168.126.50
```

结束时记录打印的 `RESULT_DIR=/tmp/amr_rescue_run.XXXXXX`。原始判分输入为：

```bash
$RESULT_DIR/capture/results.json
```

把该文件复制回电脑，例如保存为：

```text
F:\嵌赛\amr_rescue_clean_v2_test_prep1\board_results.json
```

## 4. 判分

电脑 TX 窗口第一行会打印私有输出目录，其中含 `expected_private.json`：

```powershell
D:\radioconda\python.exe -I .\score_clean_v2.py `
  --board-results .\board_results.json `
  --expected .\runs\clean_v2_实际目录\expected_private.json `
  --out-json .\clean_v2_score.json
```

判定：

- `20–24/24`：`CONTINUE`，证明同一通用恢复器能识别生成的纯净格式波形；数字上限参考为 23/24，而非强行要求 24/24。
- `16–19/24`：`INVESTIGATE_ONE_DAY`，只允许用保存的接收证据定位一次，不立即训练。
- `<16/24`：`CLEAN_SIGNAL_TARGET_NOT_MET`，不能用 S1/S2 的 95% 外推纯净生成信号。

本测试不修改模型，也没有新增 FPGA 算法；目标只是隔离并验证输入波形泛化能力。
