# DC 传输适配契约 — fix10class24-original-radioml-dc-ab1（单/双 SDR 共享单一权威）

**Token** `M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DC-AB1-DC-TRANSPORT-ADAPTATION-CONTRACT`

本文件固化「最小 DC 适配对照」的适配数学与三条铁律，是 **singlesdr** 与 **dualsdr** 两个板端
loader/runner 的**单一权威**。机器可读版在同目录 `dc_transport_adaptation_contract.json`；可执行
单一来源是 `scripts/radioml_dc_adapt.py`（主机侧）与 `board_package/radioml_dc_adapt.hpp`（板端
共享头，两个 runner 都 include 它 —— 绝无两套计算）。

本契约是 `tx_derived_conversion_contract.md`（direct 转换，逐字节不变）的**增量**，不重写 direct。

## 1. 目标与两条适配路径

```
direct         现有行为, 逐字节不变:
               iq -> cyclic tile 1024->53760 -> CI16(RMS2048) -> 恢复 -> 前 1024 * unscale

dc-transport   移除原始 IQ 均值 (DC), 只传 AC 分量, RX 恢复后按冻结参数还原尺度 + 加回 DC:
               dc   = mean(iq)                      (复均值: I/Q 分别取均值)
               ac   = iq - dc
               ac   -> cyclic tile 1024->53760 -> CI16(ac, scale = 2048/ac_rms)
               RX 生产恢复 (与 direct 完全一致, 阶段 1)
               ac_r = counts[:1024] * inverse_scale    (阶段 2: TX 尺度还原)
               iq_r = ac_r + dc                         (阶段 3: DC 加回)
```

两条路径共用同一 phase 名, 由 `--adaptation=direct|dc-transport` 区分; direct 保持现有行为,
**无秘密改尺度**。

## 2. 三段式（阶段 1/2/3 严格分离, 严禁双重尺度还原）

| 阶段 | 内容 | direct | dc-transport |
|---|---|---|---|
| 1 RF 链路增益恢复 | `recover_payload_with_coarse_cfo`（16QAM 训练块 + wide-linear + coarse/fine CFO + 分数定时 + payload 增益） | 不变 | **与 direct 完全一致** |
| 2 TX 尺度还原 | 单次乘法把恢复 CI16 counts 映回目标 f32 幅度域 | `* unscale`（`native_rms/2048`） | `* inverse_scale`（`ac_rms/2048`） |
| 3 DC 加回 | 加回均值 | 无 | `+ (dc_i + j*dc_q)` |

* `inverse_scale` 不是 `unscale` 的二次处理: 二者是同一「counts → 目标 f32 域」的尺度。
  direct 目标域 = 原始 IQ 域; dc-transport 目标域 = AC 域。恢复链路内部 gain 恢复（阶段 1）与
  单次乘法（阶段 2）是不同量, **绝无双重还原**。
* `expected.tx_scale ~ 1.0`（因为 `.i16` 已预缩放到 RMS2048）—— 阶段 1 对 direct/dc 同形。

## 3. 逐帧记录（绑定输入 SHA, 绝不绑定类别/识别结果）

| 字段 | 定义 | 口径 |
|---|---|---|
| `dc_i, dc_q` | `mean(iq).real / .imag` | 复均值（可负/零） |
| `ac_rms` | `sqrt(mean(|ac|^2))` | **复 RMS**（与生产 `native_rms` 一致, 非 per-I/Q 分量 RMS） |
| `tx_scale` | `2048 / ac_rms` | TX 量化尺度（作用于 AC） |
| `inverse_scale` | `ac_rms / 2048` | counts → AC f32 域 |
| `native_rms` | `sqrt(mean(|iq|^2))` | 原始 IQ RMS（provenance, 不参与 dc 逆变换） |
| `input_sha` | `sha256(原始 .bin)` | DC 参数绑定键 |

DC 参数以 `input_sha` 为键绑定, 与类别/识别结果**解耦**。

## 4. 22 列 dc-transport 清单（direct 18 列 + DC 4 列）

```
selection_id  hdf5_row_index  raw24_class  modulation  dataset_snr_db  input_file
model_input_sha256  host_pred  tx_payload_file  tx_payload_sha256  native_rms  tx_scale
unscale  peak_pre  peak_post  clip_pre  clip_post  adaptation
dc_i  dc_q  ac_rms  inverse_scale
```

- `adaptation` 列 = `dc_transport_cyclic_tile_1024_to_53760_rms2048_ci16`（逐字节冻结）。
- direct 清单 = 前 18 列, `adaptation` = `cyclic_tile_1024_to_53760_rms2048_ci16`。
- 板端 loader 按 `--adaptation` 选择 18 或 22 列解析, 表头逐字节比对, fail-closed。

## 5. 板端模型窗口（共享头 `radioml_dc_adapt.hpp`）

```cpp
// direct:        tensor[k]   = payload[k].real() * fr.unscale
//                tensor[n+k] = payload[k].imag() * fr.unscale
// dc-transport:  tensor[k]   = payload[k].real() * fr.dc.inverse_scale + fr.dc.dc_i
//                tensor[n+k] = payload[k].imag() * fr.dc.inverse_scale + fr.dc.dc_q
```

`rml24dc::reconstruct_dc_window` 由两个 runner 共用, 数学**只有一份**。

## 6. 数字验证（24 帧, 类无关正确性）

对 short24 的每一帧: `adapt_forward -> adapt_inverse -> 冻结 BF16 推理`, 报告
数值误差/finiteness/裁剪 + 逐帧预测一致（**分类一致, corr/nMSE 不能替代**）。

诚实边界: 数字验证证明 DC 适配本身的确定性往返; 生产恢复在无 RF 时退化为恒等
（CFO=0/定时精确/无 IQ 不平衡/链路增益=1）, 数字验证不声明 C++ 恢复的 Python 等效物。

## 7. 冻结身份（逐字节不变, 与 direct 契约一致）

- 模型 JSON `28272abc…` / RAW `c1781aec…` / CKPT `96cd25f8…`
- 24 类标签序 `rml24::kLabelOrder24`; 480/24 帧身份与 npu-ab1 逐字节一致
- 生产 coarse-CFO + 分数定时 + 广线性恢复; 0.100 门 + 至多 3 次重捕 + 末次选择
- 模型窗口位置/长度、canonical 训练序列、RMS2048、TX 衰减 ≤ −40 dB、RX 手动 35 dB、
  中心 2.4 GHz、速率 2.56 Msps、RX/TX 带宽 18 MHz
- 不训练 / 不调参 / 不换模型 / 不新增滤波/重采样/参考窗搜索

## 8. 四条红绳（永不违反）

1. **direct 逐字节不变** —— 无秘密改尺度; `--adaptation=direct` 的产物与行为 == 现有。
2. **共享实现一份** —— DC 数学只在 `radioml_dc_adapt.{py,hpp}`, 单/双 SDR 都调用同一份。
3. **三段式不双重还原** —— 阶段 1（RF 增益）/ 阶段 2（TX 尺度）/ 阶段 3（DC 加回）严格分离。
4. **DC 参数绑定 input SHA** —— 绝不绑定类别/识别结果; 门拒/缺失 = 失败（不从分母剔除）,
   hard_invalid 绝不强制。
