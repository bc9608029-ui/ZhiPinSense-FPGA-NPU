#!/usr/bin/env python3
"""inventory_realrf.py -- Phase A data & identity audit (M29-RML24-REALRF-TRAINABILITY-AUDIT1).

READ-ONLY scan of the existing real-RF and digital capture sessions + the frozen
source waveforms, emitting results/data_inventory.tsv and results/inventory_verdict.json.

Detects (taskbook 4.2):
  - duplicate source SHA / duplicate recovered-tensor SHA
  - cross-session source-waveform overlap (leakage -> train/val/test splitability)
  - class coverage per session
  - protocol / waveform-version mixing

Red lines honoured: no training, no board/SDR/transmit, never uses labels/source
identity to assist recovery, never removes gate-rejected/wrong/non-finite samples.

Run:  python -I scripts/inventory_realrf.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Frozen identities (verbatim, unchanged).
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"

# Source waveforms (frozen public protocol v2): one waveform per class.
TX_MANIFEST = Path(r"F:\嵌赛\fix10class24_waveform_correct_v2_work\tx_package\public_protocol_tx_manifest.tsv")
TX_DIR = TX_MANIFEST.parent

# Capture sessions.  "dual" == real dual-SDR RF; "file" == digital file playback
# (no RF, no capture.diag.tsv).  Both carry the SAME 24 source waveforms.
SESSIONS = [
    dict(session_id="rf_fix2_target",
         capture_kind="dual_rf",
         d=Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")),
    dict(session_id="rf_independent_v2",
         capture_kind="dual_rf",
         d=Path(r"F:\嵌赛\board_capture\rml24_independent_v2_dual_1773374217_210")),
    dict(session_id="digital_fix2_v2",
         capture_kind="file_digital",
         d=Path(r"F:\嵌赛\board_capture\rml24_fix2_v2_file_1773373830_244")),
    dict(session_id="digital_independent_v2",
         capture_kind="file_digital",
         d=Path(r"F:\嵌赛\board_capture\rml24_independent_v2_file_1773373809_210")),
]

RESULT_TSV = "board_independent_rx_results.tsv"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return [], []
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        cells = ln.split("\t")
        rows.append(dict(zip(header, cells)))
    return header, rows


def load_source_manifest() -> dict[int, dict]:
    hdr, rows = read_tsv(TX_MANIFEST)
    out = {}
    for r in rows:
        sid = int(r["source_index"])
        out[sid] = dict(source_id=r["source_id"], conversion_version=r["conversion_version"],
                        class_index=int(r["class_index"]), class_name=r["class_name"],
                        burst_sha256=r["burst_sha256"], burst_file=r["burst_file"])
    return out


def main() -> int:
    src = load_source_manifest()
    n_src = len(src)
    src_ids = sorted(set(s["source_id"] for s in src.values()))
    wv_versions = sorted(set(s["conversion_version"] for s in src.values()))
    classes = sorted(set(s["class_index"] for s in src.values()))
    print("source waveforms: n=%d  source_ids=%s  versions=%s  classes=%d" %
          (n_src, src_ids, wv_versions, len(classes)))

    inv_header = ["sample_id", "source_index", "source_sha256", "label", "session_id",
                  "protocol_version", "waveform_version", "capture_kind", "raw_rx_path",
                  "recovered_tensor_path", "tensor_sha256", "gate_result", "residual",
                  "board_pred", "model_sha"]
    inv_rows = []

    per_session: dict[str, dict] = {}
    all_source_sha = set()
    all_tensor_sha = set()
    dup_tensor = 0
    source_by_session: dict[str, set] = {}

    for sess in SESSIONS:
        d = sess["d"]
        res = d / RESULT_TSV
        if not res.is_file():
            print("  MISSING results: %s" % res)
            per_session[sess["session_id"]] = dict(error="missing results")
            continue
        _, rows = read_tsv(res)
        src_set = set()
        sess_dup_tensor = 0
        n = 0
        for r in rows:
            sid = int(r["source_index"])
            cls = int(r["class_index"])
            burst = src.get(sid, {})
            burst_sha = burst.get("burst_sha256", "")
            src_set.add(burst_sha)
            all_source_sha.add(burst_sha)

            tensor_path = d / ("%d.recovered.tensor.bin" % sid)
            tsha = sha256_file(tensor_path) if tensor_path.is_file() else ""
            if tsha:
                if tsha in all_tensor_sha:
                    dup_tensor += 1
                    sess_dup_tensor += 1
                all_tensor_sha.add(tsha)

            raw_path = d / ("%d.raw.i16" % sid)
            inv_rows.append([
                "%s:%02d" % (sess["session_id"], sid), str(sid), burst_sha,
                "%s_%s" % (cls, r["class_name"]), sess["session_id"],
                "v2", burst.get("conversion_version", ""), sess["capture_kind"],
                str(raw_path) if raw_path.is_file() else "",
                str(tensor_path) if tensor_path.is_file() else "",
                tsha, r["gated"], r["training_residual_rel"], r["board_pred"],
                FROZEN_MODEL_RAW_SHA,
            ])
            n += 1
        source_by_session[sess["session_id"]] = src_set
        per_session[sess["session_id"]] = dict(
            n_frames=n, n_unique_sources=len(src_set), dup_tensor=sess_dup_tensor,
            classes=len(set(int(r["class_index"]) for r in rows)),
            gate_pass=sum(1 for r in rows if r["gated"] == "1"),
            correct=sum(1 for r in rows if r["board_pred"] == r["class_index"]),
        )

    # cross-session source overlap
    sess_names = [s["session_id"] for s in SESSIONS if s["session_id"] in source_by_session]
    pair_overlap = {}
    for i, a in enumerate(sess_names):
        for b in sess_names[i + 1:]:
            pair_overlap["%s|%s" % (a, b)] = len(source_by_session[a] & source_by_session[b])

    # sufficiency verdict (taskbook 4.2 / 6.2 / 9.4)
    n_rf_sessions = sum(1 for s in SESSIONS if s["capture_kind"] == "dual_rf"
                        and s["session_id"] in per_session)
    unique_sources_total = len(all_source_sha)
    same_24_repeated = (n_src == 24 and unique_sources_total == 24
                        and all(len(source_by_session.get(s, set())) == 24
                                for s in sess_names))
    insufficient = n_rf_sessions < 5 or unique_sources_total < 5 * 20 * 24 or same_24_repeated

    verdict = {
        "token": "M29-RML24-REALRF-TRAINABILITY-AUDIT1-INVENTORY",
        "n_source_waveforms": n_src,
        "n_unique_source_sha_total": unique_sources_total,
        "source_ids": src_ids,
        "waveform_versions": wv_versions,
        "n_real_rf_sessions": n_rf_sessions,
        "per_session": per_session,
        "cross_session_source_overlap": pair_overlap,
        "same_24_source_waveforms_repeated_across_sessions": bool(same_24_repeated),
        "duplicate_tensor_sha_count": dup_tensor,
        "sufficiency": ("CURRENT_DATA_INSUFFICIENT_FOR_FINAL_FINETUNING"
                        if insufficient else "SUFFICIENT_FOR_EXPLORATORY_ONLY"),
        "leakage_check": "TRAIN_VAL_TEST_SPLIT_IMPOSSIBLE"
        if same_24_repeated else "split_possible",
        "n_sessions_needed_for_final": 5,
    }

    out_dir = ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "data_inventory.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(inv_header) + "\n")
        for row in inv_rows:
            f.write("\t".join(row) + "\n")
    with open(out_dir / "inventory_verdict.json", "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2, ensure_ascii=False)

    print("\n=== per-session ===")
    for s in SESSIONS:
        sid = s["session_id"]
        p = per_session.get(sid, {})
        if "error" in p:
            print("  %-24s %s" % (sid, p["error"]))
            continue
        print("  %-24s frames=%d src=%d gate=%d/24 correct=%d/24 dup_tensor=%d" %
              (sid, p["n_frames"], p["n_unique_sources"], p["gate_pass"],
               p["correct"], p["dup_tensor"]))
    print("\n=== cross-session source overlap (24 = total) ===")
    for k, v in pair_overlap.items():
        print("  %-50s %d/24" % (k, v))
    print("\nsufficiency = %s" % verdict["sufficiency"])
    print("leakage = %s" % verdict["leakage_check"])
    print("wrote %s + %s" % (out_dir / "data_inventory.tsv", out_dir / "inventory_verdict.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
