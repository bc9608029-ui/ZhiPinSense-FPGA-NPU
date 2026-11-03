#include "iq_dual_sdr_coarse_cfo_recovery.hpp"
#include "iq_rf_training_frame.hpp"
#include "sha256.hpp"

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::string need_value(int argc, char** argv, int& i, const char* name) {
    if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
    return argv[++i];
}

std::vector<std::int16_t> read_ci16_le(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open " + path);
    f.seekg(0, std::ios::end);
    const std::streamoff bytes = f.tellg();
    if (bytes <= 0 || (bytes % 4) != 0)
        throw std::runtime_error("CI16 byte count must be positive and divisible by 4");
    f.seekg(0, std::ios::beg);
    std::vector<unsigned char> raw(static_cast<std::size_t>(bytes));
    f.read(reinterpret_cast<char*>(raw.data()), bytes);
    if (!f) throw std::runtime_error("short read from " + path);
    std::vector<std::int16_t> out(raw.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i) {
        const std::uint16_t u = static_cast<std::uint16_t>(raw[i * 2]) |
            (static_cast<std::uint16_t>(raw[i * 2 + 1]) << 8);
        out[i] = static_cast<std::int16_t>(u);
    }
    return out;
}

iqrfrec::EstimateConfig config(double target_rms) {
    iqrfrec::EstimateConfig cfg;
    cfg.min_corr = 0.9;
    cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;
    cfg.max_cfo_hz = static_cast<double>(iqrftrain::kFs) /
                     (2.0 * static_cast<double>(iqrftrain::kTailStart));
    cfg.max_sro_ppm = 30.0;
    cfg.search_limit = 0;
    cfg.payload_tx_target_rms = target_rms;
    return cfg;
}

int self_test() {
    std::vector<std::int16_t> payload(iqrftrain::kPayloadComplex * 2, 0);
    const std::vector<std::int16_t> one = iqrftrain::build_burst(payload);
    std::vector<std::int16_t> repeated;
    repeated.reserve(one.size() * 2);
    for (int i = 0; i < 2; ++i) repeated.insert(repeated.end(), one.begin(), one.end());
    const auto rec = iqdual23fix10::recover_payload_with_coarse_cfo(
        iqrftrain::deinterleave(repeated), config(0.0), 1.0);
    if (!rec.rec.valid || rec.payload_best_fractional_corr < 0.99) {
        std::fprintf(stderr,
                     "replay_fix10_failed_rx self-test: FAIL valid=%d failure=%s "
                     "payload_best_corr=%.9f\n",
                     rec.rec.valid ? 1 : 0, iqrfrec::failure_token(rec.rec.failure),
                     rec.payload_best_fractional_corr);
        return 1;
    }
    std::puts("replay_fix10_failed_rx self-test: PASS");
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string path;
        std::string expect_sha;
        double target_rms = 2048.0;
        double payload_scale = 1.0;
        for (int i = 1; i < argc; ++i) {
            const std::string a = argv[i];
            if (a == "--self-test") return self_test();
            if (a == "--rx-ci16") path = need_value(argc, argv, i, "--rx-ci16");
            else if (a == "--expect-sha256")
                expect_sha = need_value(argc, argv, i, "--expect-sha256");
            else if (a == "--target-rms")
                target_rms = std::stod(need_value(argc, argv, i, "--target-rms"));
            else if (a == "--payload-scale")
                payload_scale = std::stod(need_value(argc, argv, i, "--payload-scale"));
            else throw std::runtime_error("unknown argument: " + a);
        }
        if (path.empty())
            throw std::runtime_error("usage: replay_fix10_failed_rx --rx-ci16 FILE "
                                     "[--expect-sha256 HEX] [--target-rms 2048] "
                                     "[--payload-scale SCALE]");
        bool sha_ok = false;
        const std::string sha = sdr::sha256_hex_file(path, &sha_ok);
        if (!sha_ok) throw std::runtime_error("cannot hash " + path);
        if (!expect_sha.empty() && sha != expect_sha)
            throw std::runtime_error("SHA256 mismatch: want=" + expect_sha + " got=" + sha);
        const std::vector<std::int16_t> iq = read_ci16_le(path);
        const auto out = iqdual23fix10::recover_payload_with_coarse_cfo(
            iqrftrain::deinterleave(iq), config(target_rms), payload_scale);
        std::printf(
            "FIX10PREP3_REPLAY sha256=%s complex_count=%zu valid=%d failure=%s "
            "timing=%zu coarse_cfo_hz=%.9f fine_cfo_hz=%.9f "
            "fractional_timing_samples=%.9f fractional_corr_before=%.9f "
            "fractional_corr_after=%.9f payload_fractional_corr_before=%.9f "
            "payload_fractional_corr_after=%.9f "
            "payload_best_fractional_timing_samples=%.9f "
            "payload_best_fractional_corr=%.9f "
            "payload_best_fractional_preamble_corr=%.9f "
            "payload_training_corr=%.9f payload_training_residual=%.9f\n",
            sha.c_str(), iq.size() / 2, out.rec.valid ? 1 : 0,
            iqrfrec::failure_token(out.rec.failure), out.rec.timing_offset,
            out.coarse_cfo_hz, out.rec.cfo_hz, out.fractional_timing_samples,
            out.fractional_corr_before, out.fractional_corr_after,
            out.payload_fractional_corr_before, out.payload_fractional_corr_after,
            out.payload_best_fractional_timing_samples,
            out.payload_best_fractional_corr,
            out.payload_best_fractional_preamble_corr,
            out.rec.payload_training_corr, out.rec.payload_training_residual);
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "replay_fix10_failed_rx: ERROR: %s\n", e.what());
        return 2;
    }
}
