# Frozen preprocessing and numerical contract

## Actual frozen sample path

```text
symbols / OFDM bins / FSK phase
→ pulse shaping or waveform generation (complex128)
→ per-record clean RMS normalization to amplitude=1.0
→ configured static CFO/phase in generator (both zero formally)
→ cast complex64
→ ChannelPipeline in its fixed source order
→ stack [real, imag] and cast float32
→ tensor [2,1024]
→ TimePowerPhase float frontend
→ time branch + physical branch + concat classifier
```

The clean generator executes:

```text
r = sqrt(mean(I[n]^2 + Q[n]^2))
x_clean[n] = x_generated[n] * amplitude / r
amplitude = 1.0
zero check: r <= np.finfo(np.float64).eps
epsilon value = 2.220446049250313e-16
```

This is a per-record normalization, but it occurs **before** ChannelPipeline.
There is no per-record power/RMS normalization after channel effects or before
the network. Train, validation, development_test and SNR sweep use the same
generator/channel/tensor formulas; only their deterministic split/epoch seeds
and assigned samples differ.

The time branch starts with Conv1D and has no input normalization. The physical
branch begins with `BatchNorm1d(3, affine=False)`. Its PyTorch defaults are
`eps=1e-5`, `momentum=0.1`; training statistics cover batch and time axes, and
evaluation uses frozen running statistics. This is not record-wise RMS
normalization.

Source-of-truth functions:

- `datasets.modulation_generator._normalize_rms` and `generate_iq`
- `datasets.synthetic_dataset.SyntheticModulationDataset.__getitem__`
- `channel.channel_pipeline.ChannelPipeline.__call__`
- `models.qam_aware_rfnet.TimePowerPhaseRFNet.forward`

## SDR int16 to model input

Let `I_int,Q_int` be signed int16 samples and let `s_adc` be model units per ADC
count, including the frozen receiver gain calibration:

```text
I_float = s_adc * I_int
Q_float = s_adc * Q_int
x_model = I_float + j Q_float
```

The reference Q1.15 interpretation uses `s_adc=2^-15`, but this value is not a
claim about a future SDR driver. The actual `s_adc` must be measured/frozen with
non-blind replay vectors. Do not normalize every received frame to RMS=1: doing
so would remove amplitude/noise behavior present during training.

There is an important Sim-to-Real risk. Training first sets desired clean RMS to
1, then adds exact AWGN. At -20 dB the total RMS can be approximately
`amplitude_scale*sqrt(101)`, far outside a Q1.15 full-scale interval. A real ADC
and AGC cannot reproduce this without a different gain/headroom convention.
Consequently Q1.15 is a mathematical transport reference only. Receiver AGC,
ADC clipping and the model-unit scale must be characterized before claiming
low-SNR parity.

## FPGA Power/Lag equivalence

Compute exact integers:

```text
P_int  = I_int^2 + Q_int^2                         // unsigned 32 bit
Re_int = I[n]I[n-1] + Q[n]Q[n-1]                  // signed 33 bit
Im_int = Q[n]I[n-1] - I[n]Q[n-1]                  // signed 33 bit
```

Then:

```text
P_float  = s_adc^2 * P_int
Re_float = s_adc^2 * Re_int
Im_float = s_adc^2 * Im_int
```

These are mathematically identical to computing Power/Lag from converted float
IQ. Lag values at sample zero are deterministic zero. No square root, angle or
complex hardware operator is involved.

For symmetric INT8 tensor scale `S_c` and zero point zero:

```text
q_c = saturate[-127,127](round_ties_away(value_float / S_c))
```

An RTL implementation may replace `s_adc/S_c` and `s_adc^2/S_c` with calibrated
integer multiplier/shift pairs. Those coefficients, rounding rule, saturation
count and channel order are part of the deployed model artifact—not runtime
metadata features.

The reference test scales span Q1.15's mathematical ranges. Final scales must
come from a frozen calibration set drawn from the training distribution.
