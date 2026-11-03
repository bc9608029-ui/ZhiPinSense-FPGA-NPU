# Passive-Scan Result List -- SYNTHETIC DEMO (NOT REAL RF)

> Source: `host_tests/make_passive_scan_demo.cpp` (scripted fake device + synthetic spectra).
> This is a FORMAT example only.  It contains NO real RF capture and NO modulation identification.

Band: 2400.000–2408.000 MHz, step 1.0 MHz, coverage ≈ 2.048 MHz, 9 steps.  RX sample rate 2.56 MSPS, 1024-bin PSD, noise floor −90 dBFS (synthetic).

| # | Step LO (MHz) | Detected (MHz) | BW (kHz) | SNR (dB) | outcome | verified | note |
|---|--------------|----------------|----------|----------|---------|----------|------|
| 1 | 2400.000 | 2400.701 | 2.50 | 22.00 | CLASSIFICATION_UNAVAILABLE | no | single candidate |
| 2 | 2402.000 | 2401.396 | 12.50 | 15.00 | CLASSIFICATION_UNAVAILABLE | no | single candidate |
| 3 | 2404.000 | 2403.201 | 2.50 | 17.00 | CLASSIFICATION_UNAVAILABLE | no | single candidate |
| 4 | 2406.000 | 2406.301 | 2.50 | 19.00 | CLASSIFICATION_UNAVAILABLE | no | single candidate |
| 5 | 2408.000 | 2407.601 | 2.50 | 14.00 | CLASSIFICATION_UNAVAILABLE | no | single candidate |

Every record is a DETECTED candidate.  `verified=no` and `CLASSIFICATION_UNAVAILABLE` are deliberate: a passive signal does not satisfy the frozen model-input contract, so no modulation label is ever asserted.
