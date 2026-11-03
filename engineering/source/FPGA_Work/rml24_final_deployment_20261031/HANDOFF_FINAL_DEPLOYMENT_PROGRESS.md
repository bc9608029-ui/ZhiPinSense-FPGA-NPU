# Continue toward final deployment - 2026-10-31

## Current override: explicit approval received and RF RUNNING

User explicitly approved fixed240 + search240 + sweep24. APPROVAL.json is recorded with current plan/helper hashes. Controller native session84729 is already running; monitor11393. DO NOT launch a duplicate controller, re-create output directories, or re-use the preparation-only instructions below to restart. Read LIVE_PROGRESS.json and formal_console.log first. Each round restores the original bit/services, audits fixed denominator and then the controller proceeds. After completion, inspect all scores and gates before staging/activation. Final deployment remains unperformed.

Historical preparation state: WAITING_REQUIRED_USER_APPROVAL_FOR_FORMAL_RF. No formal RF round started. Do not interpret the user's absence as approval. The pending async question requests fixed240 + search240 + sweep24, ~75-90 minutes, using this FORMAL_PLAN.json. User earlier explicitly required approval before long regression. Deployment intent is authorized in general, but test-specific prior-approval condition remains.

## Verified diagnosis

Phase27 saved raw IQ and actual input tensors, repeated the three formerly failing sources with first-window scoring:2/3. All49 eligible recovered inputs were replayed through unchanged original NPU, together with the three clean source inputs. Clean predictions: expected17 ->18, expected23 ->23, expected10 ->9. Thus two are also frozen-model clean-input errors, not solely receiver/FPGA corruption. No model/source/threshold changes made. New-message45/48 remains reported separately. Failure-source retest is diagnostic, never substituted for earlier accuracy.

Diagnostics: E:/FPGA_Work/smartscan_prefetch_fix3_20261031/phase27_three_waveform_diagnostic. Board raw capture /root/rml24_fix3_1793441664/quiet/capture. Direct NPU comparison /root/rml24_clean_compare_1773394583/RESULT.json. Private mapping remains PC-side.

## Formal test readiness

FORMAL_PLAN.json defines exact modes, sources, times and gates. TRUTH_FROZEN_PC_ONLY.json matches all240 historical private events and source SHAs. tx_formal.py is an independent timed sender, with no RX connection, restore readback and stop request support. audit_formal.py retains first failures/missing and enforces actual FPGA backend/NPU accounting. Three synthetic scoring tests PASS, no-approval launch gate PASS. Three isolated workflows each restore original bit/services. Board errors request immediate TX stop; TX failures abort a round. All helpers and external dependencies are SHA frozen.

When explicit approval arrives: write APPROVAL.json with allowed=true, exact current plan_sha256 and helpers_sha256 from READINESS_RECEIPT.json plus actual user answer. Do not copy old approval. Run D:/Miniconda3/python.exe -u E:/FPGA_Work/rml24_final_deployment_20261031/run_formal.py, preserving console output here. It sequentially runs fixed240, search240 and sweep24 and audits them. All failures remain. No automatic re-test or promotion. Accuracy gates235/240,235/240,23/24 plus missing0 and all hardware/restore/accounting gates. If hardware/process error, stop subsequent rounds; do not blind restart on unsafe busy.

## Deployment prep (not installed)

Persistent guard fix at E:/FPGA_Work/rml24_restart_guard_20261031: six simulated faults, supervisor78 propagation, systemd mock no-restart, two quiet cycles and single realRF check passed. Persistent state /var/lib/rml24-fpga-shared-guard; do not auto-clear on reboot. Requires independently verified reset and explicit audited recovery after fault. Not automatic FPGA reset.

SD currently original: download.bit22fec95c..., uEnv b8156344..., BOOT.bin ff350477.... uEnv loads download.bit via fpga loadb before Linux, so preserve BOOT/uEnv/Image/DTB; replace only converted candidate bit after promotion. Candidate converted bit f42dd12f... at E:/FPGA_Work/smartscan_prefetch_fix3_20261031/outputs/smartscan_fix3_candidate. No SD/Flash writes done.

Separate service/launcher/retention templates in deployment_prep. systemd-analyze verify PASS, not installed. Launcher requires explicit promotion receipt and frozen files; persistent faults exit78. Retention deletes only old clean own-run evidence, keeps faults/unknown/live; filesystem test PASS. Production launcher and cold boot NOT yet accepted. Physical HDMI/touch and power-cycle checks require user availability.

Original bit restored. Original UI active. Original receiver service is legacy PC-control-dependent, retries192.168.126.50:39012 when unavailable. Do not claim this old service is autonomous or that the integrated release has been deployed.

## Do not skip

Preserve backup; no full BOOT.bin rewrite needed. Keep model/public frame/detection thresholds unchanged. Do not claim new-seed perfection, all timing PASS (inherited NPU min-period warnings remain), full hardware auto-recovery, physical screen PASS, or permanent deployment before actual acceptance.
