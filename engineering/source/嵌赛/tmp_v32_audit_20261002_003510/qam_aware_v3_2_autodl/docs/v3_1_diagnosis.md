# V3.1 Formal Result — Evidence-Based Root-Cause Diagnosis

Scope: read-only diagnosis of the V3.1 formal result package
(`input/qam_aware_v3_1_formal_results.tar.gz`, extracted to `input/v3_1_results/`).
No code was modified to reach these conclusions; every claim is grounded in a
specific artifact in that package.

Reference baseline: frozen champion `frozen_qam_aware_v2_time_power_phase`
(accuracy 0.705476, macro-F1 0.697538, QAM mean 0.464762).

---

## 1. Verdict summary

V3.1 is a **capacity + loss-reweighting overfit** that achieved a **real but
narrow QAM gain by systematically misclassifying non-QAM classes as 64QAM**.
The QAM gain (+0.138 QAM-mean) is entirely paid for by regressions in
BPSK/QPSK/CPFSK/OFDM and at 0 dB. The single monolithic classifier with
reweighted loss had no mechanism to *preserve* the frozen V2 decision boundary
while *adding* QAM discriminative power — the two objectives were coupled, and
the QAM objective won at the expense of everything else.

## 2. The ten evidence points

### (1) Capacity explosion relative to V2 → overfitting
`formal/config/effective_config.json` shows V3.1 is far larger than V2
(71,656 params): `iq_stem_channels=32`, `stage_channels=[64,96,128]`,
`classifier_features=128`, `physical_moment_order=4`. This multiplies trainable
capacity ~20× while the training set (100,800 samples, 21 SNR × 8 classes × 600)
is unchanged.

### (2) Train/validation divergence is textbook overfitting
`formal/logs/training_history.csv`: train accuracy reaches **0.999** while
validation accuracy peaks at **0.687** and validation **loss rises** from 0.989
to 1.634 over the run. The model memorizes the training distribution and never
generalizes the extra capacity.

### (3) Best epoch is 7, not 60
`best_epoch=7` (`training_history.csv` + `formal/checkpoints/best.pt`). The
`minimum_epochs_before_stopping: 60` setting forced 60 epochs of a cosine
schedule, but validation accuracy/F1 plateau after epoch 7 and validation loss
*increases* afterward. The "run the full trajectory" fix did not help; it only
burned compute while the model overfit.

### (4) Higher-order moments + QAM class weights bias toward 64QAM
`effective_config.json`: `physical_moment_order=4` (E[x], E[x²], E[x³], E[x⁴])
combined with `class_weights {16QAM: 1.2, 64QAM: 1.3}`. Raw 3rd/4th moments are
dominated by the outermost amplitude ring, and the 1.3 weight on 64QAM further
pulls the decision boundary toward 64QAM.

### (5) Systematic 64QAM over-prediction (confusion matrix)
`formal/tables/v2_compatible_confusion_matrix.csv` (1050 samples/class), rows =
true class, columns = predicted:

| true → 64QAM | count |
|---|---|
| BPSK → 64QAM | 195 |
| QPSK → 64QAM | 222 |
| 8PSK → 64QAM | 219 |
| 16QAM → 64QAM | 345 |
| 2FSK → 64QAM | 80 |
| CPFSK → 64QAM | 162 |
| OFDM → 64QAM | 148 |

Every non-QAM class leaks a large share into 64QAM. This is not a QAM-vs-QAM
confusion; it is a global 64QAM prior.

### (6) Per-class deltas isolate the damage
`formal/tables/v3_1_acceptance.json` (V3.1 − V2):

| class | Δ accuracy |
|---|---|
| BPSK | −0.0733 |
| QPSK | −0.1438 |
| 8PSK | +0.0114 |
| 16QAM | +0.0295 |
| 64QAM | **+0.2467** |
| 2FSK | −0.0124 |
| CPFSK | −0.0829 |
| OFDM | −0.1029 |

The only material gain is 64QAM; BPSK/QPSK/CPFSK/OFDM all regress far beyond the
0.03 per-class drop gate.

### (7) QAM gain is real but concentrated and subsidized
`qam_mean_gain = +0.1381` is driven almost entirely by 64QAM (+0.247). It is
achieved by *relabeling* non-QAM samples as 64QAM, not by genuinely separating
QAM constellations — hence the simultaneous QAM gain and PSK/OFDM collapse.

### (8) Low-SNR regression at 0 dB
`formal/tables/v2_compatible_snr_metrics.csv`: 0 dB accuracy drops by **−0.046**
(vs +0.033 at 10 dB, +0.053 at 20 dB). The 64QAM prior is most harmful at low
SNR where PSK/OFDM/CPFSK are already fragile and get pushed over the 64QAM
boundary.

### (9) Root design flaw: coupled objectives, no preservation mechanism
V3.1's classifier is a single `Linear(2·c2 + direct_features, 128) → … → 8`
head. The only lever for "improve QAM" is class reweighting, which *globally*
shifts all decision boundaries. There is no architectural separation between
"preserve the V2 logit path" and "add a QAM correction". The model cannot add
QAM power without disturbing every other class.

### (10) Regularization was insufficient for the capacity
`label_smoothing=0.03` and `weight_decay=0.0002` were too weak to contain a
~20× capacity increase; the train curve still hit 99.9%.

## 3. Implication for V3.2 (design principle)

V3.2 inverts the mistake: it keeps V2's frozen logit path **intact** and adds a
separate, zero-gated QAM delta branch that can only *correct* logits additively.
There is no reweighting of the base classifier, no capacity increase in the
backbone, and knowledge distillation keeps the learned logits anchored to the
frozen V2 teacher. The delta branch can only help QAM if it does not hurt the
others, because the promotion gate constrains per-class and per-SNR regression.
