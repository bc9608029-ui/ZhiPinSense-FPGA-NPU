# M29 RML23 Stage H-E / Route E — fix4 判责仪表修复审计

状态：**M29-RML23-IQ-DIGITAL-LOOPBACK-READY-FOR-BOARD-TEST**（不因本轮 host 测试改
`DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / RF_LEAKAGE_NOT_PROVEN` 为 PROVEN；不写任何
`*_PASS / PROJECT_COMPLETE / FINAL_* / BOARD_TEST_PASS`）。

基线：fix3 全量 `sdr_rml23_live_board_package_iq_digital_loopback_fix3.tar.gz`
（SHA `f3128a68…`）；fix4 是纯诊断仪表正确性增量，不碰生产链路。

---

## §1 证据（fix3 板测观察，来自 fix3 交付记录）

fix3 板测的 sweep 日志暴露了判责仪表**自身**的缺陷，把真实结果错判 `ambiguous`：

| 观察 | 值 | 指向缺陷 |
|---|---|---|
| TX 数据格式 | `16b/16b shift+0 signed fully-defined` roundtrip=1 | — |
| RX 数据格式 | `16b/12b shift+0 signed fully-defined` roundtrip=0 | 镜像 mask bug |
| 高幅档 RX raw | `≈ TX raw / 16`，`raw_gain ≈ -24.08 dB = 20·log10(1/16)` | 计数域满量程差 |
| `rx_logical_rms` | `≈ 2800 ~ 4091`（假 RMS） | 镜像 mask bug |
| `clip_rate` | `≈ 24 ~ 50%`（假削顶） | 镜像 mask bug |
| `kind` / `target_rms` | `""` / `0.0` | 字段未传播 |
| `ROOT_CAUSE` | `ambiguous` | 判责逻辑缺陷 |

三个已定位的 fix3 仪表缺陷（代码逐行确认）：

1. **kind/target_rms 未传播**：`sweep_one_level()` 签名无 `kind/target_rms`，
   `sweep_all_levels()` 双层循环未传入 → `SweepLevel.kind=""`、`.target_rms=0.0`；
   用恒为 0 的 `target_rms` 选“最高档”失效。
2. **host 镜像不符 libiio 语义**：`format_convert_raw_to_host()` 先**无条件**
   `v &= 0xFFF`，再因 `is_fully_defined=true` 跳过符号扩展。`-32=0xFFE0` →
   `&0x0FFF=0x0FE0=4064` → 假 RMS≈4096 + 假削顶。libiio 语义 = 复制/端序 →
   容器 shift → **仅当 `is_fully_defined=false`** 才 sign-extend(signed) /
   clear-high-bits(unsigned)；`fully_defined=true` 不得无条件 mask。
3. **直接比 counts 可能错**：TX 16-bit、RX 12-bit，`TX 512/32768 == RX 32/2048`
   归一化相同；count gain -24.08 dB 未必是真实衰减，可能只是计数域满量程差异。

**首要假设（禁止预先写死）**：-24.08 dB 来自 TX16/RX12 计数域尺度，而非真实回环
衰减。编码阶段**不得**提前声明 `DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE` 已证明——只有
板端 fix4 同时满足 normalized≈0 dB、corr≥0.9、无削顶、多档线性、libiio≡host 镜像，
才判 COUNT_DOMAIN_SCALE。

---

## §2 根因 → 修复

fix4 引入 COUNT 域 vs NORMALIZED 域双指标，让判责仪表能分离五种情形：

```
count_gain_db      = 20·log10(rx_count_rms / tx_count_rms)                       （原始 16-bit 容器）
normalized_gain_db = 20·log10((rx_count/2^(rx_bits-1)) / (tx_count/2^(tx_bits-1)))
```

满量程从 `DataFormatInfo` 推导（signed full scale = `2^(bits-1)`；本板 TX=32768、
RX=2048，**不硬编码**）。`-24.08 dB` count gain 配 `~0 dB` normalized gain =
`COUNT_DOMAIN_SCALE`（位宽满量程差，非真实衰减）。

### 判责优先级（A→G，严格顺序）

- **A** 任一有效档 `rx_libiio_diverged` → `LIBIIO_CONVERT_SEMANTICS`
- **B** capture 失败 / RX 全零 / 严重削顶 / 有效档不足 → `NOT_PROVEN`
- **C** 报告格式解码与原始容器不一致（`|logical gain − count gain| > 3 dB` 或
  `corr < 0.9`），**且**某非报告 shift 同时恢复形状（corr≥0.9）与尺度
  （`|logical gain − count gain| ≤ 3 dB`）且无新增削顶 → `FORMAT_MISALIGNMENT`
- **D** 报告格式（修正镜像）corr 仍不达 0.9 → `NOT_PROVEN`
- **E** normalized≈0（|dB|≤3）：`tx_bits≠rx_bits` 且 count gain 符位宽差 →
  `COUNT_DOMAIN_SCALE`；`tx_bits==rx_bits` 且 count≈0 → `UNITY`
- **F** normalized 显著<0（位宽差不能解释 + 多档线性 + corr 合格 + 无削顶）→
  `FIXED_ATTENUATION`
- **G** 其余 → `NOT_PROVEN`

### 关键设计点

- **corr 是尺度不变的**：纯位位置错位（缩放 2^shift）不降 corr。故 C 步的错位判据
  用“逻辑增益 ≠ 计数增益”（报告解码与原始容器不一致）而非 corr 改善；只有非报告
  shift 同时恢复 corr 与尺度才判 FORMAT_MISALIGNMENT。E/F 前加一致性护栏：
  `|logical_gain − count_gain| > 3 dB` 且无 shift 恢复 → `NOT_PROVEN`。
- 有效档选择：主判责用 `target_rms ≥ 64` 高幅档 + 无削顶 + RX 高于量化底噪
  （`kQuantFloorCounts=2.0`）；8/16 低幅档仅作量化边界证据、不主导。
- 阈值：`kFidelityCorrThreshold=0.9`（沿用 `find_correct_rx_shift` 既有常量）、
  `kGainPreservedDb=3.0`。增益对但 corr 不足仍 NOT_PROVEN。

---

## §3 要求 → 实现对照

| 要求 | 实现位置 |
|---|---|
| 镜像严格修复（先限定容器宽→逻辑右移→按 fully_defined/signed/bits） | `sdr_adapter/pluto_device.hpp::format_convert_raw_to_host` |
| 独立 signed 诊断视图（非 libiio 镜像） | `format_convert_raw_to_host_force_signed` |
| RX convert 独立参考（不触生产 read_rx） | `Device::rx_convert_raw_libiio` 纯虚 + `FakePlutoDevice`/`LibiioDevice` 实现 |
| 双域指标 + 符号自检 + shift 扫描 | `iq_digital_loopback_sweep.hpp`（`SweepLevel`/`SignCheck`/`ShiftScanEntry`/`measure_shift`） |
| A→G 判责 + components | `classify_root_cause`（`RootCause.components` + `components_str()`） |
| 格式纠错（位位置，非乘数） | `find_correct_rx_shift`（shift 0..15，仅 FORMAT_MISALIGNMENT 用） |
| 测试夹具 scale（冻结 SHA 后） | `auto_select_scale`（COUNT_DOMAIN_SCALE→`2^(tx-rx)`；FIXED_ATTENUATION→`2^(tx-rx)/G_norm`） |
| 板端证据打印 | `board_gate9_full_chain_rml23.cpp`（FORMAT/SIGNCHECK/LEVEL/SHIFT_SCAN/SAMPLE/ROOT_CAUSE/RECOMMENDATION） |
| 独立复核分析器 | `scripts/analyze_iq_digital_loopback_sweep.py`（独立重推 A→G + root_cause_match + 6 自检） |

---

## §4 核心代码（节选）

### 4.1 修正后的 convert 镜像（`pluto_device.hpp`）

```cpp
const std::uint32_t length_mask =
    (length_bits >= 16) ? 0xFFFFu : ((1u << length_bits) - 1u);
std::uint32_t value = static_cast<std::uint16_t>(raw_container) & length_mask;  // 限定容器宽
value >>= shift;                                                               // 逻辑右移（uint32）
if (!f.is_fully_defined) {                                                     // 仅非 fully-defined 才 mask/符号扩展
    const std::uint32_t mask = (bits >= 16) ? 0xFFFFu : ((1u << bits) - 1u);
    value &= mask;
    if (f.is_signed && bits < 16 && (value & (1u << (bits - 1))))
        value |= ~mask;
}
return static_cast<std::int16_t>(value);
```

### 4.2 双域指标（`sweep_one_level` 内）

```cpp
L.tx_count_rms = L.tx_raw_rms;
L.rx_count_rms = L.rx_raw_rms;
L.count_gain_db = L.raw_gain_db;
const double tx_fs = signed_full_scale(tx_fmt.bits);   // 2^(tx_bits-1)
const double rx_fs = signed_full_scale(rx_fmt.bits);   // 2^(rx_bits-1)
L.normalized_gain_db = 20.0 * std::log10(
    (L.rx_count_rms / rx_fs) / (L.tx_count_rms / tx_fs));
```

### 4.3 错位判据（C 步，尺度匹配而非 corr 改善）

```cpp
const bool reported_inconsistent =
    std::fabs(L.gain_db - L.count_gain_db) > kGainPreservedDb ||
    L.corr < kFidelityCorrThreshold;
// ... 对每个非报告 shift：
const bool recovers_shape = e.corr >= kFidelityCorrThreshold;
const bool recovers_scale =
    std::fabs(e.logical_gain_db - L.count_gain_db) <= kGainPreservedDb;
const bool no_clip = e.clip_rate <= rep_clip + 1e-6;
if (recovers_shape && recovers_scale && no_clip) -> FORMAT_MISALIGNMENT
```

---

## §5 文件差异（相对 fix3 全量 `f3128a68…`）

8 修改 + 2 新增（package 内），交付 txt 为独立 dist 工件：

| 文件 | 状态 | 基线行数 → 现在 |
|---|---|---|
| `sdr_adapter/pluto_device.hpp` | 改 | 699 → 755 |
| `sdr_adapter/pluto_device_libiio.cpp` | 改 | 809 → 825 |
| `board_package/iq_digital_loopback_sweep.hpp` | 改 | 564 → 895 |
| `board_package/board_gate9_full_chain_rml23.cpp` | 改 | 2887 → 2950 |
| `board_package/iq_digital_loopback_runner.hpp` | 改 | 626 → 634 |
| `board_package/iq_digital_loopback_transfer.hpp` | 改 | 188 → 230 |
| `host_tests/test_iq_digital_loopback_sweep.cpp` | 改 | 252 → 421 |
| `scripts/analyze_iq_digital_loopback_sweep.py` | 改 | 351 → 649 |
| `scripts/package_iq_digital_loopback_fix4.py` | 新 | — |
| `docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX4_AUDIT.md` | 新 | — |

**未变**：模型 json/raw、标签、正式预处理、production read_rx 默认 libiio 路径、
RTL/XDC/位流/Flash、Stage G A/B/C/D 语义、历史包（fix3 全量 `f3128a68…`、fix3
patch `c87b2b73…` 及更早全部保留）。

**红线遵守**：不新增默认 signed 覆盖、不推荐 `--rx-format-signed=1`、tx_atten 上限
-40 dB 不变、`DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / RF_LEAKAGE_NOT_PROVEN /
arbitrary_modulated_iq_fidelity=BOARD_REQUIRED` 不变。

---

## §6 离线验证（本轮，未碰板）

1. `host_tests/build_host_tests.sh` + `run_tests.sh` → **ALL HOST TESTS PASSED**
   （`test_iq_digital_loopback_sweep` 14 场景 **92/0**；`test_iq_digital_loopback`、
   `test_iq_digital_loopback_sequence`、`test_route_e_raw_rx_output_fields` 无回归）。
2. `host_tests/syntax_check.sh` → `gate9_rml23: syntax OK`（另有 gate7/gate9/gate10 OK）。
3. `analyze_iq_digital_loopback_sweep.py --selfcheck` → **6/6 PASS**（TX16/RX12 计数域、
   真固定衰减、shift 错误、libiio/host 镜像错误、corr 不足、削顶）。
4. 打包器 dependency closure 审计 OK；两份 tarball 独立解包 `sha256sum -c` 全 OK；
   包内文件与工作树逐字节一致。
5. 板端复测命令见 §7，由用户执行；本审计**不**声称板端回环保真已通过。

---

## §7 板端复测（用户执行；不强制写死 ip）

```bash
# 第一步：判责 sweep（-40 dB 上限不变）
./scripts/run_gate9_rml23.sh --phase=iq-digital-loopback-sweep \
  --center=2400000000 --rx-gain=10 --tx-atten=-40 \
  --frozen-dir=DIR --input-kind=radioml-reconstructed-2p56m \
  --sweep-kinds=tone,ramp,prbs --sweep-levels=64,128,256,512 \
  > /root/rml23_route_e_fix4_sweep.log 2>&1
python3 -I scripts/analyze_iq_digital_loopback_sweep.py \
  --log /root/rml23_route_e_fix4_sweep.log \
  --json /root/rml23_route_e_fix4_sweep.json
```

预期：SIGNCHECK ok=1；LEVEL 有 kind/target_rms；rx_libiio≡rx_host_mirror；
count_gain≈-24.08、normalized≈0；SHIFT_SCAN shift0 corr≈1；仅 corr 达标才正式命中
`COUNT_DOMAIN_SCALE`（否则 NOT_PROVEN）；`RECOMMENDATION
action=--digital-loopback-tx-scale=16 semantics=rx_count_domain_to_tx_count_domain`。

第二步（仅确认 COUNT_DOMAIN_SCALE 后）：`--digital-loopback-tx-scale=16` 重跑 4 类
fidelity 门（不加 signed），观测缩放前后 SHA/scale/src/dst domain/clip=0/RX
RMS/corr/fidelity token。

第三步：全部目标文件达 `PRESERVES_IQ` 才允许扩展 24 类。
