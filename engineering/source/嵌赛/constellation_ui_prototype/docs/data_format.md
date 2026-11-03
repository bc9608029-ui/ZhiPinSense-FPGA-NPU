# 数据格式约定（data_format.md）

M29 RML23 离线星座图原型读取两类文件，成对出现：

1. **JSON 元数据 sidecar**（描述如何解读二进制文件）；
2. **二进制 IQ 文件**（`.f32` 或 `.ci16`），与 sidecar 位于同一目录，文件名由 sidecar 的 `iq_file` 字段给出。

## 1. JSON sidecar（schema_version=1，扁平对象）

只允许一层扁平对象（标量字段）。**拒绝**嵌套数组/对象、未知 `schema_version`、未知 `dtype`/`layout`、重复字段、非有限数值、以及 `confidence` 超出 [0,1]。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | number | 是 | 仅接受整数 `1`；其他一律拒绝 |
| `stage` | string | 是 | `RAW_RX` / `RECOVERED_PAYLOAD` / `MODEL_INPUT` / `SYMBOL_SAMPLED` |
| `dtype` | string | 是 | `"<i2"`（CI16）或 `"<f4"`（F32）；**绝不从扩展名推断** |
| `layout` | string | 是 | `"planar"` 或 `"interleaved"` |
| `complex_count` | number | 是 | 正整数，复采样个数 |
| `payload_sha256` | string | 是 | 64 位小写十六进制，二进制文件整体 SHA-256 |
| `iq_file` | string | 是 | 二进制文件名（禁止路径分隔符 / `..`） |
| `frame_id` | number | 否 | 非负整数，用于目录播放排序与重复/回退告警 |
| `sample_rate_hz` | number | 否 | 非负整数 |
| `source_index` | number | 否 | 数据集源索引 |
| `modulation` | string | 否 | 例如 `BPSK`、`4ASK` |
| `predicted_class` | string | 否 | 预测类别 |
| `baseline_class` | string | 否 | 基线类别（用于一致性比对） |
| `confidence` | number | 否 | 必须 ∈ [0,1] 且有限 |
| `confidence_valid` | bool | 否 | 缺省 `false`（不可用）；仅 `true` 时 `confidence` 才作为真实测量显示 |
| `cfo_hz` / `sro_ppm` | number | 否 | 必须有限 |
| `cfo_valid` / `sro_valid` | bool | 否 | 缺省 `false`（不可用） |
| `gain_mag` | number | 否 | 必须有限；仅当 `gain_valid=true` 才显示为真实 RF 增益幅度 |
| `gain_valid` | bool | 否 | 缺省 `false`（不可用） |
| `d2_rec_scale` | number | 否 | 非负且有限；D2 恢复标量，**绝不显示为 RF `gain_mag`** |
| `recovery_metrics_valid` | bool | 否 | 缺省 `false`；`true` 表示恢复流程产出并标注了随附恢复指标 |
| `metric_provenance` | string | 否 | 例如 `placeholder` / `clean2b-d2-recovery` / `real`；缺省空串 |
| `symbol_timing_valid` | bool | 否 | 见下文红线 |

**有效性字段缺省策略（fail-closed）**：上述 `*_valid` 字段缺失或类型非法时一律按 `false`（不可用）处理，`metric_provenance` 缺失按空串处理。因此数值 `0` 永远不会被当作“真实测得的 0”显示；UI 显示「占位/不可用」或「不可用」。

**红线**：`stage == "SYMBOL_SAMPLED"` 时 `symbol_timing_valid` 必须为 `true`，否则拒绝加载。UI 绝不用降采样伪造符号采样点。

## 2. 二进制 IQ 文件

全部为**小端（little-endian）**，按 `dtype` + `layout` 组合解析：

| dtype | layout | 字节/复采样 | 布局 |
|---|---|---|---|
| `<i2` | `interleaved` | 4 | `I0,Q0,I1,Q1,…`（int16 LE） |
| `<i2` | `planar` | 4 | `I0..I_{N-1}` 然后 `Q0..Q_{N-1}` |
| `<f4` | `interleaved` | 8 | `I0,Q0,I1,Q1,…`（float32 LE） |
| `<f4` | `planar` | 8 | `real[0:N]` 然后 `imag[0:N]` |

`MODEL_INPUT` 使用 **planar f32 `[2,1024]`**（RadioML 兼容张量：`real[0:1024]` + `imag[0:1024]`）。

校验链（fail-closed，任何一步失败即整体拒绝并停止播放，绝不自动跳过）：

1. sidecar 可读且 JSON 合法（扁平）；
2. `schema_version == 1`；
3. `stage` / `dtype` / `layout` 为已知枚举；
4. `complex_count` 为正整数；
5. `payload_sha256` 为 64 位十六进制；
6. `iq_file` 为安全裸文件名；
7. 二进制文件字节数 == `complex_count × bytes_per_complex`（长度不匹配拒绝）；
8. 二进制文件 SHA-256 == `payload_sha256`（SHA 不匹配拒绝）；
9. F32 逐样本拒绝 NaN/Inf（CI16 无此表示，天然安全）。

## 3. 视图语义（四视图，不混用）

- `RAW_RX`：SDR 原始采样（含噪声/CFO/增益/过采样），颜色灰白。
- `RECOVERED_PAYLOAD`：同步 + CFO/SRO + 增益恢复后的载荷（可能过采样），颜色青色。
- `MODEL_INPUT`：实际送入 NPU 的 `[2,1024]` 张量，颜色绿色。
- `SYMBOL_SAMPLED`：仅当 `symbol_timing_valid=true` 才可用，颜色黄色；否则视图 DISABLED。

**RAW_RX 红线**：`RAW_RX` 只接受真实 SDR 原始接收数据。clean2b 的 D2 TX / 冻结载荷（`clean_bpsk_*.ci16`）**不是** RAW_RX，禁止标注为 RAW_RX。没有真实板端采集数据前，不新增 RAW_RX 夹具；UI 显示「RAW_RX 暂无真实夹具」。

## 4. 渲染坐标

- 星座图在**居中正方形**内绘制，I/Q 同刻度，原点居中，范围对称 `[-r, +r]`。
- `r` 取值：`AUTO`（|I|,|Q| 合并幅值的 98 分位 × 1.10，稳健抗离群）、`FIXED_1`（r=1）、`FIXED_2`（r=2）、`CUSTOM`（用户给定，>0）。
- 超出 `[-r,+r]` 的点标记为越界（红色），只钳位绘制、不静默丢弃；颜色永不是唯一信息源（阶段文字 + 图例始终可见）。
