#pragma once

// iq_fix10class24_failed_rx_dump.hpp -- fix10class24-dualsdr2 Phase B: the FAILED
// RX diagnostic dump.  When the 24-class BF16 dual-SDR runner's fidelity gate
// refuses a sample (rf_verdict != "RF_PRESERVES_IQ") AND --dump-failed-rx is set,
// the runner calls dump_failed_rx_sample() to persist every artifact the offline
// replayer (host_tools/replay_fix10class24_failed_rx.cpp) needs to reproduce the
// recovery and scan the fractional-timing / integer-timing candidate grid.
//
// This header is ADDITIVE and iCraft-free / libiio-free: it depends only on the
// red-line recovery headers + sha256.hpp, so it compiles identically on the board
// and the host, and can be unit-tested without the NPU / chain / board device.
//
// Files written to <out_dir>/failed_rx/<source_index>/:
//   raw_rx_ci16le.bin                  -- the interleaved int16 RX capture
//   expected_scaled_payload_ci16le.bin -- expected.payload (post-scale payload)
//   expected_full_burst_ci16le.bin     -- expected.burst (full 59904-complex burst)
//   coarse_corrected_rx_cf64le.bin     -- the coarse-CFO-de-rotated capture (cf64)
//   recovered_payload_f32le.bin        -- ccr.payload (f32; empty when rec invalid)
//   recovery_diagnostics.json          -- every recovery field + the EstimateConfig
//   SHA256SUMS.txt                     -- "SHA256  name" for the five .bin artifacts
// All binary artifacts are forced little-endian, independent of host byte order.

#include "iq_dual_sdr_coarse_cfo_recovery.hpp"   // iqdual23fix10::CoarseCfoRecovery
#include "iq_pc_tx_board_rx_transfer_fix10.hpp"  // iqpctbrx::TxBurstBuild (+ FrozenIq)
#include "iq_rf_sync_recovery.hpp"               // iqrfrec::EstimateConfig / failure_token
#include "iq_rf_training_frame.hpp"              // iqrftrain::kPi / kFs / kPayloadComplex
#include "../sdr_adapter/sha256.hpp"             // sdr::Sha256 / sdr::sha256_hex_file

#include <sys/stat.h>

#include <cerrno>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqfix10dump {

// ---- little-endian binary writers (host byte-order independent) ----------------
inline void write_ci16_le(const std::string& path,
                          const std::vector<std::int16_t>& samples) {
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    if (!f) throw std::runtime_error("dump: cannot create " + path);
    for (std::int16_t sample : samples) {
        const std::uint16_t u = static_cast<std::uint16_t>(sample);
        const char bytes[2] = {static_cast<char>(u & 0xffu),
                               static_cast<char>((u >> 8) & 0xffu)};
        f.write(bytes, sizeof bytes);
    }
    f.close();
    if (!f) throw std::runtime_error("dump: cannot finish " + path);
}

inline void write_cf64_le(const std::string& path,
                          const std::vector<std::complex<double>>& samples) {
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    if (!f) throw std::runtime_error("dump: cannot create " + path);
    for (const std::complex<double>& z : samples) {
        std::uint64_t re_bits = 0, im_bits = 0;
        const double re_val = z.real();
        const double im_val = z.imag();
        std::memcpy(&re_bits, &re_val, 8);
        std::memcpy(&im_bits, &im_val, 8);
        const char re[8] = {static_cast<char>(re_bits & 0xffu),
                            static_cast<char>((re_bits >> 8) & 0xffu),
                            static_cast<char>((re_bits >> 16) & 0xffu),
                            static_cast<char>((re_bits >> 24) & 0xffu),
                            static_cast<char>((re_bits >> 32) & 0xffu),
                            static_cast<char>((re_bits >> 40) & 0xffu),
                            static_cast<char>((re_bits >> 48) & 0xffu),
                            static_cast<char>((re_bits >> 56) & 0xffu)};
        const char im[8] = {static_cast<char>(im_bits & 0xffu),
                            static_cast<char>((im_bits >> 8) & 0xffu),
                            static_cast<char>((im_bits >> 16) & 0xffu),
                            static_cast<char>((im_bits >> 24) & 0xffu),
                            static_cast<char>((im_bits >> 32) & 0xffu),
                            static_cast<char>((im_bits >> 40) & 0xffu),
                            static_cast<char>((im_bits >> 48) & 0xffu),
                            static_cast<char>((im_bits >> 56) & 0xffu)};
        f.write(re, sizeof re);
        f.write(im, sizeof im);
    }
    f.close();
    if (!f) throw std::runtime_error("dump: cannot finish " + path);
}

inline void write_f32_le(const std::string& path,
                         const std::vector<std::complex<double>>& samples) {
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    if (!f) throw std::runtime_error("dump: cannot create " + path);
    for (const std::complex<double>& z : samples) {
        const float re = static_cast<float>(z.real());
        const float im = static_cast<float>(z.imag());
        std::uint32_t re_bits = 0, im_bits = 0;
        std::memcpy(&re_bits, &re, 4);
        std::memcpy(&im_bits, &im, 4);
        const char re_b[4] = {static_cast<char>(re_bits & 0xffu),
                              static_cast<char>((re_bits >> 8) & 0xffu),
                              static_cast<char>((re_bits >> 16) & 0xffu),
                              static_cast<char>((re_bits >> 24) & 0xffu)};
        const char im_b[4] = {static_cast<char>(im_bits & 0xffu),
                              static_cast<char>((im_bits >> 8) & 0xffu),
                              static_cast<char>((im_bits >> 16) & 0xffu),
                              static_cast<char>((im_bits >> 24) & 0xffu)};
        f.write(re_b, sizeof re_b);
        f.write(im_b, sizeof im_b);
    }
    f.close();
    if (!f) throw std::runtime_error("dump: cannot finish " + path);
}

// ---- small self-contained helpers (no dependency on the heavy runner) ----------
inline std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

inline std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 2);
    for (char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += c;
                }
        }
    }
    return out;
}

inline void mkdir_p(const std::string& dir) {
    std::string cur;
    for (char c : dir) {
        cur.push_back(c);
        if (c == '/') {
            if (::mkdir(cur.c_str(), 0777) != 0 && errno != EEXIST)
                throw std::runtime_error("dump: cannot mkdir " + cur + ": " +
                                         std::strerror(errno));
        }
    }
    if (::mkdir(dir.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("dump: cannot mkdir " + dir + ": " +
                                 std::strerror(errno));
}

// ---- the failed-sample diagnostic dump -----------------------------------------
inline void dump_failed_rx_sample(
        const iqdloop::FrozenIq& fz,
        const iqpctbrx::TxBurstBuild& expected,
        const std::vector<std::int16_t>& rx_int16,
        const std::vector<std::complex<double>>& rx,
        const iqdual23fix10::CoarseCfoRecovery& ccr,
        double coarse_cfo_hz, double fine_cfo_hz, double total_cfo_hz,
        bool cfo_finite, bool cfo_in_range,
        const std::string& rf_verdict, const std::string& out_dir,
        double target_rms, const iqrfrec::EstimateConfig& rec_cfg,
        double coarse_cfo_unambiguous_range_hz, double fine_cfo_range_hz,
        double coarse_cfo_search_min_hz, double coarse_cfo_search_max_hz) {
    const iqrfrec::PerFileRecovery& rec = ccr.rec;
    const std::string dir =
        join_path(out_dir, "failed_rx/" + std::to_string(fz.source_index));
    mkdir_p(dir);

    const std::string raw_path = join_path(dir, "raw_rx_ci16le.bin");
    const std::string payload_path = join_path(dir, "expected_scaled_payload_ci16le.bin");
    const std::string burst_path = join_path(dir, "expected_full_burst_ci16le.bin");
    const std::string derot_path = join_path(dir, "coarse_corrected_rx_cf64le.bin");
    const std::string recovered_path = join_path(dir, "recovered_payload_f32le.bin");
    const std::string json_path = join_path(dir, "recovery_diagnostics.json");
    const std::string sums_path = join_path(dir, "SHA256SUMS.txt");

    write_ci16_le(raw_path, rx_int16);
    write_ci16_le(payload_path, expected.payload);
    write_ci16_le(burst_path, expected.burst);

    // Recomputed coarse de-rotation -- byte-identical to the production `derot`
    // local inside recover_payload_with_coarse_cfo (a pure per-sample phase ramp
    // anchored at capture sample 0).  Recomputing here avoids touching the red-line
    // header, whose derot vector is not exposed.
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * coarse_cfo_hz *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }
    write_cf64_le(derot_path, derot);
    // ccr.payload is empty when rec.valid == false -- the gate-refused recovery,
    // which is exactly the failed-sample case.  The empty file is a faithful record.
    write_f32_le(recovered_path, ccr.payload);

    std::vector<std::string> sums;
    const auto record_sha = [&](const std::string& name, const std::string& path) {
        bool ok = false;
        const std::string h = sdr::sha256_hex_file(path, &ok);
        if (!ok) throw std::runtime_error("dump: cannot hash " + path);
        sums.push_back(h + "  " + name);
        return h;
    };
    const std::string raw_sha = record_sha("raw_rx_ci16le.bin", raw_path);
    record_sha("expected_scaled_payload_ci16le.bin", payload_path);
    record_sha("expected_full_burst_ci16le.bin", burst_path);
    record_sha("coarse_corrected_rx_cf64le.bin", derot_path);
    record_sha("recovered_payload_f32le.bin", recovered_path);

    std::ofstream meta(json_path, std::ios::binary | std::ios::trunc);
    if (!meta) throw std::runtime_error("dump: cannot create " + json_path);
    meta << "{\n"
         << "  \"format\":\"interleaved_le\",\n"
         << "  \"source_index\":" << fz.source_index << ",\n"
         << "  \"file_name\":\"" << json_escape(fz.file_name) << "\",\n"
         << "  \"modulation\":\"" << json_escape(fz.modulation) << "\",\n"
         << "  \"raw24_class\":" << fz.source_class << ",\n"
         << "  \"snr_db\":" << fz.snr_db << ",\n"
         << "  \"split_role\":\"" << json_escape(fz.split_role) << "\",\n"
         << "  \"rf_verdict\":\"" << json_escape(rf_verdict) << "\",\n"
         << "  \"failure\":\"" << iqrfrec::failure_token(rec.failure) << "\",\n"
         << "  \"failure_enum\":" << static_cast<int>(rec.failure) << ",\n"
         << "  \"target_rms\":" << target_rms << ",\n"
         << "  \"tx_scale\":" << expected.tx_scale << ",\n"
         << "  \"payload_sha_pre\":\"" << expected.payload_sha_pre << "\",\n"
         << "  \"payload_sha_post\":\"" << expected.payload_sha_post << "\",\n"
         << "  \"burst_sha\":\"" << expected.burst_sha << "\",\n"
         << "  \"raw_rx_complex_count\":" << (rx_int16.size() / 2) << ",\n"
         << "  \"raw_rx_sha256\":\"" << raw_sha << "\",\n"
         << "  \"coarse_cfo_hz\":" << coarse_cfo_hz << ",\n"
         << "  \"fine_cfo_hz\":" << fine_cfo_hz << ",\n"
         << "  \"total_cfo_hz\":" << total_cfo_hz << ",\n"
         << "  \"cfo_finite\":" << (cfo_finite ? 1 : 0) << ",\n"
         << "  \"cfo_in_range\":" << (cfo_in_range ? 1 : 0) << ",\n"
         << "  \"coarse_cfo_unambiguous_range_hz\":" << coarse_cfo_unambiguous_range_hz << ",\n"
         << "  \"fine_cfo_range_hz\":" << fine_cfo_range_hz << ",\n"
         << "  \"coarse_cfo_search_min_hz\":" << coarse_cfo_search_min_hz << ",\n"
         << "  \"coarse_cfo_search_max_hz\":" << coarse_cfo_search_max_hz << ",\n"
         << "  \"fractional_timing_samples\":" << ccr.fractional_timing_samples << ",\n"
         << "  \"fractional_corr_before\":" << ccr.fractional_corr_before << ",\n"
         << "  \"fractional_corr_after\":" << ccr.fractional_corr_after << ",\n"
         << "  \"payload_fractional_corr_before\":" << ccr.payload_fractional_corr_before << ",\n"
         << "  \"payload_fractional_corr_after\":" << ccr.payload_fractional_corr_after << ",\n"
         << "  \"payload_best_fractional_timing_samples\":" << ccr.payload_best_fractional_timing_samples << ",\n"
         << "  \"payload_best_fractional_corr\":" << ccr.payload_best_fractional_corr << ",\n"
         << "  \"payload_best_fractional_preamble_corr\":" << ccr.payload_best_fractional_preamble_corr << ",\n"
         << "  \"recovered_payload_complex_count\":" << ccr.payload.size() << ",\n"
         << "  \"timing_offset\":" << rec.timing_offset << ",\n"
         << "  \"training_corr\":" << rec.training_corr << ",\n"
         << "  \"training_residual\":" << rec.training_residual << ",\n"
         << "  \"gain_mag\":" << rec.gain_mag << ",\n"
         << "  \"phase_deg\":" << rec.phase_deg << ",\n"
         << "  \"sro_ppm\":" << rec.sro_ppm << ",\n"
         << "  \"phase_drift_deg\":" << rec.phase_drift_deg << ",\n"
         << "  \"payload_gain_mag\":" << rec.payload_gain_mag << ",\n"
         << "  \"payload_rms_gain_mag\":" << rec.payload_rms_gain_mag << ",\n"
         << "  \"payload_phase_deg\":" << rec.payload_phase_deg << ",\n"
         << "  \"payload_tx_scale\":" << rec.payload_tx_scale << ",\n"
         << "  \"payload_training_corr\":" << rec.payload_training_corr << ",\n"
         << "  \"payload_training_residual\":" << rec.payload_training_residual << ",\n"
         << "  \"estimate_config\":{\n"
         << "    \"min_corr\":" << rec_cfg.min_corr << ",\n"
         << "    \"max_residual\":" << rec_cfg.max_residual << ",\n"
         << "    \"max_cfo_hz\":" << rec_cfg.max_cfo_hz << ",\n"
         << "    \"max_sro_ppm\":" << rec_cfg.max_sro_ppm << ",\n"
         << "    \"search_limit\":" << rec_cfg.search_limit << ",\n"
         << "    \"payload_tx_target_rms\":" << rec_cfg.payload_tx_target_rms << "\n"
         << "  }\n"
         << "}\n";
    meta.close();
    if (!meta) throw std::runtime_error("dump: cannot finish " + json_path);

    std::ofstream sums_f(sums_path, std::ios::binary | std::ios::trunc);
    if (!sums_f) throw std::runtime_error("dump: cannot create " + sums_path);
    for (const std::string& line : sums) sums_f << line << "\n";
    sums_f.close();
    if (!sums_f) throw std::runtime_error("dump: cannot finish " + sums_path);

    std::printf("FIX10CLASS24_BF16_FAILED_RX_DUMP file=%s dir=%s raw_rx_sha256=%s\n",
                fz.file_name.c_str(), dir.c_str(), raw_sha.c_str());
    std::fflush(stdout);
}

}  // namespace iqfix10dump
