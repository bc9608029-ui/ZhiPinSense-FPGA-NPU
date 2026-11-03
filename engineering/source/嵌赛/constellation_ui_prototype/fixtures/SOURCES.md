# 测试夹具来源与校验（SOURCES.md）

本目录只包含**少量真实 IQ 文件 + 对应的 JSON 元数据 sidecar**，用于离线星座图原型的功能验证。
不复制整数据集、不复制模型权重。所有二进制文件均为字节级复制（复制后 SHA-256 与原文件一致）。

夹具分为两组（hotfix1 起）：

- **`valid/`**：可正常播放的真实 IQ 帧（4 帧）。
- **`negative/`**：必须 fail-closed 的负样本（7 个）。
- **`obsolete/`**：已移出的旧夹具与旧 sidecar（历史证据，任何测试/UI 都不读取，见 `obsolete/README.md`）。

## 源文件（只读参考树，未修改）

| 源文件（绝对路径） | 源 SHA-256 |
|---|---|
| `F:\嵌赛\fix10clean2b_work\clean2b_smoke\source_clean_bpsk.f32` | `2bd781bfdc21b327cefd360306095beaefcf601edb1e649764d1cfc7c243d880` |
| `F:\嵌赛\fix10clean2b_work\clean2b_smoke\source_clean_4ask.f32` | `af2787ecb4fb0dcfc0ec622f92107873020c7c367f685b2b7b4c82c7b102446f` |
| `F:\嵌赛\fix10clean2b_work\clean2b_smoke\recovered_tensor_clean_bpsk.f32` | `38ba788a3bcbe20c16d91b3dbed1835c7b8697d8f575a1c5b20da96303bd2f79` |
| `F:\嵌赛\fix10clean2b_work\clean2b_smoke\recovered_tensor_clean_4ask.f32` | `c677f61ac6c593c15e923367425699071f43c714fb63f8ea93b84b266365b4aa` |
| `F:\嵌赛\fix10clean2b_work\clean2b_smoke\clean_bpsk_4713bc2e.ci16` | `4713bc2e2f0612748ef7fc05c95d5ecd3ee0368b7cf3b3935ff36f4e367843ee`（**已移出正常夹具，见下**） |

## `valid/` 夹具与源文件的对应关系

| 夹具文件 | 来源 | SHA-256（复制后验证一致） | 说明 |
|---|---|---|---|
| `bpsk_clean_model_input.f32` | `source_clean_bpsk.f32` | `2bd781bf…d880` | BPSK 实际 [2,1024] 模型输入（planar f32，8192 字节） |
| `ask4_clean_model_input.f32` | `source_clean_4ask.f32` | `af2787ec…446f` | 4ASK 实际 [2,1024] 模型输入（planar f32，8192 字节） |
| `bpsk_recovered_payload.f32` | `recovered_tensor_clean_bpsk.f32` | `38ba788a…2f79` | BPSK D2 恢复载荷（planar f32，8192 字节） |
| `ask4_recovered_payload.f32` | `recovered_tensor_clean_4ask.f32` | `c677f61a…4aa` | 4ASK D2 恢复载荷（planar f32，8192 字节） |

## `negative/` 夹具（必须 fail-closed）

| 夹具文件 | 二进制来源 | 说明 |
|---|---|---|
| `wrong_sha.f32` | `source_clean_bpsk.f32`（字节复制） | sidecar `payload_sha256` 伪造成 64 个零 → 必须拒绝 |
| `wrong_length.f32` | `source_clean_bpsk.f32`（字节复制） | sidecar `complex_count` 伪造成 2048 → 长度不匹配必须拒绝 |
| `nan_inf.f32` | 由夹具生成脚本生成（注入 NaN/Inf） | 8 复采样 planar f32，注入 NaN/Inf → 必须拒绝 |
| `unknown_schema.f32` | `source_clean_bpsk.f32`（字节复制） | `schema_version` 伪造成 2 → 必须拒绝 |
| `unknown_dtype.f32` | `source_clean_bpsk.f32`（字节复制） | `dtype` 伪造成 `<f8` → 必须拒绝 |
| `unknown_layout.f32` | `source_clean_bpsk.f32`（字节复制） | `layout` 伪造成 `column-major` → 必须拒绝 |
| `unknown_stage.f32` | `source_clean_bpsk.f32`（字节复制） | `stage` 伪造成 `FAKE_STAGE` → 必须拒绝 |

## 关键说明（hotfix1 语义修正）

1. **RAW_RX 无真实夹具**：原 `bpsk_raw_rx.ci16` 实为 clean2b 的 **D2 TX / 冻结载荷**（`clean_bpsk_4713bc2e.ci16`），**不是**真实 SDR 原始接收。已移入 `obsolete/`，且**没有**真实板端采集数据前**不新增伪造 RAW_RX**。UI 图例下方明确显示「RAW_RX 暂无真实夹具」。
2. **`confidence` 是示意性占位值**（BPSK=0.98、4ASK=0.96），**不是真实模型输出**。sidecar 用 `"confidence_valid": false` + `"metric_provenance": "placeholder"` 显式标注，UI 显示「占位/不可用」。本离线 UI 不运行模型、不改模型输入、不含分类算法；`predicted_class`/`baseline_class` 来自 `source_index`（1500=BPSK、500=4ASK）的类别映射，仅用于展示 UI 字段语义。
3. **`cfo_hz` / `sro_ppm`**：真实值来自 `iq_rf_sync_recovery.hpp` 的 `PerFileRecovery`；本离线原型未对这批数据重新计算，故 `"cfo_valid": false` / `"sro_valid": false`，UI 显示「不可用」。
4. **`gain_mag` 与 `d2_rec_scale` 分开**：`gain_mag` 是真实 RF 增益幅度，仅当 `"gain_valid": true` 才显示；本夹具集 `gain_valid=false`（无真实 RF 增益测量），UI 显示「不可用」。RECOVERED_PAYLOAD 夹具中的恢复标量以 **`d2_rec_scale`** 命名（BPSK=0.98077767、4ASK=0.997743875，`recovery_metrics_valid=true`，`metric_provenance="clean2b-d2-recovery"`），**绝不冒充 RF gain_mag**。
5. **`symbol_timing_valid` 全部为 false**：因此 UI 的「符号采样（SYMBOL_SAMPLED）」视图始终为 DISABLED，绝不通过降采样伪造符号点。
6. **有效性字段缺省策略（fail-closed）**：`confidence_valid` / `recovery_metrics_valid` / `gain_valid` / `cfo_valid` / `sro_valid` 缺失时默认 `false`（不可用），`metric_provenance` 缺失时为空。因此数值 `0` 永不被当作「真实测得的 0」。
