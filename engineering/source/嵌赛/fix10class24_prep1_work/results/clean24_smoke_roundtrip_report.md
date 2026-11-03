# fix10class24-prep1 — offline roundtrip verification

checkpoint_sha256 = `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d`

| source_index | modulation | raw24 pred | dep23 pred | raw24 agree | dep23 agree | corr | nmse | rms_scale_err |
|---|---|---|---|---|---|---|---|---|
| 0 | OOK | OOK(0) | OOK(0) | YES | YES | 0.999936 | 1.383e-04 | 3.029e-03 |
| 500 | 4ASK | 4ASK(1) | 4ASK(1) | YES | YES | 0.999925 | 1.523e-04 | 1.320e-03 |
| 1000 | 8ASK | 8ASK(2) | 8ASK(2) | YES | YES | 0.999928 | 1.450e-04 | 1.228e-03 |
| 1500 | BPSK | BPSK(3) | BPSK(3) | YES | YES | 0.999877 | 2.649e-04 | 4.272e-03 |
| 2000 | QPSK | QPSK(4) | QPSK(4) | YES | YES | 0.999906 | 2.162e-04 | 5.162e-03 |
| 2500 | 8PSK | 8PSK(5) | 8PSK(5) | YES | YES | 0.999910 | 2.053e-04 | 4.911e-03 |
| 3000 | 16PSK | 16PSK(6) | 16PSK(6) | YES | YES | 0.999925 | 1.771e-04 | 5.037e-03 |
| 3500 | 32PSK | 32PSK(7) | 32PSK(7) | YES | YES | 0.999904 | 2.198e-04 | 5.238e-03 |
| 4000 | 16APSK | 16APSK(8) | 16APSK(8) | YES | YES | 0.999906 | 2.108e-04 | 4.671e-03 |
| 4500 | 32APSK | 32APSK(9) | 32APSK(9) | YES | YES | 0.999953 | 1.173e-04 | 4.705e-03 |
| 5000 | 64APSK | 64APSK(10) | 64APSK(10) | YES | YES | 0.999941 | 1.457e-04 | 5.209e-03 |
| 5500 | 128APSK | 128APSK(11) | 128APSK(11) | YES | YES | 0.999873 | 2.759e-04 | 4.492e-03 |
| 6000 | 16QAM | 16QAM(12) | 16QAM(12) | YES | YES | 0.999919 | 1.884e-04 | 5.005e-03 |
| 6500 | 32QAM | 32QAM(13) | 32QAM(13) | YES | YES | 0.999880 | 2.630e-04 | 4.544e-03 |
| 7000 | 64QAM | 64QAM(14) | 64QAM(14) | YES | YES | 0.999911 | 1.998e-04 | 4.671e-03 |
| 7500 | 128QAM | 128QAM(15) | 128QAM(15) | YES | YES | 0.999966 | 9.557e-05 | 5.175e-03 |
| 8000 | 256QAM | 256QAM(16) | 256QAM(16) | YES | YES | 0.999968 | 9.472e-05 | 5.476e-03 |
| 8500 | AM-SSB-WC | AM-SSB-WC(17) | AM-SSB(17) | YES | YES | 1.000000 | 7.696e-07 | 1.462e-05 |
| 9000 | AM-SSB-SC | AM-SSB-SC(18) | AM-SSB(17) | YES | YES | 0.999997 | 6.476e-06 | 5.869e-05 |
| 9500 | AM-DSB-WC | AM-DSB-WC(19) | AM-DSB-WC(18) | YES | YES | 0.999745 | 5.667e-04 | 7.228e-03 |
| 10000 | AM-DSB-SC | AM-DSB-SC(20) | AM-DSB-SC(19) | YES | YES | 0.999652 | 7.470e-04 | 6.821e-03 |
| 10500 | FM | FM(21) | FM(20) | YES | YES | 0.999869 | 3.476e-04 | 7.611e-03 |
| 11000 | GMSK | GMSK(22) | GMSK(21) | YES | YES | 0.999876 | 2.600e-04 | 3.417e-03 |
| 11500 | OQPSK | OQPSK(23) | OQPSK(22) | YES | YES | 0.999882 | 2.549e-04 | 4.025e-03 |

**raw24_prediction_agreement = 24/24**  **deployed23_prediction_agreement = 24/24**  **raw24_label_correct = 24/24**  **deployed23_label_correct = 24/24**  **clip_count_zero = 24/24**  **nan_inf = 0**
