# AD-AMR Net V1 — independent model line

Independent re-implementation of the ICC 2024 **AD-AMR Net** ("Adaptive Denoising
With Efficient Channel Attention for Automatic Modulation Recognition", `ma.pdf`)
for the 8-class RF modulation recognition task (BPSK/QPSK/8PSK/16QAM/64QAM/2FSK/
CPFSK/OFDM) on the 8-modulation / 21-SNR synthetic dataset shared by the V2/V3.x
tracks (25200/5040/8400, seed 2026).

This track is **separate** from the frozen V2 champion and V3.3: it does not
modify, import, or initialize from any frozen asset, and it does not use the
3-channel physical feature planes (the paper's input is IQ-only `R^{2 x L}`).

## Layout

- `models/ad_amr_net.py` — ADM (WaveUNet+ECA denoiser), FEM (stem Conv + ERSBs),
  ECA, soft-thresholding, `ADAMRNet`, profile.
- `datasets/ad_amr_dataset.py` — clean/noisy IQ-pair dataset with deterministic
  reproducibility and non-overlapping sample ids.
- `training/` — loss (P0/P1), trainer (Adam + ReduceLROnPlateau + AMP + early
  stopping + resume), metrics, entrypoint.
- `evaluation/evaluate_ad_amr.py` — full metric suite + access audit.
- `scripts/` — ONNX export + NPU-gap audit, CUDA preflight, staged pilot, packaging.
- `tests/` — 12 test categories (shapes, ADM length, ECA/ERSB, P0/P1, data
  determinism/isolation, overfit, smoke, resume, NaN/Inf, ONNX/ORT, bash -n,
  ZIP/manifest/LF).
- `autodl_ad_amr_v1/` — AutoDL setup/preflight/pilot/resume/package scripts.
- `docs/` — audit, architecture mapping, implementation assumptions, deployment
  gap, final report.
- `init/v2_time_power_phase_best.pt` — frozen V2 champion (reference only, never
  loaded as an initialization source).

## Quick start (CPU)

```bash
python -m pytest tests -q
python -m training.train_ad_amr --config configs/ad_amr_v1_smoke.yaml
python -m evaluation.evaluate_ad_amr --config configs/ad_amr_v1_smoke.yaml --split ad_amr_validation
```

## AutoDL (GPU)

```bash
bash autodl_ad_amr_v1/setup_env.sh
bash autodl_ad_amr_v1/run_preflight.sh     # -> AD_AMR_V1_CUDA_PREFLIGHT_PASS
bash autodl_ad_amr_v1/run_pilot.sh         # -> AD_AMR_V1_PILOT_PASS / NO_GO
```

## Status

`ready-for-cuda-preflight`.  No formal training, no board/SDR/FPGA work, and no
NPU deployment is claimed.  See `docs/ad_amr_v1_report.md`.

- CPU tests: 33 passed (8 third-party deprecation warnings).
- Single-batch overfit (P0 and P1): loss falls, training accuracy → 100% — verified
  by `python -m scripts.overfit_probe`.
- Final archive `dist/ad_amr_v1_autodl.zip` (48 files, LF-only manifest, CRC ok).
  The full 64-hex-char SHA-256 and exact byte size are recorded in
  `dist/ad_amr_v1_autodl.zip.sha256` and `pretraining_readiness.json` — both kept
  *outside* the archive, since a file cannot contain its own archive's hash without
  changing it.
