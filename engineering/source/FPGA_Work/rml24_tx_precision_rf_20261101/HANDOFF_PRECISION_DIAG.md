# Targeted TX precision RF comparison

This is development evidence on six selected earlier failures. It does not change the formal234/240 search result and does not authorize deployment.

- 14_05.bin: original0/4; high precision3/4.
- 13_01.bin: original0/3; high precision4/4.
- 17_00.bin: original3/3; high precision4/4.
- 18_06.bin: original2/3; high precision3/3.
- 18_07.bin: original3/3; high precision3/3.
- 23_04.bin: original3/4; high precision3/4.

Capture counts differ because asynchronous acquisition is not synchronized to TX; report denominators separately. Analog attenuation compensates ideal pilot magnitude; no RF power meter calibration was performed. Original receiver, model and frame structure stayed unchanged.

Evidence: SCORE.json; PRIVATE_EVENTS.json (scale/gain/mismatch); CLASSIFICATION_RESULT.json; RESULT.json; RESTORED_SERVICE.txt. Unaveraged IQ retained on board under /root/rml24_tx_precision_rf_20261101.

Next: independent24-class source0 short coverage is running under E:/FPGA_Work/rml24_tx_precision_24rf_20261101. A formal candidate needs separately frozen contracts and authorized full regression.
