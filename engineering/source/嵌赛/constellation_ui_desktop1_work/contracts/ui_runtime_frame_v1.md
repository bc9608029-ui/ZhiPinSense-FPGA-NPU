# 运行时帧数据契约（ui_runtime_frame_v1.md）

M29 RML23 星座图 UI（`constellation_ui_desktop1_work`）运行时消费的帧数据契约。
本文件是**唯一权威口径**：离线 `FileIqFrameSource` 与未来实时源（UnixSocket / SharedMemory）
必须产出同一 `IqFrame` 语义，才能复用同一渲染路径。本文档与
`docs/data_format.md`（磁盘序列化）、`docs/future_live_integration.md`（实时集成接口）一致；
如有冲突，以代码 `src/IqFrame.hpp` / `src/IqFrameLoader.cpp` 为准。

## 1. 版本

- `schema_version = 1`（sidecar 序列化版本）。
- 帧源接口版本：`class IqFrameSource`（`src/IqFrame.hpp`），本阶段**只定义接口**，仅实现
  `FileIqFrameSource`。

## 2. 帧源接口（运行时唯一入口）

```cpp
class IqFrameSource {
public:
    virtual ~IqFrameSource() = default;
    // 拉取下一帧。返回 false 表示流结束或硬错误（error 被填充）。
    // 损坏帧必须停止播放，绝不自动跳过。
    virtual bool nextFrame(IqFrame& frame, std::string& error) = 0;
};
```

渲染器（`ConstellationItem`）与 `Controller` 只消费 `IqFrame`，与来源无关。实时集成时只需
把 `Controller::onTimer()/step()` 里“读 sidecar 文件”替换为 `source_->nextFrame(frame, err)`，
`applyFrame()`（抽稀 / 坐标 / 颜色 / 推送渲染）**完全不变**。

## 3. 规范帧结构 `IqFrame`（内存态）

Qt-free 纯 C++17 结构，字段见 `src/IqFrame.hpp`。运行时任何来源都必须填充以下**必填**字段，
否则 loader / 渲染按 fail-closed 拒绝：

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `stage` | `Stage` | 是 | `RawRx`/`RecoveredPayload`/`ModelInput`/`SymbolSampled`，见 §5 |
| `dtype` | `DType` | 是 | `I16`(`<i2`) 或 `F32`(`<f4`) |
| `layout` | `Layout` | 是 | `Planar` 或 `Interleaved` |
| `complex_count` | `uint64` | 是 | 复采样个数（正整数） |
| `i` / `q` | `vector<float>` | 是 | 长度均为 `complex_count` |
| `payload_sha256` | `string` | 是 | 64 位小写十六进制，二进制整体 SHA-256 |
| `iq_file` | `string` | 是 | 裸文件名（禁路径分隔符 / `..`） |

可选元数据字段（`frame_id`/`sample_rate_hz`/`source_index`/`modulation`/`predicted_class`/
`baseline_class`/`confidence`/`cfo_hz`/`sro_ppm`/`gain_mag`/`d2_rec_scale`）与对应的
`*_valid` 标志（`confidence_valid`/`cfo_valid`/`sro_valid`/`gain_valid`/`recovery_metrics_valid`/
`symbol_timing_valid`）以及 `metric_provenance`：**任一指标只有在 `*_valid == true` 时才可作为
真实测量显示**；缺失/类型非法一律按 `false`（不可用），数值 `0` 永不被当作“真实测得的 0”。

## 4. 磁盘序列化（sidecar + 二进制 IQ）

任何来源产出的帧，若落盘，必须满足 `docs/data_format.md` 的扁平 sidecar 契约：

- **sidecar**：一层扁平 JSON（拒绝嵌套容器、未知 `schema_version`、未知 `dtype`/`layout`、
  重复字段、非有限数值、`confidence ∉ [0,1]`）。
- **二进制**：小端；`<i2`=4B/复采样（planar=`I0..N-1` 后 `Q0..N-1`，interleaved=`I0,Q0,…`），
  `<f4`=8B/复采样。`MODEL_INPUT` 使用 **planar f32 `[2,1024]`**（`real[0:1024]`+`imag[0:1024]`）。

**校验链（fail-closed，任一步失败整体拒绝并停止播放，绝不自动跳过）**：

1. sidecar 可读且 JSON 合法（扁平）；2. `schema_version == 1`；3. `stage`/`dtype`/`layout`
已知枚举；4. `complex_count` 正整数；5. `payload_sha256` 64 位十六进制；6. `iq_file` 安全裸名；
7. 二进制字节数 == `complex_count × bytes_per_complex`；8. 二进制 SHA-256 == `payload_sha256`；
9. F32 逐样本拒绝 NaN/Inf。

## 5. 四视图语义（不混用，颜色永不是唯一信息源）

| stage | 含义 | 颜色 | 备注 |
|---|---|---|---|
| `RAW_RX` | SDR 原始采样（含噪声/CFO/增益/过采样） | 灰白 `#D0D4D8` | **只接受真实 SDR 原始接收数据**，禁伪造 |
| `RECOVERED_PAYLOAD` | 同步+CFO/SRO+增益恢复后的载荷（可能过采样） | 青 `#22C3E6` | |
| `MODEL_INPUT` | 实际送入 NPU 的 `[2,1024]` 张量 | 绿 `#3DDC84` | |
| `SYMBOL_SAMPLED` | 每符号星座点 | 黄 `#E8C93C` | **仅 `symbol_timing_valid==true`**，否则视图 DISABLED；UI 绝不用降采样伪造符号点 |

越界点（超出 `[-r,+r]`）标红 `#E5605F`，只钳位绘制、不静默丢弃。

## 6. 坐标渲染（确定性）

- 星座在**居中正方形**内绘制，I/Q 同刻度，原点居中，范围对称 `[-r,+r]`。
- `r`：`AUTO`（\|I\|,\|Q\| 合并幅值 98 分位 ×1.10，稳健抗离群）/ `FIXED_1` / `FIXED_2` / `CUSTOM`。
- 抽稀 `decimate_indices(n, max_points)`：确定性等距索引，`idx[0]==0`，**绝无逐帧随机**（不闪烁）。
- 全部坐标/抽稀数学为 C++ 纯函数，**从不走 QML JS**。

## 7. 中文字体部署前置条件

UI 文本为中文，运行时环境**必须**具备 CJK 字体回退，否则渲染为豆腐块（tofu）。桌面/WSLg
验证已安装 Microsoft YaHei（`msyh.ttc`）+ SimHei（`simhei.ttf`）到 `~/.local/share/fonts/`
并 `fc-cache -f`，`fc-match -s "sans-serif:lang=zh"` 命中。板端集成前必须在目标文件系统
部署等价 CJK 字体 + fontconfig 缓存，否则中文 UI 不可读。

## 8. 离线模拟器（offline_frame_simulator.py）

`tools/offline_frame_simulator.py` 生成**确定性**合成帧，仅用于四视图渲染验证（**不是真实 RF**）：
- `metric_provenance = "synthetic-offline-desktop1"`，`source_index = -1`，`confidence_valid=false`
  等全部 `*_valid=false`，绝不冒充真实测量。
- `payload_sha256` 为所写二进制的真实 SHA-256（fail-closed 可校验）。
- 四阶段：`raw_rx`（QPSK 8sps+CFO+DC+12dB 噪声）、`recovered_payload`（QPSK 4sps+26dB 残差）、
  `model_input`（BPSK [2,1024]）、`symbol_sampled`（16QAM 1sps+30dB，`symbol_timing_valid=true`）。
- **红线**：合成夹具只放在 `fixtures/synthetic/`，标注清晰，不得与真实夹具 `fixtures/valid/`
  混放，不得标注为 `real` / 真实板端数据。`RAW_RX` 合成仅用于渲染验证，不代表存在真实 RAW_RX 夹具。
