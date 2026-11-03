# M29 RML23 Stage H/F — fix9r2d1 离线分析器热修（manifest 长名→短名映射 + 循环切片）

- 状态：**`M29-RML23-FIX9R2D1-ANALYZER-HOTFIX-READY`**
- 交付性质：**只修离线 Python 分析器**（`scripts/analyze_fix9r2d_capture.py`）。**不改**任何 C++、`iq_rf_sync_recovery.hpp`、TX/RX 路径、帧布局、同步算法、模型/标签/预处理、RF 门限、fix10、Phase 2 恢复算法。
- 基线：fix9r2d 全量包 `sdr_rml23_live_board_package_iq_rf_loopback_fix9r2d.tar.gz`（SHA `34a11a5c…`）。本热修**不重跑 R8**，直接复用板端已落盘的 16 个 `.f32` 波形 + 2 个 manifest（`route_f_fix9r2d_waveforms.tsv`、`route_f_fix9r2d_capture.tsv`）。

---

## 1. 为什么（两个离线分析器缺陷，均为 Python，非硬件）

fix9r2d 六判责离线分析器在**真实板端 manifest** 上无法运行，两个 bug 都在 `scripts/analyze_fix9r2d_capture.py`：

1. **manifest 长名 → 内部短名映射缺失（Task A）**：`load_all_waveforms` 用 `w[kind] = x` 以 manifest **长名**（如 `raw_cycle_0_full_frame`）为键存储波形，而 `analyze_one_capture` 读取的是**短名**（`w["cycle0"]`）→ 真实板端数据立即 `KeyError: 'cycle0'`。self-test 之所以没暴露：它直接以短名构造 dict、绕过 manifest 解析。
2. **普通切片静默截断（Task B）**：`analyze_one_capture` 用 `cycle0[circ:circ+TRAIN_LEN]` 等普通切片。当 `timing_offset` 使 `circ + …` 越过 `PERIOD=59904` 末尾时，普通切片会返回不足长（甚至空）而非循环回卷 → 周期内长度错误、corr 计算失真。

两个 bug 均在离线分析器，与板端恢复链无关；现有 16 波形与 2 个 manifest 完全有效，**无需重新上板采集**。

---

## 2. 变更（仅 `scripts/analyze_fix9r2d_capture.py` 一个源文件 + 一个新增测试 + 本文档 + SHA manifest）

### Task A — kind 映射（fail-closed）

- `load_all_waveforms(entries, label="")` 改为 `internal_key = KIND_MAP[kind]; w[internal_key] = x`，返回以 8 个**短名**为键的 dict。
- 加载后严格断言 8 个内部短名 `train_ref/train_rx/pay_rx/full/cycle0/cycle1/pay_ref/provisional` 齐全。
- 未知 kind → fail-closed；两个 kind 映射到同一内部 key → fail；缺失 key → fail。
- 错误信息**必含文件名**与缺失/重复/未知 kind；`analyze_one_capture` **永不接触 manifest 长名**。

### Task B — 循环切片

- 新增唯一公共函数 `circular_slice(x, start, length)`：`x` 必须为长度 `PERIOD` 的 1-D 复数向量；`start` 任意整数（可为负或 ≥ PERIOD，按 PERIOD 取模）；`0 < length ≤ PERIOD`；严格返回 `length` 个采样；任何异常立即抛错（**永不静默截断**）。
- `analyze_one_capture` 的 4 处普通切片改为 `circular_slice`，并在计算指标前再次断言 `len(cyc0_train)=len(cyc1_train)=1024`、`len(cyc0_pay)=len(cyc1_pay)=53760`。

### 新输出 token

- `FIX9R2D1_KIND_MAPPING result=PASS external_kinds=8 internal_keys=8`
- `FIX9R2D1_CIRCULAR_SLICE result=PASS training_lengths=1024,1024 payload_lengths=53760,53760`
- 成功路径补 `FIX9R2D_ACCEPTANCE result=PASS`（原 REJECTED fail-closed 不变：拒绝时退出码 2、无任何 verdict token、**不写 JSON**——避免伪造判责 JSON）。

---

## 3. 验证（Task E，全部离线，`python -I`；本机 `python`=Anaconda 3.13.5，无 `python3` 别名，故用 `python -I` 等价执行）

| 检查 | 结果 |
| --- | --- |
| `python -I scripts/test_fix9r2d1_analyzer_manifest.py` | **23/23 PASS** |
| `python -I scripts/analyze_fix9r2d_capture.py --self-test` | **7 判责用例 + acceptance-gate 6/6 = PASS** |
| `python -m py_compile scripts/analyze_fix9r2d_capture.py` | OK |
| 无 KeyError / 无警告 / 无静默截断 / 门限不变 | PASS |

23 项覆盖（18 项任务书点名 + 扩展）：真实 8 长 kind 映射、缺失 `raw_cycle_0_full_frame`、未知 kind、重复 internal key、错误长度、equality=0、complete=0、timing 中央/近尾/training 跨周期/payload 跨周期、负 start、start>周期、长度始终准确、两周期一致/不一致、原 7 self-test 无回归、全程无 KeyError；并含真实风险用例 `circ + PAYLOAD_START + PAYLOAD_LEN > PERIOD`（旧普通切片返回 `old=0`，`circular_slice` 返回完整 53760）。

端到端 CLI（真实临时 manifest + 16 个 `.f32` + `--out`）实测输出：

```
FIX9R2D1_KIND_MAPPING result=PASS external_kinds=8 internal_keys=8
FIX9R2D1_CIRCULAR_SLICE result=PASS training_lengths=1024,1024 payload_lengths=53760,53760
FIX9R2D_ACCEPTANCE result=PASS
FIX9R2D_VERDICT file=f1 verdict=STABLE_LTI_CHANNEL
FIX9R2D_VERDICT file=f2 verdict=STABLE_LTI_CHANNEL
FIX9R2D_VERDICT verdict=STABLE_LTI_CHANNEL (files=2, distinct=1)
```
退出码 0；JSON `{accepted, per_file, problems}` 正常落盘。

---

## 4. 板端热更（Task F，我禁碰板，命令由用户执行）

热更**不是**重跑 R8，**不是**重新打全量板包；仅把 4 个文件串口上传覆盖到已解包的 fix9r2d 板目录 `$PKG_ROOT`（如 `/root/sdr_rml23_live_board_package_iq_rf_loopback_fix9r2d`）。

源 → 目标：

| 源（本机 `board_rml23_live/`） | 目标（板端 `$PKG_ROOT/`） |
| --- | --- |
| `scripts/analyze_fix9r2d_capture.py` | `$PKG_ROOT/scripts/analyze_fix9r2d_capture.py` |
| `scripts/test_fix9r2d1_analyzer_manifest.py` | `$PKG_ROOT/scripts/test_fix9r2d1_analyzer_manifest.py` |
| `docs/M29_RML23_FIX9R2D1_ANALYZER_HOTFIX_AUDIT.md` | `$PKG_ROOT/docs/M29_RML23_FIX9R2D1_ANALYZER_HOTFIX_AUDIT.md` |
| `FIX9R2D1_ANALYZER_SHA256SUMS.txt` | `$PKG_ROOT/FIX9R2D1_ANALYZER_SHA256SUMS.txt` |

板端步骤（示例，`$PKG_ROOT` 按实际路径替换）：

```bash
# 1) 备份旧分析器
cp "$PKG_ROOT/scripts/analyze_fix9r2d_capture.py" \
   "$PKG_ROOT/scripts/analyze_fix9r2d_capture.py.fix9r2d_buggy_backup"
# 2) 单文件串口上传（4 次，每个文件一次；目标路径见上表）
#    例（XMODEM/ZMODEM，按板端上传工具）:  send  <本机文件>  <板端目标路径>
# 3) 上传后逐文件 SHA 校验（应与 FIX9R2D1_ANALYZER_SHA256SUMS.txt 一致）
sha256sum "$PKG_ROOT/scripts/analyze_fix9r2d_capture.py"
sha256sum "$PKG_ROOT/scripts/test_fix9r2d1_analyzer_manifest.py"
sha256sum "$PKG_ROOT/docs/M29_RML23_FIX9R2D1_ANALYZER_HOTFIX_AUDIT.md"
# 4) 复用现有 manifest 重新离线判责（不重跑 R8；在 16 波形 + 2 manifest 所在目录）
python3 -I "$PKG_ROOT/scripts/analyze_fix9r2d_capture.py" \
    --wave-manifest route_f_fix9r2d_waveforms.tsv \
    --capture-manifest route_f_fix9r2d_capture.tsv \
    --out route_f_fix9r2d_verdict.json
```

（板端 `python3` 按板端环境为准；本机验证用 `python -I`。最终 SHA/字节数以 `FIX9R2D1_ANALYZER_SHA256SUMS.txt` 与交付报告 §9 为准。）

---

## 5. 门禁 / 红线 / 停止点

- 最高状态 **`M29-RML23-FIX9R2D1-ANALYZER-HOTFIX-READY`**。
- **禁止**：宣告 RF 通过；修改恢复算法；运行 46 样本；新增均衡器；恢复 fix10；把本次 Python 错误归因于硬件；要求用户重新采集已完整保存的波形。
- **不批准**：碰板；改 C++；改 `iq_rf_sync_recovery.hpp`；TX/RX 路径；帧布局；同步算法；模型/标签/预处理；RF 门限；fix10；当前板端波形和 manifest；任何 Phase 2 恢复算法。
- `FIX9R2D1_*` 与 `FIX9R2D_ACCEPTANCE` 只是离线分析器结构门/热修门，**绝不携带** RF 回归 PASS/FAIL 语义；六判责 token 判定后仍需用户批准才谈最小恢复。
