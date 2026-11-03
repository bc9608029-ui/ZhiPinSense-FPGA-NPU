#pragma once

// synthetic_iq_runner.hpp — Stage G three-route digital injection *tensor source*.
//
// This header is iCraft-free and libiio-free: it only PRODUCES the [2,1024] fp32
// model-input tensors for the three routes and the route-A manifest parsing /
// fail-closed byte checks.  It never opens a device and never runs the NPU.  The
// board runner (board_gate9_full_chain_rml23.cpp::run_synthetic_iq_phase) composes
// it with chain::NpuClassifier24.
//
// Routes (task 39e5 Stage G):
//   A  source=radioml     inject-point=model-input  -- the extracted RadioML2018
//      frozen-test-split frames (prepared by scripts/extract_radioml_stage_g.py),
//      read back with byte/SHA/label/size fail-closed checks.
//   B  source=generated   inject-point=model-input  -- 128 kSPS (8 sps) RRC-shaped
//      BPSK/QPSK/4ASK/16QAM, sliced into 1024-sample windows, fed [2,1024] direct.
//   C  source=generated   inject-point=raw-rx       -- 2.56 MSPS (160 sps) int16,
//      pushed through the REAL production chain::PreprocessChain (2.56M -> 128k
//      -> [2,1024]).  The board runner then replays C's final tensor through the
//      model-input infer path and asserts bit-identical raw24 (NPU determinism +
//      boundary identity).
//
// B and C draw their symbol stream from the SAME (modulation, seed) index stream,
// so they share the identical symbol/constellation sequence by construction --
// only the upsample factor differs (8 vs 160 sps).  The filter is generated once
// and the startup/end transient is discarded; windows are sliced from one
// continuous steady-state waveform (no per-frame filter reset, no phase break).
//
// Normalization is a GLOBAL strategy (never per-class): "none" or "complex-rms-1".
// Every constellation is unit-power and the RRC is unit-energy-per-symbol, so the
// natural waveform RMS is ~1.0 and "none" already lands in the model's clean-signal
// input domain (RMS == amplitude == 1.0).

#include "chain_common.hpp"
#include "synthetic_iq_generator.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace syniq_run {

constexpr std::size_t kRouteAInputBytes = chain::kTensorBytes;  // 8192

// ---------------------------------------------------------------------------
// Route A: manifest + byte/SHA/label/size fail-closed loading.
// ---------------------------------------------------------------------------

struct RouteAFrame {
    int index = -1;               // 0-based sequential index
    long long source_index = -1;  // HDF5 row id (test_indices value)
    int hdf5_label = -1;          // 24-class source label index (0..23)
    double snr_db = 0.0;
    int class_index = -1;         // == hdf5_label (cross-checked)
    std::string class_name;
    std::string bin_file;
    std::string bin_sha256;       // 64-hex SHA-256 of the .bin
};

// Split a line on '\t', preserving empty trailing fields (identical semantics to
// the board's own split_tsv).
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

// Parse <bin_dir>/manifest_a.tsv and verify every .bin:
//   * .bin exists and is exactly 8192 bytes (kRouteAInputBytes);
//   * .bin SHA-256 == manifest bin_sha256;
//   * index is contiguous 0,1,2,...; hdf5_label == class_index; class_index in
//     0..23; bin_file is a flat filename (no path separators, no "..").
// Throws on ANY mismatch (fail-closed).
inline std::vector<RouteAFrame> load_route_a(const std::string& bin_dir) {
    const std::string tsv_path = bin_dir + "/manifest_a.tsv";
    std::ifstream tsv(tsv_path);
    if (!tsv)
        throw std::runtime_error("route A: missing manifest_a.tsv in " + bin_dir);

    std::vector<RouteAFrame> frames;
    std::string line;
    int expected_index = 0;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        const std::vector<std::string> f = split_tab(line);
        if (f.size() < 8)
            throw std::runtime_error("route A: malformed manifest_a.tsv line ("
                                     "expected 8 columns): " + line);

        RouteAFrame fr;
        fr.index = std::atoi(f[0].c_str());
        fr.source_index = static_cast<long long>(std::atoll(f[1].c_str()));
        fr.hdf5_label = std::atoi(f[2].c_str());
        fr.snr_db = std::atof(f[3].c_str());
        fr.class_index = std::atoi(f[4].c_str());
        fr.class_name = f[5];
        fr.bin_file = f[6];
        fr.bin_sha256 = f[7];

        if (fr.index != expected_index)
            throw std::runtime_error("route A: non-contiguous index " +
                                     std::to_string(fr.index) +
                                     " (expected " + std::to_string(expected_index) + ")");
        if (fr.class_index < 0 || fr.class_index >= rml23::kSourceClassCount)
            throw std::runtime_error("route A: class_index out of range: " +
                                     std::to_string(fr.class_index));
        if (fr.hdf5_label != fr.class_index)
            throw std::runtime_error("route A: hdf5_label != class_index for frame " +
                                     std::to_string(fr.index));
        if (fr.class_name.empty())
            throw std::runtime_error("route A: empty class_name for frame " +
                                     std::to_string(fr.index));
        if (fr.bin_file.empty() ||
            fr.bin_file.find('/') != std::string::npos ||
            fr.bin_file.find('\\') != std::string::npos ||
            fr.bin_file.find("..") != std::string::npos)
            throw std::runtime_error("route A: unsafe bin_file in manifest: " +
                                     fr.bin_file);
        if (fr.bin_sha256.size() != 64)
            throw std::runtime_error("route A: bin_sha256 not 64 hex for frame " +
                                     std::to_string(fr.index));

        const std::string bin_path = bin_dir + "/" + fr.bin_file;
        std::size_t sz = 0;
        bool ok = false;
        const std::string got = sha256_of_file(bin_path, &sz, &ok);
        if (!ok)
            throw std::runtime_error("route A: cannot read " + bin_path);
        if (sz != kRouteAInputBytes)
            throw std::runtime_error("route A: " + fr.bin_file + " size " +
                                     std::to_string(sz) + " != 8192");
        if (got != fr.bin_sha256)
            throw std::runtime_error("route A: SHA-256 mismatch for " + fr.bin_file +
                                     " (manifest " + fr.bin_sha256 +
                                     ", file " + got + ")");

        frames.push_back(fr);
        ++expected_index;
    }
    if (frames.empty())
        throw std::runtime_error("route A: manifest_a.tsv has zero samples");
    return frames;
}

// Read one route-A .bin (8192 bytes == 2048 fp32) into out[0..2047].
inline void load_route_a_tensor(const RouteAFrame& f, const std::string& bin_dir,
                                float* out) {
    const std::string path = bin_dir + "/" + f.bin_file;
    std::ifstream in(path, std::ios::binary);
    if (!in)
        throw std::runtime_error("route A: cannot open " + path);
    in.read(reinterpret_cast<char*>(out), chain::kTensorBytes);
    if (static_cast<std::size_t>(in.gcount()) != chain::kTensorBytes)
        throw std::runtime_error("route A: short read from " + path);
}

// ---------------------------------------------------------------------------
// Routes B/C: generated tensor production.
// ---------------------------------------------------------------------------

struct GeneratedConfig {
    syniq::Modulation mod = syniq::Modulation::BPSK;
    int sps = 8;                     // 8 = model-input (B), 160 = raw-rx (C)
    std::uint64_t seed = 0x39e5ULL;
    double beta = 0.35;
    int span = 8;
    std::string norm = "none";       // "none" | "complex-rms-1"
    double rms_counts = 16.0;        // raw-rx (C) int16 quantization target
    std::uint32_t fs_in = 2560000;   // raw-rx (C) sample rate
};

// RadioML2018 24-class source index for each generated modulation (== the frozen
// source order: BPSK=3, QPSK=4, 4ASK=1, 16QAM=12).
inline int source_class_index(syniq::Modulation m) {
    switch (m) {
        case syniq::Modulation::BPSK:  return 3;
        case syniq::Modulation::QPSK:  return 4;
        case syniq::Modulation::ASK4:  return 1;
        case syniq::Modulation::QAM16: return 12;
    }
    return -1;
}

// Route B: directly-synthesized 128 kSPS steady-state waveform, sliced into
// `frames` contiguous 1024-sample windows, each -> [2,1024] planar fp32 (plane0=I,
// plane1=Q).  No extra scale: the waveform RMS is already ~1.0 (unit-power
// constellations + unit-energy RRC), matching the model's clean-signal domain.
inline std::vector<std::vector<float>> generate_model_input_tensors(
        const GeneratedConfig& cfg, int frames) {
    if (frames < 1)
        throw std::runtime_error("synthetic-iq: frames must be >= 1");
    if (cfg.sps != 8)
        throw std::runtime_error("route B requires sps == 8 (model-input)");

    const int n_sym = cfg.span + frames * static_cast<int>(chain::kFrameComplex / cfg.sps);
    const auto sym = syniq::symbol_indices(cfg.mod, cfg.seed, n_sym);
    auto wave = syniq::pulse_shape(sym, cfg.mod, cfg.sps, cfg.beta, cfg.span);
    syniq::apply_normalization(wave, cfg.norm);

    const std::size_t want = static_cast<std::size_t>(frames) * chain::kFrameComplex;
    if (wave.size() != want)
        throw std::runtime_error("synthetic-iq: route B waveform length mismatch");

    std::vector<std::vector<float>> tensors;
    tensors.reserve(static_cast<std::size_t>(frames));
    for (int i = 0; i < frames; ++i) {
        std::vector<float> t(chain::kTensorFloats);
        const std::size_t base = static_cast<std::size_t>(i) * chain::kFrameComplex;
        for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
            t[k] = static_cast<float>(wave[base + k].real());
            t[chain::kFrameComplex + k] = static_cast<float>(wave[base + k].imag());
        }
        tensors.push_back(std::move(t));
    }
    return tensors;
}

struct RawRxOutput {
    std::vector<std::vector<float>> tensors;  // each [2,1024] fp32
    syniq::QuantStats quant;                  // measured int16 RMS/peak/clip
    // Stage H-E (Route E) Route-C persistence support: the EXACT post-quantization
    // interleaved int16 (I0,Q0,I1,Q1,...) that was pushed into the production
    // PreprocessChain.  This is the same `iq` block quantize_int16 returned -- it is
    // carried out verbatim (never re-generated, never re-quantized, never inferred
    // back from the tensors) so the board runner may persist it with a 3-way SHA.
    std::vector<std::int16_t> iq;             // full quantized waveform
    std::uint64_t pushed_complex = 0;         // == need (samples actually pushed)
    double quant_scale = 0.0;                 // rms_counts / pre-quantization RMS
};

// Route C: 2.56 MSPS int16 -> PreprocessChain (÷2048, NCO off, 2.56M -> 128k
// polyphase FIR, ×rec_scale = 2048/rms_counts) -> `frames` [2,1024] tensors.
// Uses the production chain so the decimation fidelity is the REAL one, and the
// resulting tensors land in the same model-domain scale as route B.
inline RawRxOutput generate_raw_rx_tensors(const GeneratedConfig& cfg, int frames) {
    if (frames < 1)
        throw std::runtime_error("synthetic-iq: frames must be >= 1");
    if (cfg.sps != 160)
        throw std::runtime_error("route C requires sps == 160 (raw-rx)");

    chain::PreprocessChain chain(
        cfg.fs_in, 0.0,
        chain::calibrate_rec_scale(cfg.rms_counts, chain::kTargetModelRms));
    const std::size_t need = chain.required_input(static_cast<std::size_t>(frames));

    const int n_sym = cfg.span +
        static_cast<int>((need + static_cast<std::size_t>(cfg.sps) - 1) /
                         static_cast<std::size_t>(cfg.sps)) + 1;
    const auto sym = syniq::symbol_indices(cfg.mod, cfg.seed, n_sym);
    auto wave = syniq::pulse_shape(sym, cfg.mod, cfg.sps, cfg.beta, cfg.span);
    syniq::apply_normalization(wave, cfg.norm);

    syniq::QuantStats st;
    const std::vector<std::int16_t> iq = syniq::quantize_int16(wave, cfg.rms_counts, st);
    if (iq.size() / 2 < need)
        throw std::runtime_error("synthetic-iq: route C waveform too short");

    // Quantization scale = rms_counts / pre-quantization RMS (recorded for the
    // Stage H-E manifest, requirement 3).  Re-derived from `wave` before it is
    // dropped; the int16 bytes themselves are untouched.
    double pre_e = 0.0;
    for (const auto& v : wave) pre_e += std::norm(v);
    const double pre_rms = std::sqrt(pre_e / static_cast<double>(wave.size()));
    const double quant_scale = (pre_rms > 0.0) ? (cfg.rms_counts / pre_rms) : 0.0;

    chain.push_int16(iq.data(), need);

    std::vector<std::vector<float>> tensors;
    tensors.reserve(static_cast<std::size_t>(frames));
    for (int i = 0; i < frames; ++i) {
        std::vector<float> t(chain::kTensorFloats);
        if (!chain.pull_tensor(t.data()))
            throw std::runtime_error("synthetic-iq: route C produced too few tensors");
        tensors.push_back(std::move(t));
    }
    if (chain.ready() != 0)
        throw std::runtime_error("synthetic-iq: route C produced extra tensors");

    RawRxOutput out;
    out.tensors = std::move(tensors);
    out.quant = st;
    out.iq = iq;                         // verbatim post-quantization bytes (Stage H-E)
    out.pushed_complex = need;           // == the samples actually pushed
    out.quant_scale = quant_scale;
    return out;
}

}  // namespace syniq_run
