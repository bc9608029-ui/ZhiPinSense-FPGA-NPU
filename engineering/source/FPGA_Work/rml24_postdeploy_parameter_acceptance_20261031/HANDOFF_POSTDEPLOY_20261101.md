# Final deployment and post-deployment test handoff

Date: 2026-11-01. Status: DEPLOYED_COLD_BOOT_BACKEND_AND_USER_DISPLAY_CHECK_PASS.

## Installed system
Release: /opt/rml24-integrated/releases/r1773414967
Current: /opt/rml24-integrated/current
Service: rml24-integrated.service (enabled, active; observed NRestarts=0).
SD download.bit SHA256: f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c
SD uEnv.txt SHA256: 0091f295e6a4c501cc358a659f52528462cf41fac683370336f98fcd92cd1fa5
Backup: /root/rml24_final_install_20261031/backup
Original services retained but disabled. Original model and inference core unchanged.

## Observed cold boot
User powered off after confirmed Power down, then powered on. New boot_id 45b4754c-e04b-4d8c-8a3a-467bcd5b9b01 differs from original b68cfa6b-e214-407a-8d6d-74b2e10e5221. Kernel command line contains frozen candidate bit SHA. Service and NPU/UI/RX processes auto-started before testing; no manual program download or service start was issued. Physical display is pending separate confirmation.
Current run: /var/log/rml24-integrated/r84ec9319d081.

## Completed checks
Prior formal frozen-waveform RF: FIXED235/240, SEARCH237/240, SWEEP24/24, missing0.
Backend control: fixed2401/2400 MHz actual readback; scan counts11/5/21/8; six invalid ranges/steps rejected without changing applied settings; three modes; STOP/START; restored defaults.
TX GUI: 12 cases, three classes(3/4/12), original/new message, gains -40/-50; all TX completion/restoration checks passed. Matched valid records all predicted expected class; this is a limited diagnostic, not 24-class general accuracy.
Frequency search, continuous45-second observation per case: 2398MHz class3 5/5 valid records correct; 2400MHz class4 14/14; 2403.6MHz class3 14/14. All three cases have valid results and no observed wrong valid record. Post-only QPC mapping used, not formal paired pre/post clock acceptance.

## Preserved limitations/failures
Initial TX address usb:1.9.5 was stale after power cycle: no attributes changed. Re-enumerated unique TX usb:1.10.5.
One-second intermittent TX test missed2398/2403.6MHz; longer dwell captured both. Do not claim arbitrary short bursts are always discovered.
Legacy collect_status.py chooses newest filesystem timestamp and can select previous boot log after RTC reset. Standalone live_status.py instead resolves systemd MainPID --run; deployed signed recognition files were not altered. Do not use old health summary alone to declare service failed.
Spectrum is frame-relative, not calibrated dBm/dBFS. Constellation is unsynchronized recovered IQ, not symbol-timing/carrier-recovered ideal points. FPGA assists display PSD only. Inherited NPU min-period timing exceptions remain documented in prior FPGA handoff; not full timing-clean assertion.
No long stability soak, all-message/all-class/all-gain exhaustive matrix, or simultaneous multi-signal validation claimed.

## Remaining
Physical final UI/touch confirmation. Original user already confirmed earlier UIs, but latest deployed visual changes need explicit confirmation.
Do not modify model/frame/thresholds simply to improve these scores. No further full240 regression needed for unchanged system unless a material code change occurs.
History: FIXED/SEARCH three confirmations; SWEEP one valid observation. No change in this round.
Default restored: FIXED2400MHz, scan2395..2405MHz step1MHz, running.
Normal shutdown before removing power. Final use does not require login or JTAG.

## Evidence
FINAL_FREQUENCY_DIAGNOSTIC.json; PARAMETER_RF_DIAGNOSTIC.json; board_parameter_evidence.txt; longhold_board_evidence.txt; clock_post.json; final_rf_serial.txt.
Sessions: session_1793499963273022800 (12 cases), session_1793500134094180700 (short-dwell misses), session_1793500316938617800 (long-dwell3freq).
All PC outputs in this directory. Board parameter result: current run/POSTDEPLOY_PARAMETER_TEST.json.

## Final user display confirmation
2026-11-01: User confirmed final five-page display and page switching normal, in reply to the screen/plots/history check. This closes that visual checklist. No new frequency-keypad or touch-parameter application test was requested in this final check; backend parameter application passed separately.
