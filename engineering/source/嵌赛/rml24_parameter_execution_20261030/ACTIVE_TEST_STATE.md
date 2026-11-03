# Active unattended tests — 2026-10-31 00:03

User explicitly authorized finishing both tests autonomously and does not want yes/no interruptions. Continue, do not pause solely to request routine test choices. System permission gates still apply; do not bypass them.

## Live process

- `resume_all.py` PID 14636, unified exec session **54326**, still running.
- Earlier `run_tests.py` PID15220/session40203 finished with no-space guard, not an RF correctness failure. Original receiver service was restored at that point.
- Windows Task Scheduler supervisor registration failed with Access Denied; **no scheduled supervisor is running**. Do not claim otherwise. The current native Python process explicitly chains the remaining stages itself.
- Latest authoritative RF stage is `STATUS.json` (full45 running). `RESUME_STATUS.json` can retain the last recovery substage until the experiment returns.

## Verified results

All have denominator24 for smoke /240 for full, fixed opportunity selection before inference, measurement_valid=true:

| arm | 1 | 2 | 4 | 8 |
|---|---:|---:|---:|---:|
| smoke35 |23|23|24|24|
| smoke25 |16|22|22|23|
| smokeAGC |14|23|23|21|
| smoke45 |24|24|24|24|
| full35 |231|236|237|239|
| full25 |176|205|216|223|
| fullAGC |187|214|221|220|

full45 original attempt transmitted its plan but RX refused before capture due insufficient space. Local failed attempt was preserved as `full45_failed_no_space_*`. Retry starts PC time 2026-10-31 ~00:02:20, 240 slots *6s; RX PID7887. Expect capture ~00:26:40, then NPU replay/scoring. No need to rerun completed arms.

## Space recovery complete

- Backup `raw_before_space_recovery.tar`, 2794455040 bytes, 9336 regular files, each file SHA and member set independently verified against remote manifest.
- Removed only5203 matching `.raw.npy` temporary copies from **this run** on board, after rechecking their SHA. Deleted2728536448 bytes. Evidence receipt `SPACE_RECOVERY_RECEIPT.json`.
- First-phase raw now in F tar, not its original board pathname. Logs and tensors remain on board. Do not claim all old raw still exists there.
- Board temporary run: `/root/rml24_param_exec_1793366907`.

## Board environment/access

- host root@192.168.126.49; PC wired .10. SSH works now.
- Test key **usable NTFS copy**: `C:/Users/shado/.ssh/rml24_test_20261030_ed25519` (derive USERPROFILE). Original F key cannot be used with Windows OpenSSH because F reports Everyone ACLs; do not try repeatedly or expose private bytes.
- `/root` ownership was corrected by user from fmsh to root so sshd StrictModes accepts test key. Key has restrict option, no PTY; noninteractive command/SFTP allowed.
- helpers use exact frozen host key validation and identities-only. See `run_tests.py` SSH/SCP definitions. No password needed now.
- board prep `/root/rml24_test_setup_w1QsCF/rml24_test_readiness_20261030`.
- Python `/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3`.
- NPU `/root/amr_rescue_20261025/build/npu_stream`.
- model `/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16`; frozen raw c1781aec… /json28272abc…
- recovery `/opt/rml24-system/rml24_final/recovery/candidate_two_dc.py`, SHAe0aa1202…
- RX usb:1.4.5, TX usb:1.7.5, recheck if hardware reconnects.
- PC libiio0.26 `D:/radioconda/Library/bin/libiio.dll`; add its parent with os.add_dll_directory. System32 libiio incompatible old API.
- receiver `rml24-receiver.service`, UI `rml24-ui.service`. Receiver auto-restarts waiting for old PC .50; ActiveState can be activating rather than active. Do not treat that as missing service or silently leave it disabled.

## Automatic next stage

`resume_all.py` finishes full45, writes PARAMETER_RESULTS.json and restores original receiver state, then executes `run_fpga_tests.py` as its child.

FPGA script:

1. Board native compile first; preserve any compile failure and repair it, no new bit generation needed.
2. Historical **read-only** Vivado2018.3 JTAG enumeration (`enumerate_pl_jtag_v2.tcl`); must find exactly one xc7z030. If no cable, report actual external blocker; do not fake programming.
3. Stop exact original RX/UI services, no unrelated process kills. Use known historical JTAG programming script with only frozen bit path replaced. No Flash/SD/BOOT writes.
4. Candidate SHA47b9e1fd…; original rollback SHA22fec95c… . Workspace prep has both verified files.
5. Isolated MMIO/DDR probe,8 NumPy/software/fpga/auto vectors, explicit missing-driver fallback, NPU liveness, candidate RF24/240 at35dB.
6. Finally restore original bit (up to2 attempts), NPU liveness, original active UI/RX services. Pull service/UI logs. Physical screen observation remains unverified without user.

- FPGA work ASCII scratch `F:/FPGA_Work/rml24_boardtest_20261030`, no new synthesis/route.
- B output `fpga_execution/`; its STATUS.json and fpga_supervised.log show exact current stage.
- Candidate retains the same two inherited NPU min-period violations as old working baseline: not full STA PASS/manufacturer waiver.
- This is **isolated diagnostic** and new-image regression. Formal receiver scan backend integration and continuous1000-frame stress are not implemented by the current script; report them pending, not completed.

## Reports

Run `summarize_results.py` to refresh RESULTS_LATEST.json/.md from actual score files; it does not access devices. Do not promote gain45 or fewer repeats based on smoke alone. No shortened-TX performance claim: actual TX still sends8 segments. Silence test checks capture/restore, not negative-control classification rejection.
