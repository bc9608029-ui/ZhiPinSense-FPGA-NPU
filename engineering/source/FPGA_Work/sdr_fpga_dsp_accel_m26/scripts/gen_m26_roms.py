#!/usr/bin/env python3
"""Generate the M26 ROM initialization files (quarter-wave sin LUT + FIR taps).

Mirrors the C++ golden/fixed models exactly:
  * m26_sin_lut.mem    : lut[j] = q15(sin(j*pi/512)), j=0..255      (m26fixed::build_sin_lut)
  * m26_fir_coeff.mem  : q15 of design_lowpass(32, 0.4, fs)          (m26golden::design_lowpass)
  * m26_hann.mem       : q15 of hann_window(1024)                    (m26golden::hann_window)
  * m26_twiddle.mem    : q15 of build_twiddle(1024), 32-bit/line
                         {im[15:0], re[15:0]} = exp(-j 2pi m/N)      (m26fixed::build_twiddle)

q15 = round-half-away-from-zero to 16-bit, symmetric saturation to [-32768, 32767].
Deterministic; re-running produces byte-identical files.
"""
import math

FS = 128000.0
N_FFT = 1024
PI = math.pi


def q15(x: float) -> int:
    r = math.floor(x * 32768.0 + 0.5) if x >= 0 else math.ceil(x * 32768.0 - 0.5)
    if r > 32767:
        return 32767
    if r < -32768:
        return -32768
    return int(r)


def design_lowpass(taps: int, cutoff_norm: float) -> list[float]:
    h = []
    M = taps - 1
    fc = cutoff_norm
    for i in range(taps):
        n = i - M / 2.0
        hamm = 0.54 - 0.46 * math.cos(2.0 * PI * i / M)
        sinc = 2.0 * fc if n == 0.0 else math.sin(2.0 * PI * fc * n) / (PI * n)
        h.append(sinc * hamm)
    s = sum(h)
    if s != 0.0:
        h = [v / s for v in h]
    return h


def hex16(v: int) -> str:
    return "%04X" % (v & 0xFFFF)


def hex32(re_v: int, im_v: int) -> str:
    return "%08X" % (((im_v & 0xFFFF) << 16) | (re_v & 0xFFFF))


def main() -> None:
    # quarter-wave sin LUT
    lut = [q15(math.sin(j * PI / 512.0)) for j in range(256)]
    with open("rtl/m26_sin_lut.mem", "w") as f:
        f.write("\n".join(hex16(v) for v in lut) + "\n")

    # FIR taps (32-tap symmetric lowpass, DC gain 1)
    taps = [q15(v) for v in design_lowpass(32, 0.4)]
    with open("rtl/m26_fir_coeff.mem", "w") as f:
        f.write("\n".join(hex16(v) for v in taps) + "\n")

    # periodic Hann window, N=1024
    hann = [q15(0.5 - 0.5 * math.cos(2.0 * PI * n / N_FFT)) for n in range(N_FFT)]
    with open("rtl/m26_hann.mem", "w") as f:
        f.write("\n".join(hex16(v) for v in hann) + "\n")

    # FFT twiddle factors exp(-j 2pi m/N), {im, re}
    tw_re = [q15(math.cos(-2.0 * PI * m / N_FFT)) for m in range(N_FFT)]
    tw_im = [q15(math.sin(-2.0 * PI * m / N_FFT)) for m in range(N_FFT)]
    with open("rtl/m26_twiddle.mem", "w") as f:
        f.write("\n".join(hex32(tw_re[m], tw_im[m]) for m in range(N_FFT)) + "\n")

    print("sin lut[0]=%s lut[255]=%s" % (hex16(lut[0]), hex16(lut[255])))
    print("fir taps[15]=%s taps[16]=%s (32 taps, DC sum=%.6f)"
          % (hex16(taps[15]), hex16(taps[16]), sum(taps) / 32768.0))
    print("hann[0]=%s hann[512]=%s hann[1023]=%s"
          % (hex16(hann[0]), hex16(hann[512]), hex16(hann[1023])))
    print("tw[0]={im=%s,re=%s} tw[256]={im=%s,re=%s}"
          % (hex16(tw_im[0]), hex16(tw_re[0]), hex16(tw_im[256]), hex16(tw_re[256])))


if __name__ == "__main__":
    main()
