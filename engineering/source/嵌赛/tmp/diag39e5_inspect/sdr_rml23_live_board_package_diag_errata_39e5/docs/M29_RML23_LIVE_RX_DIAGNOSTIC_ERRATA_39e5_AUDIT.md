# M29 RML23 LIVE-RX 诊断勘误 39e5 — 根因审计表 + 修改函数/行号

状态：`M29-RML23-LIVE-RX-DIAGNOSTIC-ERRATA-READY-FOR-BOARD-TEST`（最高允许，未上板复测）
冻结身份：model json `d43a2284…` / raw `2425d990…` / params_md5 `7966a482…` / 位流 `22fec95c…` 不变。

本表把每条板端证据映射到**具体代码层**，并给出**修改的函数与行号**。执行顺序固定 A→B→C→D→E→F。

---

## 0. 证据 → 层 → 函数/行号 映射总表

| 证据 | 现象 | 根因 | 层 | 修改函数 / 行号 | 阶段 |
|---|---|---|---|---|---|
| E6 | UI 显示 `CTRL DISCONNECTED`，`/run/sdr_amr_control_rml23.sock` 不存在 | `--phase=live-rx` 从未创建反向控制 socket（loopback/ambient 有，live-rx 没有） | 控制通道（producer 反向 socket） | `run_live_rx_phase` +1489/1492/1514；STOP 语义 +1594 | A |
| E7 | state 心跳有效但 UI 显示 `STALE DATA` | UI 把「有分类结果」与「链路新鲜」合成一个布尔量；NO_SIGNAL 心跳无 result → 不刷新新鲜时钟 | UI 状态接收/显示 | `board_ui_live_rml23.cpp` 4 变量声明 +521..527、解析 +580..631、显示块 +641..712、headless 守卫 +896 | A |
| E2/E3/E4 | QPSK→QAM 分类跳变 | **禁止盲调 rec-scale / 平滑掩盖 / 硬编码 QPSK GT**；先建诊断仪表（捕获、分析、三后端对比）定位是模型固有还是板端误差 | 分类链（诊断，不盲修） | 捕获钩子 chain_common.hpp（C）；`scripts/analyze_live_rx_capture.py`（D）；`scripts/compare_three_backends.py`（E） | C/D/E |
| E5 | `occupied_bins=1024` 饱和 | 占带宽测量计数饱和；改为理论占带宽（90/95/99%） | DSP 测量 | 分析工具内理论计算（D），不修 DspMeasure | D |
| E8 | TX 审计对象错误 | 之前审计的是 8ASK 局部数组而非真实循环 TX 缓冲 | TX 路径 | A/B 拆分审计（C） | C |

---

## 1. 证据 6 — CTRL 缺陷（控制通道层）

**根因**：`run_live_rx_phase` 是 live-rx 独立新 phase，只做 RX + presence-gated NPU，**从未启动反向控制 socket**。而 UI 与 `start_all_rml23.sh` 都期望 `--ctl-sock=/run/sdr_amr_control_rml23.sock` 存在（`start_all_rml23.sh` 用 `socket_served_by` 判定 producer 就绪）。loopback/ambient phase 在 `+426`/`+897` 有完整控制服务，live-rx 缺失。

**修改**（`board_package/board_gate9_full_chain_rml23.cpp`）：
- `+1489` `ctl_sock = board::get_opt(... "--ctl-sock", "/run/sdr_amr_control_rml23.sock")`
- `+1492` `ui::UnixSocketServer control(ctl_sock); if (!control.start()) throw`
- `+1507` `control_thread_main` 线程 + `ControlThreadGuard`
- `+1514` `LIVE_RX_CONTROL_READY sock=...` 日志
- `+1526..1564` `apply_pending` lambda：直接把命令 `mode_ctl::apply_command(mst, c.raw)` 应用到 `mst`（live-rx 无 Producer12），回 ACK、更新 cstate、发 state event + `CONTROL_EVENT`
- 主循环 `+1578` `apply_pending("loop_top")`；`+1620` `apply_pending("frame_top")`

**需求 #3 — STOP 仍心跳**：`+1594` STOPPED 分支 `apply_pending("stopped"); sleep(10ms); continue;`，但 1000ms steady 心跳块 `+1583..1590` 在其上、始终执行 → UI 显示 `STOPPED` 而非 `STALE`。

---

## 2. 证据 7 — freshness 缺陷（UI 状态接收/显示层）

**根因**：旧代码用单一布尔量同时承载「收到过分类结果」和「链路新鲜」，且只在 **result** 帧刷新新鲜时钟。NO_SIGNAL/ACQUIRING 期间只有 `type:"state"` 心跳、无 result → 新鲜时钟不推进 → 超过 stale_ms 判定 STALE，尽管心跳一直在。

**修改**（`board_package/board_ui_live_rml23.cpp`，需求 #4 四变量拆分）：
- `+521..524` 声明 `have_valid_message` / `have_valid_result` / `last_valid_message_rx` / `last_valid_result_rx`（均用 UI 自身 `steady_clock`，**绝不**用 producer `timestamp_us`）
- `+580..583` result 分支置 4 变量；`+607..608` state 分支**只**置 `have_valid_message`/`last_valid_message_rx`
- `+641..712` 显示优先级重写：WAITING → STALE(disconnected/timeout) → STOPPED → NO_SIGNAL → ACQUIRING → SIGNAL_PRESENT(Live if have_valid_result) → 兜底
- `+695` `UI_STATUS old/new/reason/freshness_age_ms` 状态变更日志；`+712` `UI_RX_STATS` 每 1000ms 累计计数
- `+896` `if (!headless && flip_sched.should_submit(...))` headless 守卫（host 测试无 framebuffer 时不 submit）

**架构决策**：显示规则**只**放在 RML23 UI freshness 块，**不**改 `ui_state_map.hpp::apply_state_event`（被 12 类 UI 与 `test_heartbeat_socket.cpp:117` 共享，改它会破坏 12 类契约）。

---

## 3. 证据 2/3/4 — QPSK→QAM 跳变（诊断，不盲修）

红线：不盲调 `--rec-scale`、不用平滑掩盖 QAM 跳变、不硬编码 QPSK ground truth。本轮交付的是**诊断仪表**，不是分类改动：
- C：捕获钩子（把真实送入 NPU 的 tensor 逐字节落盘，供离线复算）→ **已交付** `board_package/capture_hook.hpp`（`board::TensorCapture`，原子写）+ `run_live_rx_phase` `--capture-dir` 接线（见 §7）
- D：分析工具（占带宽 90/95/99%、逐帧 argmax/置信度轨迹）
- E：三后端导出对比（Host/板端 NPU/参考 numpy，判定跳变来自模型还是板端）

---

## 4. 证据 5 — occupied_bins=1024（DSP 测量层）

**根因**：`occupied_bins` 在强信号下饱和到 1024（=FFT 全 bin 数）。**需求 #5**：分析工具**只做理论占带宽**（90/95/99% 能量），不信任饱和的 DspMeasure 测量值。

---

## 5. 证据 8 — TX 审计（TX 路径层，需求 #9 A/B 拆分）

- **A**：真实循环 TX 缓冲（RF loopback 实际发送的 `std::vector<int16_t>` / 环形缓冲）= `board::make_periodic_tone(tone_hz, fs, periods)`（`board_common.hpp:304`，内部 `pluto::make_cw_tone`）。整数周期 CW 音，12-bit 峰值 ≤2048，环形回卷无相位跳变。
- **B**：8ASK 是**分类标签**（`cat::target_24()[2]` / `cat::target_23()[2]` = `"8ASK"`），**不是** TX 缓冲。RML23 生产者的 TX 路径只有 `make_periodic_tone`，从无 8ASK 波形构造；live-rx 是 RX-only（`set_loopback(0)`，`tx_active=0`，**从不创建 TX 缓冲**）。
两者在报告中分离呈现，绝不混为一谈。宿主测试 `host_tests/test_tx_audit_rml23.cpp` 分别断言 A（真实 CW 音身份：有限/交错/峰值受限/整数周期无缝回卷/恒定包络=非 ASK）与 B（8ASK=标签，非缓冲，且 12 类生成器的振幅键控类是 4ASK 而非 8ASK）。

---

## 6. model_scale 字段审计（需求 #10）

**结论：`r.model_scale = 1.0` 正确，无需改值，已补注释**。

语义（`producer_12class.hpp:112` 注释 + `board_gate9_full_chain_rml23.cpp:402..405` 头注释）：
- `model_scale` = M2（auto-level / WorkModeEngine）数字标量，**在 receiver_scale 张量之上**再乘。
- live-rx 无 WorkModeEngine（直接测量 + presence-gated NPU），恒为 FIXED → 数字标量恒等 `1.0`。
- `rec_scale`（`--rec-scale`，板测=128）是 **receiver_scale**，由 `chain::PreprocessChain(fs_in, nco_offset, rec_scale)` 在预处理阶段单独施加，**绝不存入** `model_scale`。

对照：12 类 ambient/loopback 用 `r.model_scale = d.model_scale`（`+729`/`+1223`），其中 FIXED 模式下 `engine_.model_scale()` 恒为 1.0 → 与 live-rx 硬编码 1.0 **一致**。

修改：`board_gate9_full_chain_rml23.cpp:1700..1706` 补 6 行注释，值仍 `1.0`（`+1707`）。

---

## 7. 阶段 C 完成记录（捕获钩子 + 设备缓冲一致性审计 + TX 审计 A/B）

### 7.1 捕获钩子（需求 #6「atomic capture」）— 已交付

- 新增 `board_package/capture_hook.hpp`：`board::TensorCapture`（iCraft/libiio-free，仅 `sdr::Sha256` + `<cstdio>`）。
- **原子性**：8192 B（`[2,1024]` fp32，plane0=I/plane1=Q，小端，与 `deployment_golden/input_N.bin` 同布局）先写同级 `<name>.tmp` 再 `rename()` 落定；读者要么看到完整文件、要么看不到（崩溃不留半截 tensor）。返回这 8192 B 的 SHA-256 供日志指纹。
- 接线 `run_live_rx_phase`：`--capture-dir`（空=禁用，默认空，热路径零文件 I/O）→ 每帧 `classify_now(ps)` 成立、`npu.infer(tensor.data(), …)` **之前**捕获（捕获字节 == NPU 输入字节）→ `LIVE_RX_CAPTURE frame=… bytes=8192 sha256=… presence=…` 日志；`detail` 追加 `capture_dir`。
- 宿主测试 `host_tests/test_capture_hook.cpp`（10/10）：禁用返回空、坏目录 fail-closed、SHA 逐字节一致、最终名+恰好 8192 B+与 NPU 输入逐字节相等、`.tmp` 不残留（原子 rename）、同帧重捕返回同 SHA。

### 7.2 设备缓冲一致性审计 — 已存在，无需改码

`board::Continuity`（`board_common.hpp:252`：`single_refill` + `capacity_ok()`）、`board::capture_contiguous`（`:275`，单次 refill、容量不足/短读/超时 fail-closed）、live-rx 调用（`run_live_rx_phase` 捕获块）与 `continuity_ok_all` 门控**已在位**；宿主测试 `test_contiguous_cli.cpp` 已覆盖 `Continuity::ok/capacity_ok/report` + `capture_contiguous` 单 refill/容量不足/短读/超时 4 态。本轮**不改码**，仅在本表落账为「已存在 + 宿主已测」。

### 7.3 TX 审计 A/B 拆分（需求 #9）— 已交付

见 §5。宿主测试 `host_tests/test_tx_audit_rml23.cpp`（12/12）：TX_A 断言真实循环 CW 缓冲身份（交错/峰值≤2048/整数周期无缝回卷/恒定包络=非 ASK），TX_B 断言 8ASK=分类标签（`target_24()[2]`/`target_23()[2]`）而非 TX 缓冲，且 RML23 TX 路径唯一的波形构造器是 `make_periodic_tone`。

---

## 8. 阶段 D 完成记录（分析工具 + 理论占带宽，需求 #5）

新增 `scripts/analyze_live_rx_capture.py`（纯 stdlib + numpy，`-I` 可跑）：

- 读 `--capture-dir` 逐帧 tensor（8192 B，`[2,1024]` fp32，plane0=I/plane1=Q），
  解析 `--log`（`LIVE_RX_CAPTURE` + result JSONL）输出逐帧 argmax/置信度轨迹。
- **理论占带宽**（`occupied_bins_min_contig`）：最小连续 bin 区间含 X% 总 FFT 功率
  （prefix-sum + `searchsorted`，非循环，NCO 居中）。输出 **90/95/99% 三档**。
- **DC 保留 / DC 去除 双套结果**（避免 LO 泄漏支配累计功率）。
- **双边谱**：complex IQ PSD 用 `return_onesided=False` 等价语义，不按实信号单边 Welch。
- 明确区分**理论带宽 / null-to-null / fractional-power OBW**，绝不固定返回 128 kHz Nyquist。
- 未修 `DspMeasure`（其 `occupied_bins` 饱和是板端测量缺陷，另案），本轮只在分析端给出正确量。
- `--self-test` 5 例全过：纯音→1 bin、双音跨 60 bin 间隙→61、白噪声→宽带(912/969/1015，**不饱和**)、
  DC→1 bin、全零→0。合成 3 帧冒烟 exit 0。

---

## 9. 阶段 E 完成记录（三后端导出/比较，需求 #7）

### 9.1 本机盘点（`compare_three_backends.py --inventory`）

| 后端 | 本机状态 | 依据 |
|---|---|---|
| `fp32_onnx` | **AVAILABLE** | onnxruntime 1.30.0 + `work/onnx/rml24_24class_opset17.onnx`（sha `976618a1…`） |
| `host_quantized` | **AVAILABLE**（冻结导出） | `deployment_golden/expected_logits_or_argmax.json` 240 帧 `raw_24_logits`；iCraft HostBackend **运行时**本机未装，仅用其冻结结果 |
| `board_npu` | **UNAVAILABLE** | 无 ZG330 / iCraft NPU 后端；待板执行 `bash scripts/run_gate9_rml23.sh --phase=offline --count=240 --logits-export=/tmp/board_logits` |

任一后端缺失**不得**宣称三后端判责；本机只能跑 fp32-vs-host（量化对比）。

### 9.2 三个导出入口（导出/导入方式，key=input SHA + model identity）

- **board_npu**：`board_package/logits_export.hpp`（`board::LogitsExport`，原子 `.tmp`+`rename`）
  + `run_live_rx_phase`/`run_offline` 接线 `--logits-export`，每帧写
  `logits_<frame_id>.json`（`backend:"board_npu"`、`input_sha256`、`model_sha`、`raw24[24]`）。
  热路径默认关（空 dir 零文件 I/O）。语法检查通过（`gate9_rml23: syntax OK`）。
- **fp32_onnx**：`scripts/export_fp32_onnx.py`（onnxruntime CPU，`logits` [1,24] raw pre-merge），
  写 `logits_<fid>.json`（`backend:"fp32_onnx"`、`compiled_model_raw_sha256=2425d990…`）。实测 240 帧导出 OK。
- **host_quantized**：冻结 `deployment_golden/expected_logits_or_argmax.json` 的每样本 `raw_24_logits`
  （key = `input_NNN.bin` 的 SHA-256）。

### 9.3 比较（`compare_three_backends.py`）

- 只按 **input_sha256 相同** 且 **model identity 一致** 配对比对；身份/后端标签不符 → fail-closed 拒收。
- 量纲：三者均为 **fp32 raw-24 pre-merge logits**（bf16 后端已由 vendor 反量化为 float），
  直接算 `max_abs_diff`/`cosine` 与 `merge_logits_24_to_23` 后的 merged-23 argmax 一致性。

**实测（fp32 vs host_quantized，240 帧全匹配）**：

```
raw24 max_abs_diff  min=0.0139  median=0.2209  max=1.8158
raw24 cosine        min=0.311    median=0.9841  max=0.9998
merged-23 argmax agree  180/240  (75%)
```

**诚实结论**：bf16 量化（host 参考 vs fp32 源）在 60/240 帧改变 merged-23 argmax，
量化本身即可造成 QPSK↔QAM 跳变；这是真实测量，非隐藏。board_npu 未导出前，
此为 **2 后端量化对比，非三后端判责**；板端导出后重跑即可补全第三后端。

### 9.4 负向自测

- 身份门禁：`compiled_model_raw_sha256` 错 → 拒收 ✓
- 后端标签门禁：`fp32` 目录冒充 `board_npu` → 拒收 ✓
- merge 语义：source=3 热 → merged argmax=3 ✓

---

## 10. 阶段收尾 — B 级预缩放捕获（#1）、D 级 NPU 输入传输审计（#2）、start_all 去重（#11）

前一轮曾把 §7.1（post-scale final tensor 捕获）当作 #1、把 §7.2（`board::Continuity` RX 单次 refill 一致性）当作 #2——二者是**相邻但不相同**的审计点。本轮补上真正的 #1 与 #2，并完成 #11。

### 10.1 B 级抓取点（需求 #1）— 已交付

- `board_package/chain_common.hpp` 新增 `PreScaleCapture`（快照 1024 复数 `frame_` + 抽取状态）
  与 `PreScaleObserver`；`PreprocessChain::set_pre_scale_observer()` **默认关**，无悬挂/可覆写公开 getter。
- 在 `push_int16` 的 `if (frame_.size() == kFrameComplex)` 块内、`build_tensor()` **之前**触发：
  快照对象由 `PreprocessChain` 自身拷贝 `frame_`（观测者拿 const 引用，可保留），
  记录 `in_complex / resampler_out / resampler_discarded / resampler_out_index / up / down / phase / rec_scale`。
  **不是第二套计算链**——它观察的是 `build_tensor()` 即将消费的同一份 `frame_`。
- `sdr_adapter/resampler.hpp` 新增 `out_index()`（绝对下一输出索引，含已丢弃瞬态）与
  `current_phase()`（`(out_idx*down) mod up`），使捕获的抽取相位可复现。
- 宿主测试 `host_tests/test_chain_common.cpp::test_pre_scale_capture`：断言
  `final_tensor[I/Q] == pre_scale[I/Q] × rec_scale` 逐元素一致、每就绪帧恰好一次捕获、
  记录 rec_scale / 抽取相位 / 绝对输出索引。

### 10.2 D 级 "not_available" 审计（需求 #2）— 已交付（先取证再声明）

需求 #2 不许直接宣称 input_tensor_mem「not_available」，必须先给出**具体类型/接口/代码证据**。已取得：

- 编译输入 `@hostt`；本适配器 `icraft::xrt::Tensor(input_value).mallocOn(HostDevice::MemRegion())`
  （`npu_classifier24.hpp:130`）——映射目的地就是**主机内存**，`write` 即 host memcpy。
- XRT 公开接口 `tensor.h`/`device.h` **无 sync/msync/flush API**（已逐头审计）；
  设备侧传输 + cache sync 在 `ZG330Backend::Session::forward()`（编译 SDK，头不可见）。
- 故「msync vs 驱动同步节点」这一项的真实答案是：**主程序无显式 msync**，同步发生在
  `forward()` 内部——这是**接口证据支撑的结论**，不是未审计就搪塞。

`npu_classifier24.hpp` 新增 `set_input_audit(bool)`（默认关，热路径零开销）+ 私有 `audit_input()`：

- `write` 之前取 `src_sha = SHA256(source)`；`write` 之后、`forward` 之前 `read` 回映射区，
  **硬断言字节同一**（不一致即抛，不静默）；
- 记录 `byte_count/shape=[1,2,1024]/dtype=FP32/layout=contig-C-order plane0=I plane1=Q/
  stride=[8192,4096,4]/region=host/alloc_align_mod64` 与同步节点说明（一次性日志
  `NPU_INPUT_AUDIT …`）；
- `forward` 返回后**再读** `inputs_[0]`，要求与 `src_sha` 字节同一（后端须把主机输入当只读）。
- 不可读场景（ADDR 型 `MemPtr` 无 `cptr()`）由 `try/catch` 降级为 `align_mod64=UINT64_MAX`，
  不伪装成功。

### 10.3 start_all 参数去重 + 有效配置打印（需求 #11）— 已交付

`scripts/start_all_rml23.sh` 重构参数流（`bash -n` 通过；去重逻辑独立冒烟 4 例全过）：

- 先解析 UI 参数（`--ui-sock/--stale-ms/--display-refresh-hz/--no-touch`，未知 UI 参数 → `exit 2`）
  与 producer 参数（`--` 之后），再构造**一次性最终 producer argv**。
- `--phase/--frames/--rx-lo/--rx-bw/--rx-gain/--rec-scale/--nco-offset/--rf-diag/
  --rf-diag-interval` 全部去重成**单一有效值**（用户参数内 last-wins），并从 argv 中移除；
  **绝不依赖二进制 later-occurrence-wins 去消解重复 flag**；未知 producer flag 原样透传。
- `--model-sha` 为冻结身份，恒取 `$MODEL_RAW_SHA`（不来自用户参数），**不会误传给 UI 或从 UI 误读**。
- 打印 `LIVE_RX_EFFECTIVE_CONFIG phase=… frames=… rx_lo=… rx_bw=… rx_gain=…
  nco_offset=… rec_scale=… sock=… ctl_sock=…`（9 字段齐备，与需求逐字一致），
  `sock=$UI_SOCK_OPT`、`ctl_sock=$CTL_SOCK`。
- producer argv 每 flag 至多出现一次：`--model-json/--model-raw/--model-sha/--sock/--ctl-sock/
  --phase/--frames/--rx-gain/--rec-scale/--nco-offset`（`rx_lo/rx_bw` 仅在非 `-` 时追加，
  `rf-diag(+interval)` 仅在开启时追加），最后 `_passthru` 透传未知 flag。

### 10.4 需求 #8 / #12 收口

- #8：本 package 仍只声明 `…-READY-FOR-BOARD-TEST`；host 集成/单测 ≠ 真实板端 SDR/NPU；
  mock parser 测试绝不描述为 live-rx 板测。三后端里 board_npu 在 §9.1 显式标 `UNAVAILABLE`。
- #12：执行顺序 A→B→C→D→E→F，各阶段独立验证后再合并；本轮在 Stage F（打包）前把
  #1/#2/#11 各自独立实现并验证（`test_chain_common` 新增 #1 用例、`npu_classifier24.hpp`
  语法检查、`bash -n` + 去重冒烟）。
