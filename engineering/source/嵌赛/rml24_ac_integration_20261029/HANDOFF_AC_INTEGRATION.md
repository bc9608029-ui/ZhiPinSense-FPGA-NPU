# RML24 AC 集成交接（39e5 最终整改收口）

状态：`OFFLINE_DEPLOYMENT_FLOW_VERIFIED_BOARD_ACCEPTANCE_PENDING`。部署/启动/回退/预检的
**离线流已核验**；板端 aarch64 编译、实屏/触控、真实设备恢复、240×2 RF 仍未通过。这是电脑侧
候选，不是 RF PASS，也没有替换正式自启动。

## 1. 本轮解决什么（最终整改 4 个已证实问题）

| # | 问题 | 收口 |
|---|---|---|
| 1 | 启动入口可绕过严格依赖门 | `run_ac_candidate.sh` 必填 `--expect FILE` + `--python PY`；在创建任何子进程前调用**本交付内** `preflight_deploy.py` 对真实 TEST_TREE 跑**严格模式**，只接受 `rc=0 且 result=PASS_STRICT`；`PASS_OFFLINE_ONLY`、缺项、某项 SHA 错、known 文件漂移、预检脚本缺失/异常 → 一律非零退出且**启动 0 个子进程** |
| 2 | 回退可误杀正式进程 | 启动时记录每个子进程完整身份（boot_id / `/proc/PID/stat` starttime / 角色 / 精确 exe / NUL 分隔 argv 的 sha256）；回退要求**身份组合全部满足**才停，任一不符或不可核对即 `REFUSED` 返回非零，绝不退化到通用程序名；PID 只接受 >1 正整数；先 RX→等其清理退出→UI→NPU，RX 有界 TERM 宽限不默认 KILL |
| 3 | `--cleanup` 路径校验不足 | **移除自动删除**：`rollback_ac_candidate.sh` 不再提供 `--cleanup`（传 `--cleanup` 明确拒绝 rc=2），运行目录/日志/用户文件**永远保留** |
| 4 | socket 默认与正式服务冲突、就绪误报 | 三个 socket 全部放在本次新建独占的 `$RUN/` 下（`npu.sock`/`ui.sock`/`control.sock`）；启动前检查 Unix socket 路径字节长度；RUN 必须绝对路径、独占创建、拒绝已存在；就绪=本次进程存活 + 本次 socket + 真实 ready 日志标记（UI 分 `UI_LIVE_READY` 进程通信就绪 与 `UI_FB_READY` 实屏 两档） |

## 2. 冻结身份（前 8）

| 对象 | SHA256（前 8） |
|---|---|
| 模型 JSON | `28272abc…` |
| 模型 RAW | `c1781aec…` |
| two-DC | `e0aa1202…` |
| 接收核 | `cb529824…` |
| 单目标入口（DEFAULT，未改） | `4d35cf5e…` |
| 多信号入口（候选） | `35f8dd6c…` |
| ReceiverEntry | `125590e7…` |
| 多信号合同/跟踪/调度/PSD | `f23dd340…` / `7af0ff26…` / `95723bae…` / `4dba4f7e…` |
| C++ 分发/解析/状态 | `d3b7dc70…` / `5799f904…` / `38cc7484…` |

## 3. 交付包

```
dist/rml24_ac_integration_candidate.tar.gz
  内含 54 文件 + SHA256SUMS_AC.txt（authoritative 自校验清单）
  归档 SHA256 由打包步骤打印并写入 dist/RECEIPT_AC.txt（在归档外，避免自引用）
  上一版 54 文件归档 SHA `128b0768…` 已作废，一律以本版 dist/RECEIPT_AC.txt 为准
```

生成：`python3 -I scripts/package_ac_candidate.py`
独立核验：`python3 -I scripts/verify_ac_package.py --archive dist/rml24_ac_integration_candidate.tar.gz --out /tmp/ac_verify --base local_base`

## 4. 离线验证结果（本机实测，非板端）

| 项 | 结果 |
|---|---|
| Python pytest | **64 passed**（9 旧新对照 + 55 C 线平坦部署适配） |
| C++ host 编译+单测 | **ALL CHECKS PASSED (84 checks)**（g++ 15.2.0，-Wall -Wextra 无告警） |
| 独立解包 + SHA 核验 | **PASS**（54 文件全对） |
| 5 个 multisignal 模块独立 import + ReceiverEntry 表面 | **PASS**（10 方法齐全） |
| 依赖闭包静态解析 | 单目标入口 9 模块、候选入口 12 模块，**unresolved=none**（对合并树） |
| preflight_deploy.py 退出契约（真实预检逐项） | 无 `--expect`→`PASS_OFFLINE_ONLY` rc=0；全 `--expect`→`PASS_STRICT dependency_identity_verified=YES` rc=0；缺 1 项→rc=3 `expect_incomplete`；某项 SHA 错→rc=3 `expect_mismatch`；known 文件漂移→rc=2；缺文件→rc=1；坏树→rc=4 |
| 部署/启动/回退脚本无设备模拟 | `bash -n` 6 脚本全过；`selftest_deploy_flow.sh` **55/55**（严格门 8 反例 + 回退身份 13 反例 + 无删除 + 完整编排成功） |

**未上板**：aarch64 编译、实屏、触控、真实 `rml24_targets` 数据流、真实设备恢复、240+240 RF 回归、
5 个 BASE 依赖板端 SHA 核验。

## 5. 部署 / 交接 / 回滚唯一命令（本轮专用标识 `ac_integration`）

```bash
# —— 上传交付目录后 ——
DELIVERY=/root/rml24_ac_integration_delivery
BASE=/root/rml24_standalone_execution_20261027/candidate
TEST=/root/rml24_ac_integration_test_$(date +%s)

# 1) 部署到全新测试树（校验 7 个冻结基线 SHA，就地不改 BASE）
bash "$DELIVERY/scripts/install_overlay.sh" --base "$BASE" --out "$TEST"
printf '%s\n' "$TEST" | tee /root/rml24_ac_integration_test_root.txt

# 2) 采集 5 个 BASE 依赖实测 SHA（含 mode_control_server）
bash "$DELIVERY/scripts/board_collect_dep_sha.sh" --base "$BASE" --test "$TEST"

# 3) 离线预检（只采集/比对，禁 RF）
python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST"

# 4) 确认 5 依赖实测 SHA 与 docs/DEPENDENCY_IDENTITY.md 一致后，写成期望清单
#    <实测sha256>  rml24_final/runtime/standalone_control.py
#    <实测sha256>  rml24_final/runtime/radio_tuning.py
#    <实测sha256>  rml24_final/runtime/scan_runtime.py
#    <实测sha256>  rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py
#    <实测sha256>  rml24_final/runtime/mode_control_server.py
python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST" --expect /tmp/dep_expect.txt
```

**依赖验收门**：`PASS_OFFLINE_ONLY dependency_identity_verified=NO rf_forbidden=YES` 不是完整
验收，此时禁 RF；只有 `PASS_STRICT dependency_identity_verified=YES`（5 项 BASE 依赖齐全且全匹配）
才允许进 RF。`dependency_identity_verified` **仅指依赖身份验收**，绝不暗示板端/RF 整体验收。

启动候选入口用 `scripts/run_ac_candidate.sh`（**必须** `--expect` 与 `--python`；内部先跑严格预检
门，只接受 `PASS_STRICT`，再起 NPU→UI→接收端、逐项就绪检查、记录三进程完整身份），回滚用
`scripts/rollback_ac_candidate.sh`（**身份核对**只停本轮进程，默认保留目录与日志，**无自动删除**）：

```bash
# 启动：--expect 用步骤 4 的期望清单；--python 板端默认 python3（启动前会自检可用）
bash "$DELIVERY/scripts/run_ac_candidate.sh" \
  --test "$TEST" --legacy-root /root/amr_rescue_20261025 \
  --model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 \
  --run /root/rml24_ac_integration_run_$(date +%s) \
  --expect /tmp/dep_expect.txt --python python3 \
  --initial-mode BAND_SCAN --duration-sec 60

# 回滚：身份核对（boot_id/starttime/exe/argv）后才停；只停本轮；目录日志保留
bash "$DELIVERY/scripts/rollback_ac_candidate.sh" --run <本次 RUN 目录>
```

## 6. 两个入口

- **DEFAULT/fallback（原路径，未改）**：`standalone_receiver.py`（4d35cf5e），经既有
  `run_repeat_mean_gapfix1.sh` 或原启动方式运行。
- **候选多信号入口**：`standalone_receiver_multisignal.py`（35f8dd6c），由
  `scripts/run_ac_candidate.sh` 起（严格门 → NPU→UI→接收端 + 就绪检查 + 身份记录）。入口参数
  （已核对真实接口）：`--legacy-root`、`--npu-socket $RUN/npu.sock`、`--ui-socket $RUN/ui.sock`、
  `--ui-control-socket $RUN/control.sock`、`--out $RUN/capture`、`--initial-mode FIXED|BAND_SCAN`、
  `--duration-sec`、扫频 `--scan-start-hz/--scan-stop-hz/--scan-step-hz`、可选 `--save-captures`。
  **三个 socket 都在本次 `$RUN/` 下**，不指向固定 `/run/rml24_standalone_*`。

`--initial-mode FIXED` 走字节忠实于 A 线单目标路径（含测量/记录/UI 事件）；`BAND_SCAN`
额外每周期发 `rml24_targets` 快照给五页 UI。

## 7. 红线（不变）

不训练/不改模型/不操作 SDR/不发射/不重跑 RF；不改冻结单目标入口 4d35cf5e；不把离线
测试称 RF_PASS/PROJECT_COMPLETE；板端全部步骤由用户经串口执行；候选未安装、未自启。
阻塞项 = 板端 aarch64 编译 + 实屏/触控 + 真实设备恢复 + 240×2 RF 回归 + 5 BASE 依赖板端 SHA 核验。
