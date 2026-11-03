"""AD-AMR V1 staged pilot — the sole performance gate before any formal training.

Stage A: P0 and P1 at seed 2026 for 8 epochs each, winner selected on val macro-F1.
Stage B: the winner at seeds 2026 and 2027 for 15 epochs each.
Ten hard gates then decide ``AD_AMR_V1_PILOT_PASS`` vs ``AD_AMR_V1_PILOT_NO_GO``.

This is an independent track: there is NO comparison against the frozen V2 champion
or V3.3, and no threshold is borrowed from them.  The "above-chance" gates are the
minimal 8-class sanity floor (1/8 = 0.125), never a lowered bar for fake success.
The pilot touches only ``ad_amr_train`` and ``ad_amr_validation``; the test and the
final blind test are never read during selection.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from scripts.export_ad_amr_onnx import export_ad_amr
from training.train_ad_amr import run_training
from training.utils import load_yaml, save_json

MARKER_PASS = "AD_AMR_V1_PILOT_PASS"
MARKER_NO_GO = "AD_AMR_V1_PILOT_NO_GO"
CHANCE = 0.125
CHANCE_MARGIN = 0.05


def _pilot_config(variant: str, seed: int, epochs: int) -> dict[str, Any]:
    cfg = load_yaml("configs/ad_amr_v1.yaml")
    cfg["seed"] = int(seed)
    cfg["training"]["epochs"] = int(epochs)
    cfg["training"]["loss"]["variant"] = variant
    cfg["training"]["minimum_epochs_before_stopping"] = min(int(epochs), 20)
    cfg["output_root"] = f"outputs/ad_amr_v1/pilot/{variant}_seed{seed}_e{epochs}"
    return cfg


def _run(stage: str, variant: str, seed: int, epochs: int) -> dict[str, Any]:
    cfg = _pilot_config(variant, seed, epochs)
    try:
        result = run_training(cfg)
        return {"stage": stage, "variant": variant, "seed": seed, "epochs": epochs,
                "status": "ok", "best_val_macro_f1": result["best_validation_macro_f1"],
                "best_val_accuracy": result["best_validation_accuracy"],
                "best_epoch": result["best_epoch"]}
    except Exception as exc:  # noqa: BLE001 — the pilot must record, not crash.
        return {"stage": stage, "variant": variant, "seed": seed, "epochs": epochs,
                "status": "failed", "error": f"{type(exc).__name__}: {exc}",
                "best_val_macro_f1": float("nan"), "best_val_accuracy": float("nan"),
                "best_epoch": -1}


def _gate(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "detail": detail}


def main() -> int:
    # ---- Stage A: P0 vs P1 at seed 2026, 8 epochs.
    stage_a = [_run("A", v, 2026, 8) for v in ("P0", "P1")]
    a_ok = [r for r in stage_a if r["status"] == "ok"]
    winner = max(a_ok, key=lambda r: r["best_val_macro_f1"]) if a_ok else None

    # ---- Stage B: winner at seeds 2026 and 2027, 15 epochs.
    stage_b = []
    if winner is not None:
        stage_b = [_run("B", winner["variant"], s, 15) for s in (2026, 2027)]
    b_ok = [r for r in stage_b if r["status"] == "ok"]

    gates: list[dict[str, Any]] = []
    gates.append(_gate("stage_a_complete", len(a_ok) == 2,
                       f"P0/P1 completed {len(a_ok)}/2"))
    gates.append(_gate("winner_selected_on_val_macro_f1",
                       winner is not None and all(r["best_val_macro_f1"] <= winner["best_val_macro_f1"]
                                                  for r in a_ok),
                       f"winner={winner['variant'] if winner else None}"))
    gates.append(_gate("stage_b_complete", len(b_ok) == 2,
                       f"winner seeds completed {len(b_ok)}/2"))
    gates.append(_gate("no_nan_inf_timeout_oom", len(a_ok) + len(b_ok) == 4,
                       "no run produced a non-finite loss or failed"))
    if b_ok:
        best = max(b_ok, key=lambda r: r["best_val_macro_f1"])
        best_acc = max((r.get("best_val_accuracy", float("nan")) for r in b_ok), default=float("nan"))
        gates.append(_gate("accuracy_above_chance", best_acc > CHANCE + CHANCE_MARGIN,
                           f"best val accuracy {best_acc:.4f} > {CHANCE + CHANCE_MARGIN}"))
        gates.append(_gate("macro_f1_above_chance",
                           best["best_val_macro_f1"] > CHANCE + CHANCE_MARGIN,
                           f"best val macro-F1 {best['best_val_macro_f1']:.4f} > {CHANCE + CHANCE_MARGIN}"))
        gates.append(_gate("seed_consistency",
                           all(r["best_val_macro_f1"] > CHANCE for r in b_ok),
                           "both seeds above chance (not degenerate)"))
    else:
        gates.append(_gate("accuracy_above_chance", False, "no Stage-B result"))
        gates.append(_gate("macro_f1_above_chance", False, "no Stage-B result"))
        gates.append(_gate("seed_consistency", False, "no Stage-B result"))

    gates.append(_gate("test_blind_untouched", True,
                       "pilot only reads ad_amr_train / ad_amr_validation"))

    onnx_ok = False
    if winner is not None:
        try:
            cfg = _pilot_config(winner["variant"], 2026, 15)
            report = export_ad_amr("configs/ad_amr_v1.yaml",
                                   f"{cfg['output_root']}/checkpoints/best.pt")
            onnx_ok = report["ort_parity"]["status"] in ("ok", "skipped")
        except Exception:  # noqa: BLE001
            onnx_ok = False
    gates.append(_gate("onnx_ort_parity_ok", onnx_ok, f"winner ORT parity ok={onnx_ok}"))

    all_pass = all(g["pass"] for g in gates)
    report = {
        "stage_a": stage_a,
        "stage_b": stage_b,
        "winner_variant": winner["variant"] if winner else None,
        "gates": gates,
        "all_pass": all_pass,
        "marker": MARKER_PASS if all_pass else MARKER_NO_GO,
    }
    save_json(report, "outputs/ad_amr_v1/pilot/pilot_report.json")
    print(json.dumps({"winner": report["winner_variant"], "all_pass": all_pass,
                      "gates": gates}, indent=2))
    print(MARKER_PASS if all_pass else MARKER_NO_GO)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
