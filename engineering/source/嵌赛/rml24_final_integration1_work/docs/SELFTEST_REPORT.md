# 24-class paired RF self-test report contract

`scripts/summarize_selftest.py` consumes the frozen private truth file and one
or more complete paired board result files. It fails closed on duplicate,
missing, or extra sequence identifiers.

The denominator is never reduced: every expected sample counts, and a missing,
invalid, or failed prediction remains incorrect. The JSON output contains both
24x24 confusion matrices, per-class accuracy, the complete fix/regression lists,
and per-session totals. The TSV is a report-ready per-class table.

For the two frozen independent RF rounds, the required result is:

- baseline: 403/480 (83.96%)
- candidate: 463/480 (96.46%)
- fixes: 60
- regressions: 0

This summarizes existing evidence. It does not replace the pending byte-exact
raw-capture replay and must not be described as a new RF run.
