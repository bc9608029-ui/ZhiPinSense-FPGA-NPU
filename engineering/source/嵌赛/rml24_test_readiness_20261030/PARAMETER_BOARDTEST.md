# 增益与重复段数：独立测试步骤

## 1. 环境和范围

电脑用 `D:\Anaconda\python.exe`（需 numpy/scipy），板端选实际有 numpy/scipy 的 Python。TX/RX各一台Pluto，同轴/既定衰减连接保持原状。先用正式旧位流，不同时测试FPGA。TX固定2.4GHz、2.56MS/s、18MHz、-40dB、8重复；RX比较manual35基线/manual25/manual45/slow_attack。不是任意幅度自动补偿算法。

包整目录上传到板端 `/root/rml24_test_readiness_20261030`。PC私有资产和计划不得作为RX恢复输入；只上传板端工具时可不传 `tx/`，但该裁剪目录不能宣称整包SHA已验，改用单独记录的板端工具SHA。

板端先只读查实际路径和服务名：

```bash
find /root -type f -name npu_stream -perm /111 2>/dev/null
find /root -type f -name rml24_adamrv11_bf16.json 2>/dev/null
find /root -type f -name candidate_two_dc.py 2>/dev/null
systemctl list-units --type=service --state=running --no-pager
```

把实际核验值写进 shell 变量（以下路径是此前使用过的示例，必须 `test` 与 SHA 通过）：

```bash
ROOT=/root/rml24_test_readiness_20261030
PY=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3
NPU=/root/amr_rescue_20261025/build/npu_stream
RADIO=/root/amr_rescue_20261025/pluto_link_probe.py
# MODEL 是实际模型所在目录；RECOVERY 是当前冻结two-DC的实际文件。
# 赋值为你只读查到的完整路径后执行，不要保留占位符。
test -x "$PY" && test -x "$NPU" && test -f "$RADIO"
"$PY" -c 'import numpy,scipy,socket; print("PY_DEPENDENCIES_OK")'
"$PY" -I "$ROOT/preflight.py" --model-dir "$MODEL" --recovery "$RECOVERY" --radio "$RADIO" --npu-bin "$NPU"
```

须输出 target_dependencies=PASS。包SHA预检不替代硬件状态。RX_URI需现场只读扫描确认；先停占用RX/NPU的确切正式服务，记录其是否active，不改enable。参数命令可用 `service_guard.py --services 确切名.service --log 新日志 -- 命令...` 包装，仅恢复原本active的服务。不要用于FPGA超时复位场景。

## 2. 先无发射10秒

固定RX服务已停、TX关闭后，在板端执行（RX_URI使用本次枚举值）：

```bash
"$PY" -I "$ROOT/parameter_rx.py" --radio "$RADIO" --rx-uri "$RX_URI" --out /root/gain_silence_001 --mode manual --gain 35 --seconds 10
```

检查 `capture_summary.json` 无error、`restore_readback.json` 的 restore_verified=true。失败停测，不直接进入长采集。设备恢复异常不能只凭进程退出码称恢复成功。

## 3. 冻结计划：PC完成，RX不接收计划

PC与板之间预先具备SSH密钥认证（`clock_probe.py` 用 BatchMode；没有认证则先解决连接，绝不在RF中循环交互密码）。不调系统时间。先在PC新建会话目录：

```powershell
$Root = 'F:\嵌赛\rml24_test_readiness_20261030'
$Py = 'D:\Anaconda\python.exe'
$Run = Join-Path 'F:\嵌赛' ('gain35_smoke_' + (Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $Run -ErrorAction Stop
& $Py -I "$Root\clock_probe.py" --host root@192.168.126.49 --out "$Run\clock_pre.json"
$StartNs = & $Py -c 'import time; print(time.time_ns()+90000000000)'
& $Py -I "$Root\parameter_plan.py" --start-pc-ns $StartNs --out "$Run\plan.json" --count-per-class 1
```

默认24机会、每槽6秒（5秒发射+1秒空隙），约144秒。先只做manual35这一臂。`--count-per-class 10` 为240机会，1440秒；不要在24短测前直接四臂长跑。四臂使用同一来源和顺序，每轮重生成将来的起始时刻。记录臂顺序预设为35→25→AGC→45；第二次独立会话反向45→AGC→25→35，不能看结果改变顺序。

## 4. RX先连续采集，再PC独立TX

在PC预约开始后的90秒等待内，板端先开始连续210秒采集（24槽；240槽则用1510秒，并确认空间充足）：

```bash
"$PY" -I "$ROOT/parameter_rx.py" --radio "$RADIO" --rx-uri "$RX_URI" --out /root/gain35_smoke_001 --mode manual --gain 35 --seconds 210
```

**时间安排注意**：210秒覆盖“启动RX后最多约60秒等待+144秒TX”。若RX在预约前启动过早或预约启动太迟，可能不覆盖末槽，判分会记缺失；应让RX在TX预约前约30–50秒启动。240槽用1510秒同理。若PC干跑/检查导致预约时间已近，丢弃计划并生成新的将来计划，不能偷偷移动计划时间。

PC另一终端启动（TX_URI必须使用本次PC枚举值）：

```powershell
& $Py -I "$Root\parameter_tx.py" --plan "$Run\plan.json" --out "$Run\tx" --tx-uri $TxUri --libiio-library 'D:\radioconda\Library\bin\libiio.dll' --transmit
```

不用 `--transmit` 是纯数字干跑，会等待都不做、直接落24/240帧到新目录，不会导入IIO；干跑时不要占用正式预约计划。2026-10-30现场只读预检确认System32默认libiio为不兼容接口，而上述radioconda路径0.26可枚举本次TX为usb:1.7.5；后续仍需现场核对URI，不能固定沿用。RX不连接TX，发射不等待RX握手。AGC臂用 `--mode slow_attack`，不传 `--gain`；其余臂仅更改gain与全新输出目录。

结束后PC做第二次观察时间：

```powershell
& $Py -I "$Root\clock_probe.py" --host root@192.168.126.49 --out "$Run\clock_post.json"
scp root@192.168.126.49:/root/gain35_smoke_001/captures.jsonl "$Run\captures.jsonl"
```

必须在这轮结束后、同一台板且无重启/时钟校正条件下做post。判分使用预后偏移范围包络，>200ms或时钟跳变拒绝测量。它是有界时钟稳定假设，不是硬件同步证明；捕获时长保留时间余量，不取跨槽/边界帧。

## 5. 先选时间机会，再推理

PC：

```powershell
& $Py -I "$Root\select_opportunities.py" --plan "$Run\plan.json" --captures "$Run\captures.jsonl" --tx-events "$Run\tx\tx_events.jsonl" --clock-pre "$Run\clock_pre.json" --clock-post "$Run\clock_post.json" --out "$Run\selection.json"
scp "$Run\selection.json" root@192.168.126.49:/root/gain35_selection_001.json
```

selection只包含record_id与清单SHA，不含类别。选定后禁止根据预测重选。只推理选中的24/240条，避免对所有连续raw重复推理浪费时间；缺失机会仍保留在最终分母。

板端（其他NPU服务已停）：

```bash
bash "$ROOT/run_parameter_replay.sh" "$PY" "$NPU" "$MODEL" "$RECOVERY" /root/gain35_smoke_001 /root/gain35_replay_001 /root/gain35_selection_001.json
```

脚本校验模型SHA，独占socket，NPU→回放→清理自己创建的NPU子进程，不广泛杀进程。若子进程恢复/退出异常，保留日志并停下。回放每条raw同一次two-DC恢复，再以前1/2/4/8段平均并广播为8个模型窗口；推理调用数相同。

PC回收replay后判分：

```powershell
scp root@192.168.126.49:/root/gain35_replay_001/replay/replay.jsonl "$Run\replay.jsonl"
scp root@192.168.126.49:/root/gain35_smoke_001/capture_summary.json "$Run\capture_summary.json"
scp root@192.168.126.49:/root/gain35_smoke_001/restore_readback.json "$Run\rx_restore.json"
& $Py -I "$Root\parameter_score.py" --plan "$Run\plan.json" --captures "$Run\captures.jsonl" --replays "$Run\replay.jsonl" --tx-events "$Run\tx\tx_events.jsonl" --clock-pre "$Run\clock_pre.json" --clock-post "$Run\clock_post.json" --capture-summary "$Run\capture_summary.json" --rx-restore "$Run\rx_restore.json" --tx-restore "$Run\tx\tx_restore.json" --out "$Run\score.json"
```

同时回收NPU日志。判读退出0=分析且测量完整，2=分析完成但测量无效/不完整；缺文件等分析错误非0退出。分数只在两端恢复确认、完整日志身份与时间检查通过后解释。恢复失败、漏采、低分都保留。相同输入正确率增加不证明生产lock/sweep性能或泛化；24只是初筛，240及第二独立会话复验后才讨论晋级。带宽自适应、真正减少TX重复次数和生产入口更新均不在本实验。
