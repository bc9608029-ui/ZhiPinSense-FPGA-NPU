# fix1v2 board impl1 — independent review

Decision: NOT APPROVED. Keep evidence-delivered/pending-review; do not promote READY.
Review was offline: no board access, no RF, no training, no implementation edits.

## Checks completed

- Package SHA256: c2d641fcf4e9d449c1cbe888c3c0d732811d3f777c5545635cfab0b845ea34bd.
- 50,788 bytes, one gzip layer, 14 tar members. All 13 entries in embedded
  SHA256SUMS.txt matched member bytes (checked in memory, without extraction).
- Simulated PC TX tests rerun: pass=22 fail=0.
- WSL g++ C++17 -O2 -Wall -Wextra -Wno-unused-parameter -fsyntax-only of
  host_tests/test_radioml_independent_rx.cpp: exit 0.
  This does not compile the full board translation unit or validate real libiio.
- Reviewed both requested documents and actual loader, recovery, runner and PC engine.

## Blocking findings

### R1 — real TX restore replaces Python attribute objects

host_tools/pc_tx_sdr_fix10.py PlutoTxDevice.restore() uses attrs.__setitem__
and debug_attrs.__setitem__. Installed pylibiio exposes ordinary dictionaries of
ChannelAttr objects; writes must target the existing object's .value property.

Reproduction using matching dictionary/attribute semantics: restore() returns True,
the original frequency attribute remains 2400000000 instead of 2450000000, and
the dictionary entry has become a str. A subsequent configure() can then fail
when accessing .value. MockTxDevice does not exercise this implementation.

Runner recv_stopped() accepts and stores tx_restore_ok=false, but the caller does
not inspect it. Restore needs real writes, readback verification, and explicit
propagation of false to the run outcome. Ensure exceptions while TX is active stop
TX reliably, not merely relying on the watchdog.

### R2 — capture interval does not guarantee a full cyclic frame

Device mode captures 59904 + 2*8192 = 76288 complex samples and only searches
starts through 16384. Cyclic TX has an arbitrary phase relative to RX refill.
If the next preamble begins at 30000, its full frame ends at 89904: outside the
capture and outside the search interval. A valid cyclic stream can therefore be
mistaken for bad RF. Use sufficient capture/search coverage for arbitrary phase,
with a complete-frame bounds check and an explicit no-sync result.

Public recovery also deliberately reproduces a Python timing bug: all positive
offsets are skipped because segment lengths differ. Using a real v2 burst,
estimate_timing_offset(roll(burst,+100)) returns -4; roll(burst,-100) returns -100.
Cross-language equality is not correctness when both implementations share a bug.

### R3 — residual is gain dependent, unlike the claimed fidelity interpretation

wide_linear_fit computes sqrt(sum|r-a*x-b*conj(x)|^2 / sum|x|^2).
Since x is the TX reference, attenuation scales the residual down. An independent
synthetic 20% relative training perturbation yielded:

| RX gain | reported residual | <=0.100 |
|---|---|---|
| 1.0 | 0.1999432879 | no |
| 0.03 | 0.0059982986 | yes |

Define and validate a gain-independent relative fidelity statistic, preferably
reusing the validated production definition. Do not silently retain the number
0.100 while changing its mathematical meaning. Preserve the old statistic as a
named diagnostic if needed. Add gain/phase/IQ/CFO/timing/noise counterexamples.

### R4 — device checks are missing despite report claims

RX attributes are written but no corresponding readbacks are checked in the new
runner. No RX clipping check or measured TX-off negative-control capture exists;
HELLO configuration verification is not a noise-window measurement. Capture health
must be checked and recorded before classifying. Gate finite model inputs as well
as finite fit coefficients; reject singular/ill-conditioned inverse recovery.

### R5 — required evidence is not retained; interruption can look complete

Runner saves recovered tensors, but not full raw RX captures, actual logits,
per-attempt diagnostics, or infer-twice repeatability. Rows are written only after
the entire loop. A later exception can lose earlier rows, and Ctrl-C breaks the
loop while functional_pass only checks error/restore, not completed==24.

Persist raw RX before alignment/recovery, real logits and per-sample diagnostics,
including failed attempts. Flush rows incrementally. Keep expected=24 and emit
explicit missing/aborted outcomes; completion must require all expected samples.
Do not replace real logits in UI/result output with synthetic one-hot values.

### R6 — delivered deployment instructions are not executable as written

BOARDTEST.md calls bash build_on_board.sh from the tree root, but neither this
archive nor the specified base provides that root entry. Base scripts/build_on_board.sh
delegates to the original multi-target build scripts, not a proven single-thread
new build. run_gate9_rml23.sh is under scripts/, not the root. Model SHA is abbreviated,
OUT is not initialized, input extraction layout is unspecified, and Windows PC
commands use Bash continuations. The named fix1 judger accepts only --kind digital;
the separate v2 board-vs-baseline judger needs an explicit compatible command.

Deliver one exact baseline/patch application sequence, native single-thread build,
correct binary install path, full model hashes, input directories, PC PowerShell
command, board run command and actual board-result judging/transfer command.
Standalone extracted host test currently includes ../board_package_base/ while
the archive installs the headers under board_package/: fix that layout mismatch.

### R7 — overwrite claims need actual base comparison

The archive contains host_tools/pc_tx_sdr_fix10.py and fix10_tx_protocol.py under
existing base filenames. The new engine is public-protocol-specific; these cannot
be described as entirely new files without proving legacy compatibility.
Prefer distinct entry/module names or prove old entry-point behavior unchanged.

## Bounded follow-up acceptance

Fix only the above implementation, safety, evidence and deployment defects.
Do not retrain, change the frozen model or waveform assets, add a new RF matrix,
or auto-add FPGA/equalization experiments. Add counterexample tests through the
actual device-path orchestration with injected device/control interfaces, not only
an ideal burst passed directly to recover_and_classify_one(). Rebuild the package,
verify clean-base overlay and rerun regressions. Full aarch64 build and actual RF
remain user-executed steps and must not be claimed offline.
