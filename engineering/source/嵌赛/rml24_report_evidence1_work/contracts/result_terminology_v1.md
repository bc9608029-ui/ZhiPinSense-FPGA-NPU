# M29 RML24 final-report result terminology (v1)

This contract fixes the vocabulary used across the evidence ledger, the report
draft, and the checker, so that every conclusion carries an unambiguous
evidential weight.

## Conclusion → evidence → file → SHA → limitation

Every claim in `evidence/claim_evidence_matrix.tsv` is a 5-tuple trace:

1. **conclusion** — the sentence the report may state (no stronger than its level).
2. **evidence** — the level id (`L0..L11`, see `evidence_level_v1.tsv`) and the
   concrete source file(s).
3. **file** — a path under `F:\嵌赛\` (a read-only source tree) that backs the claim.
4. **SHA** — the recomputed SHA-256 of that file/artifact, or `NOT_VERIFIED`.
5. **limitation** — what the evidence does *not* prove.

## Verdict tokens (allowed)

| token | meaning |
|---|---|
| `VERIFIED` | conclusion supported at the cited level, nothing stronger implied |
| `VERIFIED_NEGATIVE` | a *negative* result is itself confirmed (e.g. board RF recovery failed at residual>0.10) |
| `PENDING` | required for any board-NPU RF 24-class / production-gate conclusion |
| `NOT_VERIFIED` | number/file not re-confirmed this session — must not be stated as fact |
| `SOURCE_NOT_PRESENT` | source tree/dir absent — recorded, not fabricated |
| `[PENDING_*]` | placeholder in the report skeleton for evidence not yet produced |

## Forbidden tokens (the checker rejects any file containing them)

`SMOKE-PASS` `RF-PASS` `24CLASS-PASS` `RXONLY-PASS` `RF_PATH_PROVEN`
`NPU_PASS` `PROJECT_COMPLETE` `FINAL_PASS` `FINAL_COMPLETE` and any `FINAL_*`.

## Layering rules (non-negotiable)

1. **Host ≠ board-NPU**: a host BF16 forward (L4) is not a board NPU result (L7+).
2. **数字直注 ≠ RF**: digital injection (L7) is not RF loopback (L8).
3. **两样本 ≠ 24类**: 2-sample evidence (L5/L7/L8) never implies 24-class (L9+).
4. **强制分类 ≠ 生产门禁通过**: the gate-bypassed forced classification (diagnostic)
   does not constitute a production gate pass (L10).
5. **NPU 映射 ≠ 实测性能**: the network mapping report (L6) proves deployability,
   not measured board accuracy/latency.

## Status ladder for this task

The ledger's own final status is exactly
`M29-RML24-REPORT-EVIDENCE-LEDGER-READY-FOR-ROOT-CAUSE-INSERTION`.
Nothing above it may be written here (no SMOKE/RF/24CLASS/PROJECT/FINAL).
