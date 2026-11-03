# M29 RML24 single-SDR vs dual-SDR differential audit

- Task id: `fix10class24-singlesdr-dualsdr-diffaudit1`
- Status: **`M29-RML24-SINGLESDR-DUALSDR-DIFFAUDIT1-COMPLETE`** (highest allowed token)
- Nature: READ-ONLY audit. No source modified, no package built, no board/SDR touched, no threshold changed, no retrain/requantize, no fusion, no UI.
- Date: 2026-10-18

## 一、Scope and authoritative inputs

Comparison target:
1. **Historical SUCCESSFUL** single-SDR physical self-loopback: Route F fix9r2g1 46-sample
   run (`iq_rf_loopback_23class_fix9r`), board-local TX/RX on one Pluto, merged-23 judgement.
2. **Current** 24-class BF16 dual-SDR PC-TX/board-RX run (`iq_pc_tx_board_rx_24class_bf16_fix10`,
   rxrecovery1), raw24 judgement, 18/24 forced classification.

Evidence trees (all read-only):
- Historical: `F:\嵌赛\fix9r2g1_work\sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g1`,
  `F:\嵌赛\fix9r2h4_delivery`, `F:\嵌赛\fix9r2h5_delivery`, `F:\嵌赛\rml23_fix9r2d_real_evidence`.
- Current: `F:\嵌赛\fix10class24_dualsdr_rxrecovery1_work`,
  `F:\嵌赛\fix10class24_full24_accuracy1_work`,
  `F:\嵌赛\fix10class24_noretrain1_work`,
  `F:\嵌赛\board_capture\full24_accuracy1\rml24_full24_accuracy1_1773372865.tar.gz`.

## 二、Confirmed SHA sets

Model/asset SHAs (all verified by `sha256sum` in this audit):

| asset | SHA256 | status |
|---|---|---|
| historical model_24class_ZG.json | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` | MATCH |
| historical model_24class_ZG.raw (2857720 B) | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` | MATCH |
| current rml24_adamrv11_bf16.json | `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` | MATCH |
| current rml24_adamrv11_bf16.raw (778732 B) | `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` | MATCH |

Board-capture archives (verified):

| archive | SHA256 | status |
|---|---|---|
| rml24_rx_diagnostics_full_1773379631.tar.gz | `08ef944e099270f5c166415df17eabed5c3324ff03a2940182318d4abef76922` | MATCH |
| rml24_full24_failed_rx_1773374413.tar.gz | `53b963127b5ae8575d660366ab193f02cf8339e6f6518ef769519fecf808e6ef` | MATCH |
| rml24_full24_accuracy1_1773372865.tar.gz | `93ecb5e22a0c885065193ef64f7b522feef67cd1be821e8998158456451d7b7b` | MATCH |

### Same checkpoint, different precision

Both models declare the SAME source checkpoint
`96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d`
(`rml24_seed2027_best.pt`, RML2018_24_BENCHMARK), so they are the **same training
checkpoint recompiled to different precision**:

- Historical `model_24class_ZG`: mixed INT8 + BF16 + TF32 (contains `@sint(8)` tensors),
  131 ops, params_md5 `7966a4829fc713b2e8ea6c04168be263`, raw 2857720 B.
- Current `rml24_adamrv11_bf16`: `full_network_bf16_no_int8` (int8_tensors=0), 124 ops,
  params_md5 `0c9b60b82ea1f634469b598db45738fb`, raw 778732 B.

Input/output shape identical (`[1,2,1024]` fp32 -> `[1,24]` fp32). **Never claim "same
model" merely because both output 24 dims** — they differ in precision format, op count,
weight encoding, and (below) in judgement space.

### merged23 vs raw24 / WC-SC mask

- Historical: model emits 24 logits but software `rml23_merged.hpp` folds AM-SSB-WC/SC
  into AM-SSB (`24->23` logaddexp). Baseline predictions are 0..22 (23 classes).
- Current: `deployment_mode=RAW24_UNMERGED`, 24 classes kept separate (AM-SSB-WC #17 and
  AM-SSB-SC #18 distinct). `merged_23_top1=-1` in every result frame.

The WC/SC merge **did not cause the 6 errors**: in the current run AM-SSB-SC gated correct
(`sc=1/1`) and AM-SSB-WC was gate-rejected then forced correct, so no AM-SSB WC/SC confusion
occurred. The 6 errors are elsewhere (AM-DSB WC/SC, QAM, PSK, ASK families).

## 三、Historical single-SDR success evidence (located)

The 46-sample board evidence is documented in
`fix9r2h5_delivery/.../docs/M29_RML23_FIX9R2H5_BASELINE_IDENTITY_AUDIT.md`
(and referenced by `M29_RML23_FIX9R2H2_NARROWER_PAYLOAD_TRAINING_AUDIT.md`):

> Board evidence before this fix showed `scored=46`, `rf_excluded=0`,
> `training_estimates=46`, `prediction_agreement=1.0`, and `rf_accuracy=1.0`, but
> the aggregate token remained FAIL solely through the false identity bit.

Interpretation (the task's required distinction):

- **MEASUREMENT results (valid)**: scored=46, rf_excluded=0, training_estimates=46,
  prediction_agreement=1.0, rf_accuracy=1.0 -> all 46 holdout frames gated and correct.
- **Metadata misjudgment (invalid as a measurement)**: `baseline_identity_ok=false`
  because the loader compared `original_sha256` (source RadioML sample) against the
  quantized ci16 SHA. That single bit drove the aggregate token to FAIL. The H5 hotfix
  corrected the identity check only; it did not change RF capture/sync/gain/thresholds/
  model/inference/class mapping. The h4 46-sample RF evidence "remains valid as
  measurement evidence."

Baseline for the 46-sample run: `route_f_fix9r_predictions.tsv` (46 rows,
`source_index` 86028..2535428, `frozen_baseline_pred` 0..22, two per merged class).

Historical R8 command (fix9r2g1 audit §5):
`--phase=iq-rf-loopback-23class-fix9r --input-kind=radioml-d2-2p56m
--center=2400000000 --rx-gain=30 --tx-atten=-40 --rf-path=direct-cable
--rf-tx-target-rms=2048 --diagnostic-classes=BPSK,4ASK`.

## 四、Current dual-SDR results confirmed (real RF)

Confirmed from the real board log
`.../captures/rml24_full24_accuracy1_1773372865/run.log` and its `summary.log`:

```
scored=15 rf_excluded=9 prediction_agreement=10/24 label_correct=10/24
training_estimates=15/24 negative_control=PASS tx_restore_ok=1 rx_restore_ok=1
cfo_finite=1 cfo_in_range=1 total_cfo_abs_max_hz=87.4839
```

- Normal gate: **scored=15**, **rf_excluded=9**, **label_correct=10/24**.
- Gated conditional: 10/15, coverage 15/24 = 0.625.
- Forced classification (gate bypass, host BF16): **18/24** (scalar 18/24 = wide-linear
  18/24, `scalar_wide_linear_disagree=0`).
- Rejected 9 forced: 8/9 correct (only 16PSK->32PSK wrong).

**Misclassification list (6, all deterministic same-family escalation):**

| sample (source_index/class) | error | layer |
|---|---|---|
| 500 / 4ASK | -> 8ASK | BOARD_NPU_GATED |
| 7000 / 64QAM | -> 256QAM | BOARD_NPU_GATED |
| 7500 / 128QAM | -> 256QAM | BOARD_NPU_GATED |
| 9500 / AM-DSB-WC | -> AM-DSB-SC | BOARD_NPU_GATED |
| 11500 / OQPSK | -> 32PSK | BOARD_NPU_GATED |
| 3000 / 16PSK | -> 32PSK | HOST_BF16_FORCED (rejected) |

**Real dual-SDR RF confirmation**: two distinct SDR devices (`tx_uri=usb:1.11.5` PC TX,
`rx_uri=usb:1.3.5` board RX, `tx_control=tcp://192.168.126.10:39010`), external RF
(`loopback=0`), `negative_control=PASS`, non-zero coarse CFO (-54..-89 Hz) proving
independent clocks, and per-sample `raw_rx_ci16le.bin` dumps with
`coarse_corrected_rx_cf64le.bin`. This is NOT synthetic and NOT digital direct-injection.

Separately, the failed-rx forceclass audit (`rml24_full24_failed_rx_1773374413.tar.gz`,
result tree `results/full24_failed_rx_forceclass/summary.json`) gives 15/20 correct on the
20 gate-rejected dumps, conclusion `EVIDENCE_AGAINST_GATE_RELAXATION`.

## 五、Seven-group differential (see config_chain_diff.tsv)

Summary of the DIFFERENT / NOT_PROVEN rows that matter:

- **A model**: DIFFERENT precision (INT8-mixed vs BF16), DIFFERENT judgement space
  (merged23 vs raw24). SAME checkpoint `96cd25f8...`. Input/output shape IDENTICAL.
- **B samples**: DIFFERENT source (RadioML2018 D2 holdout vs clean24_smoke generated),
  disjoint index spaces, 46 vs 24, 2-per-class vs 1-per-class. The 6 misclassified
  classes DID appear in the historical run (as classes), but never as the same samples.
  Historical baseline (INT8 merged23) != current BF16 raw24 baseline.
- **C topology**: DIFFERENT — single-SDR self-loopback (shared LO, board-local TX) vs
  dual-SDR PC-TX/board-RX (independent LO). Both physical RF (direct-cable, loopback=0,
  same -40 dB atten).
- **D SDR config**: center/sample-rate/target-RMS/attenuation IDENTICAL. **DIFFERENT:
  RX gain 30 vs 35 dB; RX bandwidth unspecified (device default) vs 18 MHz (readback
  confirmed).** LO readback / FIR config NOT_AVAILABLE (not logged).
- **E sync/recovery**: shared `iqrfrec` core (single recovery core). IDENTICAL:
  canonical frame, residual gate 0.100, bounded recapture (3 attempts), classification
  window. DIFFERENT: coarse CFO absent vs -625..+625 Hz; wide-linear compensation absent
  vs enabled. fine CFO / fractional timing / SRO / gain-phase / payload-RMS recovery
  EQUIVALENT.
- **F quality**: current CFO (dual-SDR) -63..-87 Hz total; training corr 0.928-0.978;
  payload-training residual 0.059-0.164 (9 samples > 0.100 -> rejected); image ratio
  0.009-0.089; clip 0. Historical raw fields mostly NOT_AVAILABLE (only H4 single BPSK:
  corr 0.998811, LS magnitude 0.016284, scale error 0.068177).
- **G semantics**: historical rf_accuracy 1.0 / agreement 1.0 / coverage 1.0; current
  gated 10/15, coverage 0.625, forced 18/24, end-to-end 10/24.

## 六、Causal classification (14 candidates; see causal_ranking.tsv)

Top-3 by evidence:

1. **#8 model precision/class-space (BF16 raw24 vs INT8-mixed merged23)** — SUPPORTED as
   the PRIMARY suspect for the 6 misclassifications: same checkpoint, but the deterministic
   same-family escalation persists under forced classification on the BF16 model, and the
   historical INT8-mixed merged23 was 46/46. It does not explain gate rejection.
2. **#10 sample-set difference (RadioML d2 vs clean24_smoke)** — SUPPORTED; clean samples
   are host-verified model-compatible (0.99325) so the errors emerge only after the RF
   channel; contributes to gate rejection and possibly to misclassification. Needs matched A/B.
3. **#1/#7 dual-SDR path (independent clock + PC TX) + #3/#5 TX/RX IQ imbalance /
   nonlinearity** — SUPPORTED as contributors to GATE REJECTION (residual 0.10-0.16,
   image ratio up to 0.089, second-order corr 0.204), but they do NOT explain the fixed
   same-family misclassifications (WL forced = scalar forced = 18/24).

EXCLUDED (by existing evidence): #4 DC offset, #9 raw24-vs-merged23 (for these 6 errors),
#11 classification window/preprocessing (byte-equivalent), #14 software/cross-arch
reference (canonical replay byte-identical). WEAK: #2 intra-frame phase drift. PLAUSIBLE
confounders: #5 nonlinearity, #6 RX gain/bw.

## 七、Minimum conclusions (5/5)

1. **Is existing evidence enough to prove "dual-SDR is the ONLY cause"?** NO. At least
   four non-RF differences coexist (model precision, 23-vs-24 class, sample set, RX
   gain/bw), and the 18/24 forced errors are deterministic same-family confusion that the
   dual-SDR-specific clock/CFO path cannot produce. Dual-SDR as the ONLY cause is not
   provable from current evidence.

2. **Is existing evidence enough to support "dual-SDR-specific path is the PRIMARY
   suspect"?** Only PARTIALLY, and split by failure mode. For the GATE REJECTIONS
   (residual 0.10-0.16), the dual-SDR RF path (independent clock + analog frontends +
   IQ imbalance/nonlinearity/noise) is the leading contributor. For the 6
   MISCLASSIFICATIONS, the model-domain same-family confusion (candidate #8/#10) is the
   primary suspect, not the dual-SDR path. A single "primary suspect" cannot be assigned
   to both failure modes simultaneously.

3. **Which confounders can the pending BF16 single-SDR 24-class A/B exclude?** If the A/B
   holds fixed the BF16 raw24 model (`28272abc`/`c1781aec`), the same clean24_smoke
   samples, and the same RX gain=35 / RX bw=18 MHz / center / rate / target-RMS / 0.100
   gate / canonical frame, then swapping dual-SDR->single-SDR isolates the RF-topology
   difference. It thereby EXCLUDES: #1 (dual-SDR independent clock/CFO), #7 (PC-TX vs
   board-local TX), #6 (RX gain/bw, if pinned to 35/18), #3/#5 (TX/RX IQ imbalance and
   nonlinearity specific to the two-unit path), while leaving #8 (model) and #10 (samples)
   and #9 (raw24 judgement) matched-but-still-in-play as shared background.

4. **If the new single-SDR reaches 24/24, wording must be:** "With model, samples, and
   config held fixed, the single-SDR physical loopback recovered N/24 where the dual-SDR
   PC-TX/board-RX run scored 18/24 forced — evidence supports the dual-SDR RF path as the
   dominant RF-channel contributor to the dual-SDR failures, within this sample set and
   this BF16 raw24 model." Must NOT write `DUAL_SDR_ROOT_CAUSE_PROVEN`,
   `HARDWARE_FAULT`, or `MODEL_PROVEN_FOR_SINGLE_SDR`.

5. **If the new single-SDR ALSO fails, the first three differences to check are:**
   (a) RX gain & bandwidth (30/unset vs 35/18 MHz) — pin or sweep;
   (b) model precision/class-space (run the historical INT8-mixed `model_24class_ZG`
       merged23 on the SAME captures, and/or compare BF16 vs INT8 on the same RF path);
   (c) sample-set origin + judgement space (feed the historical RadioML d2 samples through
       the dual-SDR path and re-judge, and re-examine raw24 vs merged23).

## 八、Parameters the pending single-SDR A/B MUST hold strictly identical

1. model = `rml24_adamrv11_bf16` (json `28272abc...`, raw `c1781aec...`), RAW24_UNMERGED.
2. samples = clean24_smoke 24 files (SHA-verified), one per raw24 class.
3. center 2.4 GHz; sample rate 2.56 Msps; `--rf-tx-target-rms 2048`; TX atten -40 dB.
4. RX gain = 35 dB (readback-verified) and RX bw = 18 MHz (readback-verified) to match
   the dual-SDR run — OR explicitly document a second leg at 30/unset for the #6 test.
5. residual gate 0.100 (`kPayloadTrainingResidualMax`); bounded recapture max 3 attempts
   on `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`; canonical frame contract `9907b7be...`.
6. classification window `[1,2,1024]`; wide-linear compensation ON (to match the current
   runner's wide-linear path).
7. No threshold change, no requantize, no fusion, no UI change. Board test only.

## 九、Stop condition check

(1) both model/asset SHA sets confirmed — DONE (§二).
(2) historical single-SDR success evidence located — DONE (§三).
(3) current dual-SDR real results confirmed — DONE (§四).
(4) seven-group diff tables complete — DONE (config_chain_diff.tsv + §五).
(5) causal evidence grading complete — DONE (causal_ranking.tsv + §六).
(6) A/B must-hold-identical parameter list given — DONE (§八).
(7) no fix/board-test entered — DONE (read-only audit).
