# Metric definitions — fix10class24-ac-input-detailed-audit1
All units in **cycles/sample** (no sampling-rate mapping assumed; the
1024-point recovered tensor is NOT interpreted as 2.56 Msps).
A reference = TEST split, per class per SNR ∈ {0,10,20,30}, N=100/stratum,
seed=20261019 (never mixing SNR into one pooled mean).  C = real dual-SDR
wide-linear model-input tensors, snr_db=nan, diagnostic-gate-bypass.
The model-input contract is `X[row].T` -> [2,1024] (row0=real,row1=imag);
for feature analysis the same complex signal is loaded as
`I + jQ = X[:,0] + 1j*X[:,1]` (a layout transpose only, no DC/normalize).

## Amplitude / DC
- `rms`: sqrt(mean(|x|^2)) — total RMS (scaling).
- `ac_rms`: sqrt(mean(|x - mean(x)|^2)) — demeaned RMS (AC only).
- `dc`: |mean(x)| — complex-mean magnitude (DC level).
- `dc_i / dc_q`: real / imag of mean(x).
- `dc_power_frac`: |mean(x)|^2 / mean(|x|^2) — DC power fraction.
- `amp_q05/q25/q50/q75/q95`: quantiles of |x|.
- `papr_db`: 10*log10(max(|x|^2)/mean(|x|^2)).
- `amp_skew / amp_kurt`: 3rd standardized moment / excess kurtosis of |x|.

## I/Q joint structure
- `var_i / var_q / var_ratio`: var of real / imag; var_i/var_q (asymmetry).
- `cov_iq / corr_iq`: covariance / Pearson corr of (real, imag).
- `noncirc`: |E[x^2]| / E[|x|^2] — normalized pseudo-covariance.
- `pseudocov_mag / phase`: |E[x^2]| and arg(E[x^2]).
> I/Q asymmetry alone is NOT concluded as hardware IQ imbalance.

## Spectral (unified window=Hann, FFT n=4096, fftshift)
- `centroid`: sum(f * Pn) — spectral centroid (cycles/sample).
- `asym`: power(f>centroid) - power(f<centroid) — left/right asymmetry.
- `flatness`: exp(mean(log P))/mean P over P>0 bins; NO additive floor applied
  (SPECTRAL_FLOOR_REL = 1e-12 is a reserved numeric constant, NOT used).
- `bw99_cont`: **corrected 99% occupied bandwidth = full width of the smallest
  symmetric interval [centroid-b, centroid+b] containing 99% of power
  (CONTINUOUS interval, cycles/sample).**
- `bw99`: OLD bin-count 99% bandwidth (fraction of FFT bins by descending power
  cumsum) — kept SEPARATE, identical to threedomain audit_common.
- `bw20`: OLD bin-count 20 dB bandwidth (fraction of bins above peak/100).
- `peak_freq / peak_to_floor_db`: argmax P freq; peak vs outer-band median.

## Time / phase
- `acorr_lag1..32`: normalized complex-autocorrelation MAGNITUDE |sum conj(x[n]) x[n-k]| / sum |x[n]|^2 (abs of the COMPLEX lagged inner product, NOT abs of its real part).
- `acorr_half_lag`: first lag k where |acorr|<0.5.
- `phase_inc_mean/std`: adjacent-sample phase increment (linear mean/std).
- `phase_inc_circ_mean/std`: circular mean/std of phase increment.
- `amp_roc_mean/std/q90`: |Δ|x|| amplitude rate of change.
- `seg_power_mean/std/cv/minmax`: 8×128-sample segment RMS statistics.

**Phase low-amplitude rule (fixed before computing):** samples with
`|x| < 0.05*median(|x|)` are dropped from phase-increment statistics.

## C sample counts per class
| class | C tensors |
|---|---|
| OOK | 4 |
| 4ASK | 3 |
| 8ASK | 3 |
| BPSK | 4 |
| QPSK | INSUFFICIENT_DATA |
| 8PSK | INSUFFICIENT_DATA |
| 16PSK | 4 |
| 32PSK | 3 |
| 16APSK | 3 |
| 32APSK | 1 |
| 64APSK | 1 |
| 128APSK | 3 |
| 16QAM | 2 |
| 32QAM | 3 |
| 64QAM | 3 |
| 128QAM | 3 |
| 256QAM | 3 |
| AM-SSB-WC | 4 |
| AM-SSB-SC | 3 |
| AM-DSB-WC | 1 |
| AM-DSB-SC | 1 |
| FM | 2 |
| GMSK | 1 |
| OQPSK | 3 |
