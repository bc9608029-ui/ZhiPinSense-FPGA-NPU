# Formal V1/V2 channel impairment audit

Baseline V1 reads `configs/baseline.yaml`. QAM-Aware V2 loads that same baseline
and only adds its model/output/final-blind sections. The saved V2
`effective_config.json` matches the following channel settings.

| Impairment | Formal state | Probability / range | Frozen source |
|---|---|---|---|
| AWGN | Enabled; effectively always applied | Assigned SNR `-20:2:20 dB`; exact per-record noise power | `channel/awgn.py:add_awgn`, final block of `ChannelPipeline.__call__` |
| Rayleigh | Disabled | probability 0 | `channel/fading.py:rayleigh_fading` |
| Rician | Disabled | probability 0; K 3–10 inactive | `channel/fading.py:rician_fading` |
| Multipath | Disabled | probability 0; 2–5 taps, max delay 12 inactive | `channel/fading.py:multipath_fading` |
| CFO | Enabled | probability 0.6; uniform -1200…1200 Hz | `channel/impairments.py:carrier_frequency_offset` |
| Random phase | Enabled | probability 0.6; uniform -3.14159…3.14159 rad | `channel/impairments.py:random_phase_offset` |
| Phase noise | Disabled | probability 0; std 0.0001…0.004 rad inactive | `channel/impairments.py:phase_noise` |
| SFO | Disabled | probability 0; -80…80 ppm inactive | `channel/impairments.py:sampling_frequency_offset` |
| IQ imbalance | Disabled | probability 0; gain -1…1 dB, phase -5…5° inactive | `channel/impairments.py:iq_imbalance` |
| DC offset | Disabled | probability 0; magnitude 0…0.08 inactive | `channel/impairments.py:add_dc_offset` |
| Amplitude scaling | Enabled | probability 0.5; uniform 0.7…1.3 | `channel/impairments.py:amplitude_scale` |
| Clipping | Disabled | probability 0; 1.5…3.0 × record RMS inactive | `channel/impairments.py:clip_iq` |
| Narrowband interference | Disabled | probability 0; SIR 5…25 dB inactive | `channel/impairments.py:narrowband_interference` |
| Burst interference | Disabled | probability 0; SIR 0…20 dB, duty 0.05…0.3 inactive | `channel/impairments.py:burst_interference` |

### AWGN subtlety

`SyntheticModulationDataset` assigns every formal sample an SNR from
`dataset.snr_values` and passes it as the explicit `snr_db` argument. Therefore
the pipeline adds AWGN even without consulting its random activation and uses
the 21-point `-20…20 dB` list. The `awgn.snr_db: [-10,20]` range would only be
sampled when a caller does not provide an explicit SNR; it is not the formal
train/val/test SNR range.

Noise power is referenced to desired signal power captured after fading,
multipath, amplitude scaling and clipping, but before interference and AWGN:

```text
P_noise = P_desired / 10^(SNR_dB/10)
```

The random complex Gaussian vector is rescaled so its measured finite-record
power equals `P_noise` exactly, apart from final complex64 rounding.

### Consistency verdict

The previous statement that formal training did not cover multipath, fading,
IQ imbalance, DC offset, clipping or narrowband/burst interference is correct.
It should additionally mention that phase noise and SFO were also disabled.
No contradiction was found in the existing deployment-prep documents.
