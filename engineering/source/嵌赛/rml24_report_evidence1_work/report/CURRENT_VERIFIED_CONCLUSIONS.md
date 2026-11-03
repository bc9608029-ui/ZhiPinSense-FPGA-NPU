# RML24 — Current Verified Conclusions (evidence-backed, no stronger than level)

Every line below maps to a row in `evidence/claim_evidence_matrix.tsv`. Nothing
here asserts a board-NPU RF 24-class result or a production gate pass.

## Verified (positive)

- **C01/C02** — The BF16 24-class model and its 24-class label order (AM-SSB-WC/SC
  independent) are frozen and byte-stable (json `28272abc…`, raw `c1781aec…`,
  checkpoint `96cd25f8…`).
- **C03** — Host BF16 forward classifies all 24 clean samples correctly and matches
  the frozen PyTorch argmax on all 24 (backend `icraft-host-bf16`).
- **C04** — The network maps to the ZG330 NPU: 122 HardOp @zhuget(330) + 2 host,
  0 int8, verdict `DEPLOYABLE_FULL_NETWORK_BF16` (iCraft v3.39.0).
- **C05** — The aarch64 canonical frame is frozen; preamble/tail ZC are cross-arch
  consistent while the payload-training 16QAM block diverges on x86 (`-883` vs
  `-2650`).
- **C06** — Host canonical replay reproduces the board BPSK failed dump
  field-by-field (timing 36074, coarse −118.325, corr 0.9933165, residual 0.1161988).
- **C10/C13/C14** — The diagnostic forced-classification tool chain is byte-identical
  to production on a PASS fixture, and 30/30 failed-RX dumps were exported with
  canonical crosscheck PASS.
- **C15/C16** — The prospective-validation framework (synthetic) and the UI
  constellation desktop build + screenshots exist on disk.
- **C18/C19/C20** — Delivery batches document deterministic packaging and
  byte-identical red-line headers/contracts; the raw24→deployed23 merge contract
  keeps AM-SSB-WC/SC independent in RAW24_UNMERGED mode.

## Verified (negative — confirmed failures, not passes)

- **C07** — Cross-arch RX reference uncertainty is a real diagnostic-tool gap (D1).
- **C08** — Board BPSK residual 0.116 is real RF noise (SNR ≈ 18.7 dB), not a code
  defect (D2).
- **C09** — "BPSK over / 4ASK over" is modulation-independent RF implementation
  noise (D3).
- **C11/C12/C17** — Across all 30 board captures (4 bandwidths × 3 rounds, plus
  gain 35/40/45/50 dB), the recovery gate (residual ≤ 0.10) was **never met**:
  residual 0.11–0.15, corr 0.988–0.994 → `NO_STABLE_RX_BANDWIDTH`.

## Explicitly NOT claimed

- No board-NPU digital-injection 2-sample classification result (L7).
- No board-NPU RF 2-sample classification result (L8 pass).
- No board-NPU RF 24-class accuracy (L9).
- No production gate pass (L10).
- No final acceptance (L11).

See `PENDING_EVIDENCE.md` for what is still outstanding.
