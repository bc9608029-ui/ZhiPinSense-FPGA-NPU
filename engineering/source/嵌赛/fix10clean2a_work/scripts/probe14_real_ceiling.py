"""Measure the frozen model's recall on REAL RadioML2018.01A high-SNR frames.

This is the CEILING for each class: clean generated IQ cannot be recognised
better than the model recognises the real training-domain data itself.  Reads
the F-drive HDF5 briefly (24 classes x 400 frames) and closes it promptly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import h5py  # noqa: E402

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
sys.path.insert(0, MODEL_SRC)
from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402

MODEL_KWARGS = {"denoiser_channels": 24, "denoiser_blocks": 3,
                "feature_channels": (32, 48, 64, 96), "classifier_hidden": 128,
                "dropout": 0.15}
GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
ORDER = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
         "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
         "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
         "AM-DSB-SC", "FM", "GMSK", "OQPSK"]
NF = 400


def main():
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    report = {}
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        for cidx, name in enumerate(ORDER):
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:NF]
            xi = X[q]  # [N,1024,2] float32 planar [I,Q]
            xi = np.ascontiguousarray(xi.transpose(0, 2, 1))
            with torch.inference_mode():
                out, _ = model(torch.from_numpy(xi))
            pred = out.numpy().argmax(axis=1)
            report[name] = float((pred == cidx).mean())
            print(f"{name:<8} real@30dB recall = {report[name]:.3f}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE14_REAL_CEILING.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> PROBE14_REAL_CEILING.json")


if __name__ == "__main__":
    main()
