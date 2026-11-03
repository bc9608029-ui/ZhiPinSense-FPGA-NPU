# Deployment plan - PREPARED ONLY, NOT INSTALLED

Current SD BOOT.bin, uEnv.txt and download.bit match the original backup. Existing uEnv performs fatload download.bit and fpga loadb before Linux. Therefore preserve BOOT.bin/uEnv/Image/DTB; use the validated converted bit as the single download.bit replacement after all RF gates pass. Never use an unconverted Vivado bit or rewrite Flash/BOOT.bin for this plan.

Before any installation: fresh backup and SHA verification of SD files, both original services and /opt runtime; preserve them on PC and board. Verify sufficient disk space. Preserve old release, do not overwrite /opt/rml24-system. Stage new release separately, verify every source/binary/model/bit SHA, atomic current symlink switch and service install only after promotion receipt exists.

Persistent marker survives reboot; no boot/service script may clear it. No automatic hardware reset implemented. Recovery requires proven PL/full power reset with no live owners, explicit audited marker clearance and version/idle verification before restart. The guard must fail closed for all ambiguous situations.

Template launcher currently uses a 24-hour clean supervisor session, with systemd restarting after normal EOF; it is NOT promoted or tested as production entry. Bounded production evidence retention/disk-space policy must be implemented and validated before unattended deployment. No template should be installed as-is merely because syntax passes.

Deployment gates: formal fixed240>=235, search240>=235, sweep24>=23, zero missing, clean RX/TX restoration, actual FPGA backend, no hardware faults, frozen identities. Also physical UI and final boot verification remain required. New-seed45/48 limitation remains documented.

After promotion: atomically replace SD download.bit with converted candidate, keep prior bit backup; install separate integrated service and disable old two services (do not erase definitions); start and verify software. Read back all SHAs. If failure, stop candidate gracefully, restore old SD bit/current/service enablement, and reload original PL only after owners have exited. No blind automatic restart after unsafe hardware.

Final acceptance: reboot with serial boot marker, version/idle plus UI/RX checks; physical screen and touch; power-off cold start without JTAG. Physical confirmations remain pending while user away.

## Prepared revision: boot-proven recovery, not installed

To support normal unplug/replug recovery safely, a candidate uEnv adds one kernel argument binding the bit SHA; the existing loadbit && Linux gate is retained. BOOT/Image/DTB remain unchanged. A persistent fault can be archived only after changed boot_id, exact kernel proof, exact SD bit/uEnv hashes, no NPU owners, exclusive guard lock and successful version/idle probe. Same-boot, corrupt/unknown markers and mismatches still fail closed. Six policy checks pass offline; actual Linux mount/probe/new-boot execution NOT tested yet. This supersedes the earlier 'uEnv untouched' preparation choice, not any verified hardware result.
