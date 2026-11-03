# Scan board execution — 2026-10-27
Input package SHA256 6bf4f2bb5577598ab4da8803a23e2c5df4a8037bee33af005dbc56f48ec06dbf
Original boot services and installed /opt/rml24-system remain unchanged.
Working board root /root/rml24_scan_execution_20261027
PC evidence root E:\scan_exec_20261027

Frozen model and two-DC unchanged. All private labels remain PC-only.
Gate 1: Native UI build PASS, all 7 prerequisite hashes PASS.
Gate 2: FIXED two complete rounds of the frozen 240 samples. Record every run, compare with old 475/480; no sample selection.
Gate 3: BAND_SCAN 2399–2403MHz at TX2401.3MHz, frozen 240 samples. Require no missing/invalid, log LO readback and locked checks; score every sample.
Gate 4: Wider band 2395–2405MHz at another TX frequency, negative no-TX checks and explicit unlock/rescan checks. Preserve failures if any.
Gate 5: Physical MODE page and touch confirmation, then startup replacement only if RF gates pass; reboot/cold boot requires user assistance.
Long stability explicitly deferred by user.
Historical 98.96% belongs to fixed Stage7 only; no scan claim before independent RF completion.

User-approved scope update: continue exploratory scan despite failed fixed accuracy gate; keep original startup services, skip physical UI/touch/power-cycle confirmation, no long stability. Do not claim accuracy issue fixed. Additional scheduled 78-frame diagnostic consists of 72 declared signal frames and 6 declared muted negatives. Control test uses 24 declared class-balanced waveform instances. Original 240 manifests remain unchanged.
