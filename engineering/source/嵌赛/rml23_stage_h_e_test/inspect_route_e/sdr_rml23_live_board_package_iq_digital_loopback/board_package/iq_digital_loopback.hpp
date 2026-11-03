#pragma once

// iq_digital_loopback.hpp — Stage H-E / Route E: same-device modulated-IQ digital
// loopback, *pure logic* half (host-testable).
//
// This header is iCraft-free and libiio-free.  It never opens a device and never
// runs the NPU.  It provides:
//   * Frozen-IQ loading: read the Stage G int16 artifacts (Route C persistence's
//     `iq_loopback_manifest.tsv`, or Route D's `roundtrip_manifest.tsv` + the
//     `quantized_raw_rx_*.ci16` it already persisted) with SHA/size/sample-rate
//     fail-closed checks.  Missing files fail closed with the exact token
//     STAGE_G_FROZEN_IQ_REQUIRED -- Route E NEVER re-generates a waveform.
//   * The int16-domain signal-fidelity alignment/measurement: compare the TX
//     (cyclic) modulated-IQ waveform against the RX-captured int16 (same device,
//     digital loopback), and report integer delay / optimal complex gain+phase /
//     NMSE / EVM / correlation / residual CFO / phase drift / RMS / DC / PAPR and
//     the diagnostic-only I/Q-swap and conjugation correlations.
//   * The verdict mapping (observation-only): DIGITAL_LOOPBACK_PRESERVES_IQ /
//     DIGITAL_LOOPBACK_DISTORTS_IQ / SYNC_OR_WRAP_INCONCLUSIVE /
//     DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / INSUFFICIENT_EVIDENCE.  These can
//     only be FINALISED by a board run; this header just implements the mapping.
//
// Verdict thresholds are OBSERVATION thresholds (documented, measurement-only),
// never accuracy PASS gates.  Classification error never fails infrastructure and
// vice versa (Stage H-E hard requirement 11).

#include "chain_common.hpp"
#include "rml23_merged.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqdloop {

constexpr double kPi = 3.141592653589793238462643383279502884;

// The frozen Stage G artifacts are 2.56 MSPS.  Route E must land the board on this
// rate (see the sample-rate rule in the runner) and reject any other rate.
constexpr std::uint64_t kFrozenFsIn = 2560000;

// Observation thresholds for the fidelity verdict (measurement-only).
constexpr double kPreserveMaxNmse = 0.02;   // <= -17 dB  -> "preserved"
constexpr double kDistortMinNmse = 0.05;    // >= -13 dB  -> "distorted"
constexpr double kSyncMinCorr = 0.5;        // below this -> cannot align (sync/wrap)
constexpr double kAlignMinCorr = 0.9;       // below this -> present but not clean
constexpr double kCfoNearZeroHz = 5.0;      // |CFO| <= 5 Hz  -> clocks locked
constexpr std::size_t kMinCaptureComplex = 1024;  // below this -> insufficient evidence

// ---------------------------------------------------------------------------
// Frozen-IQ descriptor + fail-closed loading.
// ---------------------------------------------------------------------------

struct FrozenIq {
    std::string path;            // full path to the .ci16 file
    std::string file_name;       // flat basename
    std::string dtype = "ci16le";
    std::string layout = "interleaved_iq";
    std::uint64_t sample_rate = kFrozenFsIn;
    std::uint64_t complex_count = 0;
    std::uint64_t byte_count = 0;
    std::string sha256;          // 64-hex of the .ci16 bytes
    std::uint64_t seed = 0;
    int source_class = -1;       // 0..23
    int deployed_class = -1;     // 0..22 (== rml23::kSourceToDeployed[source_class])
    std::string modulation;      // "BPSK"/"QPSK"/"4ASK"/"16QAM" (empty for radioml)
    double snr_db = std::numeric_limits<double>::quiet_NaN();
    long long source_index = -1; // HDF5 row (radioml) or -1 (generated)

    // Frozen classification reference (generated-2p56m sidecar only).  When
    // present, Route E compares its recovered class distribution against these.
    bool has_frozen_ref = false;
    std::string tensor_sha256;
    std::string logits_sha256;
    std::uint64_t frozen_frames = 0;
    std::uint64_t frozen_deployed_correct = 0;

    // Quantization metadata (for the manifest record; requirement 3).
    double raw_complex_rms_counts = 16.0;
    double quant_scale = 0.0;
    std::uint64_t clip_count = 0;
    double clip_ratio = 0.0;
    std::string normalization = "none";
    int sps = 160;
    double rrc_beta = 0.35;
    int rrc_span = 8;
    std::uint64_t symbol_rate_hz = 16000;
};

// Split a line on '\t', preserving empty trailing fields (same semantics as the
// board's split_tsv).
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

inline long long parse_ll(const std::string& s) {
    return static_cast<long long>(std::atoll(s.c_str()));
}
inline std::uint64_t parse_u64(const std::string& s) {
    return static_cast<std::uint64_t>(std::atoll(s.c_str()));
}
inline double parse_d(const std::string& s) {
    return std::atof(s.c_str());
}
inline bool is_hex64(const std::string& s) {
    if (s.size() != 64) return false;
    for (char c : s)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

// Read a whole file's SHA-256 and byte size.  `ok` false on any error.  The size
// is taken from the file length (seek-to-end), so the SHA is still computed by the
// streaming reader and a multi-MB frozen .ci16 is never double-buffered in RAM.
inline std::string sha256_of_file(const std::string& path, std::size_t* out_size,
                                  bool* ok) {
    if (out_size) {
        std::ifstream f(path, std::ios::binary | std::ios::ate);
        if (!f) {
            *out_size = 0;
            if (ok) *ok = false;
            return "";
        }
        *out_size = static_cast<std::size_t>(f.tellg());
    }
    return sdr::sha256_hex_file(path, ok);
}

// Full-path + SHA/byte check for a flat filename under `dir`.  Throws (fail-closed)
// on a missing file, a bad filename, a size mismatch, or a SHA mismatch.  Returns
// the full path.
inline std::string verify_frozen_file(const std::string& dir,
                                      const std::string& file_name,
                                      std::uint64_t expect_bytes,
                                      const std::string& expect_sha256,
                                      std::uint64_t* out_complex) {
    if (file_name.empty() ||
        file_name.find('/') != std::string::npos ||
        file_name.find('\\') != std::string::npos ||
        file_name.find("..") != std::string::npos)
        throw std::runtime_error("iq-loopback: unsafe frozen file name: " + file_name);

    const std::string path = dir + "/" + file_name;
    std::size_t sz = 0;
    bool ok = false;
    const std::string got = sha256_of_file(path, &sz, &ok);
    if (!ok)
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: cannot read " + path);
    if (sz != expect_bytes)
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: " + file_name +
                                 " byte size " + std::to_string(sz) + " != " +
                                 std::to_string(expect_bytes));
    if (expect_sha256.size() == 64 && got != expect_sha256)
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: SHA-256 mismatch for " +
                                 file_name + " (expected " + expect_sha256 +
                                 ", file " + got + ")");
    *out_complex = sz / 4;   // interleaved int16: 2 int16 == 4 bytes per complex
    return path;
}

// ---------------------------------------------------------------------------
// Loader A: generated-2p56m (Route C persistence sidecar).
//
// Reads <dir>/iq_loopback_manifest.tsv (header + one row per .ci16).  Every row is
// fail-closed: dtype/layout/sample_rate asserted, SHA + byte size + complex count
// verified against the file.  This is the sidecar Route C writes when run with
// --raw-iq-out-dir (Stage H-E front increment).
// ---------------------------------------------------------------------------
inline std::vector<FrozenIq> load_generated_sidecar(const std::string& dir) {
    const std::string tsv_path = dir + "/iq_loopback_manifest.tsv";
    std::ifstream tsv(tsv_path);
    if (!tsv)
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: missing " + tsv_path);

    std::vector<FrozenIq> out;
    std::string line;
    bool first = true;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        if (line[0] == '#') { first = false; continue; }
        if (first) { first = false; continue; }   // skip a header row
        const std::vector<std::string> f = split_tab(line);
        // 24 columns: file dtype layout sr_req sr_act complex byte seed source
        // mod symrate beta span sps norm rms quant_scale clip clip_ratio sha
        // tensor_sha logits_sha frozen_frames frozen_deployed_correct
        if (f.size() < 24)
            throw std::runtime_error("iq-loopback: malformed iq_loopback_manifest.tsv "
                                     "row (expected 24 columns): " + line);

        FrozenIq q;
        q.file_name = f[0];
        q.dtype = f[1];
        q.layout = f[2];
        q.sample_rate = parse_u64(f[4]);   // sr_act == nominal (software-generated)
        q.complex_count = parse_u64(f[5]);
        q.byte_count = parse_u64(f[6]);
        q.seed = parse_u64(f[7]);
        q.source_class = static_cast<int>(parse_ll(f[8]));
        q.modulation = f[9];
        q.symbol_rate_hz = parse_u64(f[10]);
        q.rrc_beta = parse_d(f[11]);
        q.rrc_span = static_cast<int>(parse_ll(f[12]));
        q.sps = static_cast<int>(parse_ll(f[13]));
        q.normalization = f[14];
        q.raw_complex_rms_counts = parse_d(f[15]);
        q.quant_scale = parse_d(f[16]);
        q.clip_count = parse_u64(f[17]);
        q.clip_ratio = parse_d(f[18]);
        q.sha256 = f[19];
        q.tensor_sha256 = f[20];
        q.logits_sha256 = f[21];
        q.frozen_frames = parse_u64(f[22]);
        q.frozen_deployed_correct = parse_u64(f[23]);
        q.has_frozen_ref = true;

        if (q.dtype != "ci16le")
            throw std::runtime_error("iq-loopback: unexpected dtype '" + q.dtype +
                                     "' for " + q.file_name);
        if (q.layout != "interleaved_iq")
            throw std::runtime_error("iq-loopback: unexpected layout '" + q.layout +
                                     "' for " + q.file_name);
        if (q.sample_rate != kFrozenFsIn)
            throw std::runtime_error("iq-loopback: frozen sample rate " +
                                     std::to_string(q.sample_rate) + " != " +
                                     std::to_string(kFrozenFsIn) + " for " + q.file_name);
        if (q.source_class < 0 || q.source_class >= rml23::kSourceClassCount)
            throw std::runtime_error("iq-loopback: source_class out of range for " +
                                     q.file_name);
        if (q.byte_count != q.complex_count * 4)
            throw std::runtime_error("iq-loopback: byte/complex count mismatch for " +
                                     q.file_name);
        if (!is_hex64(q.sha256))
            throw std::runtime_error("iq-loopback: sha256 not 64-hex for " + q.file_name);

        std::uint64_t got_complex = 0;
        q.path = verify_frozen_file(dir, q.file_name, q.byte_count, q.sha256,
                                    &got_complex);
        if (got_complex != q.complex_count)
            throw std::runtime_error("iq-loopback: complex count mismatch for " +
                                     q.file_name);
        q.deployed_class = rml23::kSourceToDeployed[q.source_class];
        q.snr_db = std::numeric_limits<double>::quiet_NaN();
        q.source_index = -1;
        out.push_back(std::move(q));
    }
    if (out.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: zero samples in " +
                                 tsv_path);
    return out;
}

// ---------------------------------------------------------------------------
// Loader B: radioml-reconstructed-2p56m (Route D persisted artifacts).
//
// Reads <dir>/roundtrip_manifest.tsv (the FROZEN 13-column Route D manifest, never
// modified) and, for each row, verifies the `quant_file` (column 8) .ci16 by
// SHA-on-the-fly + size.  dtype/layout/sample-rate are asserted by convention
// (Route D writes full 16-bit interleaved int16 @ 2.56 MSPS).
// ---------------------------------------------------------------------------
inline std::vector<FrozenIq> load_radioml_sidecar(const std::string& dir) {
    const std::string tsv_path = dir + "/roundtrip_manifest.tsv";
    std::ifstream tsv(tsv_path);
    if (!tsv)
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: missing " + tsv_path);

    std::vector<FrozenIq> out;
    std::string line;
    bool first = true;
    while (std::getline(tsv, line)) {
        if (line.empty()) continue;
        if (line[0] == '#') { first = false; continue; }
        if (first) { first = false; continue; }   // header row: index source_index ...
        const std::vector<std::string> f = split_tab(line);
        if (f.size() < 13)
            throw std::runtime_error("iq-loopback: malformed roundtrip_manifest.tsv "
                                     "row (expected 13 columns): " + line);

        FrozenIq q;
        q.source_index = parse_ll(f[1]);
        q.snr_db = parse_d(f[3]);
        q.source_class = static_cast<int>(parse_ll(f[4]));
        q.modulation = f[5];
        q.file_name = f[8];   // quant_file column

        if (q.file_name.empty() ||
            q.file_name.find('/') != std::string::npos ||
            q.file_name.find('\\') != std::string::npos ||
            q.file_name.find("..") != std::string::npos)
            throw std::runtime_error("iq-loopback: unsafe quant_file in Route D "
                                     "manifest: " + q.file_name);
        if (q.source_class < 0 || q.source_class >= rml23::kSourceClassCount)
            throw std::runtime_error("iq-loopback: source_class out of range for " +
                                     q.file_name);

        // SHA/size computed on the fly from the FROZEN Route D bytes (no re-gen).
        const std::string path = dir + "/" + q.file_name;
        std::size_t sz = 0;
        bool ok = false;
        q.sha256 = sha256_of_file(path, &sz, &ok);
        if (!ok)
            throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: cannot read " + path);
        if (sz % 4 != 0)
            throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: " + q.file_name +
                                     " size not a multiple of 4");
        q.byte_count = static_cast<std::uint64_t>(sz);
        q.complex_count = q.byte_count / 4;
        q.path = path;
        q.sample_rate = kFrozenFsIn;
        q.dtype = "ci16le";
        q.layout = "interleaved_iq";
        q.seed = 0;
        q.deployed_class = rml23::kSourceToDeployed[q.source_class];
        q.has_frozen_ref = false;
        out.push_back(std::move(q));
    }
    if (out.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: zero samples in " +
                                 tsv_path);
    return out;
}

// Dispatch loader by input kind.  Unknown kind -> fail-closed.
inline std::vector<FrozenIq> load_frozen_iq(const std::string& dir,
                                            const std::string& input_kind) {
    if (input_kind == "generated-2p56m") return load_generated_sidecar(dir);
    if (input_kind == "radioml-reconstructed-2p56m") return load_radioml_sidecar(dir);
    throw std::runtime_error("iq-loopback: unknown --input-kind: " + input_kind +
                             " (use generated-2p56m|radioml-reconstructed-2p56m)");
}

// ---------------------------------------------------------------------------
// int16-domain signal-fidelity alignment + measurement.
// ---------------------------------------------------------------------------

struct FidelityMetrics {
    std::uint64_t tx_complex = 0;    // TX waveform period (complex)
    std::uint64_t rx_complex = 0;    // RX captured length (complex)
    int delay = 0;                   // integer delay (complex samples), 0..N-1
    double gain_db = 0.0;            // optimal single complex gain, 20 log10 |g|
    double phase_deg = 0.0;          // optimal single complex phase, degrees
    double nmse = 0.0;               // normalized MSE vs cyclic TX extension
    double evm_pct = 0.0;            // 100 * sqrt(nmse)
    double corr = 0.0;               // |correlation| over the full capture
    double cfo_hz = 0.0;             // residual CFO (two-half phase slope)
    double phase_drift_deg = 0.0;    // total phase drift over the capture (deg)
    double rms_tx = 0.0, rms_rx = 0.0;
    double dc_tx = 0.0, dc_rx = 0.0;       // |mean|
    double papr_tx_db = 0.0, papr_rx_db = 0.0;
    double corr_swap = 0.0;          // diagnostic: I<->Q swapped
    double corr_conj = 0.0;          // diagnostic: conjugated
};

inline std::complex<double> iq_sample(const std::vector<std::int16_t>& iq,
                                      std::size_t k) {
    return std::complex<double>(static_cast<double>(iq[k * 2 + 0]),
                                static_cast<double>(iq[k * 2 + 1]));
}

// Align the RX capture against the CYCLIC TX waveform and measure fidelity.  The
// TX buffer is transmitted cyclically with period N = tx.size()/2, so the correct
// reference for rx[k] is tx[(k - d) mod N].  The cyclic wrap of the TX waveform is
// a property of the TX signal itself (not a loopback artifact), so it does not
// inflate NMSE.  Throws if the inputs are too short or the TX is empty.
//
// `max_delay` bounds the integer-delay search to [0, max_delay) instead of a full
// period [0, N).  A full search is O(N*R) -- intractable for a multi-Msample frozen
// waveform -- and is also meaningless here: the same-device digital-loopback
// pipeline delay is a small fixed value (a few samples to a few thousand), never a
// whole TX period.  A value of 0 keeps the full-period search (host tests).
inline FidelityMetrics align_and_measure_int16(
        const std::vector<std::int16_t>& tx, const std::vector<std::int16_t>& rx,
        std::uint64_t fs, std::size_t max_delay = 0) {
    FidelityMetrics m;
    m.tx_complex = tx.size() / 2;
    m.rx_complex = rx.size() / 2;
    if (m.tx_complex == 0)
        throw std::runtime_error("iq-loopback: empty TX waveform");
    if (m.rx_complex == 0)
        throw std::runtime_error("iq-loopback: empty RX capture");

    const std::size_t N = static_cast<std::size_t>(m.tx_complex);
    const std::size_t R = static_cast<std::size_t>(m.rx_complex);
    const std::size_t D = (max_delay > 0 && max_delay < N) ? max_delay : N;

    // 1. best integer delay (mod N) + per-delay LS complex gain, minimising the
    //    NMSE over the whole capture (each delay gets its own gain, so a pure
    //    delay/scale is never penalised as distortion).
    int best_d = 0;
    double best_err = std::numeric_limits<double>::infinity();
    for (std::size_t d = 0; d < D; ++d) {
        std::complex<double> num(0.0, 0.0), den(0.0, 0.0);
        for (std::size_t k = 0; k < R; ++k) {
            const std::size_t ref = (static_cast<std::size_t>(k) -
                                     static_cast<std::size_t>(d) + N) % N;
            const std::complex<double> x = iq_sample(tx, ref);
            const std::complex<double> y = iq_sample(rx, k);
            num += y * std::conj(x);
            den += x * std::conj(x);
        }
        if (std::abs(den) < 1e-30) continue;
        const std::complex<double> g = num / den;
        double err = 0.0;
        for (std::size_t k = 0; k < R; ++k) {
            const std::size_t ref = (static_cast<std::size_t>(k) -
                                     static_cast<std::size_t>(d) + N) % N;
            const std::complex<double> x = iq_sample(tx, ref);
            const std::complex<double> y = iq_sample(rx, k);
            err += std::norm(y - g * x);
        }
        if (err < best_err) { best_err = err; best_d = d; }
    }

    // 2. final LS gain/phase at the chosen delay.
    std::complex<double> num(0.0, 0.0), den(0.0, 0.0);
    for (std::size_t k = 0; k < R; ++k) {
        const std::size_t ref = (static_cast<std::size_t>(k) -
                                 static_cast<std::size_t>(best_d) + N) % N;
        const std::complex<double> x = iq_sample(tx, ref);
        const std::complex<double> y = iq_sample(rx, k);
        num += y * std::conj(x);
        den += x * std::conj(x);
    }
    const std::complex<double> g = (std::abs(den) > 1e-30)
        ? num / den : std::complex<double>(1.0, 0.0);

    m.delay = best_d;
    m.gain_db = 20.0 * std::log10(std::abs(g) + 1e-300);
    m.phase_deg = std::arg(g) * 180.0 / kPi;

    // 3. NMSE / correlation / RMS / DC / PAPR / swap / conj.
    double err = 0.0, ref = 0.0, ey = 0.0, ex = 0.0;
    std::complex<double> cc(0.0, 0.0), cswap(0.0, 0.0), cconj(0.0, 0.0);
    double peak_tx = 0.0, peak_rx = 0.0;
    std::complex<double> sum_tx(0.0, 0.0), sum_rx(0.0, 0.0);
    for (std::size_t k = 0; k < R; ++k) {
        const std::size_t ridx = (static_cast<std::size_t>(k) -
                                  static_cast<std::size_t>(best_d) + N) % N;
        const std::complex<double> x = iq_sample(tx, ridx);
        const std::complex<double> y = iq_sample(rx, k);
        const std::complex<double> e = y - g * x;
        err += std::norm(e);
        ref += std::norm(x);
        ey += std::norm(y);
        ex += std::norm(x);
        cc += y * std::conj(x);
        cswap += y * std::conj(std::complex<double>(x.imag(), x.real()));
        cconj += y * std::conj(std::conj(x));
        peak_tx = std::max(peak_tx, std::norm(x));
        peak_rx = std::max(peak_rx, std::norm(y));
        sum_tx += x;
        sum_rx += y;
    }
    m.nmse = ref > 0.0 ? err / ref : 0.0;
    m.evm_pct = 100.0 * std::sqrt(m.nmse);
    m.corr = std::sqrt(ex * ey) > 0.0 ? std::abs(cc) / std::sqrt(ex * ey) : 0.0;
    m.corr_swap = std::sqrt(ex * ey) > 0.0 ? std::abs(cswap) / std::sqrt(ex * ey) : 0.0;
    m.corr_conj = std::sqrt(ex * ey) > 0.0 ? std::abs(cconj) / std::sqrt(ex * ey) : 0.0;
    m.rms_tx = std::sqrt(ex / static_cast<double>(R));
    m.rms_rx = std::sqrt(ey / static_cast<double>(R));
    m.dc_tx = std::abs(sum_tx) / static_cast<double>(R);
    m.dc_rx = std::abs(sum_rx) / static_cast<double>(R);
    m.papr_tx_db = m.rms_tx > 0.0
        ? 10.0 * std::log10(peak_tx / (m.rms_tx * m.rms_tx)) : 0.0;
    m.papr_rx_db = m.rms_rx > 0.0
        ? 10.0 * std::log10(peak_rx / (m.rms_rx * m.rms_rx)) : 0.0;

    // 4. residual CFO / phase drift: phase of the residual correlation in each half
    //    of the capture.  A linear phase ramp (CFO) shows as a half-vs-half phase
    //    difference; for a same-chip digital loopback the clocks are shared so this
    //    is EXPECTED to be ~0 -- which is exactly the fact Route E measures.
    m.cfo_hz = 0.0;
    m.phase_drift_deg = 0.0;
    if (R >= 2) {
        const std::size_t H = R / 2;
        std::complex<double> c1(0.0, 0.0), c2(0.0, 0.0);
        for (std::size_t k = 0; k < H; ++k) {
            const std::size_t ridx = (static_cast<std::size_t>(k) -
                                      static_cast<std::size_t>(best_d) + N) % N;
            c1 += iq_sample(rx, k) * std::conj(iq_sample(tx, ridx));
        }
        for (std::size_t k = H; k < R; ++k) {
            const std::size_t ridx = (static_cast<std::size_t>(k) -
                                      static_cast<std::size_t>(best_d) + N) % N;
            c2 += iq_sample(rx, k) * std::conj(iq_sample(tx, ridx));
        }
        if (std::abs(c1) > 1e-30 && std::abs(c2) > 1e-30) {
            double dtheta = std::arg(c2) - std::arg(c1);
            while (dtheta > kPi) dtheta -= 2.0 * kPi;
            while (dtheta < -kPi) dtheta += 2.0 * kPi;
            m.phase_drift_deg = dtheta * 180.0 / kPi;
            m.cfo_hz = dtheta * static_cast<double>(fs) /
                       (2.0 * kPi * static_cast<double>(H));
        }
    }
    return m;
}

// ---------------------------------------------------------------------------
// Verdict mapping (observation-only).  `nmse`, `corr`, `cfo_hz`, `rx_complex`
// come from FidelityMetrics; the verdict can only be FINALISED by a board run.
// ---------------------------------------------------------------------------
inline const char* fidelity_verdict(const FidelityMetrics& m) {
    if (m.rx_complex < kMinCaptureComplex)
        return "INSUFFICIENT_EVIDENCE";
    if (m.corr < kSyncMinCorr)
        return "SYNC_OR_WRAP_INCONCLUSIVE";
    if (m.nmse <= kPreserveMaxNmse && std::fabs(m.cfo_hz) <= kCfoNearZeroHz &&
        m.corr >= 0.99)
        return "DIGITAL_LOOPBACK_PRESERVES_IQ";
    if (m.nmse >= kDistortMinNmse && m.corr >= kAlignMinCorr)
        return "DIGITAL_LOOPBACK_DISTORTS_IQ";
    return "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN";
}

// Combined classification attribution (measurement-only).  `recovered_frames`,
// `recovered_correct` are the Route E loopback numbers; `frozen_frames`,
// `frozen_correct` are the Stage G reference (present only for generated-2p56m).
// Returns a short token, never a PASS/FAIL gate.
inline std::string classification_verdict(std::uint64_t recovered_frames,
                                          std::uint64_t recovered_correct,
                                          bool has_frozen_ref,
                                          std::uint64_t frozen_frames,
                                          std::uint64_t frozen_correct) {
    if (recovered_frames == 0)
        return "INSUFFICIENT_EVIDENCE";
    const double rr = static_cast<double>(recovered_correct) /
                      static_cast<double>(recovered_frames);
    if (has_frozen_ref && frozen_frames > 0) {
        const double fr = static_cast<double>(frozen_correct) /
                          static_cast<double>(frozen_frames);
        if (rr >= fr)
            return "CLASS_CONSISTENT_WITH_FROZEN_REFERENCE";
        return "CLASS_FLIPPED_PREPROCESS_DIVERGENCE";
    }
    return (rr >= 0.5) ? "CLASS_MAJORITY_DEPLOYED" : "CLASS_DIVERGENT";
}

}  // namespace iqdloop
