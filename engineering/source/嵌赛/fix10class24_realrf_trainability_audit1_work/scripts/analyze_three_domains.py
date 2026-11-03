#!/usr/bin/env python3
"""analyze_three_domains.py -- Phase B three-domain (A/B/C) separability & info-retention audit.

READ-ONLY consolidation of already-frozen measurements into one three-domain table that
answers the trainability questions Q1/Q2 without any training:

  A = original RadioML2018.01A (train distribution, frozen BF16 model is native here)
  B = digital file recovery (same 24 tx_package source waveforms, no RF)
  C = real dual-SDR RF recovery (deployment domain)

Evidence sources (all frozen, all read-only):
  A   fix10class24_original_radioml_accuracy1_work/results/summary.json  (bf16.accuracy)
  C0  fix10class24_full24_accuracy1_work/.../summary.json  (e2e / gated / forced / coverage)
  B,C fix10class24_realrf_trainability_audit1_work/results/data_inventory.tsv (per-session)

Outputs:
  results/three_domain_summary.tsv
  results/three_domain_verdict.json

No training, no model mutation, no gate change, no sample removal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A_SUMMARY = Path(r"F:\嵌赛\fix10class24_original_radioml_accuracy1_work\results\summary.json")
C0_SUMMARY = Path(r"F:\嵌赛\fix10class24_full24_accuracy1_work\sdr_rml24_fix10class24_full24_accuracy1\results\full24_accuracy1\summary.json")
INVENTORY = ROOT / "results" / "data_inventory.tsv"


def read_tsv(path: Path) -> tuple[list[str], list[dict]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, ln.split("\t"))) for ln in lines[1:] if ln.strip()]
    return header, rows


def fnum(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return float("nan")


def residual_stats(rows: list[dict]) -> dict:
    vals = [fnum(r["residual"]) for r in rows if r["residual"].strip() not in ("", "nan")]
    if not vals:
        return dict(n=0)
    vals = sorted(vals)
    return dict(n=len(vals), min=vals[0], median=vals[len(vals) // 2],
                max=vals[-1], mean=sum(vals) / len(vals))


def main() -> int:
    # A domain
    a = json.loads(A_SUMMARY.read_text(encoding="utf-8"))
    a_acc = a["bf16"]["accuracy"]
    a_correct = a["bf16"]["correct"]
    a_total = a["bf16"]["total"]

    # C0 (full24 RF session, has forced classification)
    c0 = json.loads(C0_SUMMARY.read_text(encoding="utf-8"))
    c0_m = c0["metrics"]

    # B and C from inventory
    hdr, inv = read_tsv(INVENTORY)
    by_session: dict[str, list[dict]] = {}
    for r in inv:
        by_session.setdefault(r["session_id"], []).append(r)

    def sess_acc(sid: str) -> dict:
        rows = by_session.get(sid, [])
        n = len(rows)
        correct = sum(1 for r in rows if r["board_pred"] == r["label"].split("_", 1)[0])
        gate = sum(1 for r in rows if r["gate_result"] == "1")
        return dict(n=n, correct=correct, gate_pass=gate,
                    acc=correct / n if n else float("nan"),
                    gated_acc=(sum(1 for r in rows if r["gate_result"] == "1"
                                  and r["board_pred"] == r["label"].split("_", 1)[0])
                               / gate if gate else float("nan")),
                    residual=residual_stats(rows))

    rf_fix2 = sess_acc("rf_fix2_target")
    rf_indep = sess_acc("rf_independent_v2")
    dig_fix2 = sess_acc("digital_fix2_v2")
    dig_indep = sess_acc("digital_independent_v2")

    # pooled B (digital) and C (rf) accuracy over the tx_package 1-24 sessions
    def pool(sids: list[str]) -> dict:
        rows = [r for s in sids for r in by_session.get(s, [])]
        n = len(rows)
        correct = sum(1 for r in rows if r["board_pred"] == r["label"].split("_", 1)[0])
        gate = sum(1 for r in rows if r["gate_result"] == "1")
        return dict(n=n, correct=correct, gate_pass=gate,
                    acc=correct / n if n else float("nan"), residual=residual_stats(rows))

    b_pool = pool(["digital_fix2_v2", "digital_independent_v2"])
    c_pool = pool(["rf_fix2_target", "rf_independent_v2"])

    verdict = {
        "token": "M29-RML24-REALRF-TRAINABILITY-AUDIT1-THREE-DOMAIN",
        "domain_A_original": dict(accuracy=a_acc, correct=a_correct, total=a_total),
        "domain_B_digital": dict(
            n=b_pool["n"], correct=b_pool["correct"], accuracy=b_pool["acc"],
            gate_pass=b_pool["gate_pass"], residual=b_pool["residual"],
            per_session=dict(digital_fix2_v2=dig_fix2, digital_independent_v2=dig_indep)),
        "domain_C_rf": dict(
            n=c_pool["n"], correct=c_pool["correct"], accuracy=c_pool["acc"],
            gate_pass=c_pool["gate_pass"], residual=c_pool["residual"],
            per_session=dict(rf_fix2_target=rf_fix2, rf_independent_v2=rf_indep)),
        "domain_C0_full24": dict(
            end_to_end_accuracy=c0_m["end_to_end_accuracy"],
            end_to_end_correct=c0_m["end_to_end_correct"],
            gated_accuracy=c0_m["gated_accuracy"], gated_correct=c0_m["gated_correct"],
            coverage=c0_m["coverage"], forced_correct=c0_m["forced_correct"],
            production_threshold=c0["production_threshold"]),
        "Q1_info_retained": ("PARTIAL" if int(c0_m["forced_correct"].split("/")[0]) >= 12
                             else "NO"),
        "Q2_mismatch_vs_broken": (
            "RECEIVE_CHAIN_RESIDUAL_BOTTLENECK"
            if (b_pool["acc"] >= 0.9
                and int(c0_m["forced_correct"].split("/")[0]) > int(c0_m["end_to_end_correct"].split("/")[0]))
            else "MODEL_DOMAIN_MISMATCH"),
    }

    out = ROOT / "results"
    out.mkdir(parents=True, exist_ok=True)

    # summary tsv
    def row(name, n, correct, acc, gate, forced, residual):
        return [name, str(n), str(correct), "%.4f" % acc if acc == acc else "",
                str(gate), str(forced), "%.4f" % residual.get("median", float("nan"))
                if residual.get("n") else "", str(residual.get("n", 0))]

    header = ["domain", "n", "correct", "accuracy", "gate_pass", "forced_correct",
              "residual_median", "residual_n"]
    rows_out = [
        row("A_original_radioml", a_total, a_correct, a_acc, "", "", {}),
        row("B_digital_pool", b_pool["n"], b_pool["correct"], b_pool["acc"],
            b_pool["gate_pass"], "", b_pool["residual"]),
        row("C_rf_pool_txpackage", c_pool["n"], c_pool["correct"], c_pool["acc"],
            c_pool["gate_pass"], "", c_pool["residual"]),
        ["C0_full24_rf", "24", c0_m["end_to_end_correct"], "%.4f" % c0_m["end_to_end_accuracy"],
         str(c0_m["gated_correct"].split("/")[1]), c0_m["forced_correct"], "", "0"],
    ]
    with open(out / "three_domain_summary.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for r in rows_out:
            f.write("\t".join(r) + "\n")

    with open(out / "three_domain_verdict.json", "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2, ensure_ascii=False)

    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    print("\nwrote three_domain_summary.tsv + three_domain_verdict.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
