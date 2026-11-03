#pragma once

// radioml_npu_ab_loader.hpp -- task fix10class24-original-radioml-npu-ab1: the
// fail-closed loader for the 480 original-RadioML test frames re-fed to the board
// NPU for the Host-vs-NPU A/B.  It is iCraft-free and libiio-free (host-testable):
// it only parses the 8-column manifest + verifies every [2,1024] fp32 .bin input
// byte-for-byte, and never opens a device or runs the NPU.  The board runner
// (board_gate9_full_chain_rml23.cpp::run_radioml_original_npu_ab) composes it with
// chain::NpuClassifier24.
//
// Input data package (written by scripts/export_radioml_npu_ab_inputs.py):
//   manifest.tsv      8 columns, 480 rows:
//       selection_id  hdf5_row_index  raw24_class  modulation  snr_db
//       input_file    input_sha256    host_pred
//   <selection_id>.bin   8192 bytes = [2,1024] f32 LE (plane 0 = I, plane 1 = Q)
//   SHA256SUMS.txt
//
// The tensor is the FROZEN training input contract verbatim:
//   arr = ascontiguousarray(X[hdf5_row_index].T).astype(float32)  -- no DC /
//   normalize / resample / filter / augment.  input_sha256 must equal the Host
//   model_input_sha256 for the SAME hdf5_row_index (the export proves this; the
//   board re-proves it here so a substituted frame can never silently score).
//
// This header deliberately contains NO SDR / CFO / wide-linear / D2 / window /
// 0.100-gate / recovery dependency: it is a pure byte-identity tensor source.

#include "chain_common.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace rmlnpuab {

constexpr int kFrameCount = 480;
constexpr int kClassCount = 24;
constexpr std::size_t kInputBytes = chain::kTensorBytes;   // 8192
constexpr std::size_t kInputFloats = chain::kTensorFloats; // 2048

// The exact 8-column manifest header (must match byte-for-byte).
inline const char* manifest_header_line() {
    return "selection_id\thdf5_row_index\traw24_class\tmodulation\tsnr_db\t"
           "input_file\tinput_sha256\thost_pred";
}

struct DirectFrame {
    int selection_id = -1;        // 1..480, contiguous
    long long hdf5_row_index = -1;// frozen HDF5 row id (X[row])
    int raw24_class = -1;         // 0..23 frozen label index (true label)
    std::string modulation;       // frozen label name (informational)
    int snr_db = 0;               // 0/10/20/30
    std::string input_file;       // flat filename, e.g. "1.bin"
    std::string input_sha256;     // 64-hex SHA-256 of the .bin
    int host_pred = -1;           // Host BF16 raw24 argmax (A/B reference)
};

// Split a line on '\t', preserving empty trailing fields (identical semantics to
// the board's own split_tsv / synthetic_iq_runner.hpp).
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

// Parse <bin_dir>/manifest.tsv and verify the WHOLE input package fail-closed:
//   * header is the exact 8-column line;
//   * exactly 480 rows, each exactly 8 columns;
//   * selection_id is contiguous 1,2,...,480;
//   * hdf5_row_index / input_file / input_sha256 are each unique;
//   * raw24_class in 0..23, host_pred in 0..23, snr_db in {0,10,20,30};
//   * input_file is a flat filename (no path separators, no "..");
//   * every .bin exists, is exactly 8192 bytes, and its SHA == input_sha256.
// Throws on ANY mismatch.
inline std::vector<DirectFrame> load_manifest(const std::string& bin_dir) {
    const std::string tsv_path = bin_dir + "/manifest.tsv";
    std::ifstream tsv(tsv_path);
    if (!tsv)
        throw std::runtime_error("radioml-npu-ab: missing manifest.tsv in " + bin_dir);

    std::vector<DirectFrame> frames;
    std::set<long long> seen_row;
    std::set<std::string> seen_file;
    std::set<std::string> seen_sha;
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
                    "radioml-npu-ab: manifest header mismatch: " + line);
            continue;
        }
        const std::vector<std::string> f = split_tab(line);
        if (f.size() != 8)
            throw std::runtime_error(
                "radioml-npu-ab: malformed manifest line (expected 8 columns): " +
                line);

        DirectFrame fr;
        fr.selection_id = std::atoi(f[0].c_str());
        fr.hdf5_row_index = static_cast<long long>(std::atoll(f[1].c_str()));
        fr.raw24_class = std::atoi(f[2].c_str());
        fr.modulation = f[3];
        fr.snr_db = std::atoi(f[4].c_str());
        fr.input_file = f[5];
        fr.input_sha256 = f[6];
        fr.host_pred = std::atoi(f[7].c_str());

        if (fr.selection_id != expected)
            throw std::runtime_error("radioml-npu-ab: non-contiguous selection_id " +
                                     std::to_string(fr.selection_id) + " (expected " +
                                     std::to_string(expected) + ")");
        if (fr.hdf5_row_index < 0)
            throw std::runtime_error("radioml-npu-ab: bad hdf5_row_index for frame " +
                                     std::to_string(fr.selection_id));
        if (fr.raw24_class < 0 || fr.raw24_class >= kClassCount)
            throw std::runtime_error("radioml-npu-ab: raw24_class out of range: " +
                                     std::to_string(fr.raw24_class));
        if (fr.host_pred < 0 || fr.host_pred >= kClassCount)
            throw std::runtime_error("radioml-npu-ab: host_pred out of range: " +
                                     std::to_string(fr.host_pred));
        if (fr.snr_db != 0 && fr.snr_db != 10 && fr.snr_db != 20 && fr.snr_db != 30)
            throw std::runtime_error("radioml-npu-ab: unexpected snr_db " +
                                     std::to_string(fr.snr_db));
        if (fr.modulation.empty())
            throw std::runtime_error("radioml-npu-ab: empty modulation for frame " +
                                     std::to_string(fr.selection_id));
        if (fr.input_file.empty() ||
            fr.input_file.find('/') != std::string::npos ||
            fr.input_file.find('\\') != std::string::npos ||
            fr.input_file.find("..") != std::string::npos)
            throw std::runtime_error("radioml-npu-ab: unsafe input_file in manifest: " +
                                     fr.input_file);
        if (fr.input_sha256.size() != 64)
            throw std::runtime_error("radioml-npu-ab: input_sha256 not 64 hex for frame " +
                                     std::to_string(fr.selection_id));

        if (!seen_row.insert(fr.hdf5_row_index).second)
            throw std::runtime_error("radioml-npu-ab: duplicate hdf5_row_index " +
                                     std::to_string(fr.hdf5_row_index));
        if (!seen_file.insert(fr.input_file).second)
            throw std::runtime_error("radioml-npu-ab: duplicate input_file " +
                                     fr.input_file);
        if (!seen_sha.insert(fr.input_sha256).second)
            throw std::runtime_error("radioml-npu-ab: duplicate input_sha256 " +
                                     fr.input_sha256);

        const std::string bin_path = bin_dir + "/" + fr.input_file;
        std::size_t sz = 0;
        bool ok = false;
        const std::string got = sha256_of_file(bin_path, &sz, &ok);
        if (!ok)
            throw std::runtime_error("radioml-npu-ab: cannot read " + bin_path);
        if (sz != kInputBytes)
            throw std::runtime_error("radioml-npu-ab: " + fr.input_file + " size " +
                                     std::to_string(sz) + " != 8192");
        if (got != fr.input_sha256)
            throw std::runtime_error("radioml-npu-ab: SHA-256 mismatch for " +
                                     fr.input_file + " (manifest " + fr.input_sha256 +
                                     ", file " + got + ")");

        frames.push_back(fr);
        ++expected;
    }
    if (frames.size() != kFrameCount)
        throw std::runtime_error("radioml-npu-ab: manifest.tsv has " +
                                 std::to_string(frames.size()) + " samples (want 480)");
    return frames;
}

// Read one .bin (8192 bytes == 2048 fp32) into out[0..2047], then re-verify the
// SHA and finiteness of the read bytes (defense in depth; the manifest load
// already verified them up front).  Throws on ANY mismatch.
inline void load_tensor(const std::string& bin_dir, const DirectFrame& f,
                        float* out) {
    const std::string path = bin_dir + "/" + f.input_file;
    std::ifstream in(path, std::ios::binary);
    if (!in)
        throw std::runtime_error("radioml-npu-ab: cannot open " + path);
    in.read(reinterpret_cast<char*>(out), kInputBytes);
    if (static_cast<std::size_t>(in.gcount()) != kInputBytes)
        throw std::runtime_error("radioml-npu-ab: short read from " + path);

    const std::string sha = sdr::Sha256::hex(out, kInputBytes);
    if (sha != f.input_sha256)
        throw std::runtime_error("radioml-npu-ab: SHA-256 mismatch on read for " +
                                 f.input_file + " (manifest " + f.input_sha256 +
                                 ", file " + sha + ")");
    for (std::size_t i = 0; i < kInputFloats; ++i)
        if (!std::isfinite(out[i]))
            throw std::runtime_error("radioml-npu-ab: non-finite float at index " +
                                     std::to_string(i) + " in " + f.input_file);
}

}  // namespace rmlnpuab
