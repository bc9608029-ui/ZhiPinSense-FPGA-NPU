# M29 RML23 Stage H-E / Route E — fix3 审计：数字回环 ~20 dB 幅度损失定位与修复

状态：**M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST**（最高允许状态不变）。
本轮未碰板、未训练；未写任何 `*_PASS / PROJECT_COMPLETE / FINAL_*`；未把
`DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / RF_LEAKAGE_NOT_PROVEN` 改 PROVEN；
未把 `arbitrary_modulated_iq_fidelity` 改 PROVEN（仍 `BOARD_REQUIRED`）；
未写 `capture_ok=1` 或 program RC=0 作为回环保真 PASS。

---

## 1. 板端证据（fix2 之后，全部来自用户真实上板，逐字引用）

1. fix2 的四文件 TX SHA/非零率校验**通过**：TX 内容与冻结文件一致、非零。
2. 但 RX 幅度异常低：`rms_tx≈9.52 counts`（logical），`rms_rx` 仅 **0.728～0.848 counts**；
   RX 样本主要为 0/±1/±2；四文件全部 `RX_LOW_AMPLITUDE`。
3. `corr=0～0.389`，分类 **1/8**；-89.75 dB 与 -40 dB 结果相近（提升衰减无改善）。
4. fix2 总 gate **正确 FAIL**（fidelity 未达 PRESERVES_IQ，绝不 PASS）。
5. 约 16×（≈24 dB）的幅度损失：`rms_tx≈9.52` 与 `rms_rx≈0.8` 之比 ≈ 11.9×≈21.5 dB。

问题：fix2 能证明“TX 数据正确装载且逐文件校验”，却无法区分 RX 低幅的**来源**——
是 libiio convert 语义错、12-bit shift 对齐错、HDL 接口位对齐错，还是数字回环
本身存在一个与电平无关的固定增益。fix3 的职责是把这四者用可判责的仪表分开，
并给出**不是经验倍数**的修复。

---

## 2. 判责仪表：raw 容器 vs logical 值（gain 双通道判别）

关键判别量（对每个 sweep 电平）：

- `tx_raw_rms` = `Device::tx_raw_after_inverse()` 输出（convert_inverse 后写入 DMA 的
  **原始 16-bit 容器字节**）的 RMS；
- `rx_raw_rms` = `Device::read_rx_raw()`（DMA 读出的**原始容器字节**）的 RMS；
- `rx_logical_rms` = host 镜像 `format_convert_raw_to_host()` 对 rx raw 解码后的 logical RMS；
- `raw_gain_db` = 20·log10(rx_raw_rms / tx_raw_rms)；
- `gain_db`   = 20·log10(rx_logical_rms / tx_logical_rms)。

判责规则（`classify_root_cause`，阈值 `kGainPreservedDb=3.0`）：

| 条件 | 结论 token |
|---|---|
| 任一电平 `convert_diverged`（libiio convert_inverse 与 host 镜像输出逐字节不同） | `DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS` |
| \|raw_gain\|<3 dB 且 \|gain\|<3 dB | `DIGITAL_LOOPBACK_UNITY`（损失不在此回环） |
| \|raw_gain\|<3 dB 且 \|gain\|≥3 dB | `DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT`（raw 容器保真、logical 丢失 → 12-bit 值落在错误的容器位） |
| \|raw_gain\|≥3 dB 且 \|raw_gain−gain\|<3 dB | `DIGITAL_LOOPBACK_FIXED_ATTENUATION`（raw 与 logical 同步丢失 → 电平无关的固定回环增益） |
| 其余 | `DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN` |

判责仪表只**定位**损失来源；无论结果如何，`DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN`
不因 host 测试改 PROVEN。

---

## 3. fix3 九条要求 → 实现位置

| # | 要求 | 实现 |
|---|---|---|
| 1 | 审计 libiio TX/RX channel data format（length/bits/shift/is_signed/is_be）并板端打印实际值 | `run_iq_digital_loopback_sweep`：`IQ_DIGITAL_LOOPBACK_SWEEP_FORMAT dir=tx\|rx <describe_data_format> roundtrip_identity=0\|1`；`describe_data_format` 输出 `16b/12b shift+N signed/unsigned … LE/BE repeat=N`；roundtrip 由 `format_roundtrip_identity` 判 |
| 2 | 确定性 tone/ramp/PRBS，logical RMS 8/16/32/64/128/256/512 counts 数字回环幅度扫描 | `iq_digital_loopback_sweep.hpp`：`kSweepLevels[]`×`kSweepKinds[]`，`make_sweep_waveform`（确定性 LCG）+`scale_to_rms`，`sweep_all_levels` 逐档跑 |
| 3 | 每档报告 TX logical、convert_inverse 后原始容器字节、RX 原始容器字节、convert 后 logical、增益 dB、相关系数、削顶率 | `IQ_DIGITAL_LOOPBACK_SWEEP_LEVEL`：`kind/target_rms/tx_logical_rms/tx_raw_rms/rx_raw_rms/rx_logical_rms/gain_db/raw_gain_db/corr/tx_clip/rx_clip/rx_raw_clip/clip_rate/convert_diverged/capture_ok` |
| 4 | 判断损失来自 convert 语义 / 12-bit shift / HDL 位对齐 / 固定增益 | §2 判别 + `IQ_DIGITAL_LOOPBACK_SWEEP_ROOT_CAUSE token= reason=` |
| 5 | 格式错误则修正确格式，**不得经验倍数掩盖** | `find_correct_rx_shift` 在 shift 0..15 搜使 gain≈0 且 corr 最大的 shift，输出 `SHIFT_CORRECTION`+`--rx-format-shift=N`；板端经 `set_rx_data_format_override` 切换为 host 镜像转换（见 §4） |
| 6 | 固定增益则新增 `--digital-loopback-tx-scale`（仅测试夹具），记录缩放前后 SHA/scale/clip count，不改生产预处理语义 | `transfer_one_file(..., tx_scale)`：**冻结 SHA 校验之后**才 `llround(v*scale)` 并 clamp，记录 `tx_sha_pre_scale/tx_sha_post_scale/tx_clip_pre_scale/tx_clip_post_scale/tx_rms_pre_scale/tx_rms_post_scale`；runner 打印 `IQ_DIGITAL_LOOPBACK_TX_SCALE` |
| 7 | 自动选 RX rms∈[16,128] counts 且零削顶的安全档，重跑 4 类 | `auto_select_scale`：scale=64/(G·frozen_rms)，输出 `IQ_DIGITAL_LOOPBACK_SWEEP_SCALE_SELECTION` |
| 8 | fidelity 未达 PRESERVES_IQ 前不得跑 24 类或声明分类失败 | fix2 req 6 的门折叠保持不变（每文件 fidelity 非 `PRESERVES_IQ` 即总 gate FAIL）；fix3 sweep 仅判责，不触分类 |
| 9 | tx_atten 安全上限 -40 dB；不改模型/标签/预处理/RTL/位流/Flash | `pluto::PlutoTx::prepare()` `kSafeTxCeilingDb=-40.0` 不变；§5 文件差异仅 .cpp/.hpp/.sh/.py/.md |

---

## 4. 核心新代码与关键修复

### 4.1 `format_convert_host_to_raw` 符号扩展修复（host 镜像正确性）

旧实现对右对齐（shift<4）的负值产生“无符号 12-bit 模式”（例：shift=0 时 −64 → 4032），
破坏了 host 伪回环增益模型的符号。修复为在左移**之前**先把 `bits` 宽的值符号扩展到
16-bit 容器（见 `pluto_device.hpp::format_convert_host_to_raw`）。

**关键安全性**：对真实 AD9364 的 `shift=4`，旧/新实现**逐字节一致**（12-bit 符号位恰好落
在 bit 15），故此修复对真实板的实际转换是 no-op；它只修正 host 镜像，使
(a) host 伪回环测试、 (b) sweep 的 `convert_diverged` 判别（libiio vs host 镜像）在非 4
的 shift 上符号正确。**不改变生产预处理语义、不改变板端数据路径。**

### 4.2 格式覆盖（req 5 的板端落地，无需重编译）

`Device::set_rx_data_format_override / set_tx_data_format_override` 在真实
`LibiioDevice` 上被实现为：设置后 TX/RX convert 路径**切换**为用覆盖格式的 host 镜像
（`format_convert_host_to_raw` / `format_convert_raw_to_host`），未设置时仍走 libiio
`iio_channel_convert_inverse` / `iio_channel_convert` 原路径。sweep 在板端找到正确 shift
后，runner 用 `--rx-format-shift=N` 覆盖 RX 解码格式，重跑 4 类 fidelity 门验证。

### 4.3 sweep 仪表（`iq_digital_loopback_sweep.hpp`，NEW）

`SweepConfig`（kinds/levels/discard/delay-margin）→ `sweep_all_levels` → `SweepReport`
（tx/rx_fmt、levels[]、cause、rx_shift、scale_sel）。每电平：
`read_rx_raw(discard)` stale-flush → `tx_raw_after_inverse` 算 tx_raw → `read_rx_raw`
抓 rx_raw → host 镜像算 rx_logical → 相关性/削顶/convert 一致性 → 累积判别量。

### 4.4 runner 新 CLI

`--phase=iq-digital-loopback-sweep`（`gate9_phase.hpp::valid_phase` 新增）；runner 新增
`--digital-loopback-tx-scale`、`--rx-format-shift/--tx-format-shift`（0..15）、
`--rx-bits/--tx-bits`（0..16，0=沿用报告值），全部经 `board_common.hpp::opt_i64/opt_d`
fail-closed 解析。

---

## 5. 文件差异证明（fix3 vs fix2 全量 c841cee4…，全量递归）

模型 / 标签 / golden / 预处理契约 / RTL / XDC / 位流 / Flash 全部未变化。

新增（5）:
- `board_package/iq_digital_loopback_sweep.hpp`   —— 幅度扫描仪表 + 判责 + shift 校正 + scale 选择
- `host_tests/test_iq_digital_loopback_sweep.cpp` —— 波形/format/unity/fixed/misalignment/fallback/scale/shift 8 测试
- `scripts/analyze_iq_digital_loopback_sweep.py`   —— 独立重推判责（raw vs logical 双通道）+ 交叉核对
- `scripts/package_iq_digital_loopback_fix3.py`    —— fix3 打包器 + 依赖闭包审计
- `docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX3_AUDIT.md`（本文件）

修改（9）:
- `sdr_adapter/pluto_device.hpp`                  —— `format_convert_host_to_raw` 符号扩展；Device 抽象 `set_tx/rx_data_format_override`/`has_*_override`/`tx_raw_after_inverse`/`read_rx_raw`；FakePlutoDevice `loopback_raw_gain_/loopback_raw_shift_` + `tx/rx_fmt_effective`
- `sdr_adapter/pluto_device_libiio.cpp`           —— 真实设备 format override 切换路径 + `tx_raw_after_inverse` 干跑
- `board_package/board_gate9_full_chain_rml23.cpp` —— `run_iq_digital_loopback_sweep`（证据打印 + gate 折叠）
- `board_package/gate9_phase.hpp`                 —— `valid_phase` 新增 `iq-digital-loopback-sweep`
- `board_package/iq_digital_loopback_runner.hpp`  —— `--digital-loopback-tx-scale/--rx-format-shift/--tx-format-shift/--rx-bits/--tx-bits` + format 审计/覆盖应用 + `IQ_DIGITAL_LOOPBACK_TX_SCALE` 证据
- `board_package/iq_digital_loopback_transfer.hpp` —— `transfer_one_file(..., tx_scale)` + 缩放前后 SHA/clip/RMS 证据
- `board_package/board_common.hpp`                —— `opt_i64`（fail-closed 有符号解析）
- `host_tests/build_host_tests.sh`                —— +`test_iq_digital_loopback_sweep` 目标
- `host_tests/run_tests.sh`                       —— +运行 sweep 测试

（工作树中另有 `scripts/compare_three_backends.py`、`scripts/analyze_live_rx_capture.py`、
`docs/M29_RML23_LIVE_RX_DIAGNOSTIC_ERRATA_39e5_AUDIT.md` 三份相对 fix2 基线的改动，
属更早的“三后端判责”修复，**不属 fix3，不进入本包**——与 fix2 审计 §5 同一说明。）

---

## 6. 离线验证（从解包目录执行，未碰板）

1. `test_iq_digital_loopback_sweep`：**50/0**。
2. host 全套件 `run_tests.sh`：**ALL HOST TESTS PASSED**（exit 0）——
   含间接依赖 `format_convert_host_to_raw` 的 `test_iq_digital_loopback`、
   `test_iq_digital_loopback_sequence`、`test_route_e_raw_rx_output_fields` 全部无回归。
3. `host_tests/syntax_check.sh`：`gate9_rml23: syntax OK`（gate7/gate9/gate10 亦 OK）。
4. analyzer 独立重推交叉核对：合成 FORMAT_MISALIGNMENT / FIXED_ATTENUATION 两场景
   `root_cause_match=True`，UNITY / NOT_PROVEN 分支按同一阈值实现。
5. fix3 打包器依赖闭包审计 fail-closed：fix3 C/C++ 文件的传递 `#include` 闭包内，
   凡与 fix2 基线逐字节不同、或基线缺失却不在 `ROUTE_E_FIX3_FILES` 的头，立即终止打包。
6. 独立解包 `sha256sum -c` 校验通过（见交付说明的最终 SHA/文件数）。

host 自洽全绿 ≠ 板端判定；回环保真与 RF 泄漏只能由用户上板观测（我禁碰板、禁训练）。

---

## 7. 板端复测建议（用户执行，判决填 verdict 模板）

第一步，跑判责仪表（**唯一能区分四类损失来源**的步骤）：

```
run_gate9_rml23.sh --phase=iq-digital-loopback-sweep \
    --uri=ip:192.168.2.1 --center=2400000000 --rx-gain=10 --tx-atten=-40 \
    --frozen-dir DIR --input-kind=<generated-2p56m|radioml-reconstructed-2p56m> \
    --sweep-kinds=tone,ramp,prbs --sweep-levels=8,16,32,64,128,256,512
```

host 独立复核（**独立重推判责**，与板端 token 交叉核对）：

```
python -I scripts/analyze_iq_digital_loopback_sweep.py --log <sweep stdout> --json out_sweep.json
```

第二步，按 `IQ_DIGITAL_LOOPBACK_SWEEP_ROOT_CAUSE` 行事：

- `DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT` → 按 `SHIFT_CORRECTION`/`RECOMMENDATION` 用
  `--rx-format-shift=N` 重跑 4 类 fidelity 门；
- `DIGITAL_LOOPBACK_FIXED_ATTENUATION` → 按 `SCALE_SELECTION` 用
  `--digital-loopback-tx-scale=S` 重跑（观察 `IQ_DIGITAL_LOOPBACK_TX_SCALE` 的缩放前后
  SHA/scale/clip count）；
- `DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS` / `UNITY` / `NOT_PROVEN` → 停止判责，另行报告。

```
run_gate9_rml23.sh --phase=iq-digital-loopback --input-kind=<kind> --frozen-dir DIR \
    --file-order=manifest --file-repeat=1 [--rx-format-shift=N | --digital-loopback-tx-scale=S]
```

观测关键新增行：`IQ_DIGITAL_LOOPBACK_SWEEP_FORMAT`（req 1）、
`IQ_DIGITAL_LOOPBACK_SWEEP_LEVEL`（req 2/3，7×3 档）、
`IQ_DIGITAL_LOOPBACK_SWEEP_ROOT_CAUSE`（req 4）、
`IQ_DIGITAL_LOOPBACK_SWEEP_SHIFT_CORRECTION` / `--rx-format-shift`（req 5）、
`IQ_DIGITAL_LOOPBACK_TX_SCALE`（req 6）、
`IQ_DIGITAL_LOOPBACK_SWEEP_SCALE_SELECTION`（req 7）。

红线：fidelity 未达 `PRESERVES_IQ` 前**不得**跑 24 类或声明分类失败（req 8）；
tx_atten 上限 -40 dB 不变（req 9）；sweep 的 `result=PASS` 只表示“判责成功且参数恢复”，
**不是回环保真 PASS**，`loopback_capability=DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN` 保持。
