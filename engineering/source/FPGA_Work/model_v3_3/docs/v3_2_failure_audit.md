# V3.2 Failure Audit — Why V3.1 and V3.2 Failed the Formal Gate

This audit is the evidence base that drives every V3.3 design decision. It records
*what broke* in the two prior tracks so V3.3 closes the hole by construction rather
than by hyperparameter luck.

## Root cause (V3.2): the "frozen" backbone was not frozen

V3.2 intended to preserve the V2 champion while adding an expert, but its freeze
was cosmetic. It froze only the 6 synthesized affine input-norm parameters, leaving
**72,025 / 72,031** backbone parameters trainable.

Measured parameter-only drift of the backbone (V2 → trained V3.2), per seed:

| Seed | Backbone drift (param distance, %) |
| --- | --- |
| 2026 | 42.16% |
| 2027 | 25.30% |
| 2028 | 9.05% |

A backbone that moves by 9%–42% is no longer the champion; the "residual on top of
V2" claim becomes false, and the per-class gains (especially the hard QAM classes)
become un-interpretable — they are paid for by regressing the classes V2 was good
at (BPSK/2FSK/CPFSK/OFDM).

## Secondary failure modes

1. **Forced 60-epoch full trajectory (V3.1).** V3.1 trained the full 60 epochs
   without early stopping, then evaluated a late, overfit checkpoint. Overfitting
   on the dev namespace inflated dev metrics while hurting generalization.

2. **QAM reweighting of the base classifier (V3.1).** Upweighting 16QAM/64QAM in
   the base cross-entropy skewed the learned decision boundary and regressed the
   non-QAM classes. V3.3 removes reweighting entirely (all classes weight 1.0).

3. **Checkpoint selected on the wrong metric.** Selecting on loss/accuracy rather
   than macro-F1 misaligned with the acceptance bar (which is macro-F1-gated).

4. **No FPGA-sim-vs-FP32 gap gate.** Neither prior track checked that the deployed
   graph remained accurate under the FPGA Mandatory-Core emulated input domain, so
   a model that looked good in FP32 could regress on hardware numerics.

## What V3.3 changes (one mechanism per hole)

| V3.1/V3.2 hole | V3.3 fix |
| --- | --- |
| Backbone only cosmetically frozen → 9–42% drift | `freeze_v2_backbone`: every V2 param + BN running stats pinned; `train()` override re-applies eval mode |
| Residual could overwrite the whole logit vector | zero-gated `logits = v2 + gate·delta`, `gate=0` at init, residual L2 penalty + optional hard clamp |
| QAM reweighting regressed non-QAM | all class weights 1.0 |
| Forced 60 epochs → overfit | early stopping + `minimum_epochs_before_stopping: 10` + checkpoint on `val_macro_f1` |
| No numeric-domain gate | FPGA-sim gap floor (`maximum_fpga_sim_*_gap = 0.03`) in the promotion gate |
| Candidates stacked → unattributable | A0–A3 validated individually (one mechanism per ablation) |

## Verification that the hole is closed (all asserted by test)

- `test_v2_checkpoint_loads_strictly` — V2 `model_state` loads strictly into the
  V3.3 backbone; only the 2 synthesized affine-norm keys are extra.
- `test_frozen_backbone_byte_identical_after_optimizer_step` — after a real
  optimizer step, every frozen backbone tensor is byte-identical.
- `test_only_expert_gets_nonzero_grad` — zero frozen params carry a grad; the
  expert is the only trainable path.
- `test_a1_gate_zero_reproduces_v2` — `max_abs_diff(V3.3, V2) < 1e-6` at init.
- `test_freeze_count_and_single_batch_overfit` — freeze covers every backbone
  tensor; single-batch loss still decreases through the expert.

## Conclusion

V3.2 failed not because the residual-expert *idea* was wrong, but because the
champion backbone was allowed to move. V3.3's contribution is to make the freeze
and the zero-gate structural invariants, then to re-test them against the real V2
checkpoint before any formal GPU training is started.
