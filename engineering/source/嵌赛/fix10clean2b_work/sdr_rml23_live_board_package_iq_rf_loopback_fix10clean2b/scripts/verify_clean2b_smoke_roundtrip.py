#!/usr/bin/env python3
"""verify_clean2b_smoke_roundtrip.py -- fix10clean2b Step 2: offline roundtrip
verification of the 2-sample clean-IQ D2 artifacts against the FROZEN model.

For each clean2b smoke sample, feeds the D2 RECOVERED [2,1024] fp32 tensor back
through the frozen PyTorch model (ADAMRV11Net, checkpoint SHA 96cd25f8...) and
checks that the 24->23 merged argmax matches the offline frozen baseline
prediction recorded in clean2b_smoke_manifest.tsv.  This proves the clean-IQ
payload survives the Route-D2 amplitude-mapping + resample + restore roundtrip
(no model retraining, no NPU) before any board test.

Also measures source-vs-recovered fidelity (correlation / NMSE / RMS-scale error)
so any reconstruction regression is caught offline.

Deterministic: model in eval mode, fp32, no dropout, no shuffling.  Reads the
clean2b_smoke/ artifacts + the frozen checkpoint + the frozen model.  Writes two
reports (JSON + Markdown) to <out-dir>/clean2b_smoke_roundtrip_report.*.

Run:  python -I <this file> --smoke-dir <clean2b_smoke dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# torch/numpy/h5py come from the Anaconda env (mirrors evaluate_frozen_model_on_
# clean24.py).  USER_SITE is kept for fidelity with that script's torch source.
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

DEFAULT_SMOKE_DIR = r"F:/嵌赛/fix10clean2b_work/clean2b_smoke"
DEFAULT_OUT_DIR = r"F:/嵌赛/fix10clean2b_work/results"

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
    assert_source_order_matches,
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


def load_manifest_extra(smoke_dir: str) -> dict[int, dict]:
    """Parse clean2b_smoke_manifest.tsv (27 cols) -> source_index -> dict with
    modulation, deployed23_class, quantized_file, recovered_tensor_file,
    frozen_raw24_pred, frozen_deployed23_pred."""
    path = os.path.join(smoke_dir, "clean2b_smoke_manifest.tsv")
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines:
        raise SystemExit("empty manifest: %s" % path)
    header = lines[0].split("\t")
    assert header[0] == "sample_index" and len(header) == 27, \
        "unexpected clean2b_smoke_manifest header (%d cols): %r" % (len(header), header[:4])
    for line in lines[1:]:
        if not line:
            continue
        f = line.split("\t")
        if len(f) < 27:
            raise SystemExit("malformed clean2b_smoke_manifest row: %r" % line)
        sidx = int(f[1])
        out[sidx] = {
            "modulation": f[4],
            "raw24_class": int(f[2]),
            "deployed23_class": int(f[3]),
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
    model, ck = load_model()
    manifest = load_manifest_extra(smoke_dir)

    per_sample = []
    agreement = 0
    label_correct = 0
    for sidx in sorted(manifest):
        m = manifest[sidx]
        rec_path = os.path.join(smoke_dir, m["recovered_tensor_file"])
        # source file name is source_clean_<tag>.f32 where tag = modulation.lower()
        tag = m["modulation"].lower()
        src_path = os.path.join(smoke_dir, "source_clean_%s.f32" % tag)

        recovered = read_tensor_f32(rec_path)        # [2,1024] f32 planar
        source = read_tensor_f32(src_path)           # [2,1024] f32 planar

        x_in = np.ascontiguousarray(recovered[None, :, :], dtype=np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(x_in))    # (1, 24)
        logits24 = out.detach().numpy().astype(np.float64)
        merged = merge_many_24_to_23(logits24)         # (1, 23)
        pred23 = int(merged.argmax(axis=1)[0])

        ok_agree = (pred23 == m["frozen_deployed23_pred"])
        ok_label = (pred23 == m["deployed23_class"])
        agreement += int(ok_agree)
        label_correct += int(ok_label)

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
            "deployed23_class": m["deployed23_class"],
            "frozen_deployed23_pred": m["frozen_deployed23_pred"],
            "roundtrip_deployed23_pred": pred23,
            "roundtrip_deployed23_label": DEPLOYED_LABEL_ORDER_23[pred23],
            "prediction_agreement": ok_agree,
            "label_correct": ok_label,
            "tensor_correlation": corr,
            "tensor_nmse": nmse,
            "rms_scale_error": rms_scale_error,
            "source_sha256": sha256_file(src_path),
            "recovered_sha256": sha256_file(rec_path),
            "quantized_sha256": sha256_file(
                os.path.join(smoke_dir, m["quantized_file"])),
        })

    result = {
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "best_epoch": ck.get("best_epoch"),
        "n_samples": len(per_sample),
        "prediction_agreement": "%d/%d" % (agreement, len(per_sample)),
        "label_correct": "%d/%d" % (label_correct, len(per_sample)),
        "samples": per_sample,
    }

    json_path = os.path.join(out_dir, "clean2b_smoke_roundtrip_report.json")
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)

    md_path = os.path.join(out_dir, "clean2b_smoke_roundtrip_report.md")
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# fix10clean2b-smoke — offline roundtrip verification\n\n")
        fh.write("checkpoint_sha256 = `%s`\n\n" % EXPECTED_CHECKPOINT_SHA)
        fh.write("| source_index | modulation | roundtrip pred | baseline pred | "
                 "agreement | label | corr | nmse | rms_scale_err |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|\n")
        for s in per_sample:
            fh.write("| %d | %s | %s(%d) | %s(%d) | %s | %s | %.6f | %.3e | %.3e |\n"
                     % (s["source_index"], s["modulation"],
                        DEPLOYED_LABEL_ORDER_23[s["roundtrip_deployed23_pred"]],
                        s["roundtrip_deployed23_pred"],
                        DEPLOYED_LABEL_ORDER_23[s["frozen_deployed23_pred"]],
                        s["frozen_deployed23_pred"],
                        "YES" if s["prediction_agreement"] else "NO",
                        "YES" if s["label_correct"] else "NO",
                        s["tensor_correlation"], s["tensor_nmse"],
                        s["rms_scale_error"]))
        fh.write("\n**prediction_agreement = %s**  **label_correct = %s**\n"
                 % (result["prediction_agreement"], result["label_correct"]))

    print("CLEAN2B_SMOKE_ROUNDTRIP prediction_agreement=%s label_correct=%s "
          "n=%d" % (result["prediction_agreement"], result["label_correct"],
                    len(per_sample)))
    for s in per_sample:
        print("  %s source_index=%d roundtrip=%s(%d) baseline=%s(%d) agree=%s "
              "corr=%.6f nmse=%.3e rms_err=%.3e"
              % (s["modulation"], s["source_index"],
                 s["roundtrip_deployed23_label"], s["roundtrip_deployed23_pred"],
                 DEPLOYED_LABEL_ORDER_23[s["frozen_deployed23_pred"]],
                 s["frozen_deployed23_pred"],
                 "YES" if s["prediction_agreement"] else "NO",
                 s["tensor_correlation"], s["tensor_nmse"], s["rms_scale_error"]))
    print("wrote %s" % json_path)
    print("wrote %s" % md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
