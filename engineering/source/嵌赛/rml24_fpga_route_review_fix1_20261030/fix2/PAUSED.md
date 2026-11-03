# Pause history — resumed by user 2026-10-30 19:14

User explicitly resumed. Task `CodexSmartscanFix2Bitgen_20261030` restarted after confirming no active generator, no partial raw/final bitstream, and the routed checkpoint SHA below. The stale lock was removed only after its owner PID was absent. New supervisor PID 3140; bitgen child PID 3620. These are historical launch identifiers, not proof of current liveness; consult fresh status and processes. No synthesis/placement/routing restart or board operation occurred.

User explicitly requested pause. The verified bitgen process tree (580, 27688, 21928, 25668) was stopped and scheduled task `CodexSmartscanFix2Bitgen_20261030` is Ready, not Running. No further build/test/deployment should begin until the user resumes.

Completed synthesis, placement, routing, reports and `F:/FPGA_Work/smartscan_bram_fix1_20261030/reports_fix2/routed_fix2.dcp` are preserved. Known routed checkpoint SHA256: `3079f04b4500f750e56eb9f8649a48962ce4b5b795b830342abbb6c09023f07b`.

The last attempted stage was bitgen. `BITGEN_STATUS.json` may still say RUNNING because the supervisor was stopped deliberately; it is stale and must not be used as proof of liveness. A stale `build/bitgen.lock` may remain. On resume, verify process/task identities, preserve any partial output and review logs before clearing the stale lock or restarting generation. Do not reset synthesis/implementation or overwrite the routed checkpoint. Do not treat an interrupted raw .bit as valid.

The historical baseline exception gate has passed: only the two unchanged inherited NPU min-period endpoints are present, matching the actually used baseline bit SHA `22fec95c...`. This permits the historical controlled-candidate generation path; it is not manufacturer timing waiver/full STA PASS/board acceptance.

No new FPGA loading, Flash/SD writes, RF testing, service changes or model changes occurred.
