#pragma once

// radioml_singlesdr_ab_loader.hpp -- task fix10class24-original-radioml-singlesdr-ab1:
// the fail-closed loader for the TX-derived CI16 payload package re-fed to the board
// single-SDR runner.  It is iCraft-free and libiio-free (host-testable): it only
// parses the 18-column tx_manifest + verifies every `<selection_id>.i16` payload
// byte-for-byte, and never opens a device or runs the NPU.  The board runner
// (board_gate9_full_chain_rml23.cpp::run_radioml_original_singlesdr_ab) composes it
// with fix10canonical::buildTxBurstFromFrozen + recover_payload_with_coarse_cfo +
// chain::NpuClassifier24.
//
// Input data package (written by scripts/export_radioml_dualsdr_tx_payload.py; the
// SAME bytes for both the dualsdr and singlesdr forks -- this task VENDORS it, it
// does NOT re-derive):
//   tx_manifest.tsv  18 columns, 480 rows (see manifest_header_line below)
//   <selection_id>.i16   215040 bytes = 53760 complex CI16 payload (interleaved I0,Q0)
//   SHA256SUMS.txt
//
// The TX-derived conversion contract (contract/tx_derived_conversion_contract.json,
// authored by the dualsdr fork, single authority for BOTH forks) is:
//   original [2,1024] f32  ->  cyclic tile to 53760 complex  ->  CI16 @ RMS2048
//   (lround, half-away-from-zero)  ->  unscale = native_rms/2048 maps recovered
//   counts back to the original f32 domain.  Model window = first 1024 complex
//   samples of the RECOVERED payload, then * unscale.
//
// This header deliberately contains NO SDR / CFO / wide-linear / window / 0.100-gate /
// recovery dependency: it is a pure byte-identity payload source.  The 18 columns that
// duplicate the npu-ab1 identity (selection_id / hdf5_row_index / raw24_class /
// modulation / dataset_snr_db / input_file / model_input_sha256 / host_pred) are
// recorded here so the board re-proves the payload's provenance, and the host test
// (host_tests/test_radioml_singlesdr_ab1.py) proves those columns are byte-identical
// to the npu-ab1 manifest.

#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace rmlsinglesdr {

constexpr int kFrameCount = 480;
constexpr int kClassCount = 24;
constexpr std::size_t kPayloadComplex = 53760;           // iqrftrain::kPayloadComplex
constexpr std::size_t kPayloadInt16 = 2 * kPayloadComplex;  // 107520 int16
constexpr std::size_t kPayloadBytes = kPayloadInt16 * 2;    // 215040 bytes

// The frozen adaptation tag (must match byte-for-byte; fail-closed otherwise).
inline const char* kAdaptation() {
    return "cyclic_tile_1024_to_53760_rms2048_ci16";
}

// The exact 18-column manifest header (must match byte-for-byte).
inline const char* manifest_header_line() {
    return "selection_id\thdf5_row_index\traw24_class\tmodulation\tdataset_snr_db\t"
           "input_file\tmodel_input_sha256\thost_pred\ttx_payload_file\t"
           "tx_payload_sha256\tnative_rms\ttx_scale\tunscale\tpeak_pre\tpeak_post\t"
           "clip_pre\tclip_post\tadaptation";
}

struct SinglesdrFrame {
    int selection_id = -1;         // 1..480, contiguous
    long long hdf5_row_index = -1;// frozen HDF5 row id (X[row])
    int raw24_class = -1;          // 0..23 frozen label index (true label)
    std::string modulation;        // frozen label name (informational)
    int dataset_snr_db = 0;        // 0/10/20/30 (dataset nominal SNR, NOT real RX SNR)
    std::string input_file;        // original [2,1024] .bin name (provenance)
    std::string model_input_sha256;// 64-hex SHA of the original .bin (provenance)
    int host_pred = -1;            // Host BF16 raw24 argmax (arm-A reference)
    std::string tx_payload_file;   // flat filename, e.g. "1.i16"
    std::string tx_payload_sha256; // 64-hex SHA-256 of the .i16
    double native_rms = 0.0;       // native_rms(original_1024)
    double tx_scale = 0.0;         // 2048 / native_rms (== 1.0 when already RMS2048)
    double unscale = 0.0;          // native_rms / 2048 (counts -> original f32 domain)
    double peak_pre = 0.0;
    double peak_post = 0.0;
    int clip_pre = -1;             // must be 0 (export asserts clip_count == 0)
    int clip_post = -1;            // must be 0
    std::string adaptation;
};

// Split a line on '\t', preserving empty trailing fields (identical semantics to the
// board's own split_tsv / synthetic_iq_runner.hpp / radioml_npu_ab_loader.hpp).
inline std::vector<std::string> split_tab(const std::string& line) {
    std::vector<std::string> f;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = line.find('\t', start);
        if (pos == std::string::npos) { f.push_back(line.substr(start)); break; }
        f.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    return f;
}

// Read a whole file and return its SHA-256 (64 hex) plus size.  `ok` false on any
// open/read error (caller fails closed).
inline std::string sha256_of_file(const std::string& path, std::size_t* out_size,
                                  bool* ok) {
    *ok = false;
    *out_size = 0;
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    std::vector<char> buf((std::istreambuf_iterator<char>(f)),
                          std::istreambuf_iterator<char>());
    if (f.bad()) return "";
    *out_size = buf.size();
    *ok = true;
    return sdr::Sha256::hex(buf.data(), buf.size());
}

// Parse a double field fail-closed: finite + strictly positive (RMS/scale/unscale are
// all positive by construction; a non-positive value means a tampered manifest).
inline double parse_positive_double(const std::string& field, const char* what,
                                    int selection_id) {
    char* end = nullptr;
    const double v = std::strtod(field.c_str(), &end);
    if (end == field.c_str() || *end != '\0' || !std::isfinite(v) || !(v > 0.0))
        throw std::runtime_error("radioml-singlesdr-ab: bad " + std::string(what) +
                                 " for frame " + std::to_string(selection_id) +
                                 " (" + field + ")");
    return v;
}

// Parse <payload_dir>/tx_manifest.tsv and verify the WHOLE payload package fail-closed:
//   * header is the exact 18-column line;
//   * exactly 480 rows, each exactly 18 columns;
//   * selection_id is contiguous 1,2,...,480;
//   * hdf5_row_index / input_file / model_input_sha256 / tx_payload_file /
//     tx_payload_sha256 are each unique;
//   * raw24_class in 0..23, host_pred in 0..23, dataset_snr_db in {0,10,20,30};
//   * clip_pre == 0 and clip_post == 0 (the export asserts clip_count == 0);
//   * adaptation == kAdaptation() (the frozen conversion tag);
//   * native_rms / tx_scale / unscale finite and > 0;
//   * tx_payload_file is a flat filename (no path separators, no "..");
//   * every .i16 exists, is exactly 215040 bytes, and its SHA == tx_payload_sha256.
// Throws on ANY mismatch.
inline std::vector<SinglesdrFrame> load_tx_manifest(const std::string& payload_dir) {
    const std::string tsv_path = payload_dir + "/tx_manifest.tsv";
    std::ifstream tsv(tsv_path);
    if (!tsv)
        throw std::runtime_error("radioml-singlesdr-ab: missing tx_manifest.tsv in " +
                                 payload_dir);

    std::vector<SinglesdrFrame> frames;
    std::set<long long> seen_row;
    std::set<std::string> seen_input;
    std::set<std::string> seen_model_sha;
    std::set<std::string> seen_payload_file;
    std::set<std::string> seen_payload_sha;
    std::string line;
    int expected = 1;
    bool first = true;
    while (std::getline(tsv, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();  // CRLF tolerance
        if (line.empty()) continue;
        if (first) {
            first = false;
            if (line != manifest_header_line())
                throw std::runtime_error(
                    "radioml-singlesdr-ab: manifest header mismatch: " + line);
            continue;
        }
        const std::vector<std::string> f = split_tab(line);
        if (f.size() != 18)
            throw std::runtime_error(
                "radioml-singlesdr-ab: malformed manifest line (expected 18 columns): " +
                line);

        SinglesdrFrame fr;
        fr.selection_id = std::atoi(f[0].c_str());
        fr.hdf5_row_index = static_cast<long long>(std::atoll(f[1].c_str()));
        fr.raw24_class = std::atoi(f[2].c_str());
        fr.modulation = f[3];
        fr.dataset_snr_db = std::atoi(f[4].c_str());
        fr.input_file = f[5];
        fr.model_input_sha256 = f[6];
        fr.host_pred = std::atoi(f[7].c_str());
        fr.tx_payload_file = f[8];
        fr.tx_payload_sha256 = f[9];
        fr.native_rms = parse_positive_double(f[10], "native_rms", fr.selection_id);
        fr.tx_scale = parse_positive_double(f[11], "tx_scale", fr.selection_id);
        fr.unscale = parse_positive_double(f[12], "unscale", fr.selection_id);
        fr.peak_pre = std::strtod(f[13].c_str(), nullptr);
        fr.peak_post = std::strtod(f[14].c_str(), nullptr);
        fr.clip_pre = std::atoi(f[15].c_str());
        fr.clip_post = std::atoi(f[16].c_str());
        fr.adaptation = f[17];

        if (fr.selection_id != expected)
            throw std::runtime_error("radioml-singlesdr-ab: non-contiguous selection_id " +
                                     std::to_string(fr.selection_id) + " (expected " +
                                     std::to_string(expected) + ")");
        if (fr.hdf5_row_index < 0)
            throw std::runtime_error("radioml-singlesdr-ab: bad hdf5_row_index for frame " +
                                     std::to_string(fr.selection_id));
        if (fr.raw24_class < 0 || fr.raw24_class >= kClassCount)
            throw std::runtime_error("radioml-singlesdr-ab: raw24_class out of range: " +
                                     std::to_string(fr.raw24_class));
        if (fr.host_pred < 0 || fr.host_pred >= kClassCount)
            throw std::runtime_error("radioml-singlesdr-ab: host_pred out of range: " +
                                     std::to_string(fr.host_pred));
        if (fr.dataset_snr_db != 0 && fr.dataset_snr_db != 10 &&
            fr.dataset_snr_db != 20 && fr.dataset_snr_db != 30)
            throw std::runtime_error("radioml-singlesdr-ab: unexpected dataset_snr_db " +
                                     std::to_string(fr.dataset_snr_db));
        if (fr.modulation.empty())
            throw std::runtime_error("radioml-singlesdr-ab: empty modulation for frame " +
                                     std::to_string(fr.selection_id));
        if (fr.input_file.empty() ||
            fr.input_file.find('/') != std::string::npos ||
            fr.input_file.find('\\') != std::string::npos ||
            fr.input_file.find("..") != std::string::npos)
            throw std::runtime_error("radioml-singlesdr-ab: unsafe input_file: " +
                                     fr.input_file);
        if (fr.model_input_sha256.size() != 64)
            throw std::runtime_error(
                "radioml-singlesdr-ab: model_input_sha256 not 64 hex for frame " +
                std::to_string(fr.selection_id));
        if (fr.tx_payload_file.empty() ||
            fr.tx_payload_file.find('/') != std::string::npos ||
            fr.tx_payload_file.find('\\') != std::string::npos ||
            fr.tx_payload_file.find("..") != std::string::npos)
            throw std::runtime_error("radioml-singlesdr-ab: unsafe tx_payload_file: " +
                                     fr.tx_payload_file);
        if (fr.tx_payload_sha256.size() != 64)
            throw std::runtime_error(
                "radioml-singlesdr-ab: tx_payload_sha256 not 64 hex for frame " +
                std::to_string(fr.selection_id));
        if (fr.clip_pre != 0 || fr.clip_post != 0)
            throw std::runtime_error("radioml-singlesdr-ab: frame " +
                                     std::to_string(fr.selection_id) +
                                     " is clipped (clip_pre=" + std::to_string(fr.clip_pre) +
                                     " clip_post=" + std::to_string(fr.clip_post) +
                                     "); the export asserts clip_count == 0");
        if (fr.adaptation != kAdaptation())
            throw std::runtime_error("radioml-singlesdr-ab: frame " +
                                     std::to_string(fr.selection_id) +
                                     " has unexpected adaptation: " + fr.adaptation);

        if (!seen_row.insert(fr.hdf5_row_index).second)
            throw std::runtime_error("radioml-singlesdr-ab: duplicate hdf5_row_index " +
                                     std::to_string(fr.hdf5_row_index));
        if (!seen_input.insert(fr.input_file).second)
            throw std::runtime_error("radioml-singlesdr-ab: duplicate input_file " +
                                     fr.input_file);
        if (!seen_model_sha.insert(fr.model_input_sha256).second)
            throw std::runtime_error("radioml-singlesdr-ab: duplicate model_input_sha256 " +
                                     fr.model_input_sha256);
        if (!seen_payload_file.insert(fr.tx_payload_file).second)
            throw std::runtime_error("radioml-singlesdr-ab: duplicate tx_payload_file " +
                                     fr.tx_payload_file);
        if (!seen_payload_sha.insert(fr.tx_payload_sha256).second)
            throw std::runtime_error("radioml-singlesdr-ab: duplicate tx_payload_sha256 " +
                                     fr.tx_payload_sha256);

        const std::string i16_path = payload_dir + "/" + fr.tx_payload_file;
        std::size_t sz = 0;
        bool ok = false;
        const std::string got = sha256_of_file(i16_path, &sz, &ok);
        if (!ok)
            throw std::runtime_error("radioml-singlesdr-ab: cannot read " + i16_path);
        if (sz != kPayloadBytes)
            throw std::runtime_error("radioml-singlesdr-ab: " + fr.tx_payload_file +
                                     " size " + std::to_string(sz) + " != " +
                                     std::to_string(kPayloadBytes));
        if (got != fr.tx_payload_sha256)
            throw std::runtime_error("radioml-singlesdr-ab: SHA-256 mismatch for " +
                                     fr.tx_payload_file + " (manifest " +
                                     fr.tx_payload_sha256 + ", file " + got + ")");

        frames.push_back(fr);
        ++expected;
    }
    if (frames.size() != kFrameCount)
        throw std::runtime_error("radioml-singlesdr-ab: tx_manifest.tsv has " +
                                 std::to_string(frames.size()) +
                                 " samples (want 480)");
    return frames;
}

}  // namespace rmlsinglesdr
