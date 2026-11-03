// test_m24_a.cpp -- M24-A P1 model-independent offline module tests.
//
// Exercises the six isolated modules (FFT / waterfall / UI scheduler / patrol
// state machine / event recorder / 24-class stub) and reports ACTUAL numeric
// error, cache capacity and refresh statistics -- never a bare PASS.
//
// Frequency-error reporting convention: error is reported BOTH in Hz and as a
// fraction of the FFT bin width (bin_width = fs/n).  The peak-bin estimator used
// here is a NEAREST-BIN estimator, so its resolution limit is +-0.5 bin
// (+- fs/(2n) Hz) for a single isolated tone -- it does NOT claim 0 Hz universal
// accuracy.  Two-tone RESOLUTION is further limited by the window main-lobe
// width (Hann: ~4 bins).
//
// Performance is NOT measured here; use host_tools/m24_bench.cpp for the unified
// benchmark (pure FFT / FFT+window / full pipeline, fixed length+frames+flags).
//
// Build: host_tests/build_m24_a.sh   Run: host_tests/run_m24_a.sh

#include "../sdr_adapter/m24_class24_contract.hpp"
#include "../sdr_adapter/m24_class24_stub.hpp"
#include "../sdr_adapter/m24_event.hpp"
#include "../sdr_adapter/m24_fft.hpp"
#include "../sdr_adapter/m24_patrol.hpp"
#include "../sdr_adapter/m24_ui_scheduler.hpp"
#include "../sdr_adapter/m24_waterfall.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iterator>
#include <limits>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("FAIL: %s\n", what);
    }
}

constexpr double PI = 3.141592653589793238462643383279502884;
constexpr double kFs = 128000.0;
constexpr std::size_t kN = 1024;

// Complex tone x[k] = A * exp(j*2*pi*f0*k/fs).
std::vector<std::complex<double>> tone(std::size_t n, double fs, double f0,
                                       double amp) {
    std::vector<std::complex<double>> x(n);
    for (std::size_t k = 0; k < n; ++k) {
        const double ph = 2.0 * PI * f0 / fs * static_cast<double>(k);
        x[k] = std::complex<double>(amp * std::cos(ph), amp * std::sin(ph));
    }
    return x;
}

std::vector<double> to_db(const std::vector<std::complex<double>>& bins) {
    std::vector<double> db(bins.size());
    for (std::size_t k = 0; k < bins.size(); ++k)
        db[k] = m24::db_from_linear(std::abs(bins[k]), 1.0);
    return db;
}

// Index of the largest-magnitude bin.
std::size_t argmax_abs(const std::vector<std::complex<double>>& bins) {
    std::size_t idx = 0;
    double best = -1.0;
    for (std::size_t k = 0; k < bins.size(); ++k) {
        const double v = std::abs(bins[k]);
        if (v > best) {
            best = v;
            idx = k;
        }
    }
    return idx;
}

// Bin width in Hz for an n-point FFT at sample rate fs.
double bin_hz(std::size_t n, double fs) { return fs / static_cast<double>(n); }

}  // namespace

int main() {
    std::printf("== M24-A P1 offline module tests ==\n");

    // ---- 1. FFT single-tone frequency error (bin-aligned) ------------------
    {
        const double f0 = 16000.0;  // bin 128
        const double amp = 1000.0;
        const auto x = tone(kN, kFs, f0, amp);
        const m24::Spectrum s = m24::fft(x.data(), kN);
        check(s.valid, "1: fft valid");
        const std::size_t peak = argmax_abs(s.bins);
        const double est_freq = m24::freq_axis_hz(kN, kFs, false)[peak];
        const double err = est_freq - f0;
        const double err_bins = err / bin_hz(kN, kFs);
        std::printf("  1. FFT tone: truth=%.1f Hz est=%.3f Hz err=%+.6f Hz = %+.6f bin\n",
                    f0, est_freq, err, err_bins);
        check(std::fabs(err_bins) <= 0.001, "1: bin-aligned tone err ~ 0 bin");
        const double est_amp = std::abs(s.bins[peak]) / kN;
        std::printf("  1b. amplitude: truth=%.1f est=%.3f err=%+.3f (tol=1)\n", amp,
                    est_amp, est_amp - amp);
        check(std::fabs(est_amp - amp) <= 1.0, "1b: peak amplitude == A");
    }

    // ---- 1c. off-bin single tones (0.25 / 0.37 / 0.49 bin) -----------------
    // Nearest-bin estimator: reported freq = round(true_bin) * bin_width, so the
    // error is <= +-0.5 bin.  This is the honest resolution limit (NOT 0 Hz).
    {
        const double offsets[3] = {0.25, 0.37, 0.49};
        const std::size_t base_bin = 128;
        for (double off : offsets) {
            const double f0 = (static_cast<double>(base_bin) + off) * bin_hz(kN, kFs);
            const auto x = tone(kN, kFs, f0, 1000.0);
            const m24::Spectrum s = m24::fft(x.data(), kN);
            const std::size_t peak = argmax_abs(s.bins);
            const double est = m24::freq_axis_hz(kN, kFs, false)[peak];
            const double err_bins = (est - f0) / bin_hz(kN, kFs);
            std::printf("  1c. off-bin +%.2f bin: true=%.3f Hz est=%.3f Hz err=%+.4f bin\n",
                        off, f0, est, err_bins);
            check(std::fabs(err_bins) <= 0.5, "1c: off-bin error within +-0.5 bin");
        }
        std::printf("  1c. resolution limit (nearest-bin) = +-0.5 bin = +-%.2f Hz\n",
                    bin_hz(kN, kFs) / 2.0);
    }

    // ---- 1d. Hann window amplitude correction ------------------------------
    // Periodic Hann coherent gain = n/2.  For a bin-aligned tone, windowed
    // |X_w[m]| = A*n/2, so amplitude recovery is A = 2*|X_w[m]|/n.
    {
        const double A = 1000.0;
        const double f0 = 16000.0;  // bin 128
        auto x = tone(kN, kFs, f0, A);
        const auto w = m24::hann_window(kN);
        m24::apply_window(x, w);
        const m24::Spectrum s = m24::fft(x.data(), kN);
        const std::size_t peak = argmax_abs(s.bins);
        const double raw = std::abs(s.bins[peak]);
        const double est = 2.0 * raw / kN;  // coherent-gain correction (factor 2)
        std::printf("  1d. Hann: raw |X_w| = %.1f (expect A*n/2 = %.1f), "
                    "corrected A = %.3f (truth %.1f)\n",
                    raw, A * kN / 2.0, est, A);
        check(std::fabs(raw - A * kN / 2.0) <= 1.0, "1d: Hann coherent gain == n/2");
        check(std::fabs(est - A) <= 0.001, "1d: Hann amplitude correction (x2/n)");
    }

    // ---- 2. two-tone resolution (bin-aligned, 8 bins apart) -----------------
    {
        const double f1 = 10000.0, f2 = 11000.0;  // 8 bins apart
        auto x = tone(kN, kFs, f1, 1000.0);
        const auto y = tone(kN, kFs, f2, 1000.0);
        for (std::size_t k = 0; k < kN; ++k) x[k] += y[k];
        const m24::Spectrum s = m24::fft(x.data(), kN);
        const auto db = to_db(s.bins);
        const auto peaks = m24::detect_peaks(db, kFs, 100.0, 2);
        std::printf("  2. two-tone (8 bin sep): detected %zu peaks\n", peaks.size());
        for (const auto& p : peaks)
            std::printf("     peak bin=%zu freq=%.1f dB=%.1f\n", p.bin, p.freq_hz,
                        p.value_db);
        check(peaks.size() == 2, "2: two peaks detected at 8-bin separation");
        if (peaks.size() == 2) {
            const double df = std::fabs(peaks[0].freq_hz - peaks[1].freq_hz);
            std::printf("  2b. peak separation: truth=1000 Hz est=%.1f Hz\n", df);
            check(std::fabs(df - 1000.0) <= 125.0, "2b: two-tone separation");
        }
    }

    // ---- 2c. two-tone resolution at 1 / 2 / 4 bin separation (Hann) ---------
    // Unequal-amplitude two-tone (A1=1000, A2=700), Hann window (main lobe ~4
    // bins wide).  A tone counts as RESOLVED only when a detected peak lies
    // within +-0.5 bin of its true frequency.  The peak threshold is 40 dB above
    // the (median) noise floor: in this noiseless synthetic case the "floor" is
    // the double-precision FFT leakage (~-173..-232 dB vs signal 105..114 dB),
    // so 40 dB cleanly separates real peaks from numerical leakage.
    {
        const double A1 = 1000.0, A2 = 700.0;
        for (int sep : {1, 2, 4}) {
            const double f1 = 10000.0;  // bin 80
            const double f2 = f1 + sep * bin_hz(kN, kFs);
            auto x = tone(kN, kFs, f1, A1);
            const auto y = tone(kN, kFs, f2, A2);
            for (std::size_t k = 0; k < kN; ++k) x[k] += y[k];
            const auto w = m24::hann_window(kN);
            m24::apply_window(x, w);
            const m24::Spectrum s = m24::fft(x.data(), kN);
            const auto peaks = m24::detect_peaks(to_db(s.bins), kFs, 40.0, 2);
            const auto near = [&](double f) {
                for (const auto& p : peaks)
                    if (std::fabs(p.freq_hz - f) <= 0.5 * bin_hz(kN, kFs)) return true;
                return false;
            };
            const bool r1 = near(f1), r2 = near(f2);
            std::printf("  2c. two-tone %d-bin sep (Hann): %zu peak(s); "
                        "f1=%.0fHz resolved=%d, f2=%.0fHz resolved=%d\n",
                        sep, peaks.size(), f1, r1 ? 1 : 0, f2, r2 ? 1 : 0);
            check(r1, "2c: stronger tone always resolved");
            if (sep == 4) {
                check(r2, "2c: 4-bin sep resolves both tones");
            } else {
                check(!r2, "2c: <=2-bin sep does not resolve weaker tone");
            }
        }
        std::printf("  2c. resolution limit: Hann main-lobe ~4 bins -> two tones resolve\n"
                    "      only at >=4-bin sep; single-tone nearest-bin = +-0.5 bin.\n");
    }

    // ---- 2d. different amplitudes and different FFT lengths ----------------
    {
        for (double A : {1.0, 10.0, 1000.0}) {
            const auto x = tone(kN, kFs, 16000.0, A);
            const m24::Spectrum s = m24::fft(x.data(), kN);
            const std::size_t peak = argmax_abs(s.bins);
            const double est = std::abs(s.bins[peak]) / kN;
            std::printf("  2d. amp=%.0f -> |X|/n = %.3f (err %+.3f)\n", A, est, est - A);
            check(std::fabs(est - A) <= A * 1e-6, "2d: amplitude linearity");
        }
        for (std::size_t n : {256u, 512u, 1024u, 2048u}) {
            const std::size_t expect_bin = n / 8;
            const auto x = tone(n, kFs, 16000.0, 1000.0);
            const m24::Spectrum s = m24::fft(x.data(), n);
            check(s.valid, "2d: fft valid at this length");
            const std::size_t peak = argmax_abs(s.bins);
            const double est = std::abs(s.bins[peak]) / static_cast<double>(n);
            std::printf("  2d. n=%zu: peak bin=%zu (expect %zu), |X|/n=%.3f\n", n, peak,
                        expect_bin, est);
            check(peak == expect_bin, "2d: peak bin scales with n");
            check(std::fabs(est - 1000.0) <= 1.0, "2d: |X|==A*n across lengths");
        }
    }

    // ---- 3. amplitude / dB conversion --------------------------------------
    {
        check(std::fabs(m24::db_from_linear(1.0, 1.0)) < 1e-9, "3: db(1)==0");
        check(std::fabs(m24::db_from_linear(10.0, 1.0) - 20.0) < 1e-9, "3: db(10)==20");
        check(std::fabs(m24::db_from_power(2.0, 1.0) - 3.010299956) < 1e-6, "3: db(2x power)");
        const double dbfs = m24::db_from_linear(1000.0, 2048.0);
        const double expected_dbfs = 20.0 * std::log10(1000.0 / 2048.0);
        std::printf("  3. dBFS(amp 1000/2048) = %.4f (truth %.4f)\n", dbfs,
                    expected_dbfs);
        check(std::fabs(dbfs - expected_dbfs) <= 0.001, "3: dBFS conversion");
        check(m24::db_from_linear(0.0, 1.0) == -300.0, "3: db(0) fail-closed");
        check(m24::db_from_power(-1.0, 1.0) == -300.0, "3: db(neg) fail-closed");
    }

    // ---- 4. window function ------------------------------------------------
    {
        const auto w = m24::hann_window(kN);
        double sum = 0.0, maxw = 0.0;
        for (double v : w) {
            sum += v;
            if (v > maxw) maxw = v;
        }
        std::printf("  4. Hann: w[0]=%.6f w[%zu/2]=%.6f sum=%.3f max=%.3f\n", w[0],
                    kN, w[kN / 2], sum, maxw);
        check(std::fabs(w[0]) < 1e-9, "4: Hann w[0]==0");
        check(std::fabs(w[kN / 2] - 1.0) < 1e-9, "4: Hann peak==1");
        check(std::fabs(sum - kN / 2.0) < 1e-3, "4: Hann sum==n/2");
    }

    // ---- 5. fftshift -------------------------------------------------------
    {
        std::vector<double> v(kN, 0.0);
        v[0] = 1.0;  // DC impulse at bin 0
        const auto sh = m24::fftshift(v);
        std::printf("  5. fftshift: DC bin 0 -> shifted bin %zu\n",
                    static_cast<std::size_t>(
                        std::distance(sh.begin(),
                                      std::find(sh.begin(), sh.end(), 1.0))));
        check(sh[kN / 2] == 1.0, "5: fftshift moves DC to centre");
        const auto back = m24::fftshift(sh);
        check(back[0] == 1.0, "5: fftshift round-trip");
    }

    // ---- 6. illegal FFT length --------------------------------------------
    {
        const std::vector<std::complex<double>> x3(3, {1.0, 0.0});
        check(!m24::fft(x3.data(), 3).valid, "6: n=3 rejected");
        check(!m24::fft(nullptr, 1024).valid, "6: null pointer rejected");
        check(!m24::fft(x3.data(), 0).valid, "6: n=0 rejected");
    }

    // ---- 7. NaN / Inf fail-closed ------------------------------------------
    {
        std::vector<std::complex<double>> x(kN, {1.0, 0.0});
        x[10] = std::complex<double>(std::nan(""), 0.0);
        check(!m24::fft(x.data(), kN).valid, "7: NaN input rejected");
        x[10] = std::complex<double>(std::numeric_limits<double>::infinity(), 0.0);
        check(!m24::fft(x.data(), kN).valid, "7: Inf input rejected");
    }

    // ---- 8/9/10. waterfall ring buffer -------------------------------------
    {
        m24::Waterfall wf(4, 8);
        for (int f = 0; f < 6; ++f) {
            std::vector<float> fr(8, static_cast<float>(f));  // frame id f
            wf.push(fr);
        }
        check(wf.rows() == 4, "8: waterfall capped at capacity");
        check(wf.row(0)[0] == 5.0f, "8: newest frame overwrites correctly");
        check(wf.row(3)[0] == 2.0f, "8: oldest kept frame correct");
        const auto flat = wf.read_oldest_first();
        std::printf("  9. waterfall time-order: first=%.0f last=%.0f (expect 2,5)\n",
                    flat[0], flat[flat.size() - 1]);
        check(flat[0] == 2.0f && flat[flat.size() - 1] == 5.0f,
              "9: read_oldest_first is time-ordered");
        const std::size_t mem = wf.memory_bytes();
        std::printf("  10. waterfall memory: %zu bytes (expect %zu)\n", mem,
                    std::size_t(4 * 8 * sizeof(float)));
        check(mem == 4 * 8 * sizeof(float), "10: explicit memory cap");
        for (int f = 6; f < 20; ++f) {  // keep pushing; memory must not grow
            std::vector<float> fr(8, static_cast<float>(f));
            wf.push(fr);
        }
        check(wf.memory_bytes() == 4 * 8 * sizeof(float),
              "10: memory unchanged after many pushes");
        check(wf.rows() == 4, "10: rows never exceed capacity");
        const auto ds = wf.downsample_newest(4);
        check(ds.size() == 4, "8: display downsampling size");
    }

    // ---- 11/12/24. UI refresh scheduler ------------------------------------
    {
        m24::UiRefreshScheduler s;
        s.configure(10.0);
        s.submit_spectrum(1);
        check(s.tick(0.0), "11: first frame renders immediately");
        s.submit_spectrum(2);
        check(!s.tick(0.05), "11: rate-limited at 50 ms");
        check(s.tick(0.10), "11: renders at 100 ms");
        check(s.stats().spectrum_submitted == 2 && s.stats().spectrum_rendered == 2,
              "11: refresh rate enforced");
        m24::UiRefreshScheduler c;
        c.configure(20.0);
        for (int i = 1; i <= 5; ++i) c.submit_spectrum(static_cast<std::uint64_t>(i));
        check(c.tick(0.0), "12: coalesced submit renders");
        std::printf("  12. scheduler: submitted=%llu rendered=%llu coalesced=%llu\n",
                    static_cast<unsigned long long>(c.stats().spectrum_submitted),
                    static_cast<unsigned long long>(c.stats().spectrum_rendered),
                    static_cast<unsigned long long>(c.stats().spectrum_coalesced));
        check(c.stats().spectrum_submitted == 5 &&
                  c.stats().spectrum_rendered == 1 &&
                  c.stats().spectrum_coalesced == 4,
              "12: only latest frame kept, intermediates coalesced");
        m24::UiRefreshScheduler d;
        for (int i = 1; i <= 3; ++i) {
            d.submit_spectrum(static_cast<std::uint64_t>(i));
            check(d.tick(static_cast<double>(i)), "24: disabled renders every frame");
        }
        d.submit_control(1);
        check(d.stats().spectrum_rendered == 3 && d.stats().spectrum_coalesced == 0 &&
                  d.stats().control_processed == 1,
              "24: default-off behaviour unchanged");
    }

    // ---- 13/14/15/16. patrol state machine --------------------------------
    {
        m24::PatrolStateMachine m;
        m24::PatrolConfig cfg;
        cfg.start_freq_hz = 100.0e6;
        cfg.stop_freq_hz = 102.0e6;
        cfg.step_hz = 1.0e6;
        cfg.settle_s = 0.001;
        cfg.detect_timeout_s = 0.010;
        cfg.detect_threshold_dbm = -55.0;
        cfg.hysteresis_db = 7.0;
        m.configure(cfg);
        m24::PatrolAdapter ad;
        ad.tune = [](double) { return true; };
        ad.read_power_dbm = [] { return -30.0; };
        ad.measure = [] {
            m24::PatrolParams p;
            p.power_dbfs = -30.0;
            p.snr_db = 25.0;
            p.class_index = 0;
            p.class_name = "OOK";
            return p;
        };
        m.start();
        std::vector<std::string> seq;
        double t = 0.0;
        for (int i = 0; i < 500 && m.state() != m24::PatrolState::Stopped; ++i) {
            m.step(t, ad);
            seq.push_back(m24::patrol_state_name(m.state()));
            t += 0.0005;
        }
        bool has_all = true;
        const char* need[] = {"TUNE", "SETTLE", "DETECT", "LOCK", "ESTIMATE",
                              "CLASSIFY", "RECORD", "RESUME_SCAN"};
        for (const char* n : need) {
            bool found = false;
            for (const auto& s : seq)
                if (s == n) found = true;
            if (!found) {
                has_all = false;
                std::printf("     missing state %s\n", n);
            }
        }
        check(has_all, "13: all patrol states visited");
        check(m.state() == m24::PatrolState::Stopped, "13: scan completes -> STOPPED");
        std::printf("  13. patrol findings: %zu (expect 3 freqs)\n", m.findings().size());
        check(m.findings().size() == 3, "13: one finding per detected frequency");

        m24::PatrolStateMachine m2;
        m2.configure(cfg);
        m24::PatrolAdapter ad2;
        ad2.tune = [](double) { return true; };
        ad2.read_power_dbm = [] { return -100.0; };
        m2.start();
        m2.step(0.0, ad2);
        m2.stop();
        const auto s_after = m2.step(0.0, ad2);
        std::printf("  14. STOP: state after stop() == %s\n",
                    m24::patrol_state_name(s_after));
        check(s_after == m24::PatrolState::Stopped, "14: STOP terminates in one step");

        m24::PatrolStateMachine m3;
        m3.configure(cfg);
        m24::PatrolAdapter ad3;
        ad3.tune = [](double) { return false; };
        m3.start();
        const auto s_err = m3.step(0.0, ad3);
        std::printf("  15. tune-fail state = %s\n", m24::patrol_state_name(s_err));
        check(s_err == m24::PatrolState::Error, "15: tune failure -> ERROR");

        m24::PatrolStateMachine m4;
        m4.configure(cfg);
        m24::PatrolAdapter ad4;
        ad4.tune = [](double) { return true; };
        ad4.read_power_dbm = [] { return -100.0; };
        m4.start();
        bool saw_resume = false;
        double t4 = 0.0;
        for (int i = 0; i < 500 && m4.state() != m24::PatrolState::Stopped; ++i) {
            const auto st = m4.step(t4, ad4);
            if (st == m24::PatrolState::ResumeScan) saw_resume = true;
            t4 += 0.0005;
        }
        check(saw_resume, "16: detect timeout -> RESUME_SCAN");
        check(m4.findings().empty(), "16: no finding when nothing detected");
    }

    // ---- 17/18/19. event recorder -----------------------------------------
    {
        m24::EventRecorder rec;
        m24::EventMergeConfig mc;
        mc.freq_tol_hz = 1000.0;
        mc.time_window_s = 5.0;
        rec.configure(100, mc);
        m24::EventRecord e1;
        e1.time_s = 0.0;
        e1.center_freq_hz = 100.0e6;
        e1.class_name = "16QAM";
        rec.record(e1);
        m24::EventRecord e2 = e1;
        e2.time_s = 1.0;
        e2.center_freq_hz = 100.0e6 + 500.0;
        rec.record(e2);
        std::printf("  17. events: distinct=%zu merged=%zu (expect 1 distinct)\n",
                    rec.distinct(), rec.total_merged());
        check(rec.distinct() == 1 && rec.total_merged() == 1,
              "17: duplicate events merged");
        check(rec.events()[0].count == 2, "17: merged count == 2");
        m24::EventRecord e3 = e1;
        e3.class_name = "64QAM";
        rec.record(e3);
        check(rec.distinct() == 2, "17: different class stays distinct");

        m24::EventRecorder rec2;
        rec2.configure(100, mc);
        rec2.set_sink([](const std::string&) { return false; });
        const bool ok = rec2.record(e1);
        check(!ok && rec2.write_failed(), "19: disk failure -> fail-closed");

        m24::RotatingFileSink sink;
        sink.configure("m24_rot_test.bin", 20, 3);
        const std::string line = "{\"x\":123456789}";
        for (int i = 0; i < 12; ++i) sink.write(line);
        std::printf("  18. rotation: files_written=%zu current=%s\n",
                    sink.files_written(), sink.current_path().c_str());
        check(sink.files_written() >= 3, "18: file rotation occurred");
        sink.close();
        int on_disk = 0;
        for (int i = 0; i < 3; ++i) {
            const std::string p = "m24_rot_test.bin." + std::to_string(i);
            FILE* f = std::fopen(p.c_str(), "rb");
            if (f) {
                ++on_disk;
                std::fclose(f);
                std::remove(p.c_str());
            }
        }
        std::printf("  18. files on disk: %d (expect <= 3)\n", on_disk);
        check(on_disk <= 3, "18: rotation bounded to max_files");
    }

    // ---- 20/21/22/23. 24-class stub ---------------------------------------
    {
        m24::Class24Stub stub;
        m24::Class24Manifest bad;
        bad.model_sha256 = "";
        check(!stub.load(bad), "22: missing SHA refused");
        check(!stub.loaded(), "22: not loaded without SHA");
        {
            const auto r = stub.classify(nullptr, 0);
            check(!r.valid, "22: classify invalid when not loaded");
        }
        m24::Class24Manifest m;
        m.model_name = "STUB_SIMULATED";
        m.model_sha256 = std::string(64, 'a');
        check(stub.load(m), "20: loads with 64-char SHA");

        const auto& labels = stub.labels();
        const std::vector<std::string> expect = {
            "OOK",      "4ASK",      "8ASK",      "BPSK",     "QPSK",
            "8PSK",     "16PSK",     "32PSK",     "16APSK",   "32APSK",
            "64APSK",   "128APSK",   "16QAM",     "32QAM",    "64QAM",
            "128QAM",   "256QAM",    "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
            "AM-DSB-SC", "FM",        "GMSK",      "OQPSK"};
        bool order_ok = labels.size() == expect.size();
        for (std::size_t i = 0; i < labels.size() && i < expect.size(); ++i)
            if (labels[i] != expect[i]) order_ok = false;
        check(order_ok, "21: label order matches authoritative 24-class contract");

        std::vector<float> iq(2048, 0.0f);
        for (std::size_t k = 0; k < iq.size(); ++k)
            iq[k] = static_cast<float>(std::sin(0.01 * static_cast<double>(k)));
        const auto r = stub.classify(iq.data(), 1);
        std::printf("  20. stub: logits=%zu (expect 24) argmax=%d class=%s simulated=%d\n",
                    r.logits.size(), r.argmax, r.class_name.c_str(),
                    r.simulated ? 1 : 0);
        check(r.valid, "20: classify valid");
        check(r.logits.size() == 24, "20: exactly 24-dim output");
        check(r.argmax >= 0 && r.argmax < 24, "20: argmax in [0,24)");
        check(r.simulated, "23: result marked SIMULATED");
        const auto r2 = stub.classify(iq.data(), 1);
        check(r.argmax == r2.argmax, "23: deterministic fake logits");
        std::vector<float> iqbad = iq;
        iqbad[0] = std::numeric_limits<float>::quiet_NaN();
        const auto rbad = stub.classify(iqbad.data(), 1);
        check(!rbad.valid, "23: NaN input rejected");
    }

    std::printf("== result: assertions=%d passed=%d failed=%d ==\n",
                g_pass + g_fail, g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
