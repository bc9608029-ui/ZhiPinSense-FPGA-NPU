# AD-AMR V1.2 — targeted RF-robustness candidate

V1.2 is a controlled, data-only successor to the ten-class V1.1 student. It
does **not** change the network, class order, input contract, teachers, loss,
NPU operator policy, or formal acceptance thresholds. It addresses the only
failed V1.1 formal gate: excessive macro-F1 drop under strong CFO, multipath,
and combined impairments.

Frozen class order:

`AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`

The deployed graph remains `[N,2,1024] -> [N,10]` and uses only `Conv`,
`Relu`, `Add`, `ReduceMean`, and `Gemm` after export. The V2 champion and the
two V1 checkpoints remain frozen training-only teachers.

## What changed

Training uses a deterministic curriculum with four profiles:

- `base`: the unchanged V1.1 stochastic channel;
- `cfo_focus`: guaranteed CFO sampled inside ±2.2 kHz;
- `multipath_focus`: guaranteed 2–5-tap channel with delay up to 16 samples;
- `multi_impairment`: guaranteed CFO + phase noise + IQ imbalance + multipath.

The mix ramps from `70/10/10/10%` to `40/20/20/20%`. Validation remains on
the original V1.1 distribution. Formal OOD profiles are stronger than the
training support, so the experiment measures generalization rather than exact
parameter memorization.

The pilot compares:

1. `legacy_distribution` — exact V1.1 distribution;
2. `single_focus` — CFO and multipath profiles, no combined profile;
3. `combined_focus` — the full curriculum.

Selection combines the unchanged validation score with the worst held-out OOD
macro-F1. A robust variant must improve the V1.1-distribution control by at
least 0.02 maximum OOD-drop and pass both-seed pilot floors before formal
training is allowed.

## Status

`ready-for-cuda-preflight`, not ready for pilot/formal training until the exact
source hash prints `AD_AMR_V1_2_CUDA_PREFLIGHT_PASS` on a BF16-capable CUDA GPU.
No final-blind namespace is instantiated by preparation, pilot, or formal code.

## AutoDL flow

From the extracted archive root:

```bash
bash autodl_ad_amr_v1_2/setup_env.sh
set -o pipefail
bash autodl_ad_amr_v1_2/run_preflight.sh 2>&1 | tee ad_amr_v1_2_preflight.log
echo "preflight_rc=${PIPESTATUS[0]}"
```

Only after `preflight_rc=0` and `AD_AMR_V1_2_CUDA_PREFLIGHT_PASS`:

```bash
nohup bash autodl_ad_amr_v1_2/run_pilot.sh > ad_amr_v1_2_pilot.log 2>&1 &
echo $! | tee ad_amr_v1_2_pilot.pid
tail -f ad_amr_v1_2_pilot.log
```

Only when the pilot prints `AD_AMR_V1_2_PILOT_PASS`:

```bash
nohup bash autodl_ad_amr_v1_2/run_formal.sh > ad_amr_v1_2_formal.log 2>&1 &
echo $! | tee ad_amr_v1_2_formal.pid
tail -f ad_amr_v1_2_formal.log
```

Operator compatibility is not vendor deployment proof. A promoted checkpoint
still requires vendor compilation, emulator/board parity, and recorded/live SDR
validation.
