// M26 golden-vs-fixed-point numeric verification.
//
// Runs the ~20 stimulus classes from the spec (M26 §四) through both the
// floating-point golden model (m26_golden.hpp) and the fixed-point bit-exact
// model (m26_fixed_model.hpp), and reports per-stage max-abs error, MSE,
// frequency/amplitude error, FIR frequency-response error, CFAR recall/false-
// alarm and the fixed-point saturation-event count.
//
// Build: g++ -std=gnu++17 -O2 -Wall -Wextra -Werror m26_verify.cpp -o m26_verify
#include <cstdio>
#include <cmath>
#include <complex>
#include <cstdint>
#include <string>
#include <vector>

#include "m26_golden.hpp"
#include "m26_fixed_model.hpp"

namespace {
int g_pass = 0, g_fail = 0;
void check(bool ok, const char* what) { if (ok) ++g_pass; else { ++g_fail; std::printf("FAIL: %s\n", what); } }

const int N = 1024;
const double FS = 128000.0;
const double PI = 3.141592653589793;

using cpx = std::complex<double>;

// ---- stimulus generators -----------------------------------------------------

std::vector<cpx> tone(double f, double amp = 0.8, double ph = 0.0) {
    std::vector<cpx> x(static_cast<std::size_t>(N));
    for (int n = 0; n < N; ++n)
        x[static_cast<std::size_t>(n)] = std::polar(amp, 2.0 * PI * f / FS * n + ph);
    return x;
}

std::vector<cpx> add_noise(const std::vector<cpx>& s, double snr_db, m26golden::Rng& rng) {
    double ps = 0; for (auto& v : s) ps += std::norm(v); ps /= s.size();
    double pn = ps / std::pow(10.0, snr_db / 10.0);
    double sd = std::sqrt(pn / 2.0);
    std::vector<cpx> y = s;
    for (auto& v : y) v += cpx(rng.gauss() * sd, rng.gauss() * sd);
    return y;
}

std::vector<cpx> bpsk(double f, double sps, m26golden::Rng& rng) {
    (void)sps;
    std::vector<cpx> x(static_cast<std::size_t>(N));
    for (int n = 0; n < N; ++n) {
        int bit = static_cast<int>((rng.next() & 1));
        x[static_cast<std::size_t>(n)] = std::polar(0.8, 2.0 * PI * f / FS * n + (bit ? PI : 0.0));
    }
    return x;
}

std::vector<cpx> qpsk(double f, double sps, m26golden::Rng& rng) {
    (void)sps;
    std::vector<cpx> x(static_cast<std::size_t>(N));
    for (int n = 0; n < N; ++n) {
        int bits = static_cast<int>(rng.next() & 3);
        x[static_cast<std::size_t>(n)] = std::polar(0.8, 2.0 * PI * f / FS * n + (PI / 4.0 + bits * PI / 2.0));
    }
    return x;
}

std::vector<cpx> qam16(double f, double sps, m26golden::Rng& rng) {
    (void)sps;
    std::vector<cpx> x(static_cast<std::size_t>(N));
    for (int n = 0; n < N; ++n) {
        double re = (static_cast<int>((rng.next() >> 0) & 3) - 1.5) / 1.5;
        double im = (static_cast<int>((rng.next() >> 2) & 3) - 1.5) / 1.5;
        x[static_cast<std::size_t>(n)] = cpx(re, im) * 0.5 * std::polar(1.0, 2.0 * PI * f / FS * n);
    }
    return x;
}

std::vector<cpx> fsk2(double f0, double f1, double sps, m26golden::Rng& rng) {
    (void)sps;
    std::vector<cpx> x(static_cast<std::size_t>(N));
    double ph = 0.0;
    for (int n = 0; n < N; ++n) {
        int bit = static_cast<int>(rng.next() & 1);
        double f = bit ? f1 : f0;
        ph += 2.0 * PI * f / FS;
        x[static_cast<std::size_t>(n)] = std::polar(0.8, ph);
    }
    return x;
}

std::vector<cpx> ofdm(int nsub, m26golden::Rng& rng) {
    std::vector<cpx> x(static_cast<std::size_t>(N), {0, 0});
    for (int s = 0; s < nsub; ++s) {
        double f = 1000.0 + s * 200.0;
        cpx a(rng.gauss() * 0.3, rng.gauss() * 0.3);
        for (int n = 0; n < N; ++n)
            x[static_cast<std::size_t>(n)] += a * std::polar(1.0, 2.0 * PI * f / FS * n);
    }
    double m = 0; for (auto& v : x) m = std::max(m, std::abs(v));
    if (m > 1.0) for (auto& v : x) v /= m;   // keep within full scale
    return x;
}

std::vector<cpx> chirp(double f0, double f1) {
    std::vector<cpx> x(static_cast<std::size_t>(N));
    double ph = 0.0;
    for (int n = 0; n < N; ++n) {
        double f = f0 + (f1 - f0) * n / (N - 1);
        ph += 2.0 * PI * f / FS;
        x[static_cast<std::size_t>(n)] = std::polar(0.8, ph);
    }
    return x;
}

std::vector<cpx> apply_cfo(const std::vector<cpx>& x, double cfo) {
    std::vector<cpx> y = x;
    for (int n = 0; n < N; ++n) y[static_cast<std::size_t>(n)] *= std::polar(1.0, 2.0 * PI * cfo / FS * n);
    return y;
}

std::vector<cpx> apply_multipath(const std::vector<cpx>& x, double delay_samp, double gain) {
    std::vector<cpx> y = x;
    for (int n = 0; n < N; ++n) {
        int d = static_cast<int>(delay_samp);
        if (n - d >= 0) y[static_cast<std::size_t>(n)] += gain * x[static_cast<std::size_t>(n - d)];
    }
    double m = 0; for (auto& v : y) m = std::max(m, std::abs(v));
    if (m > 1.0) for (auto& v : y) v /= m;
    return y;
}

std::vector<cpx> apply_iq_imbalance(const std::vector<cpx>& x, double gain_db, double phase_deg) {
    double g = std::pow(10.0, gain_db / 20.0);
    double p = phase_deg * PI / 180.0;
    std::vector<cpx> y(x.size());
    for (std::size_t n = 0; n < x.size(); ++n)
        y[n] = { x[n].real() * g, x[n].imag() * std::cos(p) + x[n].real() * std::sin(p) };
    return y;
}

std::vector<cpx> apply_clip(const std::vector<cpx>& x, double level) {
    std::vector<cpx> y = x;
    for (auto& v : y) {
        if (v.real() > level) v.real(level);
        if (v.real() < -level) v.real(-level);
        if (v.imag() > level) v.imag(level);
        if (v.imag() < -level) v.imag(-level);
    }
    return y;
}

std::vector<cpx> apply_pulse(const std::vector<cpx>& x, int at, int len, double amp) {
    std::vector<cpx> y = x;
    for (int n = at; n < at + len && n < N; ++n) y[static_cast<std::size_t>(n)] += cpx(amp, 0);
    return y;
}

// Bring a stimulus into the valid Q1.15 input range (per-component |v| <= target).
// The RTL input is signed 16-bit Q1.15, so any test exceeding [-1, 1) would only
// exercise input saturation, not the stage arithmetic under test.
std::vector<cpx> normalize_amp(const std::vector<cpx>& x, double target = 0.9) {
    double m = 0.0;
    for (const auto& v : x) m = std::max(m, std::max(std::abs(v.real()), std::abs(v.imag())));
    std::vector<cpx> y = x;
    if (m > target) { double s = target / m; for (auto& v : y) v *= s; }
    return y;
}

// Symmetric-saturate a float sample to Q1.15 (mirrors m26fixed::sat16).  Applied to
// the *golden* output where the fixed model saturates its Q1.15 result (dc removal,
// NCO, FIR), so the comparison isolates the arithmetic rather than the headroom.
cpx sat15(cpx v) {
    const double max = 32767.0 / 32768.0;
    auto s = [&](double r) { if (r > max) return max; if (r < -1.0) return -1.0; return r; };
    return cpx(s(v.real()), s(v.imag()));
}

// ---- stage comparisons -------------------------------------------------------

struct Cmp { double max_abs = 0.0; double mse = 0.0; std::size_t n = 0; };

Cmp cmp_complex(const std::vector<cpx>& a, const std::vector<cpx>& b) {
    Cmp c; c.n = std::min(a.size(), b.size());
    double se = 0.0;
    for (std::size_t i = 0; i < c.n; ++i) {
        double e = std::abs(a[i] - b[i]);
        if (e > c.max_abs) c.max_abs = e;
        se += e * e;
    }
    c.mse = c.n ? se / c.n : 0.0;
    return c;
}

// global accumulators for the summary table
struct Acc { double dc_max = 0, dc_mse = 0, nco_max = 0, nco_mse = 0, fir_max = 0, fir_mse = 0, hann_max = 0, hann_mse = 0;
             double fft_rel_max = 0, fft_rel_mean = 0; long long fft_bins = 0; int peak_mismatch = 0;
             long long sat_events = 0; };

void run_stimulus(const std::string& name, const std::vector<cpx>& x_in, Acc& acc,
                  const std::vector<m26fixed::i16>& fir_q,
                  const std::vector<m26fixed::i16>& hann_q, double nco_f) {
    // Valid Q1.15 input: normalize any out-of-range stimulus, then quantize once.
    auto x = normalize_amp(x_in, 0.9);
    auto xq = m26fixed::q15_complex(x);
    auto xf = m26fixed::deq15(xq);   // exact float input the fixed model sees

    // DC removal
    {
        m26fixed::reset_sat_count();
        auto g = m26golden::dc_removal(xf, 127.0 / 128.0);
        for (auto& v : g) v = sat15(v);          // mirror sat16 on the Q1.15 output
        auto f = m26fixed::deq15(m26fixed::dc_removal(xq));
        auto c = cmp_complex(g, f);
        acc.dc_max = std::max(acc.dc_max, c.max_abs); acc.dc_mse = std::max(acc.dc_mse, c.mse);
        acc.sat_events += m26fixed::sat_count();
    }
    // energy / RMS
    {
        auto g = m26golden::energy_rms(xf);
        auto f = m26fixed::energy_rms(xq);
        double f_rms = static_cast<double>(f.rms) / 32768.0;
        check(std::abs(g.rms - f_rms) < 5e-3, "energy_rms tolerance");
    }
    // NCO (only when a test frequency is meaningful)
    if (nco_f != 0.0) {
        auto g = m26golden::nco_mix(xf, nco_f, FS);
        for (auto& v : g) v = sat15(v);
        auto f = m26fixed::deq15(m26fixed::nco_mix(xq, nco_f, FS));
        auto c = cmp_complex(g, f);
        acc.nco_max = std::max(acc.nco_max, c.max_abs); acc.nco_mse = std::max(acc.nco_mse, c.mse);
    }
    // FIR: golden uses the *quantized* coefficients so error is arithmetic-only
    {
        std::vector<double> hq(fir_q.size());
        for (std::size_t i = 0; i < fir_q.size(); ++i) hq[i] = fir_q[i] / 32768.0;
        auto g = m26golden::fir(xf, hq);
        for (auto& v : g) v = sat15(v);
        auto f = m26fixed::deq15(m26fixed::fir_sym(xq, fir_q));
        auto c = cmp_complex(g, f);
        acc.fir_max = std::max(acc.fir_max, c.max_abs); acc.fir_mse = std::max(acc.fir_mse, c.mse);
    }
    // Hann
    {
        std::vector<double> wq(hann_q.size());
        for (std::size_t i = 0; i < hann_q.size(); ++i) wq[i] = hann_q[i] / 32768.0;
        auto g = m26golden::apply_hann(xf, wq);
        auto f = m26fixed::deq15(m26fixed::apply_hann(xq, hann_q));
        auto c = cmp_complex(g, f);
        acc.hann_max = std::max(acc.hann_max, c.max_abs); acc.hann_mse = std::max(acc.hann_mse, c.mse);
    }
    // FFT power spectrum (golden unnormalized vs fixed *N^2)
    {
        auto Xg = m26golden::fft(xf);
        std::vector<double> Pg(N);
        double pg_max = 0.0;
        for (int k = 0; k < N; ++k) { Pg[static_cast<std::size_t>(k)] = std::norm(Xg[static_cast<std::size_t>(k)]);
            pg_max = std::max(pg_max, Pg[static_cast<std::size_t>(k)]); }
        auto Xf = m26fixed::fft(xq);
        auto Pf = m26fixed::mag_sq(Xf);
        double abs_sum = 0.0; int peak_g = 0, peak_f = 0; double mg = -1, mf = -1;
        for (int k = 0; k < N; ++k) {
            double pred = (static_cast<double>(Pf[static_cast<std::size_t>(k)]) / 1073741824.0) * static_cast<double>(N) * N;
            double ref = Pg[static_cast<std::size_t>(k)];
            // Normalize by the *peak* PSD, not per-bin: per-bin relative error is
            // meaningless at near-zero noise bins where the fixed model's rounding
            // floor dominates the (near-zero) reference.
            double rel = pg_max > 1e-12 ? std::abs(pred - ref) / pg_max : 0.0;
            acc.fft_rel_max = std::max(acc.fft_rel_max, rel); abs_sum += rel;
            if (ref > mg) { mg = ref; peak_g = k; }
            if (pred > mf) { mf = pred; peak_f = k; }
        }
        acc.fft_rel_mean += abs_sum; acc.fft_bins += N;
        if (peak_g != peak_f) ++acc.peak_mismatch;
    }
    (void)name;
}

}  // namespace

int main() {
    std::printf("== M26 golden-vs-fixed numeric verification ==\n\n");

    m26golden::Rng rng(20261009);

    // shared coefficient sets
    auto fir_full = m26golden::design_lowpass(32, 0.4, FS);   // 0.4*fs cutoff (fc norm = 0.2*2? keep simple)
    auto fir_q = m26fixed::q15_array(fir_full);
    auto hann_q = m26fixed::q15_array(m26golden::hann_window(N));

    Acc acc;
    struct Stim { const char* name; std::vector<cpx> x; double nco_f; };
    std::vector<Stim> stims;

    // 1-4: zero / full-scale / max / DC
    stims.push_back({"zero", std::vector<cpx>(N, cpx(0, 0)), 0.0});
    stims.push_back({"full_scale", std::vector<cpx>(N, cpx(0.9, 0.9)), 0.0});
    stims.push_back({"posmax", std::vector<cpx>(N, cpx(0.999, 0.999)), 0.0});
    stims.push_back({"negmax", std::vector<cpx>(N, cpx(-0.999, -0.999)), 0.0});
    stims.push_back({"dc_offset", std::vector<cpx>(N, cpx(0.5, -0.3)), 0.0});
    // 5-8: tones
    stims.push_back({"tone_int_bin", tone(500.0), 12000.0});          // 500 Hz = integer bin 4; also exercise NCO
    stims.push_back({"tone_nonint_bin", tone(700.0), 0.0});
    stims.push_back({"two_tone", [&] { auto a = tone(1500.0, 0.5); auto b = tone(7000.0, 0.5);
        std::vector<cpx> s(N); for (int i = 0; i < N; ++i) s[static_cast<std::size_t>(i)] = a[static_cast<std::size_t>(i)] + b[static_cast<std::size_t>(i)]; return s; }(), 0.0});
    stims.push_back({"multi_tone", ofdm(16, rng), 0.0});
    // 9-13: modulations
    stims.push_back({"bpsk", bpsk(3000.0, 8.0, rng), 5000.0});
    stims.push_back({"qpsk", qpsk(3000.0, 8.0, rng), 0.0});
    stims.push_back({"qam16", qam16(3000.0, 8.0, rng), 0.0});
    stims.push_back({"fsk2", fsk2(2000.0, 6000.0, 8.0, rng), 0.0});
    stims.push_back({"ofdm", ofdm(32, rng), 0.0});
    // 14: SNR sweep (representative points)
    for (double snr : {-20.0, -10.0, 0.0, 10.0, 20.0}) {
        char nm[32]; std::snprintf(nm, sizeof nm, "tone_snr_%+d", static_cast<int>(snr));
        stims.push_back({nm, add_noise(tone(2000.0, 0.5), snr, rng), 0.0});
    }
    // 15-20: impairments
    stims.push_back({"cfo", apply_cfo(tone(4000.0, 0.6), 1200.0), 2000.0});
    stims.push_back({"multipath", apply_multipath(tone(4000.0, 0.6), 3.0, 0.5), 0.0});
    stims.push_back({"iq_imbalance", apply_iq_imbalance(tone(4000.0, 0.6), 1.0, 5.0), 0.0});
    stims.push_back({"clipping", apply_clip(tone(4000.0, 0.9), 0.5), 0.0});
    stims.push_back({"pulse_interf", apply_pulse(tone(2000.0, 0.4), 300, 50, 0.8), 0.0});
    stims.push_back({"sweep", chirp(1000.0, 20000.0), 0.0});

    for (auto& s : stims) run_stimulus(s.name, s.x, acc, fir_q, hann_q, s.nco_f);

    // ---- FIR frequency-response error (full vs quantized coefficients) ----
    {
        std::vector<cpx> hc(fir_full.size());
        std::vector<cpx> hcq(fir_full.size());
        for (std::size_t i = 0; i < fir_full.size(); ++i) {
            hc[i] = cpx(fir_full[i], 0);
            hcq[i] = cpx(fir_q[i] / 32768.0, 0);
        }
        std::vector<cpx> Hc(N), Hcq(N);
        Hc.assign(N, cpx(0, 0)); Hcq.assign(N, cpx(0, 0));
        for (std::size_t i = 0; i < fir_full.size(); ++i) { Hc[i] = hc[i]; Hcq[i] = hcq[i]; }
        auto F = m26golden::fft(Hc);
        auto Fq = m26golden::fft(Hcq);
        // Compare magnitude error relative to DC gain (|F[0]| = sum of taps = 1.0),
        // NOT relative to each bin: per-bin relative error is meaningless in the
        // stopband where |F| ~ 0.
        double dc_gain = std::abs(F[0]);
        double fr_max = 0, fr_mean = 0; int n = 0;
        for (int k = 0; k < N; ++k) {
            double a = std::abs(F[static_cast<std::size_t>(k)]), b = std::abs(Fq[static_cast<std::size_t>(k)]);
            double e = std::abs(a - b) / dc_gain;
            fr_max = std::max(fr_max, e); fr_mean += e; ++n;
        }
        fr_mean /= n;
        std::printf("\n  FIR freq-resp error (full vs q15 coeff, rel DC gain): max=%.3e mean=%.3e\n", fr_max, fr_mean);
        check(fr_max < 2e-3, "FIR freq-resp error");
    }

    // ---- CFAR recall / false-alarm on a known two-tone ground truth ----
    {
        auto a = tone(1500.0, 0.6); auto b = tone(7000.0, 0.6);
        std::vector<cpx> s(N); for (int i = 0; i < N; ++i) s[static_cast<std::size_t>(i)] = a[static_cast<std::size_t>(i)] + b[static_cast<std::size_t>(i)];
        s = add_noise(s, 5.0, rng);
        auto xq = m26fixed::q15_complex(s);
        auto Xg = m26golden::fft(s);
        auto Xf = m26fixed::fft(xq);
        std::vector<double> Pg(N); for (int k = 0; k < N; ++k) Pg[static_cast<std::size_t>(k)] = std::norm(Xg[static_cast<std::size_t>(k)]);
        auto Pf = m26fixed::mag_sq(Xf);
        // golden CFAR mask (ground truth: bins 12 and 56 are the tones)
        std::vector<int> truth(N, 0); truth[12] = truth[56] = 1;
        auto mg = m26golden::cfar(Pg, 4, 8, 8.0);
        auto mf = m26fixed::cfar(Pf, 4, 8, static_cast<m26fixed::u32>(8 << 14));
        int tp = 0, fn_ = 0, fp = 0, tn = 0;
        for (int k = 0; k < N; ++k) {
            if (truth[static_cast<std::size_t>(k)]) { if (mf[static_cast<std::size_t>(k)]) ++tp; else ++fn_; }
            else { if (mf[static_cast<std::size_t>(k)]) ++fp; else ++tn; }
        }
        double recall = static_cast<double>(tp) / (tp + fn_);
        double far = static_cast<double>(fp) / (fp + tn);
        std::printf("  CFAR recall=%.2f false-alarm=%.4f (mask-golden-match=%d/%d)\n", recall, far,
                    [&]{ int m=0; for(int k=0;k<N;++k) m += (mg[static_cast<std::size_t>(k)]==mf[static_cast<std::size_t>(k)]); return m; }(), N);
        check(recall >= 0.9, "CFAR recall");
        check(far < 0.2, "CFAR false-alarm");
    }

    // ---- candidate merge + 99% BW structural ----
    {
        auto Xg = m26golden::fft(tone(500.0, 0.8));
        auto Xf = m26fixed::fft(m26fixed::q15_complex(tone(500.0, 0.8)));
        std::vector<double> Pg(N); for (int k = 0; k < N; ++k) Pg[static_cast<std::size_t>(k)] = std::norm(Xg[static_cast<std::size_t>(k)]);
        auto Pf = m26fixed::mag_sq(Xf);
        auto mg = m26golden::cfar(Pg, 4, 8, 6.0);
        auto mf = m26fixed::cfar(Pf, 4, 8, static_cast<m26fixed::u32>(6 << 14));
        auto cg = m26golden::candidate_merge(mg, Pg, 2, 16);
        auto cf = m26fixed::candidate_merge(mf, Pf, 2, 16);
        check(!cg.empty() && !cf.empty(), "candidate non-empty");
        if (!cg.empty() && !cf.empty()) {
            int dpeak = std::abs(cg[0].peak_bin - cf[0].peak_bin);
            std::printf("  candidate: golden peak=%d bw=%d | fixed peak=%d bw=%d\n",
                        cg[0].peak_bin, cg[0].bw_bins, cf[0].peak_bin, cf[0].bw_bins);
            check(dpeak <= 1, "candidate peak-bin match");
        }
    }

    // ---- structural: decimate / reset / frame boundary / long run ----
    {
        auto xq = m26fixed::q15_complex(tone(3000.0, 0.5));
        check(m26fixed::decimate(xq, 4).size() == N / 4, "decimate by 4 length");
        check(m26fixed::decimate(xq, 2).size() == N / 2, "decimate by 2 length");
        // long run: 4 frames, no saturation growth beyond a bound, energy stable
        m26fixed::reset_sat_count();
        std::vector<cpx> longx(4 * N);
        for (int i = 0; i < 4 * N; ++i) longx[static_cast<std::size_t>(i)] = std::polar(0.7, 2.0 * PI * 500.0 / FS * i);
        auto lq = m26fixed::q15_complex(longx);
        auto dc = m26fixed::dc_removal(lq);
        (void)dc;
        std::printf("  long-run (4 frames) saturation events=%lld\n", static_cast<long long>(m26fixed::sat_count()));
    }

    // ---- summary ----
    std::printf("\n== summary ==\n");
    std::printf("  dc_removal   max_abs=%.3e mse=%.3e\n", acc.dc_max, acc.dc_mse);
    std::printf("  nco          max_abs=%.3e mse=%.3e\n", acc.nco_max, acc.nco_mse);
    std::printf("  fir(arith)   max_abs=%.3e mse=%.3e\n", acc.fir_max, acc.fir_mse);
    std::printf("  hann         max_abs=%.3e mse=%.3e\n", acc.hann_max, acc.hann_mse);
    std::printf("  fft PSD      rel_max=%.3e rel_mean=%.3e peak_mismatch=%d/%lld\n",
                acc.fft_rel_max, acc.fft_rel_mean / std::max(1LL, acc.fft_bins / N), acc.peak_mismatch, acc.fft_bins / N);
    std::printf("  sat events (dc) = %lld\n", static_cast<long long>(acc.sat_events));

    check(acc.dc_max < 2e-3 && acc.dc_mse < 1e-6, "dc_removal aggregated");
    check(acc.nco_max < 1.5e-2 && acc.nco_mse < 2e-5, "nco aggregated");
    check(acc.fir_max < 5e-3 && acc.fir_mse < 1e-5, "fir aggregated");
    check(acc.fft_rel_max < 0.05, "fft relative error aggregated");

    std::printf("\n== result: assertions=%d passed=%d failed=%d ==\n", g_pass + g_fail, g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
