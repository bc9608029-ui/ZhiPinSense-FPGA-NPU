# 板端测试步骤（独立候选，不覆盖正式版）

状态：`READY_FOR_BOARD_BUILD_AND_RF_RETEST`。这是电脑侧候选，不是 RF PASS，也没有替换正式自启动。

## 0. 历史 RF 分数 vs 本轮离线测试（分列）

| 项 | 来源 | 状态 |
|---|---|---|
| 定频 233/240、扫频 237/240（漏项 0，固定分母 240） | **历史真实 RF**（上一轮，已测） | 历史已测，作为本候选晋级门槛 |
| release audit `PROMOTION_CANDIDATE checks=7 failed=0` | 本轮离线 | 已跑，PASS |
| static_audit 16/16、py_compile、scan_lock_policy、standalone_control、ui_measurements | 本轮离线 | 已跑，全 PASS |
| C++ 板端编译、实屏、触控、240+240 回归 | 板端 | **未上板，必须按本文完成** |

离线测试 PASS 不代表实屏/RF 已过；240 源身份被多次复用，不代表未知波形泛化。

## 0.1 冻结身份（SHA256 前 8）

| 对象 | SHA256（前 8） | 校验点 |
|---|---|---|
| 模型 JSON | `28272abc…` | `run_repeat_mean_gapfix1.sh` 启动前 |
| 模型 RAW | `c1781aec…` | 同上 + UI `--model-sha` |
| two-DC | `e0aa1202…` | 接收包装器运行时 |
| 接收核 | `cb529824…` | 接收包装器运行时 |
| 独立接收器（覆盖层） | `4d35cf5e…` | 接收包装器运行时 + `install_overlay.sh` 部署产物 |

## 0.2 上传

将整个交付目录上传到板端，例如 `/root/rml24_mainchain_finalize1_delivery`（内含 `scripts/install_overlay.sh` 与 `overlay/`）。下文 `DELIVERY` 指向该 `candidate/` 目录。

## 0.3 未验证项清单（板端首跑前必须逐项关闭）

四个 BASE 来源运行时依赖不在覆盖层内、也不在 7 个冻结基线 SHA 里，其板端实际内容无法离线核实。完整身份与溯源见 `candidate/docs/DEPENDENCY_IDENTITY.md`。

| # | 项 | 离线状态 | 板端关闭方式 |
|---|---|---|---|
| 1 | 部署版 `standalone_control.py`（BASE `rml24_final/runtime/`） | 未验证；本地 `522aeaaa…` 为**循环复制**证据（C 从本 candidate 抄），非独立板端基线 | A.1 预检 + `board_collect_dep_sha.sh` 对照身份表 |
| 2 | `radio_tuning.py`（BASE） | 未验证；本地 `a6df471b…` 为 10-27 独立树副本，非板端 BASE 本身 | 同上 |
| 3 | `scan_runtime.py`（BASE） | 未验证；本地 `26d38b8e…` 为 10-27 独立树副本 | 同上 |
| 4 | `rml24_dualmode_receiver_centered_v2.py`（BASE） | 未验证；本地 `11061886…` 为 10-27 独立树副本 | 同上 |
| 5 | 板端 C++ 编译 / 实屏 / 触控 / RF 240+240 | 未上板 | B / C / D 节 |

---

## A. 部署到新测试树（校验 7 个冻结基线 SHA）

```bash
set -euo pipefail
DELIVERY=/root/rml24_mainchain_finalize1_delivery   # 上传的 candidate/ 目录，按实调整
BASE=/root/rml24_standalone_execution_20261027/candidate
TEST=/root/rml24_mainchain_finalize1_test_$(date +%s)
bash "$DELIVERY/scripts/install_overlay.sh" --base "$BASE" --out "$TEST"
printf '%s\n' "$TEST" | tee /root/rml24_mainchain_finalize1_test_root.txt
sha256sum \
  "$TEST/rml24_final/board_runtime/standalone_receiver.py" \
  "$TEST/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py" \
  "$TEST/rml24_final/runtime/receiver_core.py" \
  "$TEST/rml24_final/recovery/candidate_two_dc.py"
```

安装器先校验 **七个** 被冻结基线文件的 SHA（`standalone_receiver.py`、
`ui_render.hpp`、`ui_render.cpp`、`touch_mode_control.hpp`、
`board_ui_live_rml24_final.cpp`、`ui_event.py`、`ui_state_map.hpp`）；不匹配即停止。
它复制 BASE 后再叠加，**绝不就地修改 BASE**。上面的 `sha256sum` 应看到
`standalone_receiver.py`=`4d35cf5e…`、`receiver_core.py`=`cb529824…`、
`candidate_two_dc.py`=`e0aa1202…`。

### A.1 依赖预检（部署后、构建前，fail-closed）

四个 BASE 来源运行时依赖（`standalone_control.py` / `radio_tuning.py` /
`scan_runtime.py` / `rml24_dualmode_receiver_centered_v2.py`）不在覆盖层内，也不在
7 冻结 SHA 里，必须板端核验身份后才能继续：

```bash
TEST=$(cat /root/rml24_mainchain_finalize1_test_root.txt)
DELIVERY=/root/rml24_mainchain_finalize1_delivery

# 1) 仅采集 BASE 与 TEST 树里四个依赖的实测 SHA（不自动接受）
bash "$DELIVERY/scripts/board_collect_dep_sha.sh" \
  --base /root/rml24_standalone_execution_20261027/candidate --test "$TEST"

# 2) 预检部署树：存在性 + 冻结 SHA 硬校验 + 四依赖标记「待板端核验」
python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST"
```

把步骤 1 的实测 SHA 与 `candidate/docs/DEPENDENCY_IDENTITY.md` 身份表**逐项对照**；任一不符
即停止，不进构建/RF。确认一致后，把四个依赖实测结果写成 `sha256  relpath` 清单严格复验：

```bash
cat > /tmp/dep_expect.txt <<'EOF'
<实测sha256>  rml24_final/runtime/standalone_control.py
<实测sha256>  rml24_final/runtime/radio_tuning.py
<实测sha256>  rml24_final/runtime/scan_runtime.py
<实测sha256>  rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py
EOF
python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST" --expect /tmp/dep_expect.txt
```

`preflight_deploy.py` 退出码：0=通过（含四依赖 `UNVERIFIED_NEED_BOARD_CHECK` 报告，非自动接受）；
1=缺文件；2=冻结 SHA 不符；3=expect 不符；4=用法错误。缺文件 / 冻结 SHA 不符 / expect 不符
**必须停止**，不得进入构建或 RF。

## B. 构建与语法检查

```bash
set -euo pipefail
TEST=$(cat /root/rml24_mainchain_finalize1_test_root.txt)
python3 -m py_compile \
  "$TEST/rml24_final/board_runtime/standalone_receiver.py" \
  "$TEST/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py" \
  "$TEST/rml24_final/board_runtime/repeat_mean_candidate.py" \
  "$TEST/rml24_final/runtime/scan_lock_policy.py" \
  "$TEST/rml24_final/runtime/ui_event.py"
cd "$TEST"
taskset -c 0 bash board_package/build_ui_live_rml24_final.sh
test -x bin/board_ui_live_rml24_final
```

任何编译失败都不得进入 RF 测试，且不得修改编译选项掩盖错误。注意
`standalone_control.py` 是 BASE 冻结文件、不在覆盖层内，板端原生已含（无 2500
倍数步长校验）。

## C. 控制与实屏（不发射）

1. 用独立 socket 启动候选 UI 与接收器，不能同时运行原 `rml24-ui` / `rml24-receiver`。
2. 第五页应只显示 `FIXED`、`BAND SCAN`，不得出现 AutoLock 按钮。
3. 依次点四个频率字段（定频、扫频起点/终点/步进，单位 MHz），确认数字键盘含
   `.` 小数点键与 BACK/CLEAR/CANCEL/APPLY；键入十进制 MHz（如 `2395.5`）应发出
   `SET_FIXED_HZ 2395500000`（精确转整数 Hz，无浮点截断）。
4. 检查合法命令最终出现 `APPLIED`；非法频率或过多扫频点显示
   `REJECTED/INVALID RANGE/OUT OF RANGE`；离开第五页丢弃未提交草稿。
5. 用控制 socket 查询（socket 为 `/run/sdr_amr_control_rml24_final.sock`）：

```bash
CTL=/run/sdr_amr_control_rml24_final.sock
printf 'GET_TUNING\n' | socat - UNIX-CONNECT:$CTL
printf 'SET_MODE AUTO_LOCK\n' | socat - UNIX-CONNECT:$CTL
printf 'SET_SCAN_RANGE_HZ 2300000000 2500000000 1\n' | socat - UNIX-CONNECT:$CTL
printf 'SET_FIXED_HZ 2600000000\n' | socat - UNIX-CONNECT:$CTL
```

第一条返回 fixed/start/stop/step 与 readback；`AUTO_LOCK` 必须返回 ERR；
`step=1` 因超 `max_scan_points=101` 返回 ERR；`2600000000` 越界返回 `OUT_OF_RANGE`。

UI 启动参数示例（触控默认 VID/PID `1a86:e5e3`，可按需加
`--touch-swap-xy/--touch-invert-x/--touch-invert-y`；`--model-sha` 为门禁）：

```bash
"$TEST/bin/board_ui_live_rml24_final" \
  --sock /run/sdr_amr_ui_rml24_final.sock \
  --ctl-sock /run/sdr_amr_control_rml24_final.sock \
  --model-sha c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --run-id finalize1_$(date +%s)
```

## D. 真实 RF 回归

复用上一轮同一 240 波形、同一真值、同轴链路和计分器，新建运行目录，不能覆盖
`candidate_fixed02` 或 `candidate_scan01`。接收入口：

```bash
USER_RF_VALIDATION_APPROVED=YES \
LOCKED_MISSES_BEFORE_RESCAN=5 \
LOCKED_RESCAN_HOLD_SEC=1.0 \
bash "$TEST/rml24_final/board_runtime/run_repeat_mean_gapfix1.sh" \
  --run <fresh-run-dir> \
  --legacy-root /root/amr_rescue_20261025 \
  --model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 \
  --initial-mode FIXED
```

扫频轮将 `--initial-mode` 改为 `BAND_SCAN`，并显式传入与发射计划相同的
`--scan-start-hz/--scan-stop-hz/--scan-step-hz`。TX 与计分仍用上一轮冻结脚本，
不能把窗口数当独立样本。启动脚本会先校验模型 JSON/RAW 与 two-DC 的 SHA，不符即停。

## E. 回滚与收尾

```bash
# 停止测试进程（按实替换 PID/服务名）
pkill -f board_ui_live_rml24_final || true
pkill -f run_repeat_mean_gapfix1.sh || true
pkill -f receiver_repeat_mean_gapfix1.py || true
rm -rf /root/rml24_mainchain_finalize1_test_*   # 测试树
```

因 `install_overlay.sh` 从不就地改 BASE、也从不触碰正式 `rml24-ui` /
`rml24-receiver`，回滚即删测试树；若曾切换正式服务，则用 `systemctl` 恢复原 unit
与 `enable` 状态（不得修改开机默认）。不得修改 `enable` 状态或开机默认。

## F. 必须回传

- 构建完整日志与 UI 运行日志；
- 触控四字段的命令/ACK/readback 记录（含十进制 MHz 精确转 Hz 用例）和实屏照片；
- 定频、扫频各 240 固定分母逐样本结果；
- missing、rejected、misclassified 分开统计；
- 完整接收 JSONL 和 TX 私有时间真值；
- 两次全扫的耗时分布和重扫次数。

通过标准见 `docs/HANDOFF_MAINCHAIN_FINALIZE1.md`：定频 missing=0 且 ≥233/240、
扫频 missing=0 且 ≥237/240、四字段申请值/ACK/readback 三者一致、非法范围被拒且已
应用配置不变，才允许独立部署；否则回滚备份。测试结束恢复原 `rml24-ui` /
`rml24-receiver`。
