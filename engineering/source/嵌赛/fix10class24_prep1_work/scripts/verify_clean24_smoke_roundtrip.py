#!/usr/bin/env python3
"""verify_clean24_smoke_roundtrip.py -- fix10class24-prep1 (任务四): offline
roundtrip verification of the 24-class clean-IQ D2 artifacts vs the FROZEN model.

For each of the 24 clean24 smoke samples, feed the D2 RECOVERED [2,1024] fp32
tensor back through the frozen PyTorch model (ADAMRV11Net, checkpoint SHA
96cd25f8...) and check the raw24 argmax AND the 24->23 merged argmax against the
frozen offline baseline recorded in clean24_smoke_manifest.tsv.  This proves the
clean-IQ payload survives the Route-D2 amplitude-mapping + resample + restore
roundtrip (no retraining, no NPU, no SDR) before any board test.

Also measures source-vs-recovered fidelity (correlation / NMSE / RMS-scale error)
so any reconstruction regression is caught offline.

Frozen-model loading / checkpoint / label contract / 24->23 merge are REUSED
verbatim from fix10clean2a's evaluate_frozen_model_on_clean24.py (same USER_SITE
torch source, same MODEL_KWARGS, same merge_many_24_to_23).

Deterministic: model in eval mode, fp32, no dropout, no shuffling.  Writes two
reports (JSON + Markdown) to <out-dir>/clean24_smoke_roundtrip_report.*.

Run:  python -B <this file> --smoke-dir <clean24_smoke dir> --out-dir <results dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True

# torch lives in the user site-packages (removed by ``python -I``); numpy/h5py
# are in the Anaconda env.  Mirrors evaluate_frozen_model_on_clean24.py.
USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
MERGE_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\postprocess"
MERGE_CONTRACT_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\contracts"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
EXPECTED_CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"

DEFAULT_SMOKE_DIR = r"F:/嵌赛/fix10class24_prep1_work/clean24_smoke"
DEFAULT_OUT_DIR = r"F:/嵌赛/fix10class24_prep1_work/results"

MODEL_KWARGS = {
    "denoiser_channels": 24,
    "denoiser_blocks": 3,
    "feature_channels": (32, 48, 64, 96),
    "classifier_hidden": 128,
    "dropout": 0.15,
}

sys.path.insert(0, MODEL_SRC)
sys.path.insert(0, MERGE_DIR)
sys.path.insert(0, MERGE_CONTRACT_DIR)
from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402
from rml23_merged_contract import (  # noqa: E402
    DEPLOYED_LABEL_ORDER_23, SOURCE_LABEL_ORDER_24,
    assert_source_order_matches, assert_23class_contract_consistent,
)
from rml23_merged import merge_many_24_to_23  # noqa: E402


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_model():
    sha = sha256_file(CHECKPOINT)
    if sha != EXPECTED_CHECKPOINT_SHA:
        raise SystemExit("checkpoint SHA mismatch: got %s, expected %s"
                         % (sha, EXPECTED_CHECKPOINT_SHA))
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()
    return model, ck


def read_tensor_f32(path: str) -> np.ndarray:
    """Read a [2,1024] planar [real,imag] fp32 tensor (8192 bytes)."""
    data = np.fromfile(path, dtype="<f4")
    if data.size != 2048:
        raise SystemExit("%s: %d floats, want 2048" % (path, data.size))
    return data.reshape(2, 1024)


def slug(label: str) -> str:
    return label.lower().replace("-", "_")


def load_manifest(smoke_dir: str) -> dict[int, dict]:
    """Parse clean24_smoke_manifest.tsv (27 cols) -> source_index -> dict."""
    path = os.path.join(smoke_dir, "clean24_smoke_manifest.tsv")
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines:
        raise SystemExit("empty manifest: %s" % path)
    header = lines[0].split("\t")
    assert header[0] == "sample_index" and len(header) == 27, \
        "unexpected clean24_smoke_manifest header (%d cols): %r" % (len(header), header[:4])
    seen = set()
    for line in lines[1:]:
        if not line:
            continue
        f = line.split("\t")
        if len(f) < 27:
            raise SystemExit("malformed clean24_smoke_manifest row: %r" % line)
        sidx = int(f[1])
        if sidx in seen:
            raise SystemExit("duplicate source_index %d in manifest" % sidx)
        seen.add(sidx)
        out[sidx] = {
            "modulation": f[4],
            "raw24_class": int(f[2]),
            "deployed23_class": int(f[3]),
            "clip_count": int(f[16]),
            "quantized_file": f[22],
            "recovered_tensor_file": f[23],
            "tx_scale": float(f[24]),
            "frozen_raw24_pred": int(f[25]),
            "frozen_deployed23_pred": int(f[26]),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke-dir", default=DEFAULT_SMOKE_DIR)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    smoke_dir = os.path.abspath(args.smoke_dir)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    assert_source_order_matches(SOURCE_LABEL_ORDER_24)
    assert_23class_contract_consistent()
    model, ck = load_model()
    manifest = load_manifest(smoke_dir)

    per_sample = []
    raw24_agree = 0
    dep23_agree = 0
    raw24_label_ok = 0
    dep23_label_ok = 0
    clip_zero = 0
    nan_inf_total = 0

    for sidx in sorted(manifest):
        m = manifest[sidx]
        rec_path = os.path.join(smoke_dir, m["recovered_tensor_file"])
        src_path = os.path.join(smoke_dir, "source_%s.f32" % slug(m["modulation"]))

        recovered = read_tensor_f32(rec_path)        # [2,1024] f32 planar
        source = read_tensor_f32(src_path)           # [2,1024] f32 planar

        nan_inf_s = int(np.isnan(source).sum()) + int(np.isinf(source).sum())
        nan_inf_r = int(np.isnan(recovered).sum()) + int(np.isinf(recovered).sum())

        x_in = np.ascontiguousarray(recovered[None, :, :], dtype=np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(x_in))    # (1, 24)
        logits24 = out.detach().numpy().astype(np.float64)
        nan_inf_l = int(np.isnan(logits24).sum()) + int(np.isinf(logits24).sum())
        nan_inf_total += nan_inf_s + nan_inf_r + nan_inf_l

        order = np.argsort(-logits24, axis=1)
        top1_logit = float(logits24[0, order[0, 0]])
        top2_logit = float(logits24[0, order[0, 1]])
        margin = top1_logit - top2_logit
        pred24 = int(order[0, 0])

        merged = merge_many_24_to_23(logits24)         # (1, 23)
        pred23 = int(merged.argmax(axis=1)[0])

        ok_raw_agree = (pred24 == m["frozen_raw24_pred"])
        ok_dep_agree = (pred23 == m["frozen_deployed23_pred"])
        ok_raw_label = (pred24 == m["raw24_class"])
        ok_dep_label = (pred23 == m["deployed23_class"])
        raw24_agree += int(ok_raw_agree)
        dep23_agree += int(ok_dep_agree)
        raw24_label_ok += int(ok_raw_label)
        dep23_label_ok += int(ok_dep_label)
        clip_zero += int(m["clip_count"] == 0)

        # fidelity metrics (complex domain, already aligned by recovered_tensor_1024)
        sc = source[0] + 1j * source[1]
        rc = recovered[0] + 1j * recovered[1]
        cc = float(abs(np.vdot(sc, rc)))
        az = float(np.vdot(sc, sc).real)
        ar = float(np.vdot(rc, rc).real)
        corr = abs(cc) / np.sqrt(az * ar) if az * ar > 0 else 0.0
        nmse = float(np.sum(np.abs(sc - rc) ** 2)) / az if az > 0 else 0.0
        rms_src = float(np.sqrt(np.mean(np.abs(sc) ** 2)))
        rms_rec = float(np.sqrt(np.mean(np.abs(rc) ** 2)))
        rms_scale_error = abs(rms_rec - rms_src) / rms_src if rms_src > 0 else 0.0

        per_sample.append({
            "source_index": sidx,
            "modulation": m["modulation"],
            "raw24_class": m["raw24_class"],
            "deployed23_class": m["deployed23_class"],
            "true_raw24_label": SOURCE_LABEL_ORDER_24[m["raw24_class"]],
            "true_deployed23_label": DEPLOYED_LABEL_ORDER_23[m["deployed23_class"]],
            "roundtrip_raw24_pred": pred24,
            "roundtrip_raw24_label": SOURCE_LABEL_ORDER_24[pred24],
            "roundtrip_deployed23_pred": pred23,
            "roundtrip_deployed23_label": DEPLOYED_LABEL_ORDER_23[pred23],
            "baseline_raw24_pred": m["frozen_raw24_pred"],
            "baseline_deployed23_pred": m["frozen_deployed23_pred"],
            "top1_logit": top1_logit,
            "top2_logit": top2_logit,
            "margin": margin,
            "raw24_prediction_agreement": ok_raw_agree,
            "deployed23_prediction_agreement": ok_dep_agree,
            "raw24_label_correct": ok_raw_label,
            "deployed23_label_correct": ok_dep_label,
            "clip_count": m["clip_count"],
            "nan_inf": nan_inf_s + nan_inf_r + nan_inf_l,
            "tensor_correlation": corr,
            "tensor_nmse": nmse,
            "rms_scale_error": rms_scale_error,
            "source_sha256": sha256_file(src_path),
            "recovered_sha256": sha256_file(rec_path),
            "quantized_sha256": sha256_file(
                os.path.join(smoke_dir, m["quantized_file"])),
        })

    n = len(per_sample)
    raw_labels = sorted(p["modulation"] for p in per_sample)
    dep_indices = sorted(p["deployed23_class"] for p in per_sample)
    raw24_coverage = len(set(raw_labels))
    dep23_coverage = len(set(dep_indices))

    result = {
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "best_epoch": ck.get("best_epoch"),
        "n_samples": n,
        "raw24_class_coverage": "%d/24" % raw24_coverage,
        "deployed23_class_coverage": "%d/23" % dep23_coverage,
        "raw24_prediction_agreement": "%d/%d" % (raw24_agree, n),
        "deployed23_prediction_agreement": "%d/%d" % (dep23_agree, n),
        "raw24_label_correct": "%d/%d" % (raw24_label_ok, n),
        "deployed23_label_correct": "%d/%d" % (dep23_label_ok, n),
        "clip_count_zero": "%d/%d" % (clip_zero, n),
        "nan_inf_total": nan_inf_total,
        "samples": per_sample,
    }

    # Acceptance (hard fail if any is not met).
    ok = (n == 24
          and raw24_coverage == 24 and dep23_coverage == 23
          and raw24_agree == 24 and dep23_agree == 24
          and raw24_label_ok == 24 and dep23_label_ok == 24
          and clip_zero == 24 and nan_inf_total == 0)
    result["acceptance_pass"] = bool(ok)

    json_path = os.path.join(out_dir, "clean24_smoke_roundtrip_report.json")
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)

    md_path = os.path.join(out_dir, "clean24_smoke_roundtrip_report.md")
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# fix10class24-prep1 — offline roundtrip verification\n\n")
        fh.write("checkpoint_sha256 = `%s`\n\n" % EXPECTED_CHECKPOINT_SHA)
        fh.write("| source_index | modulation | raw24 pred | dep23 pred | "
                 "raw24 agree | dep23 agree | corr | nmse | rms_scale_err |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|\n")
        for s in per_sample:
            fh.write("| %d | %s | %s(%d) | %s(%d) | %s | %s | %.6f | %.3e | %.3e |\n"
                     % (s["source_index"], s["modulation"],
                        s["roundtrip_raw24_label"], s["roundtrip_raw24_pred"],
                        s["roundtrip_deployed23_label"], s["roundtrip_deployed23_pred"],
                        "YES" if s["raw24_prediction_agreement"] else "NO",
                        "YES" if s["deployed23_prediction_agreement"] else "NO",
                        s["tensor_correlation"], s["tensor_nmse"],
                        s["rms_scale_error"]))
        fh.write("\n**raw24_prediction_agreement = %s**  "
                 "**deployed23_prediction_agreement = %s**  "
                 "**raw24_label_correct = %s**  **deployed23_label_correct = %s**  "
                 "**clip_count_zero = %s**  **nan_inf = %d**\n"
                 % (result["raw24_prediction_agreement"],
                    result["deployed23_prediction_agreement"],
                    result["raw24_label_correct"],
                    result["deployed23_label_correct"],
                    result["clip_count_zero"], result["nan_inf_total"]))

    print("CLEAN24_SMOKE_ROUNDTRIP n=%d raw24_agree=%s dep23_agree=%s "
          "raw24_label=%s dep23_label=%s clip_zero=%s nan_inf=%d acceptance=%s"
          % (n, result["raw24_prediction_agreement"],
             result["deployed23_prediction_agreement"],
             result["raw24_label_correct"], result["deployed23_label_correct"],
             result["clip_count_zero"], result["nan_inf_total"],
             "PASS" if ok else "FAIL"))
    for s in per_sample:
        print("  %s source_index=%d raw24=%s(%d) dep23=%s(%d) corr=%.6f "
              "nmse=%.3e rms_err=%.3e margin=%.6f"
              % (s["modulation"], s["source_index"],
                 s["roundtrip_raw24_label"], s["roundtrip_raw24_pred"],
                 s["roundtrip_deployed23_label"], s["roundtrip_deployed23_pred"],
                 s["tensor_correlation"], s["tensor_nmse"], s["rms_scale_error"],
                 s["margin"]))
    print("wrote %s" % json_path)
    print("wrote %s" % md_path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
