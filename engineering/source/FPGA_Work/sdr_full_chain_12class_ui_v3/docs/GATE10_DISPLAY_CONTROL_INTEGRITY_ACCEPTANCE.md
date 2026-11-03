# Gate 10 显示与控制完整性 · 统一补丁验收标准（M15）

> 本文件是 M15 统一补丁（五子任务）的**板端验收标准**，覆盖 Task A / Task B /
> Task E / 新增项1 / 新增项2。离线侧已完成主机测试与语法/构建校验（`README.md`
> §主机验证），本文件定义的是**用户本人上板复测时必须逐项通过的硬门禁**。
>
> 状态红线：离线最高只标 **`READY-FOR-GATE10-DISPLAY-AND-CONTROL-INTEGRITY-HARDWARE-TEST`**，
> 未经实机验证**绝不**写任何 `*_PASS`。我禁碰板、禁写 Flash，上板由用户本人执行。

---

## 0. 通用前置（所有子任务共用）

- 用**默认**种子 `--seed=0x39e50001`（十六进制）与**默认**门限 `--min-match-rate=0.90`，
  不挑种子、不调门限、不跳过任何类/样本。
- 模型/位流保持权威：`model_12class.raw` SHA `2ae95275…`、
  合并位流 `combined_npu_hdmi_disable_icap.bit` SHA `22fec95c…`，本补丁不碰。
- 板端重编译走 `./build_on_board.sh` / `./build_npu_on_board.sh` / `./build_ui_live.sh`
  （`-O2`），产物落 `bin/`，失败不留旧二进制冒充。

---

## 1. Task A — Gate 10 顺序 12 类自测

板端程序：`board_gate10_selftest_12class`，入口 `scripts/run_gate10.sh`。

**逐类顺序自测（A3，硬门禁）**，每类严格按序：
1. `stop + destroy` 旧 TX 缓冲 → 等待稳定；
2. `create + push` 本类 TX 波形；
3. `recreate` RX 缓冲；
4. 丢弃 FIXED settle 帧后才计分类帧；
5. 仅在有证据（生命周期计数/恢复结果异常）时才重建 Pluto/NPU。

**验收项（A1/A3/A4/A5，全满足才 PASS）**：

| # | 门禁 | 判定 |
|---|------|------|
| A1 | 逐类打印 `SELFTEST_CLASS_BEGIN/END class=<i>` + 缓冲生命周期计数 | 12 类各一对，`tx/rx_buffer_{create,destroy}_count` 单调合理 |
| A4 | `--seed=0x39e50001` 十六进制解析 | `opt_u64` 接受 `0x` 前缀、拒绝前导符号（主机已测） |
| A5-1 | 每类 `matched=20/20` | 12 类全部 `match_rate >= 0.90` |
| A5-2 | 总 `valid=240` | `total_valid == 12×20` |
| A5-3 | `short/overflow/drop/disc == 0` | 零短帧/溢出/丢帧/丢弃 |
| A5-4 | `single_refill=1` | 每类单次连续 refill 交付足量 |
| A5-5 | `restore_result=PASS` | 设备状态恢复成功 |
| A5-6 | 退出码 0，`GATE_RESULT gate10_selftest_12class pass` | `board::emit` 权威单行 |

> 若 64QAM 仍 17/20（见 §4），不视为 Task A 通过——**不调门限、不换种子、不跳过该类**。
> Task A 的 PASS 是「顺序自测机制正确 + 每类达到契约门限」，64QAM 未达标时整门 FAIL，
> 归因走新增项1。

---

## 2. Task B — HDMI 脏帧 / 撕裂

板端程序：`board_ui_live_12class`，派发 `scripts/run_display_integrity_test.sh`
（`--display-diagnostic` / `--display-static` / `--display-refresh-hz`）。

**验收项（全满足才 PASS）**：

| # | 门禁 | 判定 |
|---|------|------|
| B1 | 启动顺序 `get 2 buffers → 清两缓冲 → sync → 渲染首帧 → sync → 设物理地址 → submit → READY` | 日志顺序正确，且 `UI_FB_READY` 前物理地址已设 |
| B2 | 日志 `UI_FB_INIT` / `UI_FB_READY` | 均出现且顺序正确 |
| B3 | 运行时只画**非扫描**后缓冲：`render → sync → flip` | 不向被扫描的前缓冲直画 |
| B4 | `--display-diagnostic` 报告帧缓冲状态/翻转计数；`--display-static` 静止图；`--display-refresh-hz` 报告实际刷新率 | 三项均可用，无脏帧/半帧撕裂 |
| B5 | 屏幕无可见撕裂/脏帧/闪烁 | 三页 UI 文字/徽标稳定 |

---

## 3. Task E — 控制通道实时响应 + UI 状态同步

板端程序：`board_gate9_full_chain_12class --ctl-sock`（生产者唯一持有控制通道），
验收自测 `scripts/test_mode_control_runtime.sh`。

**验收项（全满足才 PASS）**：

| # | 门禁 | 判定 |
|---|------|------|
| E1 | 控制线程**非阻塞 poll**，命令入**线程安全队列**，绝不阻塞采集循环 | `control_queue_depth` 不持续上涨 |
| E2 | 唯一生产者于 **12 安全点**之一 apply 命令 | 命令只在安全点生效，不在采集/推理中途改态 |
| E3 | 两阶段：`ACCEPTED ≤ 500ms`、`APPLIED ≤ 2s` | 日志时间戳证明 |
| E4 | `STATUS` 报 `requested/applied_mode`、`requested/applied_running`、`command_id/control_queue_depth` | requested≠applied 时能看出尚未生效 |
| E5 | `command_id` 单调递增、命令幂等、队满报错（`queue_full`） | 重复/畸形命令不改态、队满 fail-closed |
| E6 | `STOP` → 屏幕 STOPPED；`START` 恢复 | UI 状态行随权威帧切换 |
| E7 | `BAND_SCAN` 可被 `STOP` 中断 | 中断后扫频序列复位、不再逐帧回报 LO |

---

## 4. 新增项1 — 64QAM 精度诊断

> 板端证据 `class=64QAM matched=17/20 match_rate=0.850000 result=FAIL` 的决定性归因。
> 详见 `docs/64QAM_PRECISION_DIAGNOSIS.md`。

**验收项（全满足才 PASS）**：

| # | 门禁 | 判定 |
|---|------|------|
| D1 | 板端 `--dump-error-samples=3 --dump-dir=DIR` 落盘 3 个误分类帧 | `error_000..002.bin`（8192 B）+ `manifest.tsv` |
| D2 | 每样本含**模型域输入张量**（已乘 receiver_scale）+ ref/pred 类 + **完整 12 logits** | manifest 行字段齐全 |
| D3 | 主机 `compare_64qam_threeway.py` 三方对比（ONNX fp32 / `icraft-run --fake_qf` / 板端 NPU） | 脚本出 `ATTRIBUTION SUMMARY` + `VERDICT` |
| D4 | Gate 10 64QAM 生成参数 vs 训练契约逐项一致 | §3 审计表全 ✔（排除生成偏差） |
| D5 | 归因落在四类之一（int8 量化精度 / 板端执行 / fp32 基线 / 量化部署分歧） | 有决定性归因，非「未知」 |
| D6 | 若 = **int8 量化精度**（模型问题）→ 只产出可复现诊断资产 + 交棒 V2 | **不重训、不换模型、不调门限、不挑种子** |

> 预期 D5 落在 `INT8_QUANTIZATION_PRECISION`。若落 `BOARD_NPU_EXECUTION` 或
> `QUANT_DEPLOYMENT_DIVERGENCE`，则不是模型问题，回到 Gate 7 re-arm/layout 诊断。

---

## 5. 新增项2 — 真实无信号集成（ambient）

板端程序：`board_gate9_full_chain_12class --phase=ambient`，入口
`scripts/run_no_signal_ambient.sh`。

**验收项（全满足才 PASS）**：

| # | 门禁 | 判定 |
|---|------|------|
| N1 | `--phase=ambient` rx-only：`tx_active=0`，不启动 TX | 无 RF 发射路径 |
| N2 | 连续 RX + DSP + `SignalPresence` + UI | 长时间运行不崩、`SIGNAL_PRESENT↔NO_SIGNAL` 迟滞确认 |
| N3 | 非 `SIGNAL_PRESENT` 帧**绝不发假分类**（`publish=false`） | 无「无信号但显示分类」的不变式保持 |

---

## 6. 总体验收

统一补丁 PASS = **§1–§5 全部子任务门禁均通过**，且：

- 板端日志权威结果行闭合（`GATE_RESULT` / `UI_FB_READY` / `GATE9_MODE_CTL_READY` 等）。
- 主机侧回归保持全绿（`host_tests/run_tests.sh`、`test_board_build.sh`、
  `scripts/syntax_check.sh`、`bash -n`、`py_compile`）。
- 交付包 `sha256sum -c SHA256SUMS.txt` 全 OK（统一补丁 + 全量板端包）。

## 7. 红线

- 离线最高只标 **`READY-FOR-GATE10-DISPLAY-AND-CONTROL-INTEGRITY-HARDWARE-TEST`**。
- 未经实机验证，**绝不**写 `GATE10_DISPLAY_CONTROL_INTEGRITY_PASS / 64QAM_PASS /
  12CLASS_RF_PASS / DISPLAY_INTEGRITY_PASS / CONTROL_RUNTIME_PASS /
  FINAL_MODEL_PASS / OOD_PASS / FULL_SYSTEM_FINAL_PASS`。
- 不调 `--min-match-rate`、不换 `--seed`、不跳过 64QAM 或其它任何类/样本凑 PASS。
- dump 写盘失败即 fail-closed（`dump_error` → result=FAIL），绝不静默丢证据。
- 模型标签 `12CLASS_CHAIN_VALIDATION_MODEL`，OOD=NO_GO；权威位流/模型 SHA 不变。
- 我禁碰板、禁写 Flash；上板与主机三方对比均由用户本人执行。
