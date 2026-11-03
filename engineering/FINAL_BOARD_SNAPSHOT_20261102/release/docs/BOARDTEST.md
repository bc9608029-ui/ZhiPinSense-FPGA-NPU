# 板端验收：先短测，不自动开始240＋240

当前只有电脑侧准备与主机验证，不是aarch64/RF通过。保留原位流和正式自启。多频点TX是独立任务，先验发射源再评巡扫。

## 1. 上传与解包

Windows PowerShell：

```powershell
$Pkg='F:\嵌赛\rml24_sweep_history_20261029\dist\rml24_three_modes_history_candidate_20261029.zip'
Get-FileHash -Algorithm SHA256 -LiteralPath $Pkg
scp $Pkg root@192.168.126.49:/root/three_modes_history_candidate.zip
```

整包SHA以同目录.zip.sha256为准。网络IP要先ping确认，不能把历史电脑192.168.126.50与旧192.168.126.10混用。接收候选无需TX控制网络。

板端Bash：

```bash
set -euo pipefail
PY=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3
test -x "$PY"
sha256sum /root/three_modes_history_candidate.zip
TEST=$(mktemp -d /root/three_modes_history_XXXXXXXX)
"$PY" -m zipfile -e /root/three_modes_history_candidate.zip "$TEST"
cd "$TEST"
sha256sum -c SHA256SUMS.txt
printf '%s\n' "$TEST" > /root/three_modes_history_test_root.txt
```

包不带x86主机编译产物，不可复用旧UI二进制。解包是新目录，绝不覆盖BASE。

## 2. 只读记录与板端构建

```bash
TEST=$(cat /root/three_modes_history_test_root.txt)
cd "$TEST"
systemctl is-active rml24-ui rml24-receiver || true
systemctl cat rml24-ui rml24-receiver > evidence/board_original_units.txt
uname -a > evidence/board_uname.txt
taskset -c 0 bash candidate/board_package/build_ui_live_rml24_final.sh 2>&1 | tee evidence/board_build.log
test -x candidate/bin/board_ui_live_rml24_final
file candidate/bin/board_ui_live_rml24_final
```

需确认构建rc=0、UI_BUILD_RESULT result=PASS及aarch64产物。不得用x86主机日志代替。

核对服务ExecStart、启动目录、原模型、原位流及原服务恢复方式。最近交接服务名为rml24-ui/rml24-receiver，若实机不同先查明，不盲目停止其他服务。

## 3. 严格预检（不启动SDR）

```bash
PY=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3
TEST=$(cat /root/three_modes_history_test_root.txt)
LEGACY=/root/amr_rescue_20261025
MODEL=/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16
sha256sum "$LEGACY/build/npu_stream" "$LEGACY/pluto_link_probe.py" "$LEGACY/pilot_recovery.py"
```

先独立核对npu_stream就是正式稳定入口使用的可执行文件（ExecStart/启动脚本和来源记录），再把其完整SHA填入NPU_SHA；不是用任意新二进制的实测SHA冒充可信身份。包内未带模型或该外部二进制。

```bash
NPU_SHA=填写已独立核对的64位稳定NPU可执行文件SHA
"$PY" "$TEST/scripts/run_candidate.py" --check \
  --legacy-root "$LEGACY" --model-dir "$MODEL" --npu-sha "$NPU_SHA"
```

必须SWEEP_HISTORY_PREFLIGHT PASS。预检校验全候选源SHA、冻结模型JSON/RAW、legacy两个Python及NPU身份；检查解释器numpy/scipy。只匹配SHA不代替RF验收。外部依赖不同必须查来源，不能直接放宽。

## 4. 暂停正式服务，运行独立候选

只有确认原服务状态和恢复命令后，才做以下操作。原服务若本来inactive，结束不要擅自改为active。记录原enable状态；不改enable，不写自启、SD、Flash、不加载位流。

```bash
systemctl stop rml24-receiver rml24-ui
systemctl is-active rml24-receiver rml24-ui || true
RUN=/root/sweep_history_$(date +%s)
"$PY" "$TEST/scripts/run_candidate.py" \
  --legacy-root "$LEGACY" --model-dir "$MODEL" --npu-sha "$NPU_SHA" \
  --run "$RUN" --mode FIXED --fixed-hz 2400000000 \
  --duration-sec 120 --history-file /root/sweep_history_candidate.txt --save-captures
```

先无发射短测：UI/NPU/RX就绪，静默不产生有效历史，模式与频率输入可操作。然后安排已验证单信号源：定频能识别并记一条，持续识别不刷10条。MODEL/two-DC/相干平均路径必须与基线一致。

第五页可切三模式。也可每轮启动新RUN，--mode BAND_SCAN或CONTINUOUS_SCAN，附：

```text
--scan-start-hz 2395000000 --scan-stop-hz 2405000000 --scan-step-hz 1000000
```

这不是三条命令同时运行。每次等待上一监督器退出、确认设备恢复后再起下一轮。Ctrl+C停止当前监督器；其只管理自身子进程，先RX再UI/NPU。若报告RX停止超时，不默认强杀、不继续启动另一轮，先检查日志与设备恢复。

## 5. 功能短测项目

- FIXED：频率输入准确；相干平均仍使用；恢复/推理成功和失败分开。
- SEARCH LOCK：持续信号保持锁定；撤信号后按原5次且≥1秒失锁规则重新搜索。
- SWEEP：records.jsonl中的scan_index遍历1..N再从1开始，命中后仍进入下一点。中心估计后确认用的是重调谐的新采集，不能复用发现LO数据冒充居中结果。静默/恢复失败/单路持续存在均不长期卡住。
- HISTORY：真实有效结果进入；最多10个频率摘要，5条/页；同频更新、换页、详情、返回、清空确认；不同模式共用。详情不含实时IQ；列表快照关闭重开刷新。新结果到达时已打开详情不改变。
- 持久化：正常退出后重新指定同一history-file可读回；损坏测试只用副本，不破坏用户正式历史。文件故障告警，不能静默覆盖。
- 页面：五页切换；MHz小数精确到整数Hz；非法范围拒绝；SCAN进度更新；最后识别频率/时间与保存结果一致；换中心不拼接错误瀑布，历史星座不能伪造。
- 回退：监督器退出、rx_restore=[]、无stop_errors后恢复原服务，实际原界面与原接收正常。

## 6. 多频点源先验收

另见 F:\嵌赛\rml24_multifreq_tx_validation_20261029。离线发现约−28dBc的±2.56MHz副本；不是已验证的纯净双目标RF源。先静默、A-only、B-only、both、撤B、静默，并用原始IQ频谱验证主信号和副本。相位须覆盖足够完整扫描周期，TX默认10秒可能短于一次全扫，不能机械照用；双方先冻结足够时长再开始。

巡扫只需发射信号，不接受TX频点/类别通知。计分在事后用TX私有日志映射。若副本真实可检出，不能简单把多于2目标都判RX失败；先给TX源纯度/验收范围结论。

## 7. 后续回归与回传

短测通过才安排正式定频、搜索锁定、连续巡扫回归。240＋240是历史定频/扫频方案，本轮新增第三模式，需先冻结各模式样本集合和计分规则，不混为一个指标；长回归由用户另行安排，不自动执行。

固定分母；missing、拒绝、误分类分开，历史条数与扫描周期数不当成独立240样本。扫描速度报告完整周期耗时、每点耗时和命中额外耗时。不能沿用233/240、237/240作为本候选成绩。

回传：校验、board_build.log、源/模型/legacy/NPU身份、原服务记录、所有RUN日志及capture/records.jsonl、supervisor.json、原始IQ、输入张量、触摸实屏照片、历史文件及回退证明。未通过不部署。
