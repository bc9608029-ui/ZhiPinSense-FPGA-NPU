// make_passive_scan_demo.cpp -- SYNTHETIC passive-scan demo (task
// fix10class24-passive-scan-prep1).  Runs the passive_scan.hpp state machine over
// a narrow synthetic band with a scripted fake device + synthetic spectra, then
// writes two clearly-labelled example artifacts:
//
//   <outdir>/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_DEMO_RECORDS.tsv
//   <outdir>/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_RESULT_LIST.md
//
// This is a SYNTHETIC example to show the record + result-list FORMAT.  It is NOT
// a real RF measurement and is labelled as such everywhere.  It never claims a
// modulation classification: every record is CLASSIFICATION_UNAVAILABLE (the
// contract gate fails closed for a passive signal).
//
// iCraft-free / libiio-free.  Built with g++ -std=gnu++17 -O2 -Wall -Wextra -Werror.
// Not registered in run_tests.sh (it is a generator, like make_ui_*_snapshots).

#include "../board_package/passive_scan.hpp"

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

struct FakeDevice : public pscan::ScanDeviceControl {
    std::int64_t lo = 0;
    std::int64_t set_rx_lo(std::int64_t hz) override { lo = hz; return lo; }
    std::int64_t get_rx_lo() const override { return lo; }
    std::int64_t set_rx_bw(std::int64_t hz) override { return hz; }
    double set_rx_gain(double db) override { return db; }
    void save_params() override {}
    bool restore_params() override { return true; }
    bool flush_rx() override { return true; }
};

static const double kSampleRate = 2.56e6;
static const int kBins = 1024;
static const double kBinHz = kSampleRate / static_cast<double>(kBins);

// Build a flat-noise spectrum and inject synthetic tones (offset_hz from centre).
static pscan::PowerSpectrum make_spectrum(double center_hz,
                                          const std::vector<std::pair<double,double>>& tones,
                                          bool wide, float noise_dbfs) {
    pscan::PowerSpectrum s;
    s.bin_power_dbfs.assign(kBins, noise_dbfs);
    s.bin_hz = kBinHz;
    s.center_hz = center_hz;
    for (std::size_t t = 0; t < tones.size(); ++t) {
        const double off = tones[t].first;
        const double snr = tones[t].second;
        const int bin = static_cast<int>(std::llround(kBins / 2.0 + off / kBinHz));
        if (bin < 0 || bin >= kBins) continue;
        if (wide && t == 0) {
            for (int b = bin - 2; b <= bin + 2; ++b)
                if (b >= 0 && b < kBins)
                    s.bin_power_dbfs[b] = noise_dbfs + static_cast<float>(snr);
        } else {
            s.bin_power_dbfs[bin] = noise_dbfs + static_cast<float>(snr);
        }
    }
    return s;
}

// Synthesise a tone at offset_hz as interleaved int16 (for the capture buffer).
static std::vector<std::int16_t> synth_capture(double offset_hz, int n_complex) {
    std::vector<std::int16_t> out;
    out.reserve(static_cast<std::size_t>(n_complex) * 2);
    for (int k = 0; k < n_complex; ++k) {
        const double t = static_cast<double>(k) / kSampleRate;
        const double ph = 2.0 * 3.14159265358979323846 * offset_hz * t;
        const int re = static_cast<int>(std::llround(1200.0 * std::cos(ph)));
        const int im = static_cast<int>(std::llround(1200.0 * std::sin(ph)));
        out.push_back(static_cast<std::int16_t>(re));
        out.push_back(static_cast<std::int16_t>(im));
    }
    return out;
}

static void write_text(const std::string& path, const std::string& text) {
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) { std::fprintf(stderr, "cannot write %s\n", path.c_str()); std::exit(1); }
    std::fwrite(text.data(), 1, text.size(), f);
    std::fclose(f);
}

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: make_passive_scan_demo <outdir>\n");
        return 2;
    }
    const std::string dir = argv[1];

    // Synthetic signal table (band 2400.000..2408.000 MHz, 1 MHz step -> 9 steps).
    struct Synth { std::vector<std::pair<double,double>> tones; bool wide; };
    std::vector<Synth> table(9);
    table[0] = { {{700e3, 22.0}}, false };
    table[1] = { {}, false };
    table[2] = { {{-600e3, 15.0}}, true };
    table[3] = { {}, false };
    table[4] = { {{-800e3, 17.0}, {900e3, 16.0}}, false };
    table[5] = { {}, false };
    table[6] = { {{300e3, 19.0}}, false };
    table[7] = { {}, false };
    table[8] = { {{-400e3, 14.0}}, false };

    pscan::PassiveScanConfig cfg;
    cfg.start_hz = 2400000000ULL;
    cfg.stop_hz  = 2408000000ULL;
    cfg.step_hz  = 1000000ULL;
    cfg.settle_frames = 1;
    cfg.detect_frames  = 1;
    cfg.capture_frames = 2;

    FakeDevice dev;
    pscan::PassiveScanStateMachine m(cfg, dev, /*allow_unverified_argmax=*/false);
    m.start();

    // Drive one full sweep tick-by-tick.
    const float nf = -90.0f;
    while (m.running()) {
        pscan::FrameInput in;
        const int step = m.step_index();
        const double center = static_cast<double>(m.plan().center_hz(step));
        const Synth& sp = table[static_cast<std::size_t>(step)];
        switch (m.state()) {
            case pscan::ScanState::Tuning:
            case pscan::ScanState::Settling:
                break;
            case pscan::ScanState::Detecting:
                in.spectrum = make_spectrum(center, sp.tones, sp.wide, nf);
                break;
            case pscan::ScanState::Capturing:
                if (!sp.tones.empty())
                    in.capture_ci16 = synth_capture(sp.tones[0].first, 1024);
                break;
            default:
                break;
        }
        m.tick(in);
    }

    // --- records TSV ---
    const char* tsv_header =
        "record_id\tstep_index\tstep_lo_hz\tcandidate_freq_hz\tcandidate_bw_hz\t"
        "peak_power_dbfs\tnoise_floor_dbfs\tsnr_db\toccupied_bins\tunresolved\t"
        "candidates_in_step\tiq_sample_count\tiq_truncated\tiq_sha256\t"
        "classification_outcome\tverified\tunverified_class\n";
    std::string tsv = "## SYNTHETIC DEMO -- NOT REAL RF (source: make_passive_scan_demo)\n";
    tsv += "## Every record is a DETECTED candidate; classification is CLASSIFICATION_UNAVAILABLE.\n";
    tsv += tsv_header;
    char line[1024];
    for (const pscan::ScanRecord& r : m.store().records()) {
        std::snprintf(line, sizeof(line),
                      "%llu\t%d\t%llu\t%llu\t%.3f\t%.2f\t%.2f\t%.2f\t%d\t%d\t%zu\t%zu\t%d\t%s\t%s\t%d\t%d\n",
                      static_cast<unsigned long long>(r.record_id),
                      r.step_index,
                      static_cast<unsigned long long>(r.step_lo_hz),
                      static_cast<unsigned long long>(r.candidate_freq_hz),
                      r.candidate_bw_hz, r.peak_power_dbfs, r.noise_floor_dbfs,
                      r.snr_db, r.occupied_bins, r.unresolved ? 1 : 0,
                      r.candidates_in_step, r.iq_sample_count, r.iq_truncated ? 1 : 0,
                      r.iq_sha256.c_str(), r.classification_outcome.c_str(),
                      r.verified ? 1 : 0, r.unverified_class);
        tsv += line;
    }
    write_text(dir + "/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_DEMO_RECORDS.tsv", tsv);

    // --- result list markdown ---
    std::string md;
    md += "# Passive-Scan Result List -- SYNTHETIC DEMO (NOT REAL RF)\n\n";
    md += "> Source: `host_tests/make_passive_scan_demo.cpp` (scripted fake device + synthetic spectra).\n";
    md += "> This is a FORMAT example only.  It contains NO real RF capture and NO modulation identification.\n\n";
    md += "Band: 2400.000–2408.000 MHz, step 1.0 MHz, coverage ≈ 2.048 MHz, "
          "9 steps.  RX sample rate 2.56 MSPS, 1024-bin PSD, noise floor −90 dBFS (synthetic).\n\n";
    md += "| # | Step LO (MHz) | Detected (MHz) | BW (kHz) | SNR (dB) | outcome | verified | note |\n";
    md += "|---|--------------|----------------|----------|----------|---------|----------|------|\n";
    for (const pscan::ScanRecord& r : m.store().records()) {
        std::snprintf(line, sizeof(line),
                      "| %llu | %.3f | %.3f | %.2f | %.2f | %s | no | %s |\n",
                      static_cast<unsigned long long>(r.record_id),
                      r.step_lo_hz / 1e6, r.candidate_freq_hz / 1e6,
                      r.candidate_bw_hz / 1e3, r.snr_db,
                      r.classification_outcome.c_str(),
                      r.unresolved ? "UNRESOLVED_MULTISIGNAL" : "single candidate");
        md += line;
    }
    md += "\nEvery record is a DETECTED candidate.  `verified=no` and "
          "`CLASSIFICATION_UNAVAILABLE` are deliberate: a passive signal does not satisfy the "
          "frozen model-input contract, so no modulation label is ever asserted.\n";
    write_text(dir + "/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_RESULT_LIST.md", md);

    std::printf("make_passive_scan_demo: wrote %zu records to %s\n",
                m.store().size(), dir.c_str());
    return 0;
}
