# RML24 System Report — DRAFT (evidence skeleton)

> This is a **draft skeleton for root-cause insertion**. Sections marked
> `[PENDING_*]` are placeholders for evidence not yet produced. Only the
> `CURRENT_VERIFIED_CONCLUSIONS.md` content is asserted as fact at this time.
> Status: `M29-RML24-REPORT-EVIDENCE-LEDGER-READY-FOR-ROOT-CAUSE-INSERTION`.

## 1. Scope

Deploy a frozen RadioML2018 24-class classifier (ADAMRV11Net, checkpoint
`96cd25f8…`, BF16 weights `28272abc…`/`c1781aec…`) onto an FMQL30TAI board with a
ZG330 NPU, over a real dual-SDR PC-TX → board-RX RF loopback.

## 2. Frozen assets (VERIFIED — level L4/L6)

- Model identity: see `tables/t01_bf16_model_identity.tsv`.
- Label contract: 24 classes, AM-SSB-WC(17)/AM-SSB-SC(18) independent
  (RAW24_UNMERGED, merge23 forbidden). See claim C02.
- Host BF16 forward: 24/24 correct, 24/24 match frozen PyTorch, 0 NaN/Inf
  (backend `icraft-host-bf16`). See `tables/t02_host_bf16_24class_accuracy.tsv`.
- NPU mapping: 122 HardOp @zhuget(330) + 2 host, 0 int8,
  `DEPLOYABLE_FULL_NETWORK_BF16`. See `tables/t03_npu_mapping_summary.tsv`.

## 3. Receiver recovery chain

Coarse CFO (LS gain-phase, ±625 Hz) → de-rotate → Pass2 + fractional timing →
estimate → payload apply (`iqrfrec::apply`, red-line) → preprocess → NPU.
See `architecture/final_receiver_architecture.mmd`.

## 4. Root-cause findings (Phase D) — VERIFIED_NEGATIVE

- **D1** cross-arch RX reference uncertainty (`payload_gain_training_complex()`
  `sqrt`/`lround`): x86 `-883` vs aarch64 `-2650` (claim C07, table t04).
- **D2** board BPSK residual `0.116` is real RF noise (SNR ≈ 18.7 dB), not a code
  defect; no fixable systematic component within red line (claim C08, table t06).
- **D3** "BPSK over / 4ASK over" is RF implementation noise, modulation-independent
  (claim C09).

## 5. RX frontend sweep (board) — VERIFIED_NEGATIVE

Single-variable RX bandwidth sweep (18/10/5/3 MHz × 3 rounds, TX −40 dB hard cap,
RX gain 35 dB) plus a gain sweep (35/40/45/50 dB): **all 30 captures failed**
(residual 0.11–0.15), no stable 3/3 bandwidth. See `tables/t07_…`, claim C11/C12.

## 6. Forced classification of failed RX (diagnostic) — [PENDING_RXRESIDUAL_AUDIT]

The main-line `fix10class24-rxresidual-audit1` pipeline (gate-bypassed provisional
recovery → production classification window → exact model input → frozen BF16
forward → 24-dim raw logits) is built and Phase A/B/C complete
(claim C13/C14). Phase D/E/F (classify / residual decomposition / threshold) and
the 14 host tests are **not yet complete** — `[PENDING_RXRESIDUAL_AUDIT]`.

## 7. UI constellation desktop — [PENDING_UI_DESKTOP_RESULTS]

A real visible Qt desktop build + screenshots exist (claim C16). Final desktop
verification verdict and any live-NPU wiring are
`[PENDING_UI_DESKTOP_RESULTS]`.

## 8. Board 24-class RF prospective validation — [PENDING_24CLASS_RF_PROSPECTIVE_VALIDATION]

The prospective-validation framework (synthetic self-test) is ready (claim C15).
Real board 24-class RF results are `[PENDING_24CLASS_RF_PROSPECTIVE_VALIDATION]`.

## 9. FPGA utilization — [PENDING_FPGA_UTILIZATION_REPORT]

FPGA slice/DSP/BRAM utilization of the merged NPU+HDMI bitstream is
`[PENDING_FPGA_UTILIZATION_REPORT]`.

## 10. Conclusion

**Not yet formed.** No production gate pass, no RF 24-class pass, and no final
acceptance has been demonstrated. The verified state is: host BF16 24/24 correct,
NPU deployable (mapping only), and board 2-sample RF recovery marginal (residual
0.10–0.15 across all swept bandwidths/gains). Root cause of the RF marginality is
identified (Phase D D1/D2/D3) but a stable fix is not yet proven on the board.
