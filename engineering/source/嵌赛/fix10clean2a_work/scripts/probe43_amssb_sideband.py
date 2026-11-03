"""Isolate measured AM-SSB sideband: remove DC carrier, measure audio spectrum.

Determines the audio waveform (freq content, harmonic structure) that the
clean generator should use.  Also sweeps candidate structures for recall.
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


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        for name in ["AM-SSB-WC", "AM-SSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:400]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            # remove DC (per-frame mean) to isolate the sideband
            dc = xr.mean(axis=1, keepdims=True)
            sb = xr - dc
            # sideband spectrum: no window (periodic-ish) to avoid Hann smear of DC
            S = np.mean(np.abs(np.fft.fft(sb, axis=1)) ** 2, axis=0)
            S = S[:N // 2]  # positive freqs only
            fbin = np.fft.fftfreq(N, 1 / FS)[:N // 2]
            S = S / (S[1] + 1e-12)  # normalize to bin 1 (195 Hz)
            print(f"\n=== {name} sideband spectrum (DC removed, bins 1..16) ===")
            for i in range(1, 17):
                print(f"  bin{i:2d} {fbin[i]:6.0f}Hz: {S[i]:.3f}")
            # sideband power vs carrier
            sb_pow = np.mean(np.abs(sb) ** 2)
            car_pow = np.mean(np.abs(dc) ** 2)
            print(f"  carrier_pow={car_pow:.4f} sideband_pow={sb_pow:.4f} "
                  f"sideband/carrier={np.sqrt(sb_pow/car_pow):.4f}")

    # candidate sweep
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

    def sawtooth(rng):
        ph = rng.uniform(0, 1)
        n = np.arange(N)
        return 2.0 * ((n / N + ph) % 1.0) - 1.0

    def sine(rng, f=195.0):
        ph = rng.uniform(0, 2 * np.pi)
        tt = np.arange(N) / FS
        return np.sqrt(2) * np.sin(2 * np.pi * f * tt + ph)

    def cand_ssb(audio_fn, m, target, base=6_000_000, nframes=500):
        fr = []
        for i in range(nframes):
            rng = np.random.default_rng(base + i)
            a = audio_fn(rng)
            z = a + 1j * c._hilbert(a)
            x = (1.0 + m * z) * np.exp(1j * c.CLEAN_PHASE)
            fr.append(c._scale_rms(x, c.TARGET_RMS[target]))
        fr = np.array(fr)
        rec, conf = recall(fr, ORDER.index(target))
        # sideband/carrier and inst freq
        dc = np.abs(fr.mean(axis=1)).mean()
        rms = np.sqrt(np.mean(np.abs(fr) ** 2))
        sb_car = np.sqrt(1 - (dc / rms) ** 2) / (dc / rms)
        phase = np.unwrap(np.angle(fr), axis=1)
        df = np.diff(phase, axis=1) / (2 * np.pi) * FS
        istd = float(df.std())
        return rec, conf, sb_car, istd

    print("\n=== AM-SSB candidate sweep (DC carrier + SSB) ===")
    print("measured: WC sideband/carrier=0.5 instF=32.7  SC=0.33 instF=32.8")
    for audio_name, audio_fn in [("sawtooth195", sawtooth), ("sine195", sine)]:
        for m in [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]:
            rw, _, sw, iw = cand_ssb(audio_fn, m, "AM-SSB-WC")
            print(f"  {audio_name} WC m={m:.2f}: rec={rw:.3f} sb/car={sw:.3f} instF={iw:.1f}")
        for m in [0.2, 0.25, 0.3, 0.4, 0.5]:
            rs, _, ss, iss = cand_ssb(audio_fn, m, "AM-SSB-SC")
            print(f"  {audio_name} SC m={m:.2f}: rec={rs:.3f} sb/car={ss:.3f} instF={iss:.1f}")


if __name__ == "__main__":
    main()
