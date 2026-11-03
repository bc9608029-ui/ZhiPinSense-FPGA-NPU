# RML24 — Pending Evidence (what is NOT yet demonstrated)

Each item below is a placeholder in the report draft. Fill only from board/NPU
results produced by the user; this ledger (host, read-only) cannot produce them.

## P1 — `[PENDING_RXRESIDUAL_AUDIT]`

Main-line `fix10class24-rxresidual-audit1` Phase D/E/F:
forced classification of the 30 failed-RX dumps (24-dim raw logits per dump),
training-block residual decomposition via a fixed 5-tap FIR, and the residual
threshold verdict. Plus 14 host tests + summary.json.
**Required to state any per-class or per-dump forced-classification conclusion.**

## P2 — `[PENDING_UI_DESKTOP_RESULTS]`

Final visible desktop verification verdict for the constellation UI (task 二),
including any evidence of live-NPU data wiring.

## P3 — `[PENDING_24CLASS_RF_PROSPECTIVE_VALIDATION]`

Real board 24-class RF results under the prospective-validation gate policy
(`fix10class24-prospective-validation-prep1`). Synthetic self-test alone (C15)
proves framework correctness, not board behavior.

## P4 — `[PENDING_FPGA_UTILIZATION_REPORT]`

FPGA slice/DSP/BRAM utilization of the merged NPU+HDMI bitstream (M28/M29 board).

## Standing prerequisites (unchanged)

- 2-sample RF recovery must stably clear residual ≤ 0.10 before any 24-class RF run.
- Board results must be produced by the user on the board; the API does not touch
  the board and must not fabricate board evidence.
- Must not write any `SMOKE-PASS` / `RF-PASS` / `24CLASS-PASS` / `PROJECT_COMPLETE` / `FINAL_*` conclusion token until the corresponding board evidence exists.
