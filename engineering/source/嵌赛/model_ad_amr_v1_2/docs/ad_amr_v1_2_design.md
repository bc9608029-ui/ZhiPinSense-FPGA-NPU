# AD-AMR V1.2 data-robustness design

## Evidence and objective

The completed V1.1 two-seed formal evaluation passed 11 of 12 gates. It kept
strong nominal, rated-SNR, quantization, and ONNX behavior, but failed the OOD
drop gate. The largest reported drops were strong CFO, multipath, and the
combined-impairment suite. V1.2 targets exactly those failures without changing
the deployable graph.

## Frozen contracts

- Input: normalized IQ `[N,2,1024]`.
- Output: ten logits in the V1.1 class order.
- Student architecture and parameter count.
- Frozen V2/V1 teacher assets and their hashes.
- Loss, optimizer, scheduler, BF16 policy, selection thresholds, and two seeds.
- ONNX opset 17 and NPU operator whitelist.
- Final-blind prohibition.

## Deterministic paired ablation

Profile selection uses an RNG stream separate from waveform/channel generation.
For a fixed `(seed, split, epoch, index)`, enabling or disabling the curriculum
does not alter the clean waveform or the base-profile noisy waveform. This
makes the legacy and robust variants attributable to the channel distribution,
not to unrelated regenerated symbols.

The profile mixture ramps over epochs 4–15:

| Profile | Start | Target | Training support | Held-out OOD |
|---|---:|---:|---|---|
| base | 0.70 | 0.40 | V1.1 channel | unchanged validation |
| cfo_focus | 0.10 | 0.20 | ±2.2 kHz | ±2.5 kHz |
| multipath_focus | 0.10 | 0.20 | 2–5 taps, delay ≤16 | 3–6 taps, delay ≤20 |
| multi_impairment | 0.10 | 0.20 | CFO ±1.6 kHz, delay ≤14 | CFO ±1.8 kHz, delay ≤16 |

The multi profile also guarantees phase noise and IQ imbalance. AWGN and the
base stochastic effects remain active so focused records are not artificial
single-effect laboratory samples.

## Leakage and selection policy

Training sees only `ad_amr_v1_2_train`. Normal model selection sees only
`ad_amr_v1_2_validation`; focus OOD validation is used only at the end of each
pilot run. The test/final-blind namespaces remain unavailable.

Stage A runs three 30-epoch variants on seed 2026. Its score is:

`0.55 × nominal selection score + 0.45 × worst focus-OOD macro-F1`.

The winner is confirmed on seeds 2026 and 2027. The pilot cannot promote the
legacy control and requires at least 0.02 reduction in maximum focus-OOD drop,
plus normal-performance and OOD floors. Formal training retains the original
V1.1 absolute gates, including maximum OOD macro-F1 drop ≤0.08.

## Safety and deployment

Every checkpoint stores a SHA-256 training signature over seed, signal,
channel, curriculum, dataset, model, and training configuration. A checkpoint
cannot silently resume under another ablation variant. Export rejects non-V1.2
checkpoints and re-runs ONNX checker, whitelist inspection, and Runtime parity.

V1.2 changes no inference operation, so any improvement costs zero additional
NPU parameters or latency. Vendor compilation and board parity remain external
release gates.
