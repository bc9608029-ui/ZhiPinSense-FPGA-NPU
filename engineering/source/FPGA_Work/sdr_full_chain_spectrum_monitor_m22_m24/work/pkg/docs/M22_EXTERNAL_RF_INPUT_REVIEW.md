# M22 外部 SDR 实时射频输入审查（只读审计 + 根因证据 + 最小补丁提案）

- 工程：`F:\FPGA_Work\sdr_full_chain_spectrum_monitor_m22_m24\work\pkg`
- 板端包：`/root/m22_test/sdr_full_chain_spectrum_monitor_m22_m24_m22_board_package`
- 状态：**只读审查完成，未修改任何源码**。本文只交付「根因证据 + 最小补丁设计」，代码落地待用户确认后另行执行。

> 红线（全程遵守）：不重训模型、不改模型权重 / 12 类标签序 / 预处理契约、不改 RTL/XDC/位流、不写 Flash、不自动发射、不提高直连 TX 功率、不宣称 RF/HARDWARE PASS、保留 M22 已通过的 runtime/touch 测试行为。

---

## 1. 根因（按证据强度排序）

### 根因 1（主导，几乎确定）：ambient 阶段从未设置 RX LO，也不设置 RX BW

`run_ambient_phase()`（`board_package/board_gate9_full_chain_12class.cpp:922`）在整段外部射频接收路径中：

- 只做了 `negotiate_sample_rate()`（:956，写 `sampling_frequency`）、`set_rx_gain_mode("manual")`（:969）、`set_rx_gain(gain_db)`（:970）、`set_loopback(0)`（:971）。
- **没有任何 `set_rx_lo()`、没有任何 `set_rx_bw()`**。
- CLI 参数只解析了 `--uri / --rx-gain / --rec-scale / --nco-offset / --model-sha / --ctl-sock / --frames / --batch-frames / --stability-window`（:925–939），**没有 `--rx-lo`/`--center`/`--rx-bw` 选项**。

`set_rx_lo` 在本二进制里唯一的实现是 `PlutoDeviceControl::set_rx_lo`（:146–148），而它**只**被 `producer::Producer12::before_capture()`（`producer_12class.hpp:165–174`）调用，且该调用被 `if (!band_scan_active() || !running()) return;` 门控 —— 只在 BAND_SCAN 模式下重调 LO。ambient 阶段默认 FIXED 模式，`before_capture()` 每次直接 return，**永远不写 RX LO**。

后果：AD936x 的 RX LO 决定外部射频被下变频到基带的频点。ambient 阶段不写它，RX LO 就停在**板卡 boot 默认值**（不能保证是 2.400000 GHz），也不校验读回值。外部 TX 在 2.400010 GHz，若 RX LO 不在 2.400 GHz（或 RX BW 未覆盖），信号根本到不了 ADC 带内 → presence 恒为 NO_SIGNAL。**这与「digital 自测正常、ambient 无信号」完全吻合**（见根因 3）。

### 根因 2（STALE DATA 症状）：UI 把「低于门限但 RX 正常」与「超时/断开」混为一类

两段独立问题叠加：

1. **ambient 是有界一次性运行，跑完就退出**。默认 `--frames=64`，runtime 基线 `--frames=10000`（`scripts/run_m22_runtime_baseline.sh:37`）。退出后 UI 的 socket 读端 EOF → `board_ui_live_12class.cpp:552–563` 里 `producer_gone=true` → `display.status = ui::Status::Stale` → 渲染 "STALE DATA"。
2. **即便还在运行**，一个「RX 正常、帧正常、但 power 低于门限」的 NO_SIGNAL 帧：`ui_state_map.hpp::map_to_state` 只按 `mock`/流异常（`overflow/dropped/discontinuity/short_frame`）分类，NO_SIGNAL 帧没有流异常 → `Status::Live`。而 `ui_render.cpp::render_main`（约 :428）**只在 `Status::Error` 时渲染 "NO SIGNAL" chip**；`Status::Live` 下显示空类 + "LOW CONFIDENCE"。`map_to_state` 虽然写了 `st.presence = r.presence_state`（`ui_state_map.hpp:85`），但 `render_main` 完全没消费 `st.presence` 来决定状态。

结果：NO_SIGNAL（有帧、低于门限）在运行时被当成 Live/低置信，退出后被当成 STALE；全程没有一个独立的 "NO SIGNAL" 状态。这正是「无信号时 UI 显示 STALE DATA 而非 NO SIGNAL」。

### 根因 3（次要，日志稀疏）：summary-interval 默认 > frames + 逐帧结果默认进 NullSink

- `M22Config::summary_interval` 默认 5000（`board_gate9_full_chain_12class.cpp:198`）；ambient 默认 `--frames=64`，跑不满 5000 帧 → 一次 `M22_SUMMARY` 都不打印。
- 逐帧结果路由 `frame_out`：仅 `--verbose` 时写 stdout，否则写 `NullSink`（:1078–1080）。所以板端日志只有启动三行 + `PRESENCE_TRANSITION from=- to=NO_SIGNAL frame=1`（:1158–1166），与观察一致。

---

## 2. 完整调用链追踪（外部 Pluto RF → UI）

1. `main()` → `run_ambient_phase`（:1342 附近 dispatch）。
2. `pluto::make_device(uri)`（:943）→ `LibiioDevice::open()`（`sdr_adapter/pluto_device_libiio.cpp:188–251`）：扫 "usb" context，找 `ad9361-phy`/`cf-ad9361-lpc`，开 RX I/Q 流通道、RX LO（`altvoltage0`）、TX LO（`altvoltage1`）。**只开句柄，不写 LO/BW/gain**。
3. `negotiate_sample_rate`（:956）→ 写/读回 `sampling_frequency`，候选 2.56 MHz（×20）或 3.84 MHz（×30）（`fir_coeffs.h kFirSpecs`）。
4. RF 配置（:968–972）：`set_rx_gain_mode("manual")` + `set_rx_gain(10)` + `set_loopback(0)`。**缺 LO/BW**。
5. 帧循环（:1086–1230）：
   - `board::capture_contiguous`（:1107）→ `dev.read_rx(n_complex, 5000ms)` → `iio_buffer_refill`（`pluto_device_libiio.cpp:520`）。
   - `chain.push_int16(iq)`（:1116）→ `PreprocessChain`：int16 交织 → complex ÷2048 → NCO 下变频（`nco_offset`）→ 多相 FIR 重采样（2.56/3.84 MHz → 128 kHz）→ 1024 复数帧 → fp32 `[2,1024]` × rec_scale（`chain_common.hpp`）。
   - `chain.pull_tensor`（:1124）→ `prod.on_frame`（:1140）→ `npu.infer`（:1144，真实 NPU）→ `presence_.update`（`producer_12class.hpp:221–233`）→ `engine_.update` 决定 publish。
   - 组装 `ResultFrame`（:1169–1192，`version="12class-chain-v2"`），publish 门控（:1195–1207）。
   - `emit_frame_v3(frame_out, sock, r)`（:1215）→ `sock.write(rec)`（`unix_socket_sink.hpp:55`，非阻塞 `::send`，写失败静默计数丢弃）。
6. UI：`board_ui_live_12class` 读 `/run/sdr_amr_ui.sock` → `map_to_state` → `render_main` 决定 chip。

---

## 3. ambient 与 digital 输入路径对照表

| 维度 | ambient（`--phase ambient`） | digital 自测（`--phase digital`，`run_loopback_phase`:416） |
|---|---|---|
| 信号来源 | 外部 Pluto TX → 同轴线 → 板端 RX 天线输入 | 板内 TX DAC 生成 10 kHz 音 → **digital loopback** 回 RX baseband |
| `set_loopback` | `0`（外部 RF，:971） | `1`（digital，:474） |
| 是否 TX | **否**，`tx_active=0`（:973） | 是，`PlutoTx` 循环发音（:536–549） |
| TX/RX 中心频率 | **不设置**（无 `--center`/`--rx-lo`） | `--center` 默认 2.45 GHz，经 `PlutoTx` 设置（:539） |
| RX LO | **未写**（停在 boot 默认） | digital loopback 下 RF 前端被旁路，LO 不参与下变频，故不写也不影响 |
| RX BW | **未写**（停在 boot 默认） | 同上，无关 |
| 日志字段 | `AMBIENT_RX tx_active=0 loopback=0 gain_db=…`、`GATE9_AMBIENT_CTL_READY`、`PRESENCE_TRANSITION` | `GATE9_MODE_CTL_READY` 等（无 AMBIENT_RX / PRESENCE_TRANSITION 字段） |
| 依赖 RF 前端 | **强依赖**（LO/BW 必须正确） | **不依赖**（数字环回） |

> 这就是「digital 自测正常显示 AM-DSB，ambient 却检测不到外部信号」的结构性解释：digital 自测走的是片内数字环回，绕过了 mixer 与 RF BW，所以从未设置 LO/BW 也不影响；ambient 走真实 RF 前端，而该前端在 ambient 阶段从未被配置。

---

## 4. 12 问（重构自需求清单）与回答

1. **外部 RF（约 -57 dBm）为何不触发 NO_SIGNAL→SIGNAL？** 主导原因：RX LO 未设置（可能不在 2.400 GHz）且 RX BW 未设置，信号未进入 ADC 带内。次因：-57 dBm 在 10 dB gain 下换算到 ADC 计数 RMS 是否 ≥ `enter_power_dbfs=-55`（≈ RMS 3.6 counts）需诊断实测确认，但目前无法判断，因为信号可能根本没进带。
2. **UI 为何显示 STALE DATA 而非 NO SIGNAL？** 见根因 2：有帧低于门限 = Live（非 NO SIGNAL chip）；producer 退出/EOF = Stale。语义未分离。
3. **为何 digital 正常、ambient 无信号？** digital 走数字环回、绕过 RF 前端；ambient 走真实 RF 前端但未配置 LO/BW（对照表）。
4. **为何 digital 日志缺 tx_active/loopback/AMBIENT_RX/PRESENCE_TRANSITION？** 这些是 `run_ambient_phase` 专属字段（:973、:1160）；digital 走 `run_loopback_phase`，字段不同。
5. **完整路径是什么？** 见 §2。
6. **ambient 阶段 RX LO / RX BW / gain 实际设成什么？** gain=manual 10 dB（可配），loopback=0，采样率=协商值；**LO、BW 完全未设**。
7. **-55 dBFS 门限与 -57 dBm 输入是否匹配？** 无法仅凭 dBm 判定；需诊断模式的 raw I/Q RMS / peak / presence metric 实测。设计上 `enter=-55 dBFS` 相当敏感（RMS≈3.6 counts），但前提是信号进带。
8. **nco-offset 外部 RF 下该设什么？** 已备频偏排除方案（TX/RX 同频、nco-offset=0）；NCO 是基带数字下变频（`nco.hpp`），与 RF LO 独立。若 RX LO 未对准，NCO 救不回来。
9. **诊断六态如何区分？** 见 §5 的 `RF_*` 分类。
10. **UI 状态如何分离？** 见 §6。
11. **9 项回归各验证什么？** 见 §7。
12. **复测如何证明真实 RF 而非合成？** 见 §8。

---

## 5. 最小诊断补丁设计（可开关，约每 100 帧一次摘要）

新增 CLI：`--rf-diag`（开关）与 `--rf-diag-interval`（默认 100）。在 `run_ambient_phase` 帧循环里，每 `interval` 帧打印一行 `RF_DIAG`（stdout + stderr 不回串口逐帧，仅摘要）。

字段（每项在源码里的来源）：

| 字段 | 来源 |
|---|---|
| `frame` | `total_processed` |
| `refill_ret` | `board::capture_contiguous` 返回值（`board_common.hpp`）|
| `rx_uri` / `rx_device` / `rx_channel` | `dev->` 读回（新增只读 getter，或 `open()` 记录句柄名）|
| `rx_lo_hz` | **新增 `dev.get_rx_lo()` 读回 `altvoltage0.frequency`**（当前无此只读）|
| `sample_rate_hz` | `neg.actual_hz`（已有）|
| `rf_bw_hz` | **新增 `dev.get_rx_bw()` 读回 `voltage0.rf_bandwidth`** |
| `gain_mode` / `gain_db` | **新增 `dev.get_rx_gain_mode()` / `get_rx_gain()`**（读回 `gain_control_mode`/`hardwaregain`）|
| `raw_iq_min/max/mean/rms/peak/zero_fraction/nonfinite` | 在 `chain.push_int16` 前对 `iq` 计算（纯整数/统计）|
| `nco_pre_rms` / `nco_post_rms` | NCO 前后各取一帧 RMS（`chain` 内或临时）|
| `presence_metric` / `presence_threshold` / `presence_decision` | `d.measurements.power_dbfs` / 当前门限（enter/exit）/ `d.presence_state` |
| `result_submitted` | 本次是否 `emit_frame_v3` |
| `socket_send_ret` | `UnixSocketSink` 当前 `write()` 返回 void → **改为返回 bool 或暴露 per-write ok**；诊断打印 `sock.dropped_count()/error_count()` 增量 |

状态分类（每帧/每次摘要判定一个）：

- `RF_NO_SAMPLES`：refill 返回 0 或 `capture_contiguous` 失败。
- `RF_ZERO_DATA`：raw IQ 全零 / RMS≈0 / zero_fraction≈1。
- `RF_BELOW_THRESHOLD`：有非零样本，`presence_metric < presence_threshold`。
- `RF_SIGNAL_PRESENT`：`presence_decision == SIGNAL_PRESENT`。
- `NPU_NOT_RUN`：`npu.infer` 未执行（`!prod.running()` 提前 break）或 `total_processed` 无增长而 refill 正常。
- `UI_SEND_FAILED`：`sock.write` 报错/丢弃（`error_count`/`dropped_count` 增长）或未连接。

不改变任何已有行为：`--rf-diag` 默认关闭；默认路径字节不变。新增只读 getter 不改设备写入语义。

---

## 6. UI 状态语义修复设计

目标：三个状态独立，且「NO SIGNAL ≠ STALE DATA」。

- `ui_state_map.hpp`：`map_to_state` 增加分支 —— 若帧有效且 `r.presence_state == "NO_SIGNAL"`（或 `argmax_idx==-1` 且无流异常）→ 新状态 `ui::Status::NoSignal`（枚举新增）。
- `ui_render.cpp::status_label`：`NoSignal → "NO SIGNAL"`；`render_main` 对 `NoSignal` 渲染 "NO SIGNAL" chip（而非借用 `Error`）。
- `board_ui_live_12class.cpp`：`Stale` 只由「超时未收到帧」（`should_be_stale`）或 `producer_gone`（socket EOF）触发 —— 与「有帧但 NO_SIGNAL」彻底分开。
- 控制 socket 断开（`ctl_client` 连不上）：已有 `UI_CTL status=CONNECTED/DISCONNECTED` 语义，保持并在 UI 上显示 "CTRL DISCONNECTED"（独立于 RX 状态），不并入 STALE。

**红线**：不把 `NO_SIGNAL` 渲染成 `STALE DATA`，也不把 `CTRL DISCONNECTED` 当 `STALE`。

---

## 7. 9 项离线/模拟回归测试

1. **全零 IQ → NO SIGNAL 且不 STALE**：喂全零 int16，断言 presence=NO_SIGNAL、UI 状态=NoSignal（非 Stale）。
2. **低幅噪声 → NO SIGNAL**：RMS 低于 -55 dBFS 的白噪声，断言 NO_SIGNAL。
3. **明显正弦/QPSK → SIGNAL**：幅值超门限、谱峰突出，断言 SIGNAL_PRESENT 且发布类别。
4. **RX 帧持续但无信号 → NO SIGNAL（有帧）**：持续 refill 成功、无流异常、低于门限，断言 UI 显示 NO SIGNAL 而非 STALE。
5. **停止结果帧 → 超时 STALE DATA**：`stale_ms` 超时无帧，断言 Stale。
6. **control socket 断开 → CTRL DISCONNECTED**：`ctl_client` 连接失败，断言独立 DISCONNECTED 语义（非 STALE、非 NO SIGNAL）。
7. **nco-offset 正负方向单测**：`nco.hpp` 正频下变频 vs 负频，断言相位增量符号与 `exp(-j·2π·f/fs·n)` 一致。
8. **libiio refill 错误 fail-closed**：模拟 `read_rx` 返回 0/负，断言 `capture_contiguous` 返回 false → 不进 NPU、不进 UI，并报 `RF_NO_SAMPLES`。
9. **不允许 digital 合成冒充真实 RF 验收**：回归 gate 断言 —— ambient 阶段无 `tx_active=1`、无 `make_periodic_tone`、无 `set_loopback(1)`；诊断/验收脚本不得用 digital 合成输入作为 RF 通过证据。

全部为 host 可跑（fake device / 合成 IQ），不改真实 NPU / 不改模型。

---

## 8. 板端复测命令与「证明真实 RF」的判据

复测（确认根因 1 后，最小修复补丁落地时执行）：

```bash
# 修复后：显式设 RX LO + BW 再跑 ambient
./board_gate9_full_chain_12class --phase=ambient --uri= \
  --rx-lo=2400000000 --rx-bw=200000 --rx-gain=30 \
  --nco-offset=0 --rec-scale=1.0 --frames=10000 \
  --rf-diag --rf-diag-interval=100 \
  --model-json=… --model-raw=… --model-sha=…
```

证明用的是**真实 RF 而非合成数据**（四重判据，缺一不可）：

1. **`tx_active=0` + `set_loopback(0)` 客观在场**：ambient 日志必须出现 `AMBIENT_RX tx_active=0 loopback=0`，且代码路径无 `make_periodic_tone`/`PlutoTx`（回归测试 9 兜底）。
2. **诊断回读值来自硬件**：`rx_lo_hz` 读回值 = 用户命令设置的 2.400000 GHz（读回 ≠ 注入常量），`rf_bw_hz` 读回 200 kHz，`sample_rate_hz` 读回协商值 —— 这些是 libiio 从 `ad9361-phy` 读的真实属性。
3. **信号随外部 TX 开关变化**：关外部 TX → `RF_BELOW_THRESHOLD`/`NO_SIGNAL`（raw RMS 掉到噪底）；开外部 TX → raw RMS 抬升、`RF_SIGNAL_PRESENT`、发布类别。合成数据做不到「随物理 TX 开关而变化」。
4. **频偏可复现**：外部 TX 改频偏，诊断的 `nco_pre_rms`/谱峰位置随之移动，且必须设置正确 RX LO 后才出现 —— 证明是 RF 前端真实下变频，非片内数字注入。

> 只有上述四重判据同时成立，才允许把「外部 RF 链路」记为可用；本审查**不宣称** RF/HARDWARE PASS。

---

## 9. 交付物清单对应

1. 根因（证据排序）→ §1；2. 源码位置与调用链 → §2；3. 对照表 → §3；4. 最小诊断补丁及测试 → §5+§7；5. 最小修复补丁 → 见下；6. 板端复测命令 → §8；7. 真实 RF 判据 → §8。

### 最小修复补丁（根因 1，确认缺陷后）

- `run_ambient_phase` 增加 `--rx-lo`（默认不设 = 保持现状，避免破坏既有 runtime 基线）与 `--rx-bw`；解析后在 RF 配置块（:968–972）调用 `dev->set_rx_lo(...)`、`dev->set_rx_bw(...)`。
- 在 `PlutoDeviceControl` 或直接 `dev` 上暴露只读 `get_rx_lo/get_rx_bw/get_rx_gain`（读回用于诊断与日志确认）。
- **默认值保持向后兼容**：不传 `--rx-lo` 时行为与当前字节一致（不擅自改 LO），确保 M22 runtime/touch 既有测试不受影响。

---

*本文档为只读审查产物；补丁代码尚未写入工程。*
