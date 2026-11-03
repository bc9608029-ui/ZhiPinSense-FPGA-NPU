# 多频点发射准备与验证 — 交接（唯一入口）

状态：**OFFLINE_TX_PREP_VERIFIED_RF_PENDING**（纯离线验证通过，真实 RF 待用户设备测试）。
不是 RF_TX_VALIDATED，不得据此宣称巡扫/模型/接收链验收通过。

## 一、本任务做了什么 / 没做什么

做了：
- 冻结了 TX 发射源闭包（6 个 SHA）+ 四场景波形（4 个 SHA）。
- 纯数字验证 19/19 通过：频率轴、移频符号、占用带宽、双路可分、载荷对照、量化、镜像、guard、wrap。
- 参数化 TX 程序（默认 dry-run，`--transmit` 才碰设备）+ 离线反例测试 17/17。

没做（红线保持）：
- 不自动发射、不扫描后自动挑设备；`--transmit` 强制显式 `--tx-uri`。
- 不改接收模式 / 模型 / 公共帧 / two-DC / FPGA 位流；历史脚本 `two_target_tx.py` 原样保留。
- 不用模拟测试冒充真实 RF；本交付的「镜像抑制 -28 dBc」等是纯数字结论，真实谱纯度待板测。

## 二、目录与文件

```
F:\嵌赛\rml24_multifreq_tx_validation_20261029\
  HANDOFF_MULTIFREQUENCY_TX.md      <- 本文件（唯一入口）
  CONTRACT.json                     <- 源身份/频点/幅度/阶段/冻结阈值
  scripts/tx_common.py              <- 冻结合同模块（常量 + build_frame/resample_shift/int16 规则）
  scripts/verify_tx_offline.py      <- 纯数字验证（19/19）
  scripts/multifreq_tx.py           <- 参数化 TX 程序（dry-run 默认）
  scripts/selftest_tx.py            <- 离线反例测试（17/17，含 mock 设备）
  scripts/package_tx.py             <- 打包 + 独立解包核验
  results/verify_offline/           <- 四场景 .c16 + verification_report.json + verdict.json + psd_dual.png
  results/tx_dryrun/                <- 四场景最终设备 .i16 + dry_run_report.json
  docs/BOARDTEST_MULTIFREQUENCY_TX.md <- 板端短测手册 + 结果表模板
  dist/                             <- 最终压缩包 + SHA256SUMS + 包外 SHA
```

## 三、冻结 SHA 一览

源闭包（详见 CONTRACT.json）：
| 对象 | SHA（前 16） |
|---|---|
| ui_interactive_tx.py | c04795d6993e426a |
| pilot_recovery.py | d7538a1e27b65cd6 |
| pluto_link_probe.py | 1b248f8f39197651 |
| selftest_manifest_240.json | 272980e9ca942bf3 |
| 03_02.bin（A，类3） | 1562575bbedd6e81 |
| 09_09.bin（B，类9） | 465def280290eafb |

四场景波形（float complex128 `.c16`，与 verify 输出一致）：
| 场景 | SHA（前 16） |
|---|---|
| a_only | 5d11ab8a61a3ed51 |
| b_only | 144a9a0b30c8fd24 |
| both | 3226f4d5a1039094 |
| silence | 30e14955ebf13522 |

## 四、复现命令（离线，纯数字，无 SDR）

```bash
python=/d/Anaconda/python   # 3.13.5, numpy 2.1.3, scipy 1.16.3

cd /f/嵌赛/rml24_multifreq_tx_validation_20261029

# 1) 纯数字验证（19/19）
$python scripts/verify_tx_offline.py \
  --manifest F:/嵌赛/rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json \
  --dataset  F:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset \
  --out results/verify_offline \
  --ui-tx F:/scan_exec_20261027/ui_interactive_tx.py \
  --pilot F:/AMR_Rescue_20261025/pilot_recovery.py \
  --link  F:/AMR_Rescue_20261025/pluto_link_probe.py

# 2) TX 程序 dry-run（默认，不发射；写四场景 .i16）
$python scripts/multifreq_tx.py \
  --manifest F:/嵌赛/rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json \
  --dataset  F:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset \
  --out results/tx_dryrun

# 3) 离线反例测试（17/17，含 mock 设备）
$python scripts/selftest_tx.py
```

## 五、TX 程序参数与默认值

- `--manifest` / `--dataset` / `--out`：必填。
- `--class-a 3` `--class-b 9`：默认类别。
- `--phases silence,a_only,b_only,both,a_only,silence`：阶段序列。
- `--phase-seconds 10`：每阶段秒数。
- `--dry-run`（默认）：只构建+落盘，不发射。
- `--transmit`：真实发射；此时**必须** `--tx-uri`（显式 URI，如 `usb:1.12.5`）与 `--link`（pluto_link_probe.py 路径）。
- `--stop-file`：可选停止文件，存在即提前结束阶段循环。

行为契约（不可省略）：
1. 枚举 USB，`--tx-uri` 不在其中 → 停止（不自动挑设备）。
2. 设置 TX LO/Fs/BW/增益后逐项读回，任一不符 → 停止，不发射。
3. 每阶段写真实事件 `prepared/start_requested/active/stop/restore`（wall-clock + monotonic 时间、波形 SHA、URI、配置读回）。`rf_started` 不当作运行状态。
4. 清理：先销毁发送缓冲，再恢复属性并逐项读回；恢复失败记录并返回非 0 退出码，不以 0 掩盖。

## 六、设备短测顺序（由用户执行，见 BOARDTEST 手册）

静默 → A-only → B-only → both → 撤去B(→A-only) → 静默；短相位；真实频谱/原始 IQ 取证；已知 `±2.56 MHz` 别名与 `-28 dBc` 镜像须单独核对。详见 `docs/BOARDTEST_MULTIFREQUENCY_TX.md`。

## 七、最高允许状态边界

离线准备完成 = 来源闭包清楚 + 四场景可复现 + 最终量化检查通过 + 纯数字两路恢复通过 + 程序控制/清理反例通过 + 包独立核验通过 → **OFFLINE_TX_PREP_VERIFIED_RF_PENDING**。

可信双频点 RF 源 = 后续真实单路/双路对照及频谱/接收证据通过 + 真实停发恢复验证通过。**没有这些证据不得写 RF_TX_VALIDATED。**
