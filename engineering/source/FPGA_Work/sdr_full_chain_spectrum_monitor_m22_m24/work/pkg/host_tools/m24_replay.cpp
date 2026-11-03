// m24_replay.cpp -- M24-A offline IQ replay tool.
//
// Reads raw float32 interleaved IQ (I0 Q0 I1 Q1 ...), or synthesizes a single
// tone with --tone, and drives the isolated M24-A modules end-to-end WITHOUT
// any board, framebuffer, real RF device, or 24-class model:
//
//   per frame: window -> FFT -> dB -> fftshift -> noise floor -> peak detect
//              -> peak hold -> waterfall push -> scheduler tick
//   patrol:    mock adapter tied to the FFT peak power (tune always succeeds)
//   events:    patrol findings -> EventRecorder -> RotatingFileSink (JSON-lines)
//   optional:  --model-sha <64 hex> loads the 24-class STUB (SIMULATED only)
//
// Output is offline render data + a bounded event log.  Never touches Gate 9/10.

#include "../sdr_adapter/m24_class24_stub.hpp"
#include "../sdr_adapter/m24_event.hpp"
#include "../sdr_adapter/m24_fft.hpp"
#include "../sdr_adapter/m24_patrol.hpp"
#include "../sdr_adapter/m24_ui_scheduler.hpp"
#include "../sdr_adapter/m24_waterfall.hpp"

#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

namespace {

struct Args {
    std::string iq_path;
    double tone_hz = -1.0;  // < 0 => read --iq file
    double fs = 128000.0;
    std::size_t n = 1024;
    std::size_t frames = 256;
    std::string out_path;
    std::string model_sha;  // empty => no stub
    double rate_hz = 12.0;
};

void usage(const char* argv0) {
    std::printf(
        "usage: %s [--iq FILE] [--tone HZ] [--fs HZ] [--n LEN] [--frames N]\n"
        "          [--out EVENT_LOG] [--model-sha 64HEX] [--rate HZ]\n",
        argv0);
}

bool parse_args(int argc, char** argv, Args& a) {
    for (int i = 1; i < argc; ++i) {
        const std::string s = argv[i];
        auto next = [&](const char* name) -> const char* {
            if (i + 1 >= argc) {
                std::fprintf(stderr, "missing value for %s\n", name);
                return nullptr;
            }
            return argv[++i];
        };
        if (s == "--iq") {
            const char* v = next("--iq");
            if (!v) return false;
            a.iq_path = v;
        } else if (s == "--tone") {
            const char* v = next("--tone");
            if (!v) return false;
            a.tone_hz = std::atof(v);
        } else if (s == "--fs") {
            const char* v = next("--fs");
            if (!v) return false;
            a.fs = std::atof(v);
        } else if (s == "--n") {
            const char* v = next("--n");
            if (!v) return false;
            a.n = static_cast<std::size_t>(std::atoll(v));
        } else if (s == "--frames") {
            const char* v = next("--frames");
            if (!v) return false;
            a.frames = static_cast<std::size_t>(std::atoll(v));
        } else if (s == "--out") {
            const char* v = next("--out");
            if (!v) return false;
            a.out_path = v;
        } else if (s == "--model-sha") {
            const char* v = next("--model-sha");
            if (!v) return false;
            a.model_sha = v;
        } else if (s == "--rate") {
            const char* v = next("--rate");
            if (!v) return false;
            a.rate_hz = std::atof(v);
        } else {
            std::fprintf(stderr, "unknown arg: %s\n", s.c_str());
            return false;
        }
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    Args a;
    if (!parse_args(argc, argv, a)) {
        usage(argv[0]);
        return 2;
    }
    if (a.tone_hz < 0.0 && a.iq_path.empty()) {
        std::fprintf(stderr, "need --tone or --iq\n");
        usage(argv[0]);
        return 2;
    }
    if (!m24::is_power_of_two(a.n)) {
        std::fprintf(stderr, "--n must be a power of two\n");
        return 2;
    }

    // Optional 24-class stub (SIMULATED ONLY, never a real model).
    m24::Class24Stub stub;
    if (!a.model_sha.empty()) {
        m24::Class24Manifest m;
        m.model_name = "M24_A_STUB_SIMULATED";
        m.model_sha256 = a.model_sha;
        m.label_order_source = "radioml2018/classes.txt";
        if (!stub.load(m)) {
            std::fprintf(stderr, "stub load failed: %s\n", stub.error().c_str());
            return 2;
        }
        std::printf("# stub loaded (SIMULATED) sha=%.6s...\n", a.model_sha.c_str());
    }

    // Open IQ source.
    std::ifstream iq;
    if (a.tone_hz < 0.0) {
        iq.open(a.iq_path, std::ios::binary);
        if (!iq.is_open()) {
            std::fprintf(stderr, "cannot open --iq file: %s\n", a.iq_path.c_str());
            return 2;
        }
    }

    m24::Waterfall wf(128, a.n);
    m24::UiRefreshScheduler sched;
    sched.configure(a.rate_hz);
    m24::PeakHold hold;

    m24::PatrolConfig pcfg;
    pcfg.start_freq_hz = 100.0e6;
    pcfg.stop_freq_hz = 108.0e6;
    pcfg.step_hz = 1.0e6;
    pcfg.settle_s = 0.000;
    pcfg.detect_timeout_s = 0.001;
    pcfg.detect_threshold_dbm = -60.0;
    pcfg.hysteresis_db = 6.0;
    m24::PatrolStateMachine patrol;
    patrol.configure(pcfg);
    m24::PatrolAdapter pad;
    double last_peak_dbm = -300.0;
    pad.tune = [](double) { return true; };
    pad.read_power_dbm = [&] { return last_peak_dbm; };
    pad.measure = [&] {
        m24::PatrolParams p;
        p.power_dbfs = last_peak_dbm;
        p.snr_db = 0.0;
        p.center_freq_hz = patrol.current_freq_hz();
        p.class_index = -1;
        p.class_name = "UNKNOWN_EXPERIMENTAL";
        return p;
    };
    patrol.start();

    m24::EventRecorder rec;
    m24::EventMergeConfig mc;
    mc.freq_tol_hz = 1.0e6;
    mc.time_window_s = 5.0;
    rec.configure(512, mc);
    std::shared_ptr<m24::RotatingFileSink> sink;
    if (!a.out_path.empty()) {
        sink = std::make_shared<m24::RotatingFileSink>();
        sink->configure(a.out_path, 64 * 1024, 4);
        rec.set_sink([sink](const std::string& line) { return sink->write(line); });
    }

    const std::vector<double> w = m24::hann_window(a.n);
    std::size_t frames_ok = 0;
    double total_fft_us = 0.0;

    for (std::size_t f = 0; f < a.frames; ++f) {
        std::vector<std::complex<double>> x(a.n);
        if (a.tone_hz >= 0.0) {
            for (std::size_t k = 0; k < a.n; ++k) {
                const double ph = 2.0 * m24::kPi * a.tone_hz / a.fs * static_cast<double>(k);
                x[k] = std::complex<double>(0.5 * std::cos(ph), 0.5 * std::sin(ph));
            }
        } else {
            for (std::size_t k = 0; k < a.n; ++k) {
                float v[2] = {0.0f, 0.0f};
                iq.read(reinterpret_cast<char*>(v), sizeof(v));
                if (iq.gcount() != static_cast<std::streamsize>(sizeof(v))) break;
                x[k] = std::complex<double>(v[0], v[1]);
            }
            if (iq.eof()) break;
        }

        const auto t0 = std::chrono::steady_clock::now();
        m24::apply_window(x, w);  // Hann window before FFT (spectrum pipeline)
        m24::Spectrum spec = m24::fft(x.data(), a.n);
        const auto t1 = std::chrono::steady_clock::now();
        if (!spec.valid) {
            std::fprintf(stderr, "frame %zu: FFT invalid (%s)\n", f, spec.error.c_str());
            break;
        }
        total_fft_us +=
            std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count() / 1000.0;
        std::vector<double> mag = m24::magnitude(spec.bins);
        std::vector<double> db(mag.size());
        for (std::size_t k = 0; k < mag.size(); ++k)
            db[k] = m24::db_from_linear(mag[k], 1.0);
        const std::vector<double> shifted = m24::fftshift(db);
        const double floor = m24::noise_floor_db(shifted);
        const auto peaks = m24::detect_peaks(shifted, a.fs, 6.0, 2);
        // Mock "channel power" = strongest detected peak (else the noise floor).
        last_peak_dbm = floor;
        for (const auto& p : peaks)
            if (p.value_db > last_peak_dbm) last_peak_dbm = p.value_db;
        hold.update(shifted);

        std::vector<float> row(shifted.size());
        for (std::size_t k = 0; k < shifted.size(); ++k)
            row[k] = static_cast<float>(shifted[k]);
        wf.push(row);

        sched.submit_spectrum(static_cast<std::uint64_t>(f));
        sched.tick(static_cast<double>(f) / a.rate_hz);

        const auto prev_state = patrol.state();
        patrol.step(static_cast<double>(f) / a.rate_hz, pad);
        if (prev_state == m24::PatrolState::Record &&
            patrol.state() == m24::PatrolState::ResumeScan && !patrol.findings().empty()) {
            const auto& fd = patrol.findings().back();
            m24::EventRecord e;
            e.time_s = fd.time_s;
            e.center_freq_hz = fd.center_freq_hz;
            e.power_dbfs = fd.power_dbfs;
            e.snr_db = fd.snr_db;
            e.bandwidth_hz = fd.bandwidth_hz;
            e.classify_status = "SIGNAL_PRESENT";
            e.class_name = "UNKNOWN_EXPERIMENTAL";
            e.unknown_experimental = true;
            e.model_id = "24CLASS_MODEL_NOT_READY";
            e.iq_ref = a.iq_path.empty()
                           ? "synthetic:" + std::to_string(f)
                           : a.iq_path + ":" + std::to_string(f * a.n * 2);
            if (stub.loaded()) {
                // Feed the raw IQ into the SIMULATED stub for the contract check.
                std::vector<float> iqflat(2048, 0.0f);
                const std::size_t take = a.n < 1024 ? a.n : 1024;
                for (std::size_t k = 0; k < take; ++k) {
                    iqflat[k] = static_cast<float>(x[k].real());
                    iqflat[1024 + k] = static_cast<float>(x[k].imag());
                }
                const auto r = stub.classify(iqflat.data(), 1);
                if (r.valid) {
                    e.class_name = r.class_name;  // SIMULATED label
                    e.model_id = "24CLASS_STUB_SIMULATED";
                    e.classify_status = "UNKNOWN_EXPERIMENTAL";
                }
            }
            rec.record(e);
        }
        ++frames_ok;
    }

    std::printf("# frames processed       = %zu\n", frames_ok);
    std::printf("# waterfall rows         = %zu (capacity %zu, mem %zu B)\n", wf.rows(),
                wf.capacity(), wf.memory_bytes());
    std::printf("# scheduler submitted=%llu rendered=%llu coalesced=%llu control=%llu\n",
                static_cast<unsigned long long>(sched.stats().spectrum_submitted),
                static_cast<unsigned long long>(sched.stats().spectrum_rendered),
                static_cast<unsigned long long>(sched.stats().spectrum_coalesced),
                static_cast<unsigned long long>(sched.stats().control_processed));
    std::printf("# patrol findings        = %zu (state %s)\n", patrol.findings().size(),
                m24::patrol_state_name(patrol.state()));
    std::printf("# events distinct=%zu merged=%zu dropped=%zu write_failed=%d\n",
                rec.distinct(), rec.total_merged(), rec.dropped(),
                rec.write_failed() ? 1 : 0);
    std::printf("# mean FFT time          = %.2f us (%zu pts)\n", total_fft_us / frames_ok, a.n);
    if (sink) {
        sink->close();
        std::printf("# event log files_written=%zu (bounded to max_files)\n",
                    sink->files_written());
    }
    return 0;
}
