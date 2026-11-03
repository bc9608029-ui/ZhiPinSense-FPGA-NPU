# M29 RML23 Stage H-F / Route F — fix9r1 打包权限修复 审计与交付记录

状态：**`M29-RML23-IQ-RF-LOOPBACK-FIX9R1-READY-FOR-BOARD-TEST`**（待用户上板 46 样本复测）

fix9r 状态（不变）：`FIX9R_ALGORITHM=DELIVERED`、`FIX9R_BOARD_TEST=PENDING`。
fix9r1 状态：`FIX9R1_WORK=DELIVERED`、`FIX9R1_BOARD_TEST=PENDING`。
暂停项（不变）：`DUAL_SDR_WORK=PAUSED`（fix10 双 SDR 全部文件保留）、`FORMAL_690_RF_RUN=BLOCKED`。

---

## 1. 缺陷证据（fix9r 打包权限 DEFECT）

fix9r 交付全量包 `sdr_rml23_live_board_package_iq_rf_loopback_fix9r.tar.gz`（SHA `3642caffac4d…`）**内容正确**，但 tar 成员权限是缺陷：

```
$ tar -tvzf dist/sdr_rml23_live_board_package_iq_rf_loopback_fix9r.tar.gz | head
-rw-rw-rw- 0/0       0 ... board_package/build_on_board.sh
-rw-rw-rw- 0/0       0 ... board_package/build_npu_on_board.sh
-rw-rw-rw- 0/0       0 ... scripts/build_on_board.sh
...  （全部文件均为 -rw-rw-rw- = 0666，无一可执行）
```

- 全包 **0 个目录成员**，全部 571 个文件成员 mode 均为 `-rw-rw-rw-`（0666）。
- 板端解包后 `scripts/*.sh`、`board_package/*.sh` 无执行位 → `./scripts/build_on_board.sh` 报 **Permission denied**，板测无法启动。
- 判定：`FIX9R_PACKAGING_PERMISSION=DEFECT`。

## 2. 根因

fix9r 打包器 `scripts/package_iq_rf_loopback_fix9r.py` 的 `make_tar()` 用 `tarfile.gettarinfo(full, arcname=arc)` 取成员信息，**只覆盖了 `uid/gid/uname/gname/mtime`，没有显式覆盖 `info.mode`**。`gettarinfo` 在 Windows 上读 `os.lstat` 的 `st_mode`，而 Windows 没有 Unix 执行位（只有只读标志），于是**每个文件都被报告为 0666**（`-rw-rw-rw-`）。且打包器只遍历文件（`list_files`），从不产出目录成员。

结论：不是算法缺陷，是**打包器在 Windows 上的元数据缺陷**——必须在 tar 成员元数据里显式写入正确 mode。

## 3. fix9r1 权限实现

fix9r1 打包器 `scripts/package_iq_rf_loopback_fix9r1.py` 的 `make_tar()` 对每个成员显式赋值（绝不用 0666 / 0777）：

| 成员类型 | mode |
|---|---|
| 目录（含顶层目录，显式产出目录成员） | `0o755` |
| `*.sh`（scripts / board_package / host_tests / host_tools 等全部） | `0o755` |
| 其余普通源码 / 配置 / 文档 / 二进制 | `0o644` |

同时保持确定性元数据：`uid=0, gid=0, uname="", gname="", mtime=0`，gzip 头 `mtime=0` 且无 FNAME，compresslevel=9。**权限变化只写在 tar 成员元数据里，不改任何文件内容字节。**

## 4. fix9r 内容差异（字节级证明）

fix9r1 相对 fix9r 全量包，**内容字节变化只有 2 个新增文件**（打包器本身 + 本审计），其余 570 个内容文件 **字节完全一致**：

- 新增 `scripts/package_iq_rf_loopback_fix9r1.py`（本打包器）
- 新增 `docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R1_AUDIT.md`（本审计）
- `SHA256SUMS.txt` 重生成（多 2 行；本身是清单文件，合法变化）

**核心代码字节未变**（打包器内 `verify_content_consistency` 逐一 SHA-256 比对，结果 570 一致 / 0 变化）：

- `board_package/iq_rf_training_frame.hpp`、`iq_rf_per_frame_recovery.hpp`、`iq_rf_loopback_23class_fix9r.hpp`、`iq_rf_loopback_transfer_fix9r.hpp`、`iq_rf_fix9r_baseline.hpp`
- `board_package/board_gate9_full_chain_rml23.cpp`、`board_package/gate9_phase.hpp`
- `sdr_adapter/*` 全部、`model_rml23/*` 全部、`model_12class/*` 全部
- 24→23 合并规则、23 类标签、逐帧训练帧、RF 恢复算法、分类路径：**字节未变**

**权限变化与内容变化分开报告**：权限变化 = 全包 571 文件 mode 0666 →（13 目录 0755 + 60 `.sh` 0755 + 其余 0644）；内容变化 = 仅上述 2 新增文件 + SHA256SUMS.txt 重生成。

## 5. tar mode 验证（独立 Python 检查）

独立于打包器的 Python 脚本直接打开两个 fix9r1 包，逐成员断言：

- 目录成员 mode `& 0o777 == 0o755`；
- `.sh` 成员 mode `& 0o777 == 0o755`；
- 其余文件成员 mode `& 0o777 == 0o644`（且**不得**为 0666 / 0777）。

结果（见交付清单 §验证）：`directories_0755=13`、`shell_scripts_0755=60`、`bad_directories=0`、`bad_shell_scripts=0`、`result=PASS`。

## 6. 独立解包验证（WSL/Linux）

在 WSL（Linux 语义）下独立解包 fix9r1 全量包并验证执行位：

```bash
EXTRACTED_ROOT=<解包目录>/sdr_rml23_live_board_package_iq_rf_loopback_fix9r1
find "$EXTRACTED_ROOT" \( -path '*/scripts/*.sh' -o -path '*/board_package/*.sh' \) -type f ! -perm -111 -print
#  期望：零输出
test -x "$EXTRACTED_ROOT/scripts/build_on_board.sh"      && echo OK   # 期望 OK
test -x "$EXTRACTED_ROOT/board_package/build_npu_on_board.sh" && echo OK  # 期望 OK
```

板端**无需再 `chmod +x`**；若仍需，则 fix9r1 权限修复失败。

## 7. 离线验证结果汇总

| # | 项 | 结果 |
|---|---|---|
| 1 | fix9r 核心 host 测试（内容字节一致，结转 + 重跑） | `test_iq_rf_loopback_23class_fix9r` pass=71 fail=0；`test_iq_rf_loopback_23class`（fix9 无回归）pass=93 fail=0 |
| 2 | syntax check（字节一致，结转） | gate7/gate9/gate10/gate9_rml23 全 OK |
| 3 | analyzer self-test | `analyze_iq_rf_loopback_recovery.py --self-test` 9/9 |
| 4 | exact-baseline self-test | `build_route_f_fix9r_exact_baseline.py --self-test` 5/5 |
| 5 | dependency closure（字节一致，结转） | OK（fix9r1 不改任何 C/C++ 文件） |
| 6 | 2× 确定性打包 | 两次运行 fix9r1 打包器 SHA 一致 |
| 7 | 独立解包 `sha256sum -c` | patch / full 全部 OK |
| 8 | tar mode 审计 | directories_0755=13 shell_scripts_0755=60 bad=0 result=PASS |
| 9 | WSL 解包执行位审计 | `find ! -perm -111` 零输出；`test -x` 返回 0 |
| 10 | fix10 零残留 | fix9r1 全量包 grep `iq-external-rf` / `extrf::` / `fix10` / `pluto_external_tx` 零命中 |

fix10 暂停中测试 `test_iq_external_rf_rx_23class`（原 41/12，帧同步/CFO/SRO 未完成）标为 **`SKIPPED_PAUSED_FIX10`**，不计入 pass 数。

## 8. 红线遵守（未改）

- 模型及 NPU 二进制（`model_rml23/model_24class_ZG.raw`、`model_12class/model_12class.raw`）、23 类标签与 24→23 合并规则、逐帧训练帧、RF 恢复算法、分类路径：**未改**；
- production RX 默认路径、正式模型预处理、RTL/XDC/位流/Flash：**未改**；
- RF 安全上限 `kSafeTxCeilingDb=-40.0` / `kSafeTxAttenDb=-89.75`：**未改**；
- 暂停中 fix10 磁盘文件：**未触碰**。

## 9. 板端复测命令（用户上板，我禁碰板；无需 chmod）

```bash
# 0. 解包全量包（脚本已带 0755，直接可执行）
tar -xzf sdr_rml23_live_board_package_iq_rf_loopback_fix9r1.tar.gz
cd sdr_rml23_live_board_package_iq_rf_loopback_fix9r1

# 1. 生成 46 样本精确基线（在 frozen-dir 有 route_d2_rf_manifest.tsv 的机器上）
python3 -I scripts/build_route_f_fix9r_exact_baseline.py \
    --d2-manifest <frozen>/route_d2_rf_manifest.tsv \
    --out route_f_fix9r_exact_baseline.tsv --expect-holdout 46

# 2. 板端 23 类逐文件恢复准确率（同机 Pluto，RF 直连）
./run_gate9_rml23.sh --phase=iq-rf-loopback-23class-fix9r \
    --input-kind=radioml-d2-2p56m --frozen-dir=<frozen> \
    --baseline=route_f_fix9r_exact_baseline.tsv \
    --center=2400000000 --rx-gain=10 --tx-atten=-40 --rf-path=direct-cable
```

预期输出 token：`ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`（correct/46 明显高于 fix9 的 5/46）。
接受门（46 样本）：`training_estimate_valid=46/46`、`rf_valid=46/46`、`rf_excluded=0`、`prediction_agreement>=0.90`、`rf_accuracy>=exact_baseline_accuracy−5pp`、4ASK 不退化到 0%、无 TX/RX 削顶、`restore_result=PASS`；否则 `_REGRESSION_FAIL`。

## 10. 工件

- patch `dist/sdr_rml23_live_iq_rf_loopback_fix9r1_patch.tar.gz`（SHA 见交付清单）
- full `dist/sdr_rml23_live_board_package_iq_rf_loopback_fix9r1.tar.gz`（SHA 见交付清单）
- 交付清单 `dist/RML23_IQ_RF_LOOPBACK_FIX9R1_DELIVERY.txt`（含最终 SHA + 完整板端命令）

历史包（fix7/fix8/fix9/fix9r 及之前所有包）**未被覆盖**，fix9r 旧包 SHA 保持不变。
