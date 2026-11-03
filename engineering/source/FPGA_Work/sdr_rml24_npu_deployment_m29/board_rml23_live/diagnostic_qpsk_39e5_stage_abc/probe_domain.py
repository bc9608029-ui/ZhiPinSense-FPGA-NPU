#!/usr/bin/env python3
"""probe_domain.py -- quick empirical probe: RadioML QPSK vs real QPSK domain RMS + FP32 top-1.

Establishes the ground-truth numbers the Stage A/B/C reports rest on:
  - RadioML2018.01A QPSK (label 4) test samples at high SNR: complex RMS + planar scalar RMS
  - 78 real QPSK capture frames: same
  - FP32 ONNX top-1 distribution on both domains

Pure stdlib + numpy + h5py + onnxruntime. Run isolated: python -I probe_domain.py
"""
import glob, json, os, sys
import numpy as np
import h5py
import onnxruntime as ort

HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
IDX = r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz"
ONNX = r"F:/FPGA_Work/sdr_rml24_npu_deployment_m29/work/onnx/rml24_24class_opset17.onnx"
REAL = r"C:/Users/shado/Downloads/rml23_analysis_20261011_225430/rml23_capture_39e5_final_1773383076"

LABEL_ORDER_24 = ("OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK",
    "16APSK","32APSK","64APSK","128APSK","16QAM","32QAM","64QAM",
    "128QAM","256QAM","AM-SSB-WC","AM-SSB-SC","AM-DSB-WC",
    "AM-DSB-SC","FM","GMSK","OQPSK")

def complex_rms(x):  # x: complex array (length 1024)
    return float(np.sqrt(np.mean(np.abs(x)**2)))

def scalar_rms(iq):  # iq: [2,1024] planar
    return float(np.sqrt(np.mean(iq.astype(np.float64)**2)))

def load_real():
    frames = []
    for p in sorted(glob.glob(os.path.join(REAL, "live_rx_tensor_*.f32"))):
        d = np.fromfile(p, dtype="<f4")
        assert d.size == 2048, d.size
        iq = d.reshape(2, 1024).astype(np.float64)  # plane0=I plane1=Q
        x = iq[0] + 1j*iq[1]
        fid = int(os.path.basename(p)[len("live_rx_tensor_"):-len(".f32")])
        frames.append((fid, iq, x))
    return frames

def main():
    # ---- RadioML QPSK at high SNR (test split) ----
    with np.load(IDX, allow_pickle=False) as z:
        ti = z["test_indices"]; tl = z["test_labels"]; ts = z["test_snrs"]
    qpsk_mask = (tl == 4)
    snr30 = qpsk_mask & (np.abs(ts - 30.0) < 1e-6)
    snr28 = qpsk_mask & (np.abs(ts - 28.0) < 1e-6)
    print("RadioML test QPSK: total=%d, snr30=%d, snr28=%d" % (qpsk_mask.sum(), snr30.sum(), snr28.sum()))

    N = 400
    sel_idx = np.where(snr30)[0][:N]
    cr, sr = [], []
    h5 = h5py.File(HDF5, "r"); X = h5["X"]
    for k in sel_idx:
        raw = np.asarray(X[int(ti[k])], dtype=np.float64)  # [1024,2]
        iq = raw.T  # [2,1024] planar
        x = iq[0] + 1j*iq[1]
        cr.append(complex_rms(x)); sr.append(scalar_rms(iq))
    h5.close()
    cr = np.array(cr); sr = np.array(sr)
    print("RadioML QPSK snr30 (N=%d): complex RMS mean=%.5f std=%.5f  scalar RMS mean=%.5f std=%.5f"
          % (len(cr), cr.mean(), cr.std(), sr.mean(), sr.std()))

    # ---- real capture ----
    frames = load_real()
    rcr, rsr = [], []
    for fid, iq, x in frames:
        rcr.append(complex_rms(x)); rsr.append(scalar_rms(iq))
    rcr = np.array(rcr); rsr = np.array(rsr)
    print("Real capture (N=%d): complex RMS mean=%.5f std=%.5f  scalar RMS mean=%.5f std=%.5f"
          % (len(rcr), rcr.mean(), rcr.std(), rsr.mean(), rsr.std()))

    # ---- FP32 ONNX top-1 on both ----
    sess = ort.InferenceSession(ONNX, providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name
    def top1(iq):
        out = sess.run(None, {iname: iq.astype(np.float32)[None]})[0][0]
        return int(np.argmax(out)), out
    def hist(frames_rcr, kind):
        from collections import Counter
        c = Counter()
        for iq in frames_rcr:
            k, _ = top1(iq)
            c[LABEL_ORDER_24[k]] += 1
        return dict(c)

    # re-load radioML QPSK tensors for top1 (smaller N for speed)
    h5 = h5py.File(HDF5, "r"); X = h5["X"]
    rm_iq = []
    for k in sel_idx[:200]:
        raw = np.asarray(X[int(ti[k])], dtype=np.float64)
        rm_iq.append(raw.T)
    h5.close()
    print("RadioML QPSK snr30 FP32 top-1 (N=200):", hist(rm_iq, "rm"))
    real_iq = [f[1] for f in frames]
    print("Real capture FP32 top-1 (N=78):", hist(real_iq, "real"))

if __name__ == "__main__":
    main()
