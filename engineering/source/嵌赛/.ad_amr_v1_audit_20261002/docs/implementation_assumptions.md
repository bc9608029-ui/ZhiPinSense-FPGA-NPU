# AD-AMR V1 — Implementation assumptions

The paper states the architecture skeleton, the loss form, and the training recipe,
but leaves several dimensions unstated.  Each such dimension is implemented as an
explicit constructor/config parameter with the default below and is marked here as
an **implementation assumption** — it is never presented as a "paper setting".

| # | Dimension | Default | Rationale |
| --- | --- | --- | --- |
| A1 | Number of ADM down/up levels `L` | 4 | powers-of-2 U-Net; 1024 -> 64 bottleneck |
| A2 | ADM base channels | 16 (-> 16/32/64/128) | lands near the paper's 0.25M budget |
| A3 | Down-sampling mechanism | stride-2 conv (kernel 15) | paper gives kernel 15 but not the mechanism |
| A4 | Up-sampling mechanism | nearest x2 + conv (kernel 5) | WaveUNet convention; avoids transposed-conv checkerboard |
| A5 | ECA kernel size | `k = |log2(C)/2 + 1/2|_odd` (gamma=2, beta=1) | ECA-Net adaptive formula |
| A6 | Soft-threshold scaling | `lambda = alpha * mean(|out|)`, `alpha = ECA(|out|)` | DRSN-CW channel-wise threshold, SE replaced by ECA |
| A7 | FCL hidden size | 128 | paper does not state it |
| A8 | Dropout | 0.2 | regularization; not stated in paper |
| A9 | Batch size | 128 | RTX 3090-class; not stated |
| A10 | Weight decay | 0.0 | paper specifies Adam + lr only |
| A11 | LR scheduler | ReduceLROnPlateau on val macro-F1 (mode=max) | paper names ReduceLROnPlateau; monitored metric unstated |
| A12 | Classes | 8 (not RadioML's 24) | the contest's 8-class task |
| A13 | Denoising supervision | P0 = MSE to noisy (paper Eq. 4 literal); P1 = MSE to clean | Eq. 4 is ambiguous; both implemented, selected by pilot |

All of A1–A13 are configurable in `configs/ad_amr_v1.yaml` and validated by the
test suite.  None lowers a comparison threshold, and none is claimed as the paper's
original setting.
