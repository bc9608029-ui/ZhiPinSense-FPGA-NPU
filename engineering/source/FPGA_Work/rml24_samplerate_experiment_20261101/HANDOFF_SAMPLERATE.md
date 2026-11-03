# Sample-rate experiment, 2026-11-01
Formal deployment unchanged:2.56MS/s, range_20261101.
Single BPSK source, TX fixed2.56MS/s, 2400MHz, -40dB. RX fast AGC,5MHz RF bandwidth.
Hardware1.28MS/s write rejected EINVAL(-22): not claimed passed. No FIR/firmware changes.
Attempt2: hardware2.56MS/s, digitally decimate to1.28 then interpolate2.56:5/5 recovered and BPSK predicted. Baseline hardware2.56MS/s:5/5 recovered and BPSK predicted.
Attempt3: hardware requested5.12MS/s, actual5119999S/s; resample approximately1/2 to model2.56MS/s:5/5 recovered and BPSK predicted. Original strict equality rejection retained.20Hz hardware readback tolerance, rational resampling denominator limited1024.
Not a24class or wideband-signal validation. Digital1.28 test does not establish hardware1.28 support or no information loss for all signals.
RX original/unresampled IQ and adapted IQ both saved on board /root/rml24_samplerate_experiment_20261101/attempt2 and attempt3, with CAPTURE_RESULT/CLASSIFICATION_RESULT. PC result transcript RESULT_AND_RESTORE.txt.
During repeated clean experiment restarts systemd start-limit-hit occurred; prior process exited0/clean. No hardware guard marker. reset-failed then start restored formal service. Runtime configuration not changed.
Recommendation:retain formal2.56MS/s. Further adaptation validation needs24classes, symbol rates and bandwidths; signal bandwidth, not only sample-rate number, determines losses.
