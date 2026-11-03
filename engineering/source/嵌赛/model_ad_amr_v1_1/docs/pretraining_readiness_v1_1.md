# V1.1 pretraining readiness

- [x] Independent V1.1 directory; V1/V2 assets not overwritten.
- [x] Frozen ten-class label and `[N,2,1024]` input contracts.
- [x] AM-DSB, WBFM, GFSK deterministic-capable generators.
- [x] Single NPU-policy-compatible student model.
- [x] Frozen V2 + two V1 teacher loaders with strict class-order checks.
- [x] SNR-aware CE, reconstruction, and masked multi-teacher distillation.
- [x] BF16 CUDA autocast with FP32 losses and hard finite-gradient checks.
- [x] Gate-aware checkpointing and strict resume state.
- [x] Train/validation-only selection and final-blind refusal.
- [x] Thirty-epoch pilot avoids the observed 15-epoch V1 misranking.
- [x] Two-seed absolute ten-class formal gates and OOD battery.
- [x] Strict ONNX opset-17 checker, operator whitelist, ORT parity.
- [x] Fake-INT8 sensitivity gate (not a substitute for vendor quantization).
- [x] Content-bound CUDA preflight marker.
- [x] AutoDL staged and one-command scripts.
- [x] Clean archive manifest/CRC/SHA verification.
- [ ] Real RTX 5090 CUDA preflight — must be run after upload.
- [ ] Pilot/formal training — intentionally not started locally.
- [ ] Vendor NPU compilation and board/SDR parity — external future work.

Current status: **ready-for-cuda-preflight**.
