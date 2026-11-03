// m23_iq_replay.cpp -- M23 P0 IQ replay / parameter-estimation diagnostic tool.
//
// Replays IQ data (synthetic, with KNOWN ground truth, or a raw file) through
// the isolated M23 P0 modules -- signal presence, the five parameter estimates,
// and the four-way verdict -- and prints each parameter's ESTIMATE and, in
// synthetic mode, its ACTUAL ERROR vs the known truth (never a bare PASS).
//
// This is a HOST diagnostic only.  It does NOT touch the Gate 9/10 main chain,
// the board, the 12-class model, or the UI, and it never writes Flash.  The
// per-frame printout is a debugging aid; the board producer must NOT log every
// frame to the serial port (see docs/M23_P0_INTEGRATION_INTERFACE.md).
//
// Usage:
//   m23_iq_replay --synth tone   --carrier 10000 --cfo 250 --amp 1000 --snr 40
//                 --frames 8 --cfo-ref 10000 --cfo-order 1
//   m23_iq_replay --synth bpsk   --carrier 8000  --cfo -120 --symrate 8000
//                 --frames 8 --cfo-ref 8000  --cfo-order 2
//   m23_iq_replay --synth qpsk   --carrier 5000  --cfo 80   --symrate 4000
//                 --frames 8 --cfo-ref 5000  --cfo-order 4
//   m23_iq_replay --synth two-tone --carrier 16000 --bw 16000 --frames 8
//   m23_iq_replay --file iq.int16 --format int16 --frames 8 --cfo-ref 16000
//   m23_iq_replay --file iq.f32   --format f32   --frames 8
//   (optional) --ood-manifest /path/to/ood_threshold_manifest.json
//
// iCraft-free, libiio-free.  Build with host_tools/build_m23_iq_replay.sh.

#include "../sdr_adapter/m23_cfo.hpp"
#include "../sdr_adapter/m23_contract.hpp"
#include "../sdr_adapter/m23_iq_synth.hpp"
#include "../sdr_adapter/m23_ood_u_switch.hpp"
#include "../sdr_adapter/m23_params.hpp"
#include "../sdr_adapter/m23_verdict.hpp"
#include "../sdr_adapter/ood_threshold_manifest.hpp"
#include "../sdr_adapter/signal_presence.hpp"

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <fstream>
#include <string>
#include <vector>

namespace {

constexpr double kFs = 128000.0;
constexpr std::size_t kFrame = 1024;

struct Options {
    std::string mode;            // tone|bpsk|qpsk|two-tone|file
    std::string file;
    std::string format = "int16";// int16|f32
    double carrier = 0.0;
    double cfo = 0.0;
    double amp = 1000.0;
    double snr = 40.0;
    double bw = 0.0;
    double symrate = 8000.0;
    double cfo_ref = 0.0;
    bool cfo_ref_set = false;
    int cfo_order = 1;
    std::size_t frames = 8;
    std::uint64_t seed = 20261009u;
    std::string ood_manifest;
};

bool has_arg(int argc, char** argv, const char* name) {
    for (int i = 1; i < argc; ++i)
        if (std::strcmp(argv[i], name) == 0) return true;
    return false;
}

const char* get_arg(int argc, char** argv, const char* name, const char* def) {
    // Accept both "--key value" and "--key=value" (last occurrence wins).
    const char* val = def;
    const std::size_t nlen = std::strlen(name);
    for (int i = 1; i < argc; ++i) {
        if (std::strncmp(argv[i], name, nlen) == 0 && argv[i][nlen] == '=') {
            val = argv[i] + nlen + 1;
        } else if (std::strcmp(argv[i], name) == 0 && i + 1 < argc) {
            val = argv[++i];
        }
    }
    return val;
}

void usage() {
    std::printf(
        "usage: m23_iq_replay --synth <tone|bpsk|qpsk|two-tone|file> [options]\n"
        "  --carrier <hz>   --cfo <hz>  --amp <counts>  --snr <db>  --bw <hz>\n"
        "  --symrate <hz>   --frames <n> --seed <n>\n"
        "  --cfo-ref <hz>   --cfo-order <1|2|4>\n"
        "  --file <path>    --format <int16|f32>          (mode=file)\n"
        "  --ood-manifest <path>                          (optional; enables OOD-U)\n");
}

// Read one raw file into count-domain complex<float>.  int16 = interleaved
// little-endian I/Q int16; f32 = interleaved little-endian I/Q float32.
bool read_file(const Options& o, std::vector<std::complex<float>>& out) {
    std::ifstream in(o.file, std::ios::binary);
    if (!in) {
        std::fprintf(stderr, "m23_iq_replay: cannot open %s\n", o.file.c_str());
        return false;
    }
    if (o.format == "int16") {
        std::vector<std::int16_t> raw;
        std::int16_t v;
        while (in.read(reinterpret_cast<char*>(&v), sizeof(v))) raw.push_back(v);
        const std::size_t n = raw.size() / 2;
        out.resize(n);
        for (std::size_t k = 0; k < n; ++k)
            out[k] = std::complex<float>(static_cast<float>(raw[k * 2 + 0]),
                                         static_cast<float>(raw[k * 2 + 1]));
    } else if (o.format == "f32") {
        float re;
        std::vector<float> raw;
        while (in.read(reinterpret_cast<char*>(&re), sizeof(re))) raw.push_back(re);
        const std::size_t n = raw.size() / 2;
        out.resize(n);
        for (std::size_t k = 0; k < n; ++k)
            out[k] = std::complex<float>(raw[k * 2 + 0], raw[k * 2 + 1]);
    } else {
        std::fprintf(stderr, "m23_iq_replay: unknown --format %s\n", o.format.c_str());
        return false;
    }
    return !out.empty();
}

std::vector<std::complex<float>> synth(const Options& o) {
    const std::size_t n = o.frames * kFrame;
    if (o.mode == "tone")
        return m23::make_tone(n, kFs, o.carrier, o.cfo, o.amp, o.snr, o.seed).iq;
    if (o.mode == "bpsk")
        return m23::make_bpsk(n, kFs, o.carrier, o.cfo, o.symrate, o.amp, o.snr,
                              o.seed).iq;
    if (o.mode == "qpsk")
        return m23::make_qpsk(n, kFs, o.carrier, o.cfo, o.symrate, o.amp, o.snr,
                              o.seed).iq;
    if (o.mode == "two-tone")
        return m23::make_two_tone(n, kFs, o.carrier, o.bw, o.amp, o.snr, o.seed).iq;
    std::fprintf(stderr, "m23_iq_replay: unknown synth kind %s\n", o.mode.c_str());
    return {};
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2 || has_arg(argc, argv, "--help") || has_arg(argc, argv, "-h")) {
        usage();
        return 1;
    }

    Options o;
    o.mode = get_arg(argc, argv, "--synth", "");
    o.file = get_arg(argc, argv, "--file", "");
    o.format = get_arg(argc, argv, "--format", "int16");
    o.carrier = std::atof(get_arg(argc, argv, "--carrier", "0"));
    o.cfo = std::atof(get_arg(argc, argv, "--cfo", "0"));
    o.amp = std::atof(get_arg(argc, argv, "--amp", "1000"));
    o.snr = std::atof(get_arg(argc, argv, "--snr", "40"));
    o.bw = std::atof(get_arg(argc, argv, "--bw", "0"));
    o.symrate = std::atof(get_arg(argc, argv, "--symrate", "8000"));
    o.frames = static_cast<std::size_t>(std::atol(get_arg(argc, argv, "--frames", "8")));
    o.seed = static_cast<std::uint64_t>(std::atoll(get_arg(argc, argv, "--seed", "20261009")));
    o.ood_manifest = get_arg(argc, argv, "--ood-manifest", "");
    if (has_arg(argc, argv, "--cfo-ref")) {
        o.cfo_ref_set = true;
        o.cfo_ref = std::atof(get_arg(argc, argv, "--cfo-ref", "0"));
    }
    o.cfo_order = std::atoi(get_arg(argc, argv, "--cfo-order", "1"));

    std::vector<std::complex<float>> iq;
    // --file alone implies file mode; --synth file is accepted too.
    const bool file_mode = (!o.file.empty() || o.mode == "file");
    if (file_mode) {
        if (o.file.empty()) { usage(); return 1; }
        if (!read_file(o, iq)) return 1;
    } else if (!o.mode.empty()) {
        iq = synth(o);
        if (iq.empty()) return 1;
    } else {
        usage();
        return 1;
    }

    // Wire the switchable OOD-U interface.  Default OFF (byte-identical to M22);
    // --ood-manifest enables it with the frozen fail-closed loader.
    m23::M23OodSwitch ood;
    if (!o.ood_manifest.empty()) {
        try {
            ood.enable(load_ood_u_manifest(o.ood_manifest));
        } catch (const std::exception& e) {
            std::fprintf(stderr, "m23_iq_replay: OOD-U manifest rejected: %s\n", e.what());
            return 1;
        }
    }

    m23::M23ParamConfig cfg;
    cfg.sample_rate_hz = kFs;
    cfg.cfo_reference_hz = o.cfo_ref;
    cfg.cfo_reference_set = o.cfo_ref_set;
    cfg.cfo_order = o.cfo_order;

    sdr::SignalPresence presence;
    sdr::MeasureScratch meas;
    m23::CfoScratch cfo_scratch;
    m23::M23ParamState param_state;

    const std::size_t total_frames = iq.size() / kFrame;
    if (total_frames == 0) {
        std::fprintf(stderr, "m23_iq_replay: fewer than %zu samples -> no frame\n",
                     kFrame);
        return 1;
    }

    std::printf("m23_iq_replay: mode=%s frames=%zu OOD-U=%s cfo-ref=%s\n",
                file_mode ? "file" : o.mode.c_str(), total_frames,
                ood.enabled() ? "on" : "off",
                o.cfo_ref_set ? get_arg(argc, argv, "--cfo-ref", "0") : "--");

    std::printf("%-7s %-20s %-13s %-11s %-9s %-13s %-12s %-10s\n", "frame",
                "verdict", "center_hz", "power_dbfs", "snr_db", "occ_bw_hz",
                "cfo_hz", "rms");
    double cfo_sum = 0.0, center_sum = 0.0;
    std::size_t cfo_n = 0, center_n = 0, present_n = 0;

    for (std::size_t f = 0; f < total_frames; ++f) {
        const std::complex<float>* base = iq.data() + f * kFrame;
        const m23::M23Params p =
            m23::estimate_params(base, kFrame, cfg, meas, cfo_scratch);

        sdr::PresenceInput pin;
        pin.power_dbfs = p.power_dbfs.valid ? p.power_dbfs.value : -120.0;
        pin.snr_est_db = p.snr_db.valid ? p.snr_db.value : NAN;
        pin.occupied_bins = p.occupied_bw_hz.valid ? 1 : 0;
        pin.nan_inf = false;
        pin.capture_error = !p.power_dbfs.valid;
        const sdr::PresenceState st = presence.update(pin);

        m23::OodSwitchResult ood_r;
        ood_r.enabled = false;  // no logits in this diagnostic; OOD-U is wired
                                // but the replay tool does not run the model
        const m23::Verdict v =
            m23::compose(st, ood_r.enabled, ood_r.rejected, ood_r.error);

        param_state.refresh(f, p);
        const bool stale = param_state.stale(f);
        if (st == sdr::PresenceState::SignalPresent) ++present_n;

        std::printf("%-7zu %-20s %-13s %-11s %-9s %-13s %-12s %-10s\n", f,
                    m23::verdict_name(v),
                    m23::render_param(p.center_freq_hz, stale).c_str(),
                    m23::render_param(p.power_dbfs, stale).c_str(),
                    m23::render_param(p.snr_db, stale).c_str(),
                    m23::render_param(p.occupied_bw_hz, stale).c_str(),
                    m23::render_param(p.cfo_hz, stale).c_str(),
                    m23::render_param(p.rms, stale).c_str());

        if (p.center_freq_hz.valid) { center_sum += p.center_freq_hz.value; ++center_n; }
        if (p.cfo_hz.valid) { cfo_sum += p.cfo_hz.value; ++cfo_n; }
    }

    std::printf("summary: frames=%zu present=%zu center_mean=%s cfo_mean=%s\n",
                total_frames, present_n,
                center_n ? std::to_string(center_sum / center_n).c_str() : "--",
                cfo_n ? std::to_string(cfo_sum / cfo_n).c_str() : "--");

    // Synthetic mode: report the actual error of each parameter vs ground truth.
    if (!file_mode) {
        const double cfo_mean = cfo_n ? cfo_sum / cfo_n : 0.0;
        const double center_mean = center_n ? center_sum / center_n : 0.0;
        const double cfo_truth = (o.mode == "two-tone") ? 0.0 : o.cfo;
        // The single-carrier models place the line at carrier + cfo, so the
        // spectral-centroid truth is carrier + cfo; two-tone centres on carrier.
        const double center_truth =
            (o.mode == "two-tone") ? o.carrier : (o.carrier + o.cfo);
        std::printf("error vs truth:\n");
        std::printf("  center_freq_hz: err=%+10.3f Hz (truth %.1f, est %.3f)\n",
                    center_mean - center_truth, center_truth, center_mean);
        if (o.cfo_ref_set && (o.mode == "tone" || o.mode == "bpsk" || o.mode == "qpsk"))
            std::printf("  cfo_hz:         err=%+10.3f Hz (truth %.1f, est %.3f)\n",
                        cfo_mean - cfo_truth, cfo_truth, cfo_mean);
    }

    return 0;
}
