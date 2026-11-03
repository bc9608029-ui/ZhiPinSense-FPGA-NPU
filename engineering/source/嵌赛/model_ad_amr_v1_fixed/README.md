# AD-AMR Net V1 — paper-driven independent model line

This package re-implements the ICC 2024 AD-AMR Net paper, *Adaptive Denoising
With Efficient Channel Attention for Automatic Modulation Recognition*, for the
contest's eight classes: BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, and OFDM.

The paper does not specify every architectural dimension. Those choices remain
explicit assumptions A1–A13 in `docs/implementation_assumptions.md`; the package
does not claim an exact official reproduction.

## Release state

Status: **pending real-GPU CUDA preflight**. CPU verification is complete, but
formal training must not be started until the current package prints
`AD_AMR_V1_CUDA_PREFLIGHT_PASS` on the target GPU.

Important deployment boundary: the paper architecture exports to ONNX and is
checked against ONNX Runtime, but its Abs/Sign/Sub/Sigmoid/Resize-family operators
are outside the existing eight-operator ZG330 NPU policy. NPU deployment is not
claimed by this research package.

## What is release-blocking

- Device-safe production training, evaluation, profiling, AMP, and export paths.
- Checkpoint version 3 restores model, optimizer, scheduler, AMP scaler, Python,
  NumPy, CPU/CUDA torch RNG, and the train DataLoader generator.
- CUDA preflight runs the real production entrypoints for P0 and P1, including a
  two-epoch train, strict resume to cumulative history `[1,2,3]`, validation
  evaluation, ONNX checker/opset 17, and mandatory ONNX Runtime parity.
- The preflight PASS marker is bound to a SHA-256 of source, configs, tests,
  scripts, requirements, and the frozen V2 checkpoint. A code change invalidates
  the old marker.
- The performance pilot uses train/validation only. It evaluates AD-AMR and the
  frozen V2 on identical samples for both seeds and applies macro-F1, accuracy,
  per-class, 0/10/20 dB, 0–10 dB, QAM, OOD, finiteness, and export hard gates.
  A result merely above random chance can never be promoted.

## AutoDL sequence

Run from the extracted package root:

```bash
bash autodl_ad_amr_v1/setup_env.sh
bash autodl_ad_amr_v1/run_preflight.sh
bash autodl_ad_amr_v1/run_pilot.sh
```

If the pilot is interrupted after checkpoints were written:

```bash
bash autodl_ad_amr_v1/resume_pilot.sh
```

Interpret the terminal marker literally:

- `AD_AMR_V1_CUDA_PREFLIGHT_PASS`: functional GPU paths passed for this exact hash.
- `AD_AMR_V1_PILOT_PASS`: the two-seed validation/OOD promotion contract passed.
- `AD_AMR_V1_PILOT_NO_GO`: keep V2 as champion; do not force promotion.

The final blind/test split is not instantiated during selection.

## Local verification

```bash
python -m pytest tests -q
python -m training.train_ad_amr --config configs/ad_amr_v1_smoke.yaml
python -m evaluation.evaluate_ad_amr --config configs/ad_amr_v1_smoke.yaml --split ad_amr_validation
python -m scripts.export_ad_amr_onnx --config configs/ad_amr_v1_smoke.yaml
```

See `docs/ad_amr_v1_release_fix_report.md` for the release-blocker audit and
`docs/ad_amr_v1_report.md` for the original paper/architecture report.
