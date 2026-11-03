# Third recheck — 07d69232 package

Decision: implementation/docs items 1–4 are addressed in the reviewed source.
Full delivery approval is still pending item 5 (independent board judging).
Do not change the DSP/model/waveform again for this remaining work.

## Independently verified

- SHA256: 07d69232a5bc881dd3c4f4296e66059efa1170f2f9a28389b9afcf47ea760639.
- 70496 bytes, one gzip layer, 15 archive members; all 14 embedded SHA entries match.
- New board judger --self-test rerun: 4/4 PASS.
- BOARDTEST PowerShell block parsed using the actual PowerShell parser: zero errors.
- Source review: ADC rail=2047; capture_ok/clip enter usable/gating; negative capture
  success/continuity/nonempty checks present; functional status computed before
  summary serialization; file mode no longer requires device-only checks.
- Documentation includes explicit RX35, fresh output directories and taskset-limited
  build. It still needs actual board-native execution, which was not performed here.

## Remaining item 5 gaps

1. **No digital baseline comparison.** The new CLI has no frozen-baseline input.
   It counts board predictions against labels, but does not compute board-versus-
   digital agreement, same-wrong cases, or new flips. A 21-column loader alone is
   not the previously requested independent A/B/C comparison.

2. **Actual C tensor files are not verified.** Device mode does not open recovered
   tensor files at all. File mode compares the row's claimed SHA to a B reference
   file, but never hashes the actual board-produced C tensor. A claimed hash is
   not evidence that the captured artifact exists or has those bytes. Add an
   actual board output/artifact directory and verify tensor shape/size, finite
   values, and recorded SHA. Raw/logit artifact verification should use the same
   binding if those hashes are claimed as verified.

3. **Duplicates are silently overwritten.** load_results and load_manifest assign
   rows[sid] before checking uniqueness. validate_identity iterates the already
   deduplicated dictionary, so its duplicate branch cannot fire. Direct reproduction:

       two rows with source_index=1 -> load_results returns one row, no exception.

   Reject duplicates before insertion; validate the exact expected 1..24 key set,
   one source/version/model identity, and preserve a fixed denominator of 24.

4. **Measurement validity is not independently decided.** A controlled mock-loaded
   device result with all labels correct but completed=0, aborted=1, all restore/
   readback/negative-control flags false and fabricated artifact SHAs returns rc=0
   and errors=[] in the current judge. Exit 0 can legitimately mean analysis
   completed, not RF success, but the report must explicitly distinguish that from
   a valid complete measurement. Reconcile summary completion/health with rows;
   mark invalid/incomplete infrastructure separately from ordinary misclassification
   and gate rejection. Never label an interrupted run as a complete 24-frame test.

## Bounded acceptance request

Only finish the board judger, counterexample tests and documentation/package:

- Bind to the frozen v2 digital baseline using source/version and reference identity;
  compute correct/24, agreement/24, coverage, gated accuracy and end-to-end accuracy,
  plus same-wrong/new-flip per-sample lists. Missing/nonfinite/gate-rejected samples
  remain in the expected 24 denominator; do not confuse analysis validity with RF
  accuracy or demand all model predictions be correct.
- Hash the actual C artifacts against their recorded SHA; file mode additionally
  compares C bytes with the digital B reference. Device mode must NOT require C
  bytes to equal B bytes.
- Exercise real emitted 21-column output, duplicate IDs, missing rows/artifacts,
  tampered tensor bytes, invalid health flags, finite=0, interruption and the
  known v2 baseline misclassification. Reject identity/tamper failures explicitly.
- Update the exact CLI commands, rerun tests, rebuild and provide full 64-hex SHA.

No new RF matrix, no retraining, no new waveform version, no recovery rewrite.
Review remains offline; no SDR or board was accessed.
