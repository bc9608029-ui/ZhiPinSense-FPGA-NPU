# fix9r2h1 shared payload-training residual gate

The fix9r2h R8 smoke test passed all acceptance conditions, including two actual
model classifications. The subsequent 46-sample run excluded 42 files. Its exact
failure distribution was:

```
42 failure=PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH
4 failure=NONE
```

The cause was a stale mode-dependent threshold selection: diagnostic R8 used the
approved migrated payload-training residual limit 0.10, while the full run switched
back to the obsolete pre-fix9r2g value 0.05. R8 values 0.085716 and 0.059065 already
proved that the two paths could disagree despite identical RF validity semantics.

This hotfix defines one canonical
`iqrfrec::kPayloadTrainingResidualMax = 0.10` and uses it in both the R8 diagnostic
gate and the full 46-sample recovery configuration. No other threshold, RF math,
model, frame, synchronization, label, or preprocessing behavior changes.

Verification:

- `test_iq_rf_loopback_23class_fix9r2a`: 38 pass, 0 fail.
- `test_iq_rf_loopback_23class_fix9r2g`: 66 pass, 0 fail, including an assertion
  that the shared R8/R9 residual contract is exactly 0.10.
- Board-source syntax: gate7, gate9, gate10, and gate9_rml23 all OK.

The next action is to rebuild the board binary and rerun the 46-sample full run.
The two-sample R8 need not be repeated because its accepted RF recovery math is
unchanged.
