# M29 RML23 FIX10CLASS24 — 24-Class Clean-IQ D2 Offline Asset Preparation (任务四)

**Status token:** `M29-RML23-FIX10CLASS24-OFFLINE-ASSETS-READY-FOR-INTEGRATION`

This document is the authoritative offline audit for **fix10class24-prep1** (任务四).
All work was performed entirely offline on the Windows dev machine, inside a single
new directory, without touching the board, any SDR, any runner, or the network.

## 1. Scope and hard constraints honored

| Constraint | Compliance |
|---|---|
| Work only in `F:\嵌赛\fix10class24_prep1_work\` | YES — all scripts/tests/artifacts/docs live here |
| Six READ-ONLY dirs never created/edited/deleted | YES — only imported `reconstruct`/`recovered_tensor_1024` from the D2 authority and the frozen contract |
| No board / SDR / runner / network | YES — pure offline HDF5 + frozen-checkpoint inference |
| Fixed non-selectable sample rule | YES — `source_index = class_index × 500`, `k=0` (see §4) |
| No confidence picking / swapping / class exclusion | YES — none of the 24 classes excluded, no fallback on failure |
| D2 math never re-implemented | YES — only `analyze_route_d2_4ask.reconstruct(...)` and `.recovered_tensor_1024(...)` imported |
| Deterministic two-run byte-identity | YES — `deterministic_two_run=PASS` (see §8) |

## 2. Inputs and frozen SHAs (all recomputed this session)

| Input | Path | SHA-256 | vs clean2a audit |
|---|---|---|---|
| clean24 formal12000 dataset | `F:\嵌赛\fix10clean2a_dataset\clean24_formal12000.hdf5` | `8b3efe0b11143b31972d392f5b85bc8bd3faf7973681c4d5d7da7ed9603ed81a` | MATCH (82 185 391 bytes) |
| frozen predictions TSV | `F:\嵌赛\fix10clean2a_results\frozen_model_predictions_formal12000.tsv` | `dd1938fa34989fa2853a46e6d298630c7984ad4e5661dd77f9635d0fecf2ba71` | MATCH |
| 24→23 merged contract | `...\board_rml23_live\contracts\rml23_merged_contract.py` | `31deebc03ca9c36fafb7cd69b85a60dae2bbaff5e3be7a1f7899fc1fae64a48e` | — |
| D2 authority (`reconstruct` source) | `...\fix10clean2b\...\scripts\analyze_route_d2_4ask.py` | `0324899eaad37de487ee2dc950c0af54eec3a753f941caba75e2de3d1f525bfa` | — |
| frozen checkpoint `best.pt` | `...\_frozen\runs\rml24_base\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt` | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` | — |

The build script (`scripts\build_clean24_smoke_d2.py`) fail-closes on all five SHAs
before producing any artifact; the verifier (`scripts\verify_clean24_smoke_roundtrip.py`)
additionally fail-closes on the checkpoint SHA at model load.

## 3. Fixed D2 parameters (== fix10clean2b smoke)

```
global_K        = 2048.0
edge_policy     = zero
guard           = 832
sample_rate     = 2560000 Hz
complex_count   = 53760   (ci16 = 215040 bytes; source/recovered = 8192 bytes)
target_rms      = 2048
split_role      = holdout
snr_db          = nan
selection_rule  = first_per_class_k0
```

## 4. Fixed selection rule (24 source indices)

`source_index = class_index × 500`, `seed = 2000000 + source_index`, `k = 0`.

| ci | raw24 label | source_index | seed | ci | raw24 label | source_index | seed |
|---|---|---|---|---|---|---|---|
| 0 | OOK | 0 | 2000000 | 12 | 16QAM | 6000 | 2006000 |
| 1 | 4ASK | 500 | 2000500 | 13 | 32QAM | 6500 | 2006500 |
| 2 | 8ASK | 1000 | 2001000 | 14 | 64QAM | 7000 | 2007000 |
| 3 | BPSK | 1500 | 2001500 | 15 | 128QAM | 7500 | 2007500 |
| 4 | QPSK | 2000 | 2002000 | 16 | 256QAM | 8000 | 2008000 |
| 5 | 8PSK | 2500 | 2002500 | 17 | AM-SSB-WC | 8500 | 2008500 |
| 6 | 16PSK | 3000 | 2003000 | 18 | AM-SSB-SC | 9000 | 2009000 |
| 7 | 32PSK | 3500 | 2003500 | 19 | AM-DSB-WC | 9500 | 2009500 |
| 8 | 16APSK | 4000 | 2004000 | 20 | AM-DSB-SC | 10000 | 2010000 |
| 9 | 32APSK | 4500 | 2004500 | 21 | FM | 10500 | 2010500 |
| 10 | 64APSK | 5000 | 2005000 | 22 | GMSK | 11000 | 2011000 |
| 11 | 128APSK | 5500 | 2005500 | 23 | OQPSK | 11500 | 2011500 |

Labels are derived ONLY from `rml23_merged_contract.SOURCE_LABEL_ORDER_24` /
`SOURCE_TO_DEPLOYED` — never hand-written in the build script.

## 5. 24→23 coverage gate (unique AM-SSB merge)

`raw24_to_deployed23_mapping.tsv` maps 22 source classes 1:1 and merges exactly
`AM-SSB-WC`(17) + `AM-SSB-SC`(18) → `AM-SSB`(deployed23 index 17).
Result: `raw24 coverage = 24/24`, `deployed23 coverage = 23/23`,
`AM-SSB` slot count = 2, every other deployed slot count = 1.

## 6. Per-class artifact SHAs (full, from clean24_smoke_SHA256SUMS.txt)

| raw24 label | source_index | CI16 SHA-256 | source F32 SHA-256 | recovered F32 SHA-256 |
|---|---|---|---|---|
| OOK | 0 | `210e585d9a7d87e916d6035a9ac6713ab4abed436db28d83d890ec420b152308` | `9e86247ba9115fa49430bcfdbd711d63485da650d5004ca6cd6c689d3a685bc1` | `04b410d13beec26612b8827ee7220e0a3dc100e65bb000b5a063b7141793eb99` |
| 4ASK | 500 | `a413e2d40d259597a0492c813c29a3b9701445e962527c835c61eb1a423af11f` | `af2787ecb4fb0dcfc0ec622f92107873020c7c367f685b2b7b4c82c7b102446f` | `c677f61ac6c593c15e923367425699071f43c714fb63f8ea93b84b266365b4aa` |
| 8ASK | 1000 | `d5ca9b1f04f920cf62260cc35a6af7f00c49d3f38d83f6b265b50f36848c3303` | `2f0a93d17d6852ffe80233169d12361f2746942f3f5555fc9669f04f7fe30911` | `f8a39fab1166cd5365a76b99554c930f532390bf3a09d48c52441930bce2168c` |
| BPSK | 1500 | `4713bc2e2f0612748ef7fc05c95d5ecd3ee0368b7cf3b3935ff36f4e367843ee` | `2bd781bfdc21b327cefd360306095beaefcf601edb1e649764d1cfc7c243d880` | `38ba788a3bcbe20c16d91b3dbed1835c7b8697d8f575a1c5b20da96303bd2f79` |
| QPSK | 2000 | `99f302baa600362c37d80b7efd056ef3919811143a3978d43ff786ccb91597a0` | `6947a63591659d5cdf3a532596b3f41a9d46e5515cccdea8a862fb2c8f10862c` | `9490fd60490db9d3a6f8fb29067e06406ad872e1935190f00b5798f544d2547f` |
| 8PSK | 2500 | `c45dfffad0883bdfd34045313000e22081dd716b7966f49fc50221bde55403e5` | `659aef19471825c7403a319080407aa2a6b603e8a6ca576226592d9a0f5940d3` | `d87ebb8763686970745ea2dd3ba81852f44ed4c724f29dc156be3035c04be6f7` |
| 16PSK | 3000 | `354bf2acb1112d5fcec06e89bb8c36d502fa8b1e9b1f98d573bd963df020423e` | `00bdd71a1fecce4d8b5b989739f8a777b537dba9087b963679029265c9ca45d6` | `7c917fa5be5d909a48065837928d4a11f4ee169ae55dae170b141c72b9c404c9` |
| 32PSK | 3500 | `e4f904abca8a0d8065b8703b9789654618698b76d6ff6588332f4e26bf92005e` | `4f8738eb5de417adf40bd271705261d2dda6f9f2de8a831334f9e7024cb21a75` | `d3a0cd18a6c3a4cab706c654de157ecfb2f57580e5e39aae202fbfd9a04099d1` |
| 16APSK | 4000 | `ae10feedbd61b06d5cb3451f7b24a872142b2bd68d5b2908a5265065da3a1850` | `09e3127cb462e7939127b1c2d79cd6b9f5b148d2a12b35af317c84a8eef04234` | `f8313cb2adcca6e32e4fcb81d0499838cfb7cd7b00e946d07c2f6f479376dfb4` |
| 32APSK | 4500 | `626c6ae7d1a38bc46e8bc94ff31a3605f45a96b00b904b4ed5a7215676995736` | `91ec84fb682e51ea188cefe51ed5c050c9f10569c96986ab95c688a29f78efc2` | `29f42381aff32c682f30ef8227a69a1c57bbca9debaf3d5de41d56dbf47825eb` |
| 64APSK | 5000 | `6712ad231d6f3abd1e1484b734c37ad1380c339208cfaa4ab3cc9e51a9e2a697` | `70aeb06ba8a200a0183ed33ba4e0fa8249a15d019a4f67c1da6febede8354866` | `ce8f98d9c81d71eb6b8269870726dcf93f12aa1ed1c20b0833b3d6fd2df4846d` |
| 128APSK | 5500 | `896977e48a3cadb52ce7d73d1364968c2d14a7904092f211a0e9374cf18289ce` | `d07838ebee164901e6fa0c58346bc6afc69c0e2e22c494deb822c2727b501e32` | `3011ebba65dfed4d062c6c36b132b7b32aa58ee0ad03ac9b06fe601a8b1d46b2` |
| 16QAM | 6000 | `b7fd7ccfeb99f1005760bead27ca3119b6c4e03357c8b25dee03341072be8ff6` | `173ad9fd8158010c525153bffce94a148c288f66fd735b4adab6f8374f0c83de` | `17bc6d1b5b7670c312c3b521d69a71496a5b8471d729797835c0f2f7488d0f51` |
| 32QAM | 6500 | `cd71f8816e5bbe7725b1577e1157e3704a57cda668db0e7a602d0b590a03da63` | `057e5a01d092bc540bc080ea6889d3eff7b575648e663c7c19cfbcfae93db0f4` | `bc88ef5d137eccea9651800a209e815a5ebe09152fe3f9f80c3a4bc508cc5101` |
| 64QAM | 7000 | `b2813e15fb4f82c479d13971c9e89178f4142e047a4e33e9f5d190ffd40fb9c2` | `b79a0482a842962c716268e62711900ca9a00721982581c10a3f2a1bb69d991b` | `60f4cfaad25a091ecbe7b5af87222f73eb827671e3ad7f800b729791c38f6590` |
| 128QAM | 7500 | `569d509aa9f98187743b63c07142c69ea692cc188e587731ea40a5ec4300d4b3` | `d18d1fd5e6cbf4763f77c7b772eb4fce38106c100f4bb05f7d3493d36f8f0a5a` | `f09edd0bc2de02db78f33faed5107e8009ae096a400341ddebc682a1c433b91d` |
| 256QAM | 8000 | `14cd1c866b705ca8a25284f093d39e7a52b4a5edb19b4f6b2198bdf29c980b47` | `afa4b7ba7c9fc1b853fb09c8891f97864a588e1ce3700c1c46348e64f9b1eeed` | `4e0e1b16c77e420aa9637f40ea5038d207c4cee8986b7053840adbb404c50795` |
| AM-SSB-WC | 8500 | `b57f6a8360a18c3d0a030d03839043d3790e626f4a7fb4b0d86d0943d0ab0872` | `fcf1330dec7a8b9ec63da5a85a5f98ac843b2758b91bfdb3d512a27f20465d3f` | `61e064103b52f7dbcb78eca11b1aa10707a80ee7fa19067337d6d8965db06618` |
| AM-SSB-SC | 9000 | `bd458a8e1738898afd0d9b1563b3e453c74d223bc87f5bc97ade018fae658295` | `f8f3f2627c80e775a087d4c71960cb2fde5a48663fbab36067568deb320f258e` | `28ef875118a411a97f68310171e12136376d59ac4b47ef8eab1d3f5c2d3d50fc` |
| AM-DSB-WC | 9500 | `d561a08538ad84412a7fa85fc307bc9ea586db09a285d177a7786d9e3a45a296` | `04dd51a3389a833c2ada65fbdf462f9fa3bc533256b4721151e036074f466012` | `4963552c80cc29283ee5067080bcf8a1df875c4098b7e08ca2903b4545789333` |
| AM-DSB-SC | 10000 | `a8ef75faa16c3800390b71f325a8512c7b4987b9c994c424e500fe82ca4e5cdf` | `959f210c02e47ecb27a1b8b72cd8e6bed014b04290929e3d1cfe47e62997166e` | `99db15b81c237a9a2aa0a3648420ecd2187e9ee71c296a26bcc8f40d2d624825` |
| FM | 10500 | `43dd981616e1c12f60dde2ff8511e287862f7a6799825a99302bad7cc816c3ed` | `967d99f9993aadce5dcaf6187bd11101752154b63a486521d253d1a5c2735d88` | `c66952e49331676232ed61d56c9ddcf61ebd04562a782ad29da437cedc2f5729` |
| GMSK | 11000 | `0b9faa0f5926ed9ccb704bef6c2c3428965cc534c62f760e2a4d45b6a0865738` | `88b47a4e05d0709b18bd8c847c987721b10c04b3f77943033e0dac5f2033096e` | `eef2bcdfdb8c5de1bfc111cc14bbe3b80f8a07b0f8e5ff3fc6ed35c69bd925be` |
| OQPSK | 11500 | `bca422946b8301e01f6830ed24e916d397c8eb9e66ef85c12c1591dcfe6b4bf4` | `8d9f796454e168d8bb5fcbf52a5bc23b10ae1b930cb16e4a4ac05981e680d444` | `140c716fcef8636a4d67b867f82ff90abf445c571ac9f7442cbf5092e0888494` |

The full byte-level SHA sidecar is `clean24_smoke\clean24_smoke_SHA256SUMS.txt`
(79 lines: 72 binaries + 6 TSVs + build report).

## 7. Per-sample frozen roundtrip results (raw24 + 24→23)

Frozen checkpoint `96cd25f8...` (best_epoch 50) run on each D2 RECOVERED
`[2,1024]` tensor. `raw24 label→pred` and `deployed23 label→pred` all agree;
two AM-SSB samples predict WC and SC in raw24 and both `AM-SSB` in deployed23.

| source_index | modulation | raw24 label→pred | deployed23 label→pred | margin | corr | NMSE | rms_scale_err |
|---|---|---|---|---|---|---|---|
| 0 | OOK | OOK→OOK | OOK→OOK | 32.975234 | 0.999936 | 1.383e-04 | 3.029e-03 |
| 500 | 4ASK | 4ASK→4ASK | 4ASK→4ASK | 19.841355 | 0.999925 | 1.523e-04 | 1.320e-03 |
| 1000 | 8ASK | 8ASK→8ASK | 8ASK→8ASK | 28.352515 | 0.999928 | 1.450e-04 | 1.228e-03 |
| 1500 | BPSK | BPSK→BPSK | BPSK→BPSK | 15.455157 | 0.999877 | 2.649e-04 | 4.272e-03 |
| 2000 | QPSK | QPSK→QPSK | QPSK→QPSK | 30.801043 | 0.999906 | 2.162e-04 | 5.162e-03 |
| 2500 | 8PSK | 8PSK→8PSK | 8PSK→8PSK | 23.021243 | 0.999910 | 2.053e-04 | 4.911e-03 |
| 3000 | 16PSK | 16PSK→16PSK | 16PSK→16PSK | 14.401928 | 0.999925 | 1.771e-04 | 5.037e-03 |
| 3500 | 32PSK | 32PSK→32PSK | 32PSK→32PSK | 21.113548 | 0.999904 | 2.198e-04 | 5.238e-03 |
| 4000 | 16APSK | 16APSK→16APSK | 16APSK→16APSK | 26.061994 | 0.999906 | 2.108e-04 | 4.671e-03 |
| 4500 | 32APSK | 32APSK→32APSK | 32APSK→32APSK | 25.908840 | 0.999953 | 1.173e-04 | 4.705e-03 |
| 5000 | 64APSK | 64APSK→64APSK | 64APSK→64APSK | 24.523323 | 0.999941 | 1.457e-04 | 5.209e-03 |
| 5500 | 128APSK | 128APSK→128APSK | 128APSK→128APSK | 21.637529 | 0.999873 | 2.759e-04 | 4.492e-03 |
| 6000 | 16QAM | 16QAM→16QAM | 16QAM→16QAM | 32.570792 | 0.999919 | 1.884e-04 | 5.005e-03 |
| 6500 | 32QAM | 32QAM→32QAM | 32QAM→32QAM | 27.620092 | 0.999880 | 2.630e-04 | 4.544e-03 |
| 7000 | 64QAM | 64QAM→64QAM | 64QAM→64QAM | 17.445772 | 0.999911 | 1.998e-04 | 4.671e-03 |
| 7500 | 128QAM | 128QAM→128QAM | 128QAM→128QAM | 6.403180 | 0.999966 | 9.557e-05 | 5.175e-03 |
| 8000 | 256QAM | 256QAM→256QAM | 256QAM→256QAM | 12.571980 | 0.999968 | 9.472e-05 | 5.476e-03 |
| 8500 | AM-SSB-WC | AM-SSB-WC→AM-SSB-WC | AM-SSB→AM-SSB | 1.015571 | 1.000000 | 7.696e-07 | 1.462e-05 |
| 9000 | AM-SSB-SC | AM-SSB-SC→AM-SSB-SC | AM-SSB→AM-SSB | 4.470667 | 0.999997 | 6.476e-06 | 5.869e-05 |
| 9500 | AM-DSB-WC | AM-DSB-WC→AM-DSB-WC | AM-DSB-WC→AM-DSB-WC | 2.905689 | 0.999745 | 5.667e-04 | 7.228e-03 |
| 10000 | AM-DSB-SC | AM-DSB-SC→AM-DSB-SC | AM-DSB-SC→AM-DSB-SC | 8.203776 | 0.999652 | 7.470e-04 | 6.821e-03 |
| 10500 | FM | FM→FM | FM→FM | 35.523286 | 0.999869 | 3.476e-04 | 7.611e-03 |
| 11000 | GMSK | GMSK→GMSK | GMSK→GMSK | 16.121332 | 0.999876 | 2.600e-04 | 3.417e-03 |
| 11500 | OQPSK | OQPSK→OQPSK | OQPSK→OQPSK | 3.107494 | 0.999882 | 2.549e-04 | 4.025e-03 |

D2 recovery fidelity matches the fix10clean2b gates: correlation ≥ 0.999652,
NMSE ≤ 7.470e-04, rms_scale_error ≤ 7.611e-03 (all ≪ 1e-2 / 1e-3 class thresholds).
The two AM-SSB samples show the tightest recovery (corr ≈ 1.0, NMSE ~1e-6..1e-7).

## 8. Acceptance and determinism

| Gate | Result |
|---|---|
| selected_samples | 24 |
| raw24 class coverage | 24/24 |
| deployed23 class coverage | 23/23 |
| clip_count = 0 | 24/24 |
| nan/inf | 0 |
| formal_excluded | 0 |
| raw24 label correct | 24/24 |
| deployed23 label correct | 24/24 |
| raw24 prediction agreement (roundtrip vs frozen baseline) | 24/24 |
| deployed23 prediction agreement (roundtrip vs frozen baseline) | 24/24 |
| deterministic_two_run (byte-identical) | PASS |
| offline test suite | 16 passed |

Determinism is enforced in-process (`main()` builds twice, requires SHA-equal maps
and JSON-equal metadata) and re-verified by `tests\test_determinism_roundtrip.py`
which runs `build_artifacts` into two fresh dirs and asserts identical SHA maps.

## 9. Offline test suite (tests\, 16 passed)

`python -B -m pytest tests -q` → `16 passed`. Coverage:

- fixed 24 source_index / seed formula / slug uniqueness
- predictions TSV duplicate sample_id rejection
- predictions TSV missing sample_id rejection (via `build_artifacts`)
- predictions TSV bad-header rejection
- class-order misalignment rejection (`read_hdf5` vs contract)
- HDF5 wrong-shape rejection
- HDF5 wrong-dtype rejection
- CI16 `<i2` contiguous little-endian (on-disk, 24 files)
- F32 `<f4` contiguous little-endian (on-disk, 48 files)
- 24→23 coverage counts
- AM-SSB unique merge rule
- two baseline schemas not mixed
- SHA determinism + tamper sensitivity (wrong-SHA basis)
- recovered-tensor wrong-length rejection (`read_tensor_f32`)
- build two-run consistency
- roundtrip 24/24 acceptance

All tests write only inside `F:\嵌赛\fix10class24_prep1_work\` (temp dirs under
`tests\.pytest_tmp`, cleaned up). `sys.dont_write_bytecode=True` is set before any
reference-tree import; no `.pyc` was written today into the READ-ONLY trees.

## 10. Deliverables

| Path | Content |
|---|---|
| `scripts\build_clean24_smoke_d2.py` | deterministic build (72 binaries + 6 TSVs + report + SHA sidecar) |
| `scripts\verify_clean24_smoke_roundtrip.py` | frozen-checkpoint roundtrip + fidelity + acceptance |
| `tests\` | 16-test offline suite (conftest + 3 files) |
| `clean24_smoke\` | 79 content files + build report + SHA256SUMS.txt (80 files) |
| `results\clean24_smoke_roundtrip_report.json` / `.md` | verification outputs |
| `docs\M29_RML23_FIX10CLASS24_OFFLINE_ASSETS_AUDIT.md` | this document |

## 11. Statement of non-interference and integration gate

- No board, SDR, runner, network, or any project outside
  `F:\嵌赛\fix10class24_prep1_work\` was written to. The six READ-ONLY directories
  remain untouched (only read-only imports were performed).
- **Integration gate:** these offline assets must NOT be promoted to any board
  workflow until **fix10prep3 (跨架构训练帧字节一致性)** completes its board
  leg on the authoritative ARM output. This task is offline asset preparation
  only; no RF/board conclusion is claimed here.
