# M26 集成接口（Integration Interface）

任务 id="39e5" · M26 · 本文定义 M26 各模块的对外接口、握手、元数据、CDC 与 fail-closed 行为，以及（未来）接入现有主链的边界。**本阶段不接主链**（spec §六），本文只说明接口契约，不猜测生产 Mandatory Core 握手细节（审计已明确其 RTL 在外部，本树无证据，见 `M26_BASELINE_AND_INTERFACE_AUDIT.md §3/§7`）。

---

## 1. 统一数据约定

| 项 | 值 |
|---|---|
| 输入 IQ | signed 16-bit **Q1.15**，interleaved `[I,Q]`，`tdata[31:0] = {I[15:0], Q[15:0]}`（I=re 低 16 位，Q=im 高 16 位） |
| 功率谱 | unsigned 32-bit **Q0.30**（`|X|²`） |
| 帧长 | 1024 复数 / 帧，`tlast` 定界 |
| 复位 | 异步低有效 `rst_n`；复位后所有输出寄存器=0、`tvalid=0`，**不输出旧数据** |

---

## 2. AXI-Stream 握手（自洽实现）

所有流式模块采用 1 深 skid-buffer 握手：

```
s_axis_tready = !out_valid || m_axis_tready
m_axis_tvalid = out_valid
```

- `tvalid` 只在 `tready` 同时为高时推进；下游反压时上游停止。
- 支持**连续流、间断流、反压**（spec §三 M26-A 要求）。
- 帧边界由 `tlast` 携带，随数据一起转发，不在中间重计时（`m26_decimator` 例外：抽取后 `tlast` 落在每组最后一个保留样本，见 contract §6）。

---

## 3. 模块端口契约（摘要，详见各 .sv 头注释）

### 流式（M26-A，均有 `bypass`）

| 模块 | 输入 | 输出 | 配置 | fail-closed |
|---|---|---|---|---|
| `m26_dc_removal` | IQ | IQ | `bypass` | — |
| `m26_energy_rms` | IQ（观察旁路） | `energy`(48) `rms`(16) `peak`(32) `stats_valid` | `enable` | — |
| `m26_signal_presence` | `frame_valid`+`rms` | `presence`(2) `presence_changed` | `thr_enter/thr_exit/enter_m/exit_n` | — |
| `m26_nco` | IQ | IQ | `bypass` `phase_inc`(32) | |f|>fs/2 → 相位增量饱和 + `cfg_warning` |
| `m26_fir` | IQ | IQ | `bypass`，系数构建时 ROM | — |
| `m26_decimator` | IQ | IQ | `bypass` `decim`∈{2,4,8} | 非法倍数 → `cfg_error` 停输出 |

### 频谱（M26-B）

| 模块 | 输入 | 输出 | 配置 | fail-closed |
|---|---|---|---|---|
| `m26_hann` | IQ | IQ | `bypass` | — |
| `m26_fft_1024` | IQ | IQ | `bypass` | — |
| `m26_fftshift` | IQ | IQ | — | — |
| `m26_mag_sq` | IQ | 功率(32) | — | — |
| `m26_noise_floor` | 功率流 | `n0_data`(32)+`n0_valid` | — | — |
| `m26_cfar` | 功率流 | `mask`(1024)+`mask_valid` | `guard/ref/threshold_scale_q214` | 2R+2G≥N → `cfg_error` 停 |
| `m26_candidate_merge` | 功率流 + `mask/mask_valid` | 逐候选 `cand_*` + `cand_done/cand_count/candidate_overflow` | `merge_gap/max_cand` | — |
| `m26_spectrum_top` | IQ | 中值 + 掩码 + 候选列表 + `cfg_error` | 上述全部 | CFAR 非法停 |

候选列表握手：`cand_valid` 每候选一拍（携带 `cand_start/end/peak/bw/power/wsum`），`cand_done` 一拍结束（携带 `cand_count/candidate_overflow`）；0 候选时只发 `cand_done`（`cand_count=0`）。

---

## 4. 元数据（contract §16）

每帧输出需携带 `frame_id`（递增）/ `timestamp`（样本计数）/ `sample_count`。**本阶段在集成包装层添加**（`m26_stream_frontend_top` / `m26_spectrum_top` 本身不内嵌元数据，保持数据通路纯净）；断流/复位后 `frame_id` 从 0 重计；旁路路径元数据不改变。

---

## 5. 跨时钟域（CDC）

M26 模块全为**单时钟域**（目标 100 MHz `gp_clk`），内部无 CDC。**接入主链时**需在边界加异步 FIFO / 合格同步结构（spec §五），与生产 Mandatory Core 的时钟域（50/100/200/400/800 MHz + 1 GHz NPU）隔离，不在本阶段实现。

---

## 6. 接入现有主链的边界（仅描述，不执行）

1. 现有链是 **PL-DDR Mandatory Core 寄存器图 + 内存缓冲**（基址 0x400C0000），非逐样本 AXI-Stream（审计 §2）。
2. M26 用独立 AXI-Stream 解耦；未来接入需新增**流式适配器**（把 Mandatory Core 的 IQ 缓冲按帧注入 M26 前端），该适配器不在本交付。
3. 接入前置条件（spec §六集成门禁）：M22 板测通过、OOC 仿真+综合通过、定点误差达标、CDC 检查通过、完整旁路、资源/功耗/温度可接受、顶层重跑时序+CDC+DRC+板端回放。**当前均未满足，故保持独立。**

---

## 7. 红线

- 不接 Gate 9/10 主链、不生成生产位流、不写 Flash、不碰板。
- 接口不明确处（握手/CDC 细节在外部 RTL）**不猜测接入**，M26 保持独立自洽。
- 最高状态 `M26-FPGA-DSP-OFFLINE-MODULES-READY`。
