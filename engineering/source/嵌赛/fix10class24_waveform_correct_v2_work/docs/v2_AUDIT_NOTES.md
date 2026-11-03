# 波形正确性 v2 审计笔记

Token: `M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2`

## v1 未被覆盖的证明（回报 ⑥）

v1 全部历史保留在 `F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\`，逐字不动：
- `dist/fix1_independent_rx_PATCH.tar.gz`  SHA `06c3ce495e2415d9f8b343f11c9e1c0923e897aa7a8d6b5465c56f7dce94df79`
- `dist/fix1_independent_rx_INPUTS.tar.gz` SHA `898bcaa50530e8a06345d4163f3845f7c79ca0fbf8ff6ce45090a4e9a99a7466`
- `tx_package/public_protocol_tx_manifest.tsv` SHA `a1b6c9da10e62c1f4297a6d9ab797e4e6deadff04b5ed8cf3df382a18e659ef5`
- `replay_out/independent_rx_replay.tsv` SHA `cfe68bdcd34bcb9f6f3705c936395527076bec374b5a7736547c9fa3b1dd560c`

v2 在**独立目录** `F:\嵌赛\fix10class24_waveform_correct_v2_work\`。v2 脚本只 import
冻结生成器 / fix1 契约（vendored 逐字副本 `aa5fe816…`/`0839fc40…`/`df5ff700…`/
`207552e2…`），不 import 回 v1 目录，不写 v1 任何文件。

## 修正内容（F1/F2/F3 + DSB-SC）

| id | v1 缺陷 | v2 修正 |
|---|---|---|
| F1 | `_hilbert` 返 `.real`=恒等 | 返 `.imag`=真 Hilbert |
| F2 | 因 F1，SSB 实为 DSB | 真解析 → USB 单边带 |
| F3 | SC 仅 m 更大、载波仍在 | SSB-SC 去 DC、DSB-SC 去 ±fc |
| DSB-SC | 与 WC 只差 m | 真抑制 ±fc 载波 |

只改 4 个 AM 类；其余 20 类（含 GMSK=22/OQPSK=23 红线）逐字复用冻结，字节一致已自检。

## 逐项核查结果（回报 ②）

见 `contract/v2_waveform_correctness.json`（5 判据全 PASS，37/37 自检）：
- C1 Hilbert 正交 ortho(true)=1.76e-18（identity=1.00，证明检测器能抓 F1）
- C2 SSB 单边 SSB-SC neg_frac=5.0e-32（USB）
- C3 DSB 对称 DSB-SC sym=5.6e-17
- C4 SC 抑制 SSB-SC −40.0 dB / DSB-SC −41.1 dB
- C5 WC 存在 SSB-WC +21.4 dB / DSB-WC +24.8 dB

## 诚实红线

不反向改波形凑 24/24。orig 层是 v2 修正波形数字直送（无 RF/无恢复误差）。若 orig 在
冻结 BF16 下误分类，如实记录为「模型与新波形域不匹配」，不掩盖、不归因 RF。结果见
replay summary 的 `model_vs_new_waveform_domain_mismatch` 字段。

## 幅度合同 v2

`max_peak_v2`（24 类 v2 波形最大峰）→ `S_v2=1600/max_peak_v2=71.609111379`、
`1/S_v2`。三量分离同 fix1，仅常数随波形更新。
