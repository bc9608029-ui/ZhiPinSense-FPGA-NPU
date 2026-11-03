# RML23 板端模型部署契约 (M29 Phase F5)

本目录承载 F5 实时主链唯一权威的 NPU 模型（expA_bf16_head 候选），
沿用现有 bitstream，不重新生成位流。两个文件与 23 类标签契约的 SHA 均冻结，
任何不一致都会被 `scripts/verify_package.sh` 以非零退出码拒绝。

## 冻结文件与 SHA256

| 文件 | 大小 | SHA256 (hex) |
|---|---|---|
| `model_24class_ZG.json` | 223501 B | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` |
| `model_24class_ZG.raw`  | 2857720 B | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` |
| `model_rml23.sha256`    | —        | 上述两行的 `sha256sum -c` 清单（不含自身） |

- `--model-json` 指向 `.json`（iCraft `Network::CreateFromJsonFile` 网络描述）。
- `--model-raw` 指向 `.raw`（`lazyLoadParamsFromFile` 权重，`params_md5=7966a4829fc713b2e8ea6c04168be263`）。
- 运行时 `--model-sha` 传 RAW SHA 前缀 `2425d990dbac0761…`（结果记录的 `model_sha` 溯源字段）。

## 源模型身份（溯源，非本目录文件）

- `source_model_name` = `RML2018_24_BENCHMARK`
- `source_checkpoint_sha256` = `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d`
  （`rml24_seed2027_best.pt`，24 类闭集基线）
- 目标设备 `@zhuget(330)`，`target_device` = `@zhuget(330)`
- NPU 设备 URL：`axi://zg330aiu?npu=0x40000000&dma=0x80000000`

## 输入 / 输出契约（与 F1/F4 冻结一致，不可改）

- 输入：`[1, 2, 1024]` fp32，C-order 平面 I/Q（前 1024 = I，后 1024 = Q），
  共 8192 字节，小端；`no_transinput=true`；`normalization=none_rms_already_1.0`
  （样本已 RMS≈1.0，模型不做归一化）；采样 128000 Hz。
- 输出：`[1, 24]` fp32 原始 logits（无 softmax），24 类源标签序见
  `contracts/rml23_merged_contract.py::SOURCE_LABEL_ORDER_24`。
- 本目录模型**不做** 24→23 合并：合并由软件 `board_package/rml23_merged.hpp`
  在 NPU 输出后完成（AM-SSB-WC/SC → AM-SSB 的 logaddexp 折叠）。

## 标签契约 SHA

| 契约 | SHA256 |
|---|---|
| 源 24 类标签序 | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` |
| 部署 23 类标签序 | `15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88` |
| 合并契约 | `f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e` |
| 预处理契约 | `edb11ec3f723e60b38f682e458b6f6a946a913e56310e9b59ef0ddbddb72229c` |

SHA 计算约定：`sha256(json.dumps(list(...), sort_keys=True, separators=(",", ":")))`
（见 `docs/M29_PHASE_F1_RML23_MERGED_CONTRACT.md`）。板上由
`contracts/rml23_merged_contract.py` 重算并 fail-closed 校验。

## 专家接口（预留禁用态）

`expert_enabled=false`，`expert_result=NOT_RUN`。无假专家、无规则式 SC/WC 拆分。
`raw_24_logits` / `raw_24_top1` 在结果记录中保留，供未来 SC/WC 专家使用。

## 红线

- 禁碰板 / 禁写 Flash / 禁访问 test split / 禁自动启动 QAT / 不训练专家模型。
- 不改 Vivado/RTL/XDC，沿用现有 bitstream（`22fec95c…`）。
- 本目录模型文件二进制为板端 aarch64 运行时直接加载；不得替换为 x86/WSL 产物。
