# obsolete/ — 已移出的旧夹具（保留为历史证据，不参与播放）

这些文件在 hotfix1（ui-constellation-prep1-hotfix1）中从正常夹具集**移出**，仅保留作历史对照，任何测试或 UI 都不读取本目录。

| 文件 | 移出原因 |
|---|---|
| `bpsk_raw_rx.ci16` / `bpsk_raw_rx.json` | 该 `.ci16` 实为 clean2b 的 **D2 TX / 冻结载荷**（`clean_bpsk_4713bc2e.ci16`），**不是**真实 SDR 原始接收（RAW_RX）。没有真实板端采集的 RAW_RX 数据前，不新增伪造 RAW_RX。 |
| 其余 8 个 `*.json` | 旧扁平目录结构的 sidecar（引用已被移动到 `valid/`、`negative/` 的二进制文件，且缺少有效性字段）。已用带 `confidence_valid` / `cfo_valid` / `sro_valid` / `gain_valid` / `recovery_metrics_valid` / `metric_provenance` / `d2_rec_scale` 的新 sidecar 重写于 `valid/` 与 `negative/`。 |

正确夹具位置：

- `valid/`：4 个可正常播放的真实 IQ 帧。
- `negative/`：7 个必须 fail-closed 的负样本（wrong_sha / wrong_length / nan_inf / unknown_schema / unknown_dtype / unknown_layout / unknown_stage）。
