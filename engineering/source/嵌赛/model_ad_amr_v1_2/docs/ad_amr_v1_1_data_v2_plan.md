# AD-AMR V1.1 data-v2: public-data pretraining without architecture drift

## Decision

V1.2 changed the training distribution but regressed the core validation task, so it is not
promoted.  This track freezes the proven V1.1 inference graph and tests one narrower hypothesis:
whether supervised RadioML2018.01A pretraining improves the same ten-class target model.

This is an experiment, not a promised improvement.  V1.1 remains the champion unless the paired
pilot passes every gate.

## Data path

1. Place the official `GOLD_XYZ_OSC.0001_1024.hdf5` under `data/radioml2018/`.
2. `scripts.audit_radioml2018` verifies X/Y/Z shapes, the frozen 24-class label order,
   2,555,904 rows, 4,096 rows per class/SNR stratum, finiteness, one-hot labels, and SHA-256.
3. It creates deterministic 60/20/20 indices within every class/SNR stratum and proves zero
   train/validation/test overlap.
4. Public pretraining uses only public train/validation.  Public test is never instantiated.
5. The unchanged V1.1 network is trained as a 24-class classifier. Reconstruction and teacher
   distillation are disabled because RadioML does not provide a clean/noisy pair or compatible
   teachers.
6. Every compatible tensor except the final classifier output layer is transferred into a fresh
   ten-class V1.1 model. The output layer is deliberately reinitialized.
7. Target fine-tuning uses the existing ten-class synthetic train/validation contract and teachers.

The public-data loader is fail-closed: missing, partial, reordered, tampered, or unaudited data
stops the run. It never substitutes synthetic samples while claiming public pretraining.

## Pilot comparison

The pilot trains `scratch` and `radioml_pretrained` for the same 30 epochs, same seed, same target
training data, same validation samples, and same optimizer settings. Promotion requires:

- macro-F1 gain of at least +0.005;
- rated 0–20 dB accuracy delta at least -0.005;
- 0 dB accuracy delta at least -0.02;
- worst rated-class delta at least -0.03;
- each focus OOD domain (strong CFO, multipath, multi-impairment) no worse than -0.01;
- unchanged ONNX whitelist and Runtime parity.

Failure means V1.1 stays champion. The gate is not weakened after seeing results.

## Deployment invariants

The inference class remains `ADAMRV11Net`; input stays `iq[N,2,1024]`; target output stays ten
classes; ONNX ops remain Conv/BatchNormalization/Relu/Add/ReduceMean/Gemm. Public pretraining adds
no runtime operator. Vendor NPU compilation and board parity are still separate requirements.

## AutoDL order

```bash
bash autodl_ad_amr_v1_1_data_v2/setup_env.sh
bash autodl_ad_amr_v1_1_data_v2/run_data_audit.sh
bash autodl_ad_amr_v1_1_data_v2/run_preflight.sh
bash autodl_ad_amr_v1_1_data_v2/run_public_pretrain.sh
bash autodl_ad_amr_v1_1_data_v2/run_pilot.sh
bash autodl_ad_amr_v1_1_data_v2/run_formal.sh
```

`run_pilot.sh` exits non-zero on NO-GO, so `run_complete.sh` stops before formal training.
Do not start the two-seed formal run manually unless the pilot prints
`AD_AMR_V1_1_DATA_V2_PILOT_PASS`. Formal training uses seeds 2026 and 2027,
the frozen V1.1 absolute acceptance gates, fake-INT8 evaluation, ONNX inspection,
and validation/OOD only; public test and final blind remain untouched.
