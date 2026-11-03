# V3.2 Delivery Report — Execution-Chain Fixes for the AutoDL Package

Scope: repair the V3.2 AutoDL delivery package's execution chain **without**
changing the V3.2 model direction, without creating V3.3, and without starting
formal training. All freeze constraints still hold: V2/V3/V3.1 frozen assets,
the final blind test, and every FPGA/NPU/Golden/bitstream/FMSH file are
untouched.

This report is the A–I handoff that accompanies
`dist/qam_aware_v3_2_autodl.zip`.

---

## A. Modified files

Created:

- `scripts/verify_qam_aware_v3_2_init.py` — shared init-equivalence verifier
  (single shared input tensor).
- `training/select_qam_aware_v3_2_candidate.py` — validation-only selection +
  freezing of the ablation winner.
- `evaluation/check_qam_aware_v3_2_multi_seed_acceptance.py` — three-seed
  promotion gate (mean improvement + per-seed regression floors).
- `scripts/run_qam_aware_v3_2_formal.py` — three-seed orchestrator with strict
  per-seed resume/skip.
- `configs/qam_aware_v3_2_smoke_full.yaml` — full tiny experiment config.
- `configs/qam_aware_v3_2_ablation_smoke.yaml` — tiny ablation spec.
- `autodl_v3_2/run_smoke_full.sh` — tiny full-pipeline rehearsal.
- `tests/test_qam_aware_v3_2_init_verify.py`,
  `tests/test_qam_aware_v3_2_selection.py`,
  `tests/test_qam_aware_v3_2_multi_seed.py`,
  `tests/test_qam_aware_v3_2_packaging.py`.

Modified:

- `training/qam_aware_v3_2_utils.py` — added `write_text_lf` (LF-only writer,
  kept out of the frozen `training/utils.py`).
- `evaluation/evaluate_qam_aware_v3_2.py` — evaluation seed now comes from the
  baseline (`2026`), not the training seed.
- `training/train_qam_aware_v3_2_ablation.py` — each row now embeds its full
  `training` override; summary written LF-only.
- `configs/qam_aware_v3_2_acceptance.yaml` — added `multi_seed` block.
- `configs/qam_aware_v3_2_ablation.yaml` — added `selection` block.
- `configs/qam_aware_v3_2_smoke_full.yaml` — SNR list `[0, 10, 20]` so the gate
  can check the key SNR bands.
- `scripts/package_qam_aware_v3_2_autodl.py` — LF manifest + `.sh` assertions.
- `scripts/package_qam_aware_v3_2_results.py` — rewritten for the multi-seed
  layout.
- `autodl_v3_2/run_complete.sh` — rewritten 8-step one-command entry.
- `autodl_v3_2/resume_formal.sh` — formal-only resume.
- `autodl_v3_2/run_smoke.sh` — added the four new test files.
- `autodl_v3_2/README.md`, `docs/v3_2_report.md` — updated for consistency.

Deleted (single-seed, now inconsistent):

- `autodl_v3_2/run_formal.sh`
- `autodl_v3_2/run_pilot.sh`

`training/utils.py` is byte-for-byte unchanged (its SHA-256 still matches
`configs/baseline_v1_lock.json`); the LF helper was deliberately placed in the
V3.2-specific module to avoid mutating a frozen Baseline V1 asset.

## B. Four root causes and fixes

1. **CRLF manifest (Windows newline translation).** `Path.write_text` opens in
   text mode with `newline=None`, so on Windows every `\n` became `\r\n`
   (confirmed: 161 CR bytes, BOM present). This broke `sha256sum -c` under
   Linux. *Fix:* a `write_text_lf` helper (`open(..., newline="\n")`) plus
   `_assert_lf` in both packaging scripts; the helper lives in
   `training/qam_aware_v3_2_utils.py` so the frozen `training/utils.py` stays
   untouched.
2. **Double-`torch.randn` in the init-equivalence step.** The old inlined step
   called `torch.randn` twice (`m(torch.randn(...)) - v2(torch.randn(...))`), so
   the two models saw different inputs and `max_abs_diff` was 4.7555. *Fix:* a
   shared `scripts/verify_qam_aware_v3_2_init.py` that seeds once, draws a single
   `x = torch.randn(8,2,1024)`, and requires `(m(x)-v2(x)).abs().max() < 1e-5`
   (actual result 0.0); `run_complete.sh` calls it. A test guards the exact
   logic.
3. **Evaluation used the training seed.** `evaluate_v3_2` seeded the test dataset
   with `config["seed"]` (the training seed), which is wrong once seeds vary.
   *Fix:* the evaluation seed is read from `baseline["seed"]` (2026) so all
   three seeds are compared on the identical V2 namespace.
4. **Single-level config indirection.** The loader resolves only one level of
   `experiment_config`, so an ablation/per-seed override targeting a config that
   lacks `model`/`baseline_config` raised `KeyError`. *Fix:* a full tiny
   `qam_aware_v3_2_smoke_full.yaml` carries `baseline_config` + `model` and is
   used as the `experiment_config` target for the smoke rehearsal.

## C. Full test results

- **52 tests pass** in the V3.2-scope suite (the 10-file list in
  `run_smoke.sh`), 10.5 s on CPU. This includes 21 new tests: init-equivalence
  (2), selection rule (7), multi-seed gate (7), LF/packaging (5).
- Three pre-existing `hardware.fpga.python.*` tests in `tests/` are **out of
  scope** for this model package — they import the frozen external `hardware/`
  tree, which is not shipped in the ZIP. They are untouched.
- `scripts.verify_qam_aware_v3_2_init` → `max_abs_diff: 0.0`, `gate: 0.0`,
  `input: [8,2,1024]`.
- `autodl_v3_2/run_smoke.sh` → `V3_2_AUTODL_SMOKE_PASS`;
  `npu_partition_unexpected_operators: []`; eight-op policy exact.
- `autodl_v3_2/run_smoke_full.sh` → full ablation→selection→3-seed→gate→package
  rehearsal completes; gate correctly reports `gate_passed: false`
  (`gate_result=2`) for the untrained tiny model; 63 formal files packaged.
- Resume/skip: re-running the orchestrator with finished seeds reports
  `status: "skipped"` (reason `SEED_DONE marker present`) for all three seeds and
  re-applies the gate, never re-deriving `selected_candidate.yaml`.

## D. Three-seed orchestration + resume

`scripts/run_qam_aware_v3_2_formal.py` runs three independent seeds (2026, 2027,
2028) into `outputs/qam_aware_v3_2/formal/seeds/seed<seed>/`, each with its own
`checkpoints/`, `tables/`, `onnx/`, `logs/`, `config/`, so no seed can overwrite
another's artifacts. The training override (distillation + class weights) is read
verbatim from the frozen `selected_candidate.yaml` and never re-derived.

Resume semantics (safe to re-run after interruption):

- a seed with `SEED_DONE.json` is skipped;
- a seed with `checkpoints/last.pt` but no marker resumes from that exact
  checkpoint (optimizer/scheduler/AMP/RNG/generator state);
- a seed with neither starts clean;
- `V3_2_AUTODL_COMPLETE_PASS` is printed only after every seed, evaluation,
  ONNX export, acceptance and packaging all complete.

## E. Selection rule

`training/select_qam_aware_v3_2_candidate.py` applies a pre-written,
validation-only rule:

- scope: train/validation only — `test`, `v2_compatible`, and
  `v3_2_final_blind_test` are never consulted;
- metric: `val_macro_f1`, tie-broken by `val_accuracy`;
- the winner's full `training` override is frozen into `selected_candidate.yaml`
  (+ `.json`) together with the ablation summary SHA-256, before any formal seed
  starts.

## F. Multi-seed gate definition

`evaluation/check_qam_aware_v3_2_multi_seed_acceptance.py` applies a fixed rule
(never lowered, never cherry-picked) with thresholds read verbatim from
`promotion_gates`:

- **improvement_on: mean** — the three-seed mean of accuracy (≥ +0.02),
  macro-F1 (≥ +0.02) and QAM mean (≥ +0.05) must each clear the bar;
- **regression_floors_on: every_seed** — EVERY seed must clear the per-class
  drop cap (≤ 0.03) and the 0/10/20 dB drop cap (≤ 0.01).

Final PASS = both halves hold. The evaluator uses the exact V2 development
namespace (test seed 2026) and never accesses the final blind set.

## G. LF / manifest check

- Manifest is LF-only: 0 CR bytes, no BOM, trailing LF.
- Every `.sh` (6 files) in the destination tree is LF-only.
- `sha256sum -c sha256_manifest.txt` (run from inside the destination dir, under
  Linux semantics) exits 0 for all 170 listed files.
- `bash -n` passes on all six `autodl_v3_2/*.sh`.

## H. Final archive

- Path: `F:\FPGA_Work\model_v3_2\dist\qam_aware_v3_2_autodl.zip`
- Entry point: `bash autodl_v3_2/run_complete.sh`
- Contents: 171 entries (170 project files + `sha256_manifest.txt`).
- The archive's own byte size and SHA-256 are printed by the packaging step and
  recorded in the sidecar `dist/qam_aware_v3_2_autodl.zip.sha256` (kept outside
  the archive so the value is not self-referential). The same authoritative
  values are quoted in the handoff message accompanying this report.

## I. AutoDL single command

```bash
bash autodl_v3_2/run_complete.sh
```

On success it prints `V3_2_AUTODL_COMPLETE_PASS`; on a failed gate it prints
`V3_2_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED` and exits non-zero while V2 stays
the frozen champion. The result archive is
`outputs/qam_aware_v3_2/qam_aware_v3_2_formal_results.tar.gz`.

---

## Stop condition

**Work is complete and stops here.** No formal GPU training is started from this
session; the handoff is the AutoDL package plus this report.
