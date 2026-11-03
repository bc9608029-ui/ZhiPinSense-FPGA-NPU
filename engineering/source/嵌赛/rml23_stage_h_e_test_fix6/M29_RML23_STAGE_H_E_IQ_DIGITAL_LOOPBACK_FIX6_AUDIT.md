# M29 RML23 Stage H-E / Route E — IQ 数字回环 fix6 审计

> 状态：`M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST`
> 基线：fix5 全量 `sdr_rml23_live_board_package_iq_digital_loopback_fix5.tar.gz`
> `8239285c91aa0e75c2c2483ec5a010d043bf2301fdd825d573240b40733dcb57`
> 本轮不碰板，由用户执行板端验收。不改模型/标签/正式预处理/RTL/XDC/位流/Flash。

---

## §1 证据（为什么需要 fix6）

fix5 建立了全周期 FFT 循环互相关同步与尺度无关保真判定，但遗留两类缺陷：

1. **保真与循环起点混为一谈**：`fidelity_verdict_fix5` 把 `peak_ratio < 2`（多峰）
   直接判为 `CIRCULAR_SYNC_AMBIGUOUS`。对一个**纯音/周期重复**的干净回环，其 TX
   自身循环自相关是平坦的（`r_norm[k]≈1`），交叉相关在所有循环移位上都是 ~1.0 的
   等价峰——这是「同一个波形在多个等价标注起点下」，**不是波形失真**。fix5 会把它
   错判为模糊，从而拦掉本应 `PRESERVES_IQ` 的干净回环。
2. **分类窗口跨零保护区/循环边界**：radioml 的 `quant_file` = 53760 复数 =
   20×(1024 + 2×832 保护)。Route E 朴素地每文件切 2 帧，其中一帧可能跨越零保护区
   或循环边界；Route D 的 `recovered_file`（`roundtrip_manifest.tsv` 第 9 列）已经
   持有**正确对齐的 [2,1024] 张量**，但没有被用来选窗口。

## §2 根因

- 固定 `peak_ratio >= 2` 门把「自相似产生的等价多峰」与「真·不同波形的竞争峰」混为
  一谈，无法表达「多个等价起点」这一客观现象。
- 朴素双帧切窗忽略原始 RadioML 1024 点有效区在 20 倍插值+保护段内的真实位置。

## §3 要求 → 实现对照（fix6 八项要求）

| # | 要求 | 实现位置 |
|---|------|----------|
| 1 | 保真 / 循环起点拆成两个独立结论 | `iqdloop_sync::SyncOrigin` 枚举 + `fidelity_verdict_fix6`（`iq_digital_loopback_sync.hpp`） |
| 2 | 不再用固定 `peak_ratio>=2` 作 PRESERVES_IQ 必要条件 | `kPeakRatioMin` 降级为诊断；`fidelity_verdict_fix6` 不再引用 peak_ratio |
| 3 | 计算 TX 自身循环自相关解释固有旁峰 | `circular_autocorr_norm()` + `circular_sync` 内 `r_tx = circular_cross_corr(txv,txv)` |
| 4 | 最佳对齐 corr≥0.9 + normalized_residual 一致 + 无削顶 + DMA SHA 正确 → PRESERVES_IQ | `fidelity_verdict_fix6`（DMA SHA 门在 runner 的 transfer 层） |
| 5 | 多个等价循环起点单独报 `sync_origin=AMBIGUOUS_EQUIVALENT`，不判失真 | `SyncOrigin::Equivalent` + `sync_origin_name` + `fidelity_verdict_fix6` 不因 Equivalent 拦 |
| 6 | 仅当多候选产生**不同波形**且无法确定最佳对齐才 `CIRCULAR_SYNC_AMBIGUOUS` | `origin==Ambiguous`（`unexplained_peaks>0`）才拦 |
| 7 | 依据原始 RadioML 1024 有效区选窗口，与 Route D tensor SHA/数值逐帧比对 | `FrozenIq::has_recovered_ref` + `load_recovered_tensor` + `select_classification_window`（`iq_digital_loopback.hpp`）+ runner 分类分支 |
| 8 | 不改模型/预处理/RTL/位流/增益 | 全部改动限于 Stage H-E 判责仪表 + host 测试 + 打包/文档 |

## §4 核心代码

### 4.1 `iq_digital_loopback_sync.hpp`
- 新增 `circular_autocorr_norm(tx)`：`r_norm[k]=|Σ tx[j]·conj(tx[(j-k) mod P])|/Σ|tx|²`。
- 新增 `enum class SyncOrigin { Unique, Equivalent, Ambiguous }` 与 `sync_origin_name()`
  （`UNIQUE / AMBIGUOUS_EQUIVALENT / CIRCULAR_SYNC_AMBIGUOUS`）。
- `CircularSyncResult` 增：`tx_autocorr_second / competing_peaks / equivalent_peaks /
  unexplained_peaks / best_unexplained_corr / origin`。
- `circular_sync` 末尾分类竞争峰：对每个 `corr_k >= kCompetingRatio(0.9)·peak_corr`
  的峰，`delta=(k-best) mod P`，`predicted = peak_corr·r_tx[delta]/r0`；若
  `corr_k > predicted + kPeakExplainAbsMargin(0.1)` → unexplained，否则 equivalent。
  `origin = unexplained>0 ? Ambiguous : competing>0 ? Equivalent : Unique`。
- `fidelity_verdict_fix6` 严格顺序：
  `INSUFFICIENT_EVIDENCE → CAPTURE_TOO_SHORT → RX_ALL_ZERO → RX_LOW_AMPLITUDE →
   CIRCULAR_SYNC_AMBIGUOUS(origin==Ambiguous) → DISTORTS_IQ(corr<0.9) →
   PRESERVES_IQ(corr≥0.9 ∧ !clipped ∧ normalized_gain_ok ∧ nmse_evm_consistent) →
   NOT_PROVEN`。**无 peak_ratio 依赖**。
- `fidelity_gate_ok_fix6(verdict) == "DIGITAL_LOOPBACK_PRESERVES_IQ"`。

### 4.2 `iq_digital_loopback.hpp`
- `FrozenIq` 增 `has_recovered_ref / recovered_tensor_file / recovered_tensor_path /
  recovered_tensor_sha256`。
- `load_radioml_sidecar` 读 `f[9]=recovered_file`，安全校验后 `sha256_of_file` 校验
  8192 字节（`chain::kTensorBytes`），`has_recovered_ref=true`（fail-closed）。
- 新增 `load_recovered_tensor(path, expect_sha)`：读 8192 字节 + SHA 校验 fail-closed。
- 新增 `ClassificationWindow` 与 `select_classification_window(recovered_stream,
  ref_tensor)`：在 `[0,total-N]` 内按 |相关| 搜索最佳整数延迟 `delay_offset`，最优
  LS 复增益 `g`，尺度无关 `tensor_nmse=err/ey`（分母=对齐窗口能量），`tensor_corr`，
  `aligned_sha256/ref_sha256/sha_equal`。

### 4.3 `iq_digital_loopback_runner.hpp`
- `fidelity_verdict_fix5/gate_ok_fix5` → `fix6`。
- 新增 `IQ_DIGITAL_LOOPBACK_SYNC_ORIGIN` 行：`sync_origin / tx_autocorr_second /
  competing_peaks / equivalent_peaks / unexplained_peaks / best_unexplained_corr`。
- 分类分支：`fz.has_recovered_ref` 时 `load_recovered_tensor` + `select_classification_window`
  + 打印 `IQ_DIGITAL_LOOPBACK_WINDOW` + 只分类**一个**对齐窗口；否则（generated 路径）
  逐帧分类朴素张量。

## §5 文件差异（相对 fix5 全量 `8239285c…` 基线）

5 改 + 2 新，**无模型/标签/正式预处理/RTL/XDC/位流/Flash**：

| 文件 | 类型 |
|------|------|
| `board_package/iq_digital_loopback_sync.hpp` | 改 |
| `board_package/iq_digital_loopback.hpp` | 改 |
| `board_package/iq_digital_loopback_runner.hpp` | 改 |
| `host_tests/test_iq_digital_loopback_sync.cpp` | 改 |
| `host_tests/test_iq_digital_loopback.cpp` | 改 |
| `scripts/package_iq_digital_loopback_fix6.py` | 新 |
| `docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX6_AUDIT.md` | 新 |

`iq_digital_loopback_transfer.hpp` / `pluto_device.hpp` / `pluto_device_libiio.cpp` /
`build_host_tests.sh` / `run_tests.sh` 及更早文件**逐字节一致**（依赖闭包审计覆盖）。

## §6 离线验证（本轮，不碰板）

- `host_tests/build_host_tests.sh`：全量编译 OK（`-Wall -Wextra -Werror`，g++ 15.2.0）。
- `host_tests/run_tests.sh`：**ALL HOST TESTS PASSED**。关键计数：
  - `test_iq_digital_loopback_sync` **75/0**（新增 `test_circular_autocorr_norm`、
    `test_tone_equivalent_origins`(→AMBIGUOUS_EQUIVALENT+PRESERVES_IQ)、
    `test_prbs_unique_peak`(origin==Unique)、`test_periodic_equivalent_origins`、
    `test_unexplained_competing_peak_ambiguous`(TX=[A,C]/RX=[A,A]→CIRCULAR_SYNC_AMBIGUOUS)、
    `test_classification_window_selection`(delay_offset=700 + sha_equal true/false)）。
  - `test_iq_digital_loopback` **117/0**（radioml sidecar 含 `recovered_file` +
    `has_recovered_ref` + recovered tensor SHA）。
  - `test_iq_digital_loopback_sequence` 158/0、`test_iq_digital_loopback_sweep` 92/0、
    `test_route_e_raw_rx_output_fields` 12/0，无回归。
- `host_tests/syntax_check.sh`：`gate9_rml23: syntax OK`。
- 打包器 `audit_dependency_closure` fail-closed；两份 tarball 独立解包 `sha256sum -c`
  全 OK；两次打包 SHA 一致（确定性）。

## §7 板端复测（用户执行；不写死 ip；RC=0 ≠ 回环保真 PASS）

```
# 判责 + 窗口观测（不变 4 类，先看 sync_origin 与 window）
./scripts/run_gate9_rml23.sh --phase=iq-digital-loopback --center=2400000000 \
  --rx-gain=10 --tx-atten=-40 --frozen-dir=DIR \
  --input-kind=radioml-reconstructed-2p56m > /root/rml23_route_e_fix6.log 2>&1
```

预期新增观测：
- 纯音/周期类目标文件 `IQ_DIGITAL_LOOPBACK_SYNC_ORIGIN ... sync_origin=AMBIGUOUS_EQUIVALENT`
  且 fidelity 仍 `DIGITAL_LOOPBACK_PRESERVES_IQ`（不再是 fix5 的 CIRCULAR_SYNC_AMBIGUOUS）；
- PRBS/非周期目标 `sync_origin=UNIQUE`；
- 仅当存在真·不同波形竞争峰才 `sync_origin=CIRCULAR_SYNC_AMBIGUOUS` 且 fidelity 判
  `CIRCULAR_SYNC_AMBIGUOUS`；
- `IQ_DIGITAL_LOOPBACK_WINDOW` 有 `delay_offset/tensor_corr/tensor_nmse/sha_equal`，
  `sha_equal=1` 仅当位精确回环（否则为 0，但 `tensor_corr` 仍应≈1）；
- 仍不把 sweep PASS / capture_ok=1 / program RC=0 写成回环保真 PASS；
  `DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / RF_LEAKAGE_NOT_PROVEN` 不因 host 测试改 PROVEN。

## 红线（保持）

不改模型/标签/正式预处理/RTL/XDC/位流/Flash；不调整 rec-scale/RX gain/TX attenuation
来掩盖同步问题；`tx_atten` 安全上限 -40 dB 不变；`loopback=1`；不碰真实 RF 发射；
不覆盖 fix5 及更早历史包；状态保持 `M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST`；
不写任何 `*_PASS / PROJECT_COMPLETE / FINAL_* / BOARD_TEST_PASS`。
