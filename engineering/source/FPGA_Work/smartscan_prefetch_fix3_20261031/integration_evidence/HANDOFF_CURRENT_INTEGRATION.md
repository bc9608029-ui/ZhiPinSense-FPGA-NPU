# FPGA auxiliary + TX console current verified status

Updated: 2026-10-31. Candidate only; original bit and services restored. No persistent deployment.

## Actual RF short tests

| Test | Correct / fixed denominator | Missing | TX restore readback |
|---|---:|---:|---|
| phase20_gui_rf_cases | 5/6 | 0 | True |
| phase21_gui_24_smoke | 24/24 | 0 | True |
| phase22_gui_multifrequency | 3/3 | 0 | True |
| phase23_gui_newmessage1 | 22/24 | 0 | True |
| phase24_gui_newmessage2 | 23/24 | 0 | True |

Two newly generated message sets: 45/48 (93.75%), zero missing. Separate small functional test, not formal 240-item regression or a broad generalization claim.

## Preserved failures

- phase20_gui_rf_cases: {"index": 2, "config": {"bank": 0, "message": 1, "gain_db": -60}, "chosen_frame": {"frame_id": 123, "capture_time_ns": 1773389894006786790, "pred": -1, "finite": false}, "correct": false, "missing": false, "source_sha": "1562575bbedd6e815535726f16de6752da0f7441ea609acd3cb2cf6be529c0f8"}
- phase23_gui_newmessage1: {"index": 17, "expected": 17, "chosen_frame": {"frame_id": 459, "capture_time_ns": 1773391316790965710, "pred": 18, "finite": true}, "correct": false, "missing": false, "source_sha": "2b8425f8d3d1eba567c15d4074aff185e28136d5954f6dadc7683737cc85ec51"}
- phase23_gui_newmessage1: {"index": 23, "expected": 23, "chosen_frame": {"frame_id": 601, "capture_time_ns": 1773391354558623960, "pred": 10, "finite": true}, "correct": false, "missing": false, "source_sha": "1a00009440bf3abff7fed59ff3a50760f1595e8c8c42cf31a15d9f481ef38f8e"}
- phase24_gui_newmessage2: {"index": 10, "expected": 10, "chosen_frame": {"frame_id": 285, "capture_time_ns": 1773391697743784430, "pred": 9, "finite": true}, "correct": false, "missing": false, "source_sha": "b2c068214280fe0b251afa217e14afe15a7a2bd94039744546c5cfd60718c422"}

## Scope and known limits

- FPGA auxiliary currently computes display Hann FFT/PSD, not scan-frequency decision logic, RMS/Energy/Peak migration, or model inference migration.
- Fix3 prefetch and shared XRT Device owner avoid prior DDR bubble and independent Device lifetime interference. Original failed evidence remains preserved.
- Candidate shared worker: 7b185cad8aaf526344a36666a90071e59577a2fa1488a7f8f0523ce437bc0af9.
- Candidate bit: f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c.
- Original bit restored: 22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9.
- New messages retain original public frame and eight repetitions. No model, detection threshold, public-frame, or official autostart changes.
- New-seed waveforms were generated independently of predictions; no failed sources removed.
- Strict shared RPC failures stop the candidate. Full hardware-fault automatic fallback is NOT verified or implemented.
- Unsafe busy exit 3 requires PL/board reset before memory reuse. Deployment must prevent automatic service restart on unsafe hardware; not yet production-ready.
- Two inherited NPU minimum-period violations remain; setup/hold checked, not a full timing PASS.
- Real physical HDMI/touch acceptance for this FPGA-integrated candidate remains pending. Socket/UI delivery is not physical-screen verification.
- No formal 240+240 new RF regression, persistent boot integration, or new cold-boot acceptance performed.
- Generic workflow DEVICE_STATUS fields rf_tested=false/npu_liveness_pending are stale boilerplate; use the per-test receipts and summaries for actual RF evidence.

## Next steps

1. Complete deploy-safe unsafe-exit/reset handling in a separate candidate; keep currently tested sources frozen.
2. Crosscheck private truth and freeze exact formal scoring windows, first-capture rules, source order, gain/frequency and candidate SHAs. Draft verified 240 assets exists, not approved to execute.
3. Ask user approval before long fixed240 + search240 regression per prior explicit instruction. Do not rerun an old entry blindly.
4. Physical UI verification, then reviewed persistent boot/service integration and cold boot only after all promotion gates pass.

## Evidence

See CURRENT_RF_EVIDENCE_INDEX.json for receipt paths, SHAs and all failed selections. Full board logs/raw evidence remain at each receipt DEVICE_STATUS board_evidence root.
