# RML24 final integration 1

Status: `OFFLINE_GATE_A_EVIDENCE_VERIFIED_RAW_REPLAY_PENDING`

This tree is the single computer-side integration point for the validated
24-class fixed-parameter RF receiver.  It does not modify the source evidence
under `../amr_rescue_gmsk_candidate_20261026`.

## Frozen production boundary

- Recovery: `recovery/candidate_two_dc.py`, byte-for-byte copy of the validated
  candidate (SHA-256 `e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a`).
- Model: frozen RML24 BF16 JSON/raw pair recorded in
  `contract/final_system_contract.json`.
- RF contract: public head/tail references, 2.4 GHz, 2.56 MS/s, 18 MHz
  bandwidth, TX attenuation -40 dB, RX manual gain 35 dB, direct cable.
- Scope: generated clean IQ compatible with the frozen RadioML input tensor,
  24 classes, unknown message seed.  This is not a claim of arbitrary passive
  or no-preamble recognition.

## What is complete on the computer

1. Frozen candidate and model identity contract.
2. Evidence auditor that independently recomputes both 240-frame scores.
3. Candidate-only formal receiver entry with an optional paired diagnostic
   mode; labels and expected results are not available to the receiver.
4. Raw-capture replay tool for strict recovered-tensor SHA comparison.
5. Host tests for the recovery, tensor contract and evidence audit.

## Remaining gate

The PC evidence contains the two scored `board_results.json` files, but not the
480 board-side `*.raw.npy` captures.  Copy these two directories from the board
before claiming raw-to-tensor replay closure:

```text
/root/amr_pair_validation_20261026_r1/capture
/root/amr_pair_validation_20261026_r2/capture
```

Then run `scripts/replay_raw_capture.py` once per directory.  Until all 480
recovered tensor hashes match their recorded board results, this tree must not
claim `OFFLINE_GATE_A_COMPLETE`.

## Host checks

From this directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_host_checks.ps1
```

The checks are read-only with respect to the source evidence.

