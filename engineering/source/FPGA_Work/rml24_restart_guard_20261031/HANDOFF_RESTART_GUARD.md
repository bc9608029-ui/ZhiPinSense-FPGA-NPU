# Restart protection handoff - 2026-10-31

Status: CANDIDATE_RESTART_PROTECTION_VERIFIED_NOT_DEPLOYED.
Candidate: /root/rml24_fpga_ui_20261031/delivery_guard_persistent.

## Fix

Exclusive lock inherited by worker; persistent in-flight marker fsynced before Device open. Normal worker exit 0 removes marker. Fault, signal kill, supervisor kill or launch exception retains marker and blocks subsequent Device access. Supervisor propagates exit 78. Independent service template uses RestartPreventExitStatus=78; formal services unchanged.

Persistent marker: /var/lib/rml24-fpga-shared-guard/reset_required.json.
Do NOT delete it in startup/stop/boot scripts. Linux reboot does not erase it. After a real fault require independently verified PL/full power reset AND explicit audited recovery before clearing it. Current candidate error says full board reboot required: reboot alone is insufficient to clear this persistent lock. No automatic reset or marker-clear mechanism installed.

## Verified

Six simulated fault/normal-exit tests PASS on board. Supervisor mock propagation 78 PASS. Transient mock systemd service ExecMainStatus=78, NRestarts=0 PASS. Two no-TX normal start/stop cycles PASS (initial /run variant; history retained).

Persistent variant real BPSK RF: fixed first-window denominator 1, correct1, missing0. Same waveform produced24 valid class3 captures and24 FPGA display PSD calls. Not24-class accuracy. Normal worker exit, marker removal, RX restore and TX readback restore PASS.

Original bit restored. Original UI active. Old receiver waits/retries PC control192.168.126.50:39012, unavailable; this is not healthy standalone operation or a new guard fault. Original model/NPU/bit/service configs unchanged.

## Limits and next

No real hardware hang injected, automatic reset, full reboot recovery acceptance, formal long regression or final persistent deployment. Service file is a template, not installed. This fixes the unsafe restart path in the independent candidate; it does not repair a stuck FPGA automatically. Separate new-message result45/48 unchanged, not fixed by this guard.

Before promotion: freeze truth/scoring and candidate SHAs; obtain approval for long regression; verify physical UI; review final service/fault recovery; only then deploy and cold-boot accept.

## Evidence

RESTART_GUARD_RECEIPT.json: scope/results. BOARD_EVIDENCE.json.gz: board sources, freeze and summaries. RF_FUNCTIONAL_RECEIPT.json: actual RF receipt. Two source files match board SHAs. test_guard.py and test_supervisor_guard.py reproduce mock checks.

Board no-TX: /root/rml24_fix3_1793440268.
Board RF: /root/rml24_fix3_1793440597.
PC RF: E:/FPGA_Work/smartscan_prefetch_fix3_20261031/phase26_persistent_guard_rf.
