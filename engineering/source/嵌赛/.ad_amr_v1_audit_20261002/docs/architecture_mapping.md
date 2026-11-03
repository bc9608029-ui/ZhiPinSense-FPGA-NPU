# AD-AMR V1 — Paper-to-implementation architecture mapping

Every component of the paper is mapped to a concrete PyTorch module in
`models/ad_amr_net.py`.  Paper-stated facts are marked **[paper]**; choices the
paper leaves open are marked **[assumption]** (see `implementation_assumptions.md`).

## Pipeline

```
noisy IQ x [N, 2, L]
  -> ADM  (Adaptive Denoising Module)          -> xhat [N, 2, L]   (denoised IQ)
  -> FEM  (Feature Extraction Module)          -> features [N, 64, L/16]
  -> GAP (mean over time)                      -> [N, 64]
  -> FCL -> softmax logits                     -> [N, 8]
```

`forward` returns `(logits, denoised_iq)`; `denoised_iq` feeds only the training
MSE term and is dropped by the `ADAMRClassifier` wrapper used for ONNX export.

## ADM — Adaptive Denoising Module (`class ADM`)

| Paper | Implementation |
| --- | --- |
| L down-sampling blocks: Conv1d kernel **15** + downsampling + ECA | `_DownBlock`: `Conv1d(k=15, s=2, p=7)` + BN + ReLU + ECA scale **[paper kernel 15]** |
| L up-sampling blocks: Conv1d kernel **5** + upsampling + ECA | `_UpBlock`: nearest x2 upsample + crop-concat skip + `Conv1d(k=5)` + BN + ReLU + ECA **[paper kernel 5]**; nearest upsample **[assumption]** |
| skip connections (crop-and-concat) | `_UpBlock._crop_concat` (identity here: powers-of-2 lengths match exactly) |
| concluding kernel-1 conv | `ADM.final = Conv1d(in, in, 1)` |
| L down/up blocks | `num_levels = 4` **[assumption]** |
| channel counts | `base_channels = 16`, doubling each level `[16, 32, 64, 128]` **[assumption]** |

Shape-preserving: `[N, 2, 1024] -> [N, 2, 1024]` (verified by test).

## FEM — Feature Extraction Module (`class FEM`)

| Paper (Table I) | Implementation |
| --- | --- |
| Conv k=3 s=1 ch=16 | `stem = Conv1d(2, 16, k3, s1, p1) + BN + ReLU` |
| ERSB k=3 s=2 ch=16 | `ERSB(16, 16, stride=2)` |
| ERSB k=3 s=2 ch=32 | `ERSB(16, 32, stride=2)` |
| ERSB k=3 s=2 ch=32 | `ERSB(32, 32, stride=2)` |
| ERSB k=3 s=2 ch=64 | `ERSB(32, 64, stride=2)` |

Length 1024 -> 64 (four stride-2 blocks); output 64 channels.

## ERSB (`class ERSB`)

- Two conv + BN (`conv1` k3 s=stride, `conv2` k3 s1) + identity/projected shortcut.
- Adaptive threshold: `alpha = ECA(|out|)` then `lambda = alpha * mean(|out|)`
  per channel **[assumption: DRSN-CW threshold scaling]**.
- `out = soft_threshold(out, lambda)`, then `ReLU(out + shortcut)`.

## ECA (`class ECA`)

GAP (`mean` over time) -> `Conv1d(1,1,k)` over the channel dim -> Sigmoid ->
per-channel weights `[N, C, 1]`.  Kernel `k = eca_kernel_size(C)` (ECA-Net formula
`|log2(C)/gamma + beta/gamma|_odd`, `gamma=2, beta=1`) **[assumption]**.

## Soft-thresholding (`soft_threshold`)

`sign(x) * relu(|x| - lambda)` — differentiable and exactly equal to the paper's
piecewise Eq. 1.

## FCL

`Linear(64, fusion_features) + ReLU + Dropout + Linear(fusion_features, 8)`,
`fusion_features = 128` **[assumption; paper does not give the FCL hidden size]**.

## Parameter budget (measured)

`~288K` parameters (paper states `0.25M` for 24 classes; 8 classes here, so the
FCL is smaller but the ADM dominates).  Reported exactly by `profile_ad_amr_model`;
`neural_macs ~32.5M`, `neural_flops ~65.0M`.
