# Dataset Audit V1

- Config: `F:\嵌赛\rf_cognitive_system\configs\baseline.yaml`
- Base seed: `2026`
- Exact overlap in first 64 records per split: `{'train_validation': 0, 'train_test': 0, 'validation_test': 0}`
- Blocking leakage found: `False`
- RRC/OFDM occupied bandwidth estimate: `21600.0` / `24000.0` Hz

## Findings

- **note**: Constant-envelope FSK and OFDM CP/PAPR/cyclostationarity are legitimate modulation properties, but models may rely heavily on them; report per-class results.
- **note**: All classes use randomized record-start timing. OFDM occupied bandwidth is approximately matched to RRC single-carrier bandwidth.

See the adjacent CSV files for class, SNR, modulation x SNR, power, RMS, PAPR, boundary, and timing-offset statistics.