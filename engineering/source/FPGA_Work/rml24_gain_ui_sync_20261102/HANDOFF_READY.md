# Deployment readiness handoff

Status: READY_FOR_USER_SCREEN_CONFIRMATION_NOT_DEPLOYED.

Final board candidate: /root/rml24_gain_ui_sync_20261102/candidate
Identity SHA256: d960b668f1298962ec230db661fbcf2f7881206ba49c1ceb4d39dc25518c611b
Current production release is still range_20261101. Never switch until user confirms screen powered and deployment ready.

Changes: gain acquisition then freeze and ADC-headroom protection; sweep-only bounded model-input amplitude correction for power0.8..1.25; actual per-frame RX hardwaregain telemetry replacing fixed35dB; TX labels/launch/font compatibility. The RF gain number is hardware dB readback, not the DSP channel coefficient. AUTO here means automatically selected then manually frozen during capture, not continuously changing AGC within a frame. Model, public frame,8 repetitions,2.56MS/s and persistent FPGA bit unchanged.

Evidence: new bounded candidate sweep24/24, fixed24/24, search24/24; final display candidate fixed3/3, search3/3, sweep6/6, missing0, all finite telemetry gains equal hardware final readback. Pure-input amplitude audit240/240 and saved capture12/12 passed. These are separate evidence sets, not a new full240+240 regression for final source. Earlier fixed240/240, search238/240 and coordinated13/13 are inherited only after actual two-stage source-equivalence proof in deployment/SCOPE_PROOF.json. Prior sweep22/24 retained as failure and replaced by explicitly changed sweep candidate's24/24. The two search errors remain part of the historical evidence.

Unconditional global normalization was rejected196/240 and is not used. Bounded calibration is a new internal processing rule, not arbitrary-signal invariance. This remains an existing frozen-waveform/public-frame system; no unseen-waveform or whole-band all-class accuracy claim.

Latest qualification: deployment/QUALIFIED_GATES.json with source/result hashes and provenance. UI checks: LOCAL_CHECKS.json, TX_UI_CHANGE_AUDIT.json and TX_CONSOLE_PREVIEW_FONTFIX.png. New TX entry: START_TX_CONSOLE.cmd; old launcher retained. Both original and new message banks retained.

After user readiness confirmation: create explicit DEPLOYMENT_USER_READY.json only then; run deployment/deploy_and_verify_gain_ui.py. It stages immutable software release, preserves original service/unit/bit/boot, verifies production fixed24 and sweep6 with real calibration active, clean stop/start, and rolls back on failure. Only successful DEPLOYMENT_RESULT.json establishes deployed status. No physical cold-power test has been observed for this version; do not claim otherwise. Check disk reserve and single guarded NPU owner; never clear a same-boot dirty hardware marker.
