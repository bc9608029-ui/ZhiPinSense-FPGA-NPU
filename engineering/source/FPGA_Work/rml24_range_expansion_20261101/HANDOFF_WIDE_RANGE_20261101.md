# Wide-range deployment handoff — 2026-11-01

Status: RANGE_DEPLOYED_PHYSICAL_INPUT_AND_SOFTWARE_REBOOT_PASS.

Installed board release: /opt/rml24-integrated/releases/range_20261101
Previous rollback release: /opt/rml24-integrated/releases/r1773414967
Service: rml24-integrated (enabled; observed active, NRestarts=0).
Bitstream, model, public frame, sample rate 2.56MS/s and inference preprocessing unchanged.

PC launcher: E:\FPGA_Work\rml24_range_expansion_20261101\START_TX_CONSOLE.cmd
PC console: pc/console. Previous console preserved.

## Expanded controls
TX/RX selectable frequency: 70–6000MHz, based on both actual drivers' frequency_available.
TX gain: -89.75..0dB, UI increment0.25dB; default-40dB.
RX scan start/stop can be located anywhere inside70..6000MHz, but each window remains <=101points and step<=2.304MHz. This does not perform a whole70..6000MHz search at once. No blind large-step gaps introduced.
Defaults restored FIXED2400MHz, scan2395..2405MHz step1MHz.
RX manual gain/AGC, sample rate and frame shape not exposed as new arbitrary options.
24classes and existing10/new2 messages retained; no invented extra training messages.

## Evidence
13 actual fixed-mode low-power(-40dB) BPSK frequency tests:70,100,325,433,915,1200,1800,2400,3500,3800,5000,5800,6000MHz. All13 had valid correctly classified records; total 262 valid records. Not a24class full-band accuracy guarantee. At5800MHz only3valid records, reception reliability there not equivalent to other points. Rejected/no-signal frames remain preserved.
9 TX gain values [-89.75,-70,-60,-50,-40,-30,-20,-10,0] written/read back with TX LO powered down, no RF waveform sent. This verifies settings, not successful recognition throughout gain range. Full-power direct-coax RF was not performed.
Receiver boundary script verifies70MHz/6GHz, endpoint scan windows, illegal outside-range frequencies and scan parameters, modes and default restoration. promote_range.py refuses promotion unless this board result passed.
3500MHz RX/TX actual readback3500000002Hz: candidate now permits explicit100Hz LO-only tolerance and logs actual attribute values. Other attribute tolerances not relaxed. Previous rejected attempts retained.

## Failure and repair
First candidate was blocked by outer SHA; next by wrapper embedded dependency SHA. Supervisor then terminated NPU and hardware guard required reboot. Evidence retained; no guard bypass. Reboot restored original system. Candidate inner/outer identities synchronized and verify_base() passed before retry.13-frequency tests subsequently completed.
Original model/worker/core identities retained. No firmware expansion command was run: both Plutos already reported extended range.

## Limits and remaining
Factory-qualified Pluto range325–3800MHz;70–6000 is driver-enabled extension, not uniform factory performance.
Final physical frequency-keypad confirmation requested for433/5800/2400MHz. New release reboot verification remains pending.
Existing earlier cold-boot pass belongs to previous narrow-range release. Do not silently transfer it as observed boot pass for this release.
No long soak or exhaustive cross-product of classes/messages/frequencies/gains.

## Main files
EXPANSION_GATES.json, GAIN_NO_RF_READBACK.json, EXPANSION_PLAN.json.
RF sessions: session_1793501501851229400 (8lower points), session_1793501756707224200 (5higher points). Each preserves actual Qt screenshots, events, case, TX restore and board summary.
Board evidence: /root/rml24_range_expansion_20261101/; current candidate test run POSTDEPLOY_PARAMETER_TEST.json. Prior failed logs in /var/log/rml24-integrated/r62a3b02cb079.

User physical confirmation:433/5800/2400MHz all APPLIED normally, restored2400MHz. New-release reboot check follows.

## Final reboot acceptance
Software reboot automatically loaded SD bitstream (RML24_BOOT_PL_LOADED observed), started range_20261101, and passed NPU/UI/RX readiness plus min70MHz/max6GHz control check. Boot ID fe307438-4fe1-427b-98de-dca81ca2c7b4. No login or manual service start used. Evidence REBOOT_SERIAL.txt and REBOOT_ACCEPTANCE.json. Physical power-cycle for this range-only revision not separately performed; earlier release cold-boot passed.
