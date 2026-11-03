# Exact activation order - NOT EXECUTED

1. Audit all approved formal scores, required same-input NPU integrity comparison and physical UI gate. Do not fabricate PROMOTED_RELEASE.json while any gate pending.
2. Back up current SD files, old services/enablement/current links and runtime; verify SHA. Old download.bit22fec95c..., uEnv b8156344..., BOOT ff350477....
3. Stage immutable /opt/rml24-integrated/releases/<release-id> from delivery_guard_persistent, plus prepared launcher/retention. Keep original /opt/rml24-system unchanged. Verify all artifact/model/worker/SDK identities. Stage converted candidate bitf42dd12f... separately. No activation yet.
4. Stop old UI/RX gracefully, verify no live NPU owners or guard lock. If a fault marker exists, do not clear it merely to proceed; verified PL/full reset and audited recovery required.
5. Temporary-program the validated converted candidate via JTAG and confirm DONE/EOS/GWE/CRC/version-idle. This is only an initial runtime check; final persistence comes from SD in next step.
6. Mount SD p1 explicitly, make verified old-bit backup, write newbit to a temporary file, fsync, SHA readback and atomic rename to download.bit. Preserve uEnv/BOOT/Image/DTB unchanged; sync and unmount. Keep rollback copy.
7. Atomically switch separate current symlink, install reviewed integrated unit; disable old two units without deleting them, daemon-reload, enable/start integrated service. Confirm runtime identity, actual FPGA PSD, NPU accounting, restored radio behavior and no fault marker. GUI console not launched during formal testing.
8. If activation fails, stop only own service gracefully, verify owners exited, restore old SD bit/current/enablement; load original bit before restoring old runtime. Do not reuse hardware after unsafe fault without a verified reset.
9. Software reboot and serial boot-marker/version/service check, then controlled power-off cold start without JTAG and physical screen/touch acceptance. User needed for physical power/screen steps. No statement of final success before these pass.

TX console launcher points to existing tested local Python/dependencies. It opens the GUI only, no automatic TX. User must choose device/frequency/gain/message and start deliberately. Current formal sessions must finish before opening another transmitting session.
