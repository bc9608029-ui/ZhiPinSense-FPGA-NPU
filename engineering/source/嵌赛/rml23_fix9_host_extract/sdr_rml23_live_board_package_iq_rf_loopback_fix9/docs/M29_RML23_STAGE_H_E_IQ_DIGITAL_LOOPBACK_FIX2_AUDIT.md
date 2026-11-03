# M29 RML23 Stage H-E / Route E — fix2 审计：TX/RX 数据传输与同步修复

状态：**M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST**（最高允许状态不变）。
本轮未碰板、未训练；未写任何 `*_PASS / PROJECT_COMPLETE / FINAL_*`；未把
`DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / RF_LEAKAGE_NOT_PROVEN` 改 PROVEN；
未把 `arbitrary_modulated_iq_fidelity` 改 PROVEN（仍 `BOARD_REQUIRED`）；
未写 `capture_ok=1` 或 program RC=0 作为回环保真 PASS。

---

## 1. 板端证据（fix1 之后，全部来自用户真实上板，逐字引用）

1. fix1 构建成功，Route E 全程跑通：sample rate RX/TX=2560000、loopback=1、
   参数恢复 PASS。
2. -89.75 dB：BPSK `rms_rx=0.774`、QPSK=0.573、4ASK/16QAM=0；全部 `corr=0`、
   `SYNC_OR_WRAP_INCONCLUSIVE`，分类 1/8。
3. -40 dB：BPSK `rms_rx=0.750 corr=0.105`；QPSK `rms_rx=0.687 corr=0.055`；
   4ASK/16QAM `rms_rx=0 corr=0`；分类仍 1/8。
4. 衰减再提高 49.75 dB → 结果基本不变 → 排除“TX 衰减过大”为主因。
5. TX 输入本身非零且一致：四份文件 `rms_tx≈9.52`、`tx_complex=53760`。
6. 红线：不得把 `capture_ok=1` 或 program RC=0 当作回环保真 PASS。

## 2. 根因诊断（据此形成 fix2 的 11 条硬要求）

fix1 只证明了“单份文件、单次 transfer”能跑通，但未对 **多文件之间** 的
TX/RX 缓冲区生命周期、TX 内容逐文件校验、RX stale-buffer flush、以及
“RX 全零/低幅/未同步/回绕失败”四种失败态做可证明的区分与判责。板端
`corr=0` 且 `4ASK/16QAM rms_rx=0` 提示：**可能不是信道保真问题，而是
上一份文件的 RX DMA 缓冲被静默复用（stale leak），或 TX 重新装载失败但
旧缓冲区仍在循环**。fix1 无逐文件 TX SHA 校验、无 refill 证据、无
buffer 生命周期计数，故无法把“状态泄漏”与“调制相关失真”分开。

---

## 3. fix2 修复（11 条要求 → 实现位置）

| # | 要求 | 实现 |
|---|---|---|
| 1 | 多文件间 cyclic TX buffer 创建/启动/停止/销毁/重新装载 | `iq_digital_loopback_transfer.hpp`：每文件新建 `pluto::PlutoTx`（RAII 每路径析构销毁），记录 `tx_create_delta/tx_destroy_delta/rx_create_delta/rx_destroy_delta`（`dev.tx_buffer_*_count()` 前后差值） |
| 2 | 每文件切换后确认 TX buffer 内容 SHA/非零与冻结文件一致 | `transfer_one_file` 在 cap 之前 `iqdloop::verify_loaded_tx(tx_iq, expect_sha)`（SHA 精确比对 + 非零证据）；SHA 不符/空波形 **throw fail-closed**；`IQ_DIGITAL_LOOPBACK_TX_VERIFY` 逐文件打印 |
| 3 | RX 启动前后可证明 stale-buffer flush + 记录 refill 非零率/RMS/首尾样本 | `transfer_one_file`：`dev.recreate_rx_buffer()` + 1 次 discard refill（`kDiscardComplex=4096`）+ 1 次 contiguous capture refill，每 refill 经 `iqdloop::measure_refill` 记录；`IQ_DIGITAL_LOOPBACK_REFILL` 逐 refill 打印 |
| 4 | 周期波形任意起点 + 环形回绕，相关搜索 circular alignment | `iqdloop::align_and_measure_int16`：delay 搜索 `[0,D)`，主延迟折回 `[0,N)`，LS 复增益，corr/corr_swap/corr_conj 三相关（fix1 已有，本轮保持并验证） |
| 5 | 区分 RX 全零/低幅/未同步/回绕失败，不得用 nmse=0/evm=0 表示全零成功 | `iqdloop::fidelity_verdict` 顺序：`INSUFFICIENT_EVIDENCE → RX_ALL_ZERO → RX_LOW_AMPLITUDE → SYNC_OR_WRAP_INCONCLUSIVE → PRESERVES_IQ → DISTORTS_IQ → NOT_PROVEN`；`rx_all_zero`（`rx_nonzero==0`）、`kRxLowAmplitudeCounts=2.0` 阈值 |
| 6 | fidelity fail 时总 GATE_RESULT 必须 FAIL/INCONCLUSIVE | `iq_digital_loopback_runner.hpp`：`rep.functional_pass = infra_ok && fidelity_ok;`，`fidelity_ok` 要求**每个文件** `fidelity_gate_ok`（仅 `DIGITAL_LOOPBACK_PRESERVES_IQ` 为 true）；analyzer 独立重推同一 fold |
| 7 | 单文件×4、四文件顺序、四文件逆序，判断“前两份有数据、后两份为零”状态泄漏 | 板端 `--file-order manifest|reverse`、`--file-repeat`、`--file-filter`；host `test_iq_digital_loopback_sequence.cpp` 三场景 + stale-leak 负向对照 |
| 8 | 安全上限 `tx_atten<=-40 dB`，不提高功率 | `pluto::PlutoTx::prepare()` 仍执行 `kSafeTxCeilingDb=-40.0` 上限 + 最大安全衰减读回；本轮不改 |
| 9 | 不改模型/标签/预处理/RTL/位流/Flash | 见 §5 文件差异：仅 .cpp/.hpp/.sh/.py/.md |
| 10 | host 测试 + 依赖闭包 + 板端编译包 + fix2 交付；回环保真由用户上板 | host 全套件全绿 + `package_iq_digital_loopback_fix2.py`（依赖闭包审计 fail-closed）+ 交付说明 |

## 4. 核心新代码：单一 transfer 路径（板端与 host 逐字共享）

`board_package/iq_digital_loopback_transfer.hpp::transfer_one_file()` 是板端 runner
与 host 序列测试 **逐字共享** 的同一份代码（runner `#include` 它，host 测试也
`#include` 它），保证 host 序列测试跑的就是板端将跑的确切 TX/RX 路径，不复制漂移。

顺序：`load_ci16 → verify_loaded_tx(SHA fail-closed) → 记录 buffer 计数 →
PlutoTx 构造 → prepare(-40dB 上限) → start_cyclic → recreate_rx_buffer(flush) →
discard refill → capture refill → 记录 refill 证据 → RAII 销毁 TX buffer →
buffer 计数差值`。

## 5. 文件差异证明（fix2 vs fix1 全量 3b925f3b…，全量递归）

模型 / 标签 / golden / 预处理契约 / RTL / XDC / 位流 / Flash 全部未变化。

新增（4）:
- `board_package/iq_digital_loopback_transfer.hpp`   —— 共享 transfer 路径 + `TransferResult`
- `host_tests/test_iq_digital_loopback_sequence.cpp` —— 单文件×4 / 顺序 / 逆序 / 负向对照
- `scripts/package_iq_digital_loopback_fix2.py`       —— fix2 打包器 + 依赖闭包审计
- `docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX2_AUDIT.md`（本文件）

修改（7）:
- `board_package/iq_digital_loopback.hpp`            —— `rx_all_zero` / `RX_ALL_ZERO` / `RX_LOW_AMPLITUDE` / `kRxLowAmplitudeCounts=2.0`
- `board_package/iq_digital_loopback_runner.hpp`     —— 改用 `transfer_one_file`；`--file-order/repeat/filter`；req 6 门折叠
- `sdr_adapter/pluto_device.hpp`                     —— `FakePlutoDevice` echo/stale 测试钩子（`echo_tx_on_rx`、`stale_rx_without_recreate`、`rx_recreated_since_tx_`）
- `host_tests/test_iq_digital_loopback.cpp`          —— `make_tx` 多音（偶+奇周期，破除反周期性）；+115 断言
- `host_tests/build_host_tests.sh`                   —— +`test_iq_digital_loopback_sequence` 目标
- `host_tests/run_tests.sh`                          —— +运行序列测试
- `scripts/analyze_iq_digital_loopback.py`           —— 解析 `TX_VERIFY/REFILL/BUFFER` 行 + 独立重推 `fidelity_gate`

（工作树中另有 `scripts/compare_three_backends.py`、`scripts/analyze_live_rx_capture.py`、
`docs/M29_RML23_LIVE_RX_DIAGNOSTIC_ERRATA_39e5_AUDIT.md` 三份相对 fix1 基线的改动，
属更早的“三后端判责”修复，**不属 fix2，不进入本包**。）

## 6. 离线验证（从解包目录执行，未碰板）

1. host 全套件 `run_tests.sh`：**ALL HOST TESTS PASSED**（exit 0）。
   - `test_iq_digital_loopback` **115/0**
   - `test_iq_digital_loopback_sequence` **158/0**
2. `host_tests/syntax_check.sh`（iCraft 3.39 头，`-fsyntax-only -Wall -Wextra -Werror`）
   对包内 `board_gate9_full_chain_rml23.cpp`：**gate9_rml23: syntax OK**（gate7/gate9/gate10 亦 OK）。
3. fix2 打包器依赖闭包审计 fail-closed：fix2 C/C++ 文件的传递 `#include` 闭包内，
   凡与 fix1 基线逐字节不同、或基线缺失却不在 `ROUTE_E_FIX2_FILES` 的头，立即终止打包。
4. 独立解包 `sha256sum -c` 校验通过（见交付说明的最终 SHA/文件数）。

host 自洽全绿 ≠ 板端判定；回环保真与 RF 泄漏只能由用户上板观测（我禁碰板、禁训练）。

## 7. 板端复测建议（用户执行，判决填 verdict 模板）

```
run_gate9_rml23.sh --phase=iq-digital-loopback --input-kind=generated-2p56m \
    --frozen-dir DIR --file-order=manifest --file-repeat=1
run_gate9_rml23.sh --phase=iq-digital-loopback --input-kind=radioml-reconstructed-2p56m \
    --frozen-dir DIR --file-order=manifest --file-repeat=1
# 状态泄漏诊断（req 7）：
run_gate9_rml23.sh --phase=iq-digital-loopback --input-kind=generated-2p56m \
    --frozen-dir DIR --file-order=reverse --file-repeat=1
run_gate9_rml23.sh --phase=iq-digital-loopback --input-kind=generated-2p56m \
    --frozen-dir DIR --file-order=manifest --file-repeat=4
```
随后 host 独立复核：
```
python -I scripts/analyze_iq_digital_loopback.py --log <producer stdout> \
    --frozen-dir DIR --input-kind <kind> --json out.json
```
观测关键新增行：`IQ_DIGITAL_LOOPBACK_TX_VERIFY`（req 2）、`IQ_DIGITAL_LOOPBACK_REFILL`
（req 3，discard/capture 两条）、`IQ_DIGITAL_LOOPBACK_BUFFER`（req 1，四个 delta）。
任一文件的 `fidelity` 令牌非 `DIGITAL_LOOPBACK_PRESERVES_IQ`，总 gate 必须 FAIL
（req 6），绝不能 result=PASS。
