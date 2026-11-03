# 板端测试步骤 — AC 集成候选（多信号入口 + 多目标列表页）

状态：`OFFLINE_DEPLOYMENT_FLOW_VERIFIED_BOARD_ACCEPTANCE_PENDING`。电脑侧候选，非 RF PASS，未替换正式自启动。
所有板端步骤由用户经串口执行；本文件只给命令，不碰板。

## 0. 交付包只读核验

```bash
DELIVERY=/root/rml24_ac_integration_delivery
cd "$DELIVERY"
sha256sum -c SHA256SUMS_AC.txt          # 应全部 OK，54 文件
sha256sum dist/rml24_ac_integration_candidate.tar.gz
#   与 dist/RECEIPT_AC.txt 中记录的 archive_sha256 一致（归档外回执，避免自引用）
cat dist/RECEIPT_AC.txt
```

## A. 部署到全新测试树（本轮专用标识 `ac_integration`）

```bash
set -euo pipefail
DELIVERY=/root/rml24_ac_integration_delivery
BASE=/root/rml24_standalone_execution_20261027/candidate
TEST=/root/rml24_ac_integration_test_$(date +%s)
bash "$DELIVERY/scripts/install_overlay.sh" --base "$BASE" --out "$TEST"
printf '%s\n' "$TEST" | tee /root/rml24_ac_integration_test_root.txt
```

安装器先校验**七个**被冻结基线 SHA，再复制 BASE + 叠加，**绝不就地改 BASE**。

### A.1 依赖验收门（含第 9 个 BASE 依赖 `mode_control_server.py`）

5 个 BASE 依赖未确认时**只允许采集和比对身份，不允许进入 RF**。

```bash
TEST=$(cat /root/rml24_ac_integration_test_root.txt)
DELIVERY=/root/rml24_ac_integration_delivery

# 1) 采集 5 个 BASE 依赖实测 SHA（不自动接受）
bash "$DELIVERY/scripts/board_collect_dep_sha.sh" \
  --base /root/rml24_standalone_execution_20261027/candidate --test "$TEST"

# 2) 离线预检：13 冻结 SHA 硬校验 + 5 BASE 依赖存在性/标记
python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST"
```

步骤 2 的输出是 `result=PASS_OFFLINE_ONLY dependency_identity_verified=NO rf_forbidden=YES`——**这不是
完整验收通过**，此时只能采集和比对 5 个 BASE 依赖身份，**禁止进入 RF**。把步骤 1 实测 SHA
与 `docs/DEPENDENCY_IDENTITY.md` 逐项对照（5 个 BASE 依赖，含 `mode_control_server.py`
期望 `ffd78518…`），任一不符即停。确认后进入**严格模式**——必须 5 项期望 SHA 齐全且全部匹配：

```bash
cat > /tmp/dep_expect.txt <<'EOF'
<实测sha256>  rml24_final/runtime/standalone_control.py
<实测sha256>  rml24_final/runtime/radio_tuning.py
<实测sha256>  rml24_final/runtime/scan_runtime.py
<实测sha256>  rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py
<实测sha256>  rml24_final/runtime/mode_control_server.py
EOF
python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST" --expect /tmp/dep_expect.txt
```

严格模式必须打印 `result=PASS_STRICT rc=0 dependency_identity_verified=YES`（13 冻结 + 5 BASE 依赖全部
确认）才允许进入 RF。`dependency_identity_verified` **仅指依赖身份验收**，绝不暗示板端/RF 整体验收。
退出码语义：0=离线通过（`PASS_OFFLINE_ONLY` **禁 RF**）/严格通过（`PASS_STRICT` **允 RF**）；1=缺文件；
2=冻结 SHA 不符；3=expect 不符**或** expect 缺项（严格模式缺任一 BASE 依赖即 rc=3 `expect_incomplete`，
不许进 RF）；4=用法。非 0 必须停止。

## B. 构建（含本轮新增 C++ 多目标列表文件）

```bash
set -euo pipefail
TEST=$(cat /root/rml24_ac_integration_test_root.txt)
python3 -m py_compile \
  "$TEST/rml24_final/board_runtime/standalone_receiver.py" \
  "$TEST/rml24_final/board_runtime/standalone_receiver_multisignal.py" \
  "$TEST/rml24_final/runtime/multisignal_contracts.py" \
  "$TEST/rml24_final/runtime/multisignal_tracker.py" \
  "$TEST/rml24_final/runtime/multisignal_psd.py" \
  "$TEST/rml24_final/runtime/multisignal_scan_adapter.py" \
  "$TEST/rml24_final/runtime/multisignal_receiver_entry.py" \
  "$TEST/rml24_final/runtime/ui_event.py"
cd "$TEST"
taskset -c 0 bash board_package/build_ui_live_rml24_final.sh
test -x bin/board_ui_live_rml24_final
```

板端编译必须覆盖 `target_list_dispatch.hpp` / `target_list_rml24_parse.hpp` /
`target_list_state.hpp`（本轮新增）与 `ui_render.cpp` 的 `render_target_list`。编译失败不得
进 RF，不得改编译选项掩盖错误。

## C. 原路径回归（证明 DEFAULT 未破坏）

按 `docs/BOARDTEST.md` C/D 节跑一遍**原** `run_repeat_mean_gapfix1.sh`（`--initial-mode
FIXED`），确认第五页只有 `FIXED`/`BAND SCAN`、四频率字段十进制 MHz 精确转 Hz、非法范围被拒。
这是「原路径仍可独立运行」的直接证据。

## D. 候选多信号入口（`standalone_receiver_multisignal.py`）

用 `scripts/run_ac_candidate.sh` 一次性起 **NPU → UI → 接收端**。脚本**必填 `--expect` 与
`--python`**，内部先跑严格预检门（只接受 `PASS_STRICT`，任何子进程都不在门通过前启动），
再逐个核对真实脚本接口、逐项做就绪检查，并把三个进程的完整身份（boot_id/starttime/exe/argv）
记录到 `$RUN/pids.tsv`。三个 socket 都在 `$RUN/` 下（`npu.sock`/`ui.sock`/`control.sock`）。

```bash
set -euo pipefail
TEST=$(cat /root/rml24_ac_integration_test_root.txt)
DELIVERY=/root/rml24_ac_integration_delivery
RUN=/root/rml24_ac_integration_run_$(date +%s)
LEGACY=/root/amr_rescue_20261025
MODEL_DIR=/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16

# D.1 FIXED 模式：与 A 线单目标路径逐字节对照（测量/记录/UI 事件一致）
bash "$DELIVERY/scripts/run_ac_candidate.sh" \
  --test "$TEST" --legacy-root "$LEGACY" --model-dir "$MODEL_DIR" --run "$RUN" \
  --expect /tmp/dep_expect.txt --python python3 \
  --initial-mode FIXED --duration-sec 60

# D.2 BAND_SCAN 模式：多目标调度 + 每周期 rml24_targets 快照
RUN2=/root/rml24_ac_integration_run_scan_$(date +%s)
bash "$DELIVERY/scripts/run_ac_candidate.sh" \
  --test "$TEST" --legacy-root "$LEGACY" --model-dir "$MODEL_DIR" --run "$RUN2" \
  --expect /tmp/dep_expect.txt --python python3 \
  --initial-mode BAND_SCAN --duration-sec 60 \
  --scan-start-hz 2395000000 --scan-stop-hz 2405000000 --scan-step-hz 1000000
```

启动脚本顺序：校验参数（`--expect`/`--python` 必填且存在/可用）→ 校验
`npu_stream`/`pluto_link_probe.py`/`pilot_recovery.py`/模型 JSON/RAW/UI 二进制/候选入口都存在 →
校验模型 JSON `28272abc…`、RAW `c1781aec…`、two-DC `e0aa1202…` SHA → 独占 `mkdir $RUN`（已存在
则拒绝）→ **跑严格预检门（`PASS_STRICT` 才继续）** → 记录 run_id + 空 pids.tsv → 起 `npu_stream`
（等 `$RUN/npu.sock` 就绪+存活）→ 起 `board_ui_live_rml24_final`（`--sock $RUN/ui.sock`
`--ctl-sock $RUN/control.sock`，等 socket + `UI_LIVE_READY` 日志）→ 起候选入口（等
`STANDALONE_MULTISIGNAL_READY` + `$RUN/control.sock`）。三者完整身份写入 `$RUN/pids.tsv`。

D.1 应打印 `NPU_READY`/`UI_COMM_READY`/`RECEIVER_READY`，随后日志出现
`STANDALONE_MULTISIGNAL_READY` → `STANDALONE_MULTISIGNAL_COMPLETE records=…`，且
`records`/`valid`/`rejected` 与同批 A 线单目标结果一致（推理失败即致命，非恢复）。
`UI_COMM_READY` 是**进程通信就绪**；实屏显示另需 `UI_FB_READY`（物理屏幕验收，分开判断）。

## E. 多目标列表页验收（真实 UI）

1. BAND_SCAN 模式下 UI 第 0 页应渲染 `MULTI-TARGET SCAN` 列表（按中心频率升序），
   事件不再落入 `rejected`；日志见 `UI_RX type=rml24_targets valid=1`。
2. 选中目标 → 右列 Top3/params/constellation **只来自该目标身份 + 该目标数据时间**；切换
   到另一目标、目标消失/未分类/过期、或取消时，旧 IQ/params 被清除（不显示残留星座）。
3. 选中目标与 result 帧 `spectrum_center_hz` 不一致时，渲染端清 `iq_display_valid` /
   `meas.valid`（不画旧星座）。
4. FIXED 模式第 0 页仍走原 `render_main`，页面/控件逐字节不变。

## F. RF 回归

复用上一轮同一 240 波形、同一真值、同轴链路和计分器，新建运行目录，不覆盖
`candidate_fixed02`/`candidate_scan01`。定频/扫频各 240 固定分母，missing=0 且不低于
`docs/BOARDTEST.md` 记录的晋级门槛。TX 与计分用上一轮冻结脚本，不把窗口数当独立样本。

## G. 回滚（身份核对，只停本轮 PID，无自动删除）

回滚脚本**核对完整进程身份**（同 boot_id + 同 starttime + 预期角色 + 精确 exe + NUL 分隔 argv 的
sha256 全匹配）才停该 PID；任一不符或无法可靠核对即 `REFUSED`（不杀）并返回非零，**绝不用
宽泛 `pkill`、绝不退化到通用程序名、不碰正式服务**。先 RX→等其清理退出→UI→NPU，RX 给有界
TERM 宽限（默认不 KILL）。**没有自动删除**：运行目录与日志永远保留。

```bash
DELIVERY=/root/rml24_ac_integration_delivery
# 停止本轮进程（身份核对后才停；默认保留目录和日志）
bash "$DELIVERY/scripts/rollback_ac_candidate.sh" --run /root/rml24_ac_integration_run_<本次>
```

`ROLLBACK REFUSED reason=identity_mismatch(...)` / `identity_unverifiable(...)` = 身份不符/不可核对，
**不杀**；`already_exited` = 该 PID 已退出，跳过。**不再有 `--cleanup` 选项**（传 `--cleanup` 明确
拒绝 rc=2，且不删除任何东西）。`install_overlay.sh` 从不就地改 BASE、从不碰正式服务。若曾切换
正式服务，用 `systemctl` 恢复原 unit 与 `enable` 状态（不改开机默认）。

## H. 必须回传

- 构建完整日志（含新增 C++ 文件编译通过证据）与 UI 运行日志；
- D.1 的 `STANDALONE_MULTISIGNAL_COMPLETE` 记录数与 A 线同批对照；
- D.2 的 `rml24_targets` 事件序列 + 列表页实屏照片（选择/清旧/一致性）；
- 定频、扫频各 240 固定分母逐样本结果（missing/rejected/misclassified 分开）；
- 5 个 BASE 依赖实测 SHA（`board_collect_dep_sha.sh` 输出）。
