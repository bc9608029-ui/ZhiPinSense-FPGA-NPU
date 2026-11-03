# AD-AMR V1.1 — ten-class deployable student

V1.1 is an independent successor to the paper-driven AD-AMR V1 experiment. It
keeps the useful training ideas (denoising and knowledge transfer), but the
deployed student is deliberately restricted to the current NPU operator policy.

Classes, in the frozen output order:

`AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`

The V1 seed-2026/2027 checkpoints and V2 champion are frozen teachers. They are
used only during training and are not included in the exported student graph.
AM-DSB and WBFM are supervised by ground truth only. GFSK may receive soft
knowledge from the old CPFSK teacher output, but the ground-truth labels are
never aliased.

## Status

`ready-for-cuda-preflight`, not yet ready for formal promotion or board use.
Local CPU tests, smoke train/resume, strict ONNX operator audit, and ONNX Runtime
parity pass. A real GPU must still print `AD_AMR_V1_1_CUDA_PREFLIGHT_PASS` for
this exact source/teacher hash before the pilot starts.

Operator compatibility does not equal vendor deployment proof. After training,
the graph must still compile with the vendor NPU toolchain and pass quantized
emulator/board parity on captured SDR IQ.

## Recommended AutoDL flow

Run from the extracted archive root:

```bash
bash autodl_ad_amr_v1_1/setup_env.sh
bash autodl_ad_amr_v1_1/run_preflight.sh
nohup bash autodl_ad_amr_v1_1/run_pilot.sh > ad_amr_v1_1_pilot.log 2>&1 &
tail -f ad_amr_v1_1_pilot.log
```

Only when the pilot prints `AD_AMR_V1_1_PILOT_PASS`:

```bash
nohup bash autodl_ad_amr_v1_1/run_formal.sh > ad_amr_v1_1_formal.log 2>&1 &
tail -f ad_amr_v1_1_formal.log
```

`run_complete.sh` is provided, but the staged commands above are recommended so
the pilot no-go result can be inspected before spending the formal budget.

The pilot uses three variants for 30 epochs rather than repeating V1's proven
15-epoch misranking. Formal training uses two seeds, at most 100 epochs, and
gate-aware best-checkpoint selection with early stopping after at least 30
epochs and 12 stale epochs.
