"""Characterize measured AM-SSB: carrier location, sideband audio, inst-freq.

Goal: find the clean structure that matches BOTH recall (>=0.90) and the
domain inst_freq_std (~320 Hz) / bw99 (~1 bin).
"""
from __future__ import annotations

import os
import sys
from collections import Counter

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import h5py  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as c  # noqa: E402

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
sys.path.insert(0, MODEL_SRC)
from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402

MODEL_KWARGS = {"denoiser_channels": 24, "denoiser_blocks": 3,
                "feature_channels": (32, 48, 64, 96), "classifier_hidden": 128,
                "dropout": 0.15}
ORDER = c.LABEL_ORDER_24
N = c.SAMPLE_LENGTH
FS = c.SAMPLE_RATE_HZ
GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"


def inst_std(iq):
    phase = np.unwrap(np.angle(iq), axis=1)
    df = np.diff(phase, axis=1) / (2 * np.pi) * FS
    return float(df.std())


def main():
    # measured
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        tt = np.arange(N) / FS
        for name in ["AM-SSB-WC", "AM-SSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:200]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            print(f"\n=== measured {name} ===")
            print(f"  inst_freq_std = {inst_std(xr):.1f} Hz")
            # DC (mean) and spectrum
            mean_c = np.abs(xr.mean(axis=1)).mean()
            rms = np.sqrt(np.mean(np.abs(xr) ** 2))
            print(f"  |mean|={mean_c:.4f} rms={rms:.4f} |mean|/rms={mean_c/rms:.4f}")
            # spectrum: is there a carrier at nonzero freq?
            win = np.hanning(N)
            psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(xr * win, axis=1), axes=1)) ** 2, axis=0)
            freqs = np.fft.fftshift(np.fft.fftfreq(N))
            psd /= psd.sum() + 1e-12
            pos = freqs >= 0
            fp, pp = freqs[pos], psd[pos]
            peak_i = pp.argmax()
            print(f"  spectrum peak at f={fp[peak_i]:.5f} ({fp[peak_i]*FS:.0f} Hz), value {pp[peak_i]:.3e}")
            for bi in [0, 1, 2, 3, 5, 10, 20, 30]:
                print(f"    PSD[f={fp[bi]:.5f}={fp[bi]*FS:.0f}Hz] = {pp[bi]:.3e} ({10*np.log10(pp[bi]/pp.max()):.1f} dB)")
            # audio: demodulate assuming carrier at DC (rotate to real carrier)
            # envelope magnitude and phase deviation
            a_inst = np.diff(np.unwrap(np.angle(xr)), axis=1)
            print(f"  phase-inst std = {a_inst.std():.4f} rad/sample -> {a_inst.std()*FS/(2*np.pi):.1f} Hz")

    # clean candidates
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    def recall(fr, target):
        xi = np.ascontiguousarray(np.stack([fr.real, fr.imag], axis=1)).astype(np.float32)
        with torch.inference_mode():
            out, _ = model(torch.from_numpy(xi))
        pred = out.numpy().argmax(axis=1)
        rec = float((pred == target).mean())
        cnt = Counter(pred.tolist())
        conf = ", ".join(f"{ORDER[k]}={v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:2])
        return rec, conf

    def candidate(m, carrier, fmin=200.0, fmax=3000.0, base=5_000_000, nframes=500):
        fr = []
        for i in range(nframes):
            rng = np.random.default_rng(base + i)
            a = c._audio(rng, N, FS, fmax=fmax)
            z = a + 1j * c._hilbert(a)
            m_ = m
            x = (1.0 + m_ * z) * np.exp(1j * c.CLEAN_PHASE)
            fr.append(c._scale_rms(x, c.TARGET_RMS["AM-SSB-WC" if carrier else "AM-SSB-SC"]))
        fr = np.array(fr)
        istd = inst_std(fr)
        rec, conf = recall(fr, ORDER.index("AM-SSB-WC" if carrier else "AM-SSB-SC"))
        return istd, rec, conf

    print("\n=== clean candidates (DC carrier + SSB sideband) ===")
    for m in [0.06, 0.10, 0.14, 0.18]:
        for name, carrier in [("WC", True), ("SC", False)]:
            istd, rec, conf = candidate(m, carrier)
            print(f"  {name} m={m:.2f}: instF={istd:.1f}Hz  recall={rec:.3f}  conf={conf}")

    # try higher audio band (matches ~320Hz via higher freq content)
    print("\n=== clean with audio 200-4000 Hz ===")
    for m in [0.06, 0.09]:
        for name, carrier in [("WC", True), ("SC", False)]:
            istd, rec, conf = candidate(m, carrier, fmax=4000.0)
            print(f"  {name} m={m:.2f} audio4000: instF={istd:.1f}Hz  recall={rec:.3f}")


if __name__ == "__main__":
    main()
