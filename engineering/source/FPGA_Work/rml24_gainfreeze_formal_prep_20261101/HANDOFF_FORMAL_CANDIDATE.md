# Gain-freeze candidate — formal regression preparation
Status: PREPARED_AND_OFFLINE_CHECKED; EXPLICIT_APPROVAL_REQUIRED; NOT_DEPLOYED.

Candidate /root/rml24_gainfreeze_integration_20261101/candidate. Formal /opt/rml24-integrated/current remains range_20261101. Only auto-gain-settle3x16384 then manual hold and5MHz RX filter integrated.2.56MS/s,8payload repeats, frozen model and FPGA bit unchanged. No cross-frame weak combining integrated. Current scope sustained cyclic public-framed transmission, not isolated bursts.

Evidence: paired24 classes x TX-40/-60dB manual35:24/48, auto-freeze:48/48. Integrated actual NPU/UI chain smoke24/24, missing0.213valid captures,213FPGA display calls, UI failures0. NPU frames1704/apply1/reset1703/discipline1, clean guard exit and RX restore[]. This is a smoke, not full240 validation.

Recovery incident: service restart was blocked solely by <1GiB free space; no hardware fault marker.945files/488510700bytes fully verified in E:/FPGA_Work/rml24_adaptation_archive_20261101/research_iq.tar.gz.924board raw files archived, metadata retained, baseline NPU/UI/RX readiness restored with~1.5GiB free. Formal code/bit untouched.

## Proposed four rounds
fixed240 and search240: minimum235correct each, missing0. sweep24:minimum23, missing0. Coordinated wide13 BPSK frequencies70..6000MHz:13correct, missing0; not blind full-band search.
Same original240-source truth mapping/SHA, old first-capture window+1.5s..end-.3s, fixed rejects/missing/wrong fail. Monotonic clocks only, same boot, <=250ms uncertainty and <=100ms drift. Existing frozen waveforms, not unseen-source generalization. NPU/FPGA/UI/clean stop/restore gates preserved. No raw IQ dump during long runs to avoid SD exhaustion.
Warmup40s, mute8s, gap.25s. Expected75–90minutes. Each round uses a temporary service, restores baseline after completion. No JTAG, Flash or permanent service change. Accuracy failure retained; integrity/process/clock failures stop remaining runs. No automatic deployment.

## Commands
Offline: D:/Miniconda3/python.exe <thisdir>/run_formal.py --check
Execution is blocked unless APPROVAL.json contains allowed=true and exact plan/helper hashes. APPROVAL_REQUIRED.json is informational and does not grant consent. No APPROVAL.json has been created.
After user consent, record it and exact hashes, then execute new run_formal.py (do not run old continue_device/JTAG entries). All PC outputs here onE:.

## Before promotion
All formal gates must pass. Current candidate production launcher deliberately has promotion=false. Review results and preserve rollback, then separately activate and reboot verify. Previously accepted UI binary unchanged. Gain-freeze behavior still needs full regressions; staged status is not final deployment.
