#pragma once

// replay_fix10class24_failed_rx.hpp -- fix10class24-dualsdr2 Phase C: the offline
// replayer core.  The runner (with --dump-failed-rx) writes a 7-file dump into
// failed_rx/<source_index>/; this header re-reads that dump and REPRODUCES the board
// recovery on the host using the UNCHANGED production C++ recovery functions
// (iqdual23fix10::recover_payload_with_coarse_cfo -> iqrfrec::estimate/apply).  No
// recovery math is reimplemented, and none of it lives in Python.
//
// Three responsibilities:
//   1. default replay  -- re-run recovery on raw_rx_ci16le.bin and print the SAME
//                         diagnostic the board logged (failure enum / timing / coarse &
//                         fine CFO / fractional timing / corr / residual), then
//                         cross-check against recovery_diagnostics.json within print
//                         precision (corr/residual < 1e-6, CFO < 5e-4, timing exact).
//   2. integer timing  -- +/-8 samples around the best integer timing: preamble corr
//                         and payload-training corr at each integer lag.
//   3. fractional grid -- the full [-0.5, +0.5] fractional-timing candidate grid at
//                         1/den resolution: preamble corr, de-ramped training residual,
//                         payload-training corr/residual, gain/phase, fine CFO, marking
//                         the production choice vs the min-residual vs max-corr
//                         candidates.
//
// iCraft-free / libiio-free / NPU-free: compiles identically on the host and board.

#include "iq_dual_sdr_coarse_cfo_recovery.hpp"
#include "iq_rf_training_frame.hpp"
#include "iq_fix10_canonical_frame_data.hpp"
#include "sha256.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace replay24 {

// ---- byte readers ---------------------------------------------------------------
inline std::string read_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open " + path);
    std::ostringstream ss;
    ss << f.rdbuf();
    if (!f && !f.eof()) throw std::runtime_error("short read from " + path);
    return ss.str();
}

inline std::vector<std::int16_t> read_ci16_le(const std::string& path) {
    const std::string raw = read_file(path);
    if (raw.size() == 0 || (raw.size() % 4) != 0)
        throw std::runtime_error("CI16 byte count must be positive and divisible by 4: " +
                                 path);
    std::vector<std::int16_t> out(raw.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i) {
        const std::uint16_t u = static_cast<std::uint16_t>(
            static_cast<unsigned char>(raw[i * 2])) |
            (static_cast<std::uint16_t>(static_cast<unsigned char>(raw[i * 2 + 1])) << 8);
        out[i] = static_cast<std::int16_t>(u);
    }
    return out;
}

// ---- minimal JSON scalar extraction (the dump's own flat-ish JSON) ---------------
// Finds the FIRST `"key":` (leading-quote pattern guarantees key-boundary safety even
// for keys that are prefixes of others, e.g. fine_cfo_hz vs fine_cfo_range_hz).
inline std::string json_value(const std::string& json, const std::string& key) {
    const std::string pat = "\"" + key + "\":";
    std::size_t pos = json.find(pat);
    if (pos == std::string::npos)
        throw std::runtime_error("json: missing key '" + key + "'");
    pos += pat.size();
    while (pos < json.size() &&
           (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r'))
        ++pos;
    if (pos >= json.size()) throw std::runtime_error("json: empty value for '" + key + "'");
    std::string out;
    if (json[pos] == '"') {
        ++pos;
        while (pos < json.size() && json[pos] != '"') {
            if (json[pos] == '\\' && pos + 1 < json.size()) { out += json[pos + 1]; pos += 2; }
            else out += json[pos++];
        }
    } else {
        while (pos < json.size() && json[pos] != ',' && json[pos] != '}' && json[pos] != '\n') {
            if (json[pos] != ' ' && json[pos] != '\t' && json[pos] != '\r') out += json[pos];
            ++pos;
        }
    }
    return out;
}

inline double json_num(const std::string& json, const std::string& key) {
    return std::stod(json_value(json, key));
}
inline long long json_int(const std::string& json, const std::string& key) {
    return std::stoll(json_value(json, key));
}
inline std::string json_str(const std::string& json, const std::string& key) {
    return json_value(json, key);
}

// ---- production EstimateConfig (byte-identical semantics to the runner + legacy) --
inline iqrfrec::EstimateConfig config(double target_rms) {
    iqrfrec::EstimateConfig cfg;
    cfg.min_corr = 0.9;
    cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;   // 0.10
    cfg.max_cfo_hz = static_cast<double>(iqrftrain::kFs) /
                     (2.0 * static_cast<double>(iqrftrain::kTailStart));  // ~21.74 Hz
    cfg.max_sro_ppm = 30.0;
    cfg.search_limit = 0;   // full capture
    cfg.payload_tx_target_rms = target_rms;
    return cfg;
}

inline bool near(double a, double b, double tol) { return std::fabs(a - b) <= tol; }

// ---- the dump -> replay result ---------------------------------------------------
struct ReplayResult {
    iqdual23fix10::CoarseCfoRecovery ccr;
    double target_rms = 0.0;
    double tx_scale = 1.0;
    std::string raw_rx_sha256;
    std::size_t complex_count = 0;
    // cross-check verdicts vs recovery_diagnostics.json
    bool sha_ok = false;
    bool failure_ok = false;
    bool timing_ok = false;
    bool cfo_ok = false;
    bool corr_resid_ok = false;
};

// Re-run the production recovery on the raw RX capture and cross-check the JSON.
// Returns the recovery; the caller prints the board-matching line.
inline ReplayResult replay_from_dir(const std::string& dir) {
    const std::string raw_path = dir + "/raw_rx_ci16le.bin";
    const std::string json_path = dir + "/recovery_diagnostics.json";
    const std::string json = read_file(json_path);

    const double target_rms = json_num(json, "target_rms");
    const double tx_scale = json_num(json, "tx_scale");
    const long long recorded_failure = json_int(json, "failure_enum");
    const long long recorded_timing = json_int(json, "timing_offset");
    const double recorded_coarse = json_num(json, "coarse_cfo_hz");
    const double recorded_fine = json_num(json, "fine_cfo_hz");
    const std::string recorded_raw_sha = json_str(json, "raw_rx_sha256");

    bool sha_ok = false;
    const std::string actual_raw_sha = sdr::sha256_hex_file(raw_path, &sha_ok);
    if (!sha_ok) throw std::runtime_error("cannot hash " + raw_path);

    const std::vector<std::int16_t> iq = read_ci16_le(raw_path);
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);
    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, config(target_rms), tx_scale);

    ReplayResult r;
    r.ccr = ccr;
    r.target_rms = target_rms;
    r.tx_scale = tx_scale;
    r.raw_rx_sha256 = actual_raw_sha;
    r.complex_count = rx.size();
    r.sha_ok = (actual_raw_sha == recorded_raw_sha);
    r.failure_ok = (static_cast<long long>(ccr.rec.failure) == recorded_failure);
    r.timing_ok = (static_cast<long long>(ccr.rec.timing_offset) == recorded_timing);
    r.cfo_ok = near(ccr.coarse_cfo_hz, recorded_coarse, 5e-4) &&
               near(ccr.rec.cfo_hz, recorded_fine, 5e-4);
    r.corr_resid_ok =
        near(ccr.fractional_timing_samples, json_num(json, "fractional_timing_samples"), 1e-6) &&
        near(ccr.fractional_corr_before, json_num(json, "fractional_corr_before"), 1e-6) &&
        near(ccr.fractional_corr_after, json_num(json, "fractional_corr_after"), 1e-6) &&
        near(ccr.payload_fractional_corr_before,
             json_num(json, "payload_fractional_corr_before"), 1e-6) &&
        near(ccr.payload_fractional_corr_after,
             json_num(json, "payload_fractional_corr_after"), 1e-6) &&
        near(ccr.payload_best_fractional_timing_samples,
             json_num(json, "payload_best_fractional_timing_samples"), 1e-6) &&
        near(ccr.payload_best_fractional_corr,
             json_num(json, "payload_best_fractional_corr"), 1e-6) &&
        near(ccr.payload_best_fractional_preamble_corr,
             json_num(json, "payload_best_fractional_preamble_corr"), 1e-6) &&
        near(ccr.rec.payload_training_corr,
             json_num(json, "payload_training_corr"), 1e-6) &&
        near(ccr.rec.payload_training_residual,
             json_num(json, "payload_training_residual"), 1e-6);
    return r;
}

// Print the board-matching diagnostic line + the cross-check verdict.
inline void print_replay(const std::string& dir, const ReplayResult& r) {
    const auto& c = r.ccr;
    std::printf("FIX10CLASS24_REPLAY dump_dir=%s raw_rx_sha256=%s complex_count=%zu "
                "valid=%d failure=%s failure_enum=%d timing=%zu "
                "coarse_cfo_hz=%.9f fine_cfo_hz=%.9f fractional_timing_samples=%.9f "
                "fractional_corr_before=%.9f fractional_corr_after=%.9f "
                "payload_fractional_corr_before=%.9f payload_fractional_corr_after=%.9f "
                "payload_best_fractional_timing_samples=%.9f "
                "payload_best_fractional_corr=%.9f "
                "payload_best_fractional_preamble_corr=%.9f "
                "payload_training_corr=%.9f payload_training_residual=%.9f "
                "crosscheck=%s\n",
                dir.c_str(), r.raw_rx_sha256.c_str(), r.complex_count,
                c.rec.valid ? 1 : 0, iqrfrec::failure_token(c.rec.failure),
                static_cast<int>(c.rec.failure), c.rec.timing_offset,
                c.coarse_cfo_hz, c.rec.cfo_hz, c.fractional_timing_samples,
                c.fractional_corr_before, c.fractional_corr_after,
                c.payload_fractional_corr_before, c.payload_fractional_corr_after,
                c.payload_best_fractional_timing_samples,
                c.payload_best_fractional_corr,
                c.payload_best_fractional_preamble_corr,
                c.rec.payload_training_corr, c.rec.payload_training_residual,
                (r.sha_ok && r.failure_ok && r.timing_ok && r.cfo_ok && r.corr_resid_ok)
                    ? "PASS" : "FAIL");
    if (!r.sha_ok || !r.failure_ok || !r.timing_ok || !r.cfo_ok || !r.corr_resid_ok) {
        std::printf("  crosscheck: sha_ok=%d failure_ok=%d timing_ok=%d cfo_ok=%d "
                    "corr_resid_ok=%d\n",
                    r.sha_ok ? 1 : 0, r.failure_ok ? 1 : 0, r.timing_ok ? 1 : 0,
                    r.cfo_ok ? 1 : 0, r.corr_resid_ok ? 1 : 0);
    }
    std::fflush(stdout);
}

// ---- integer timing sweep: +/-8 around the best integer timing -------------------
inline void print_timing_curve(const std::vector<std::complex<double>>& derot,
                               std::size_t best) {
    const std::vector<std::complex<double>> pre = iqrftrain::preamble_complex();
    const std::vector<std::complex<double>> pt =
        iqrftrain::payload_gain_training_complex();
    std::printf("# timing_curve best=%zu (preamble_corr payload_training_corr)\n", best);
    for (int d = -8; d <= 8; ++d) {
        const long long s = static_cast<long long>(best) + d;
        if (s < 0 || static_cast<std::size_t>(s + iqrftrain::kPayloadTrainingOffset +
                                             iqrftrain::kPayloadTrainingComplex) > derot.size())
            continue;
        const double pcorr =
            iqrfrec::detail::normalized_corr(derot, static_cast<std::size_t>(s), pre);
        const double ptcorr = iqdual23fix10::detail::fractional_reference_corr(
            derot, static_cast<std::size_t>(s + iqrftrain::kPayloadTrainingOffset), 0.0, pt);
        std::printf("TIMING %d %d %.9f %.9f\n", d, d == 0 ? 1 : 0, pcorr, ptcorr);
    }
    std::fflush(stdout);
}

// ---- fractional candidate grid: full [-0.5, +0.5] at 1/den -----------------------
// For every candidate f, run the production estimate() on the fractional-advanced
// capture and record: preamble corr (fractional), de-ramped training residual,
// payload-training corr/residual, gain/phase, fine CFO.  Mark the production choice
// (the runner's preamble-selected fraction) and the min-residual / max-corr candidates.
inline void print_fractional_curve(const std::vector<std::complex<double>>& derot,
                                   std::size_t best,
                                   const iqdual23fix10::CoarseCfoRecovery& production,
                                   const iqrfrec::EstimateConfig& cfg, int den) {
    if (den < 2) den = 2;
    const std::vector<std::complex<double>> pre = iqrftrain::preamble_complex();
    const double prod_frac = production.fractional_timing_samples;

    // First pass: cheap fractional corr + full estimate() per candidate, tracking the
    // three marks.
    double min_resid = std::numeric_limits<double>::infinity();
    double min_resid_frac = 0.0;
    double max_corr = -1.0;
    double max_corr_frac = 0.0;
    struct Row {
        double frac, pcorr, t_resid, pt_corr, pt_resid, gain, phase, cfo;
    };
    std::vector<Row> rows;
    rows.reserve(static_cast<std::size_t>(den) + 1);
    for (int q = -den / 2; q <= den / 2; ++q) {
        const double f = static_cast<double>(q) / static_cast<double>(den);
        const double pcorr =
            iqdual23fix10::detail::fractional_preamble_corr(derot, best, f, pre);
        const std::vector<std::complex<double>> aligned =
            iqdual23fix10::detail::apply_fractional_advance(derot, f);
        const iqrfrec::PerFileRecovery rec = iqrfrec::estimate(aligned, cfg);
        Row row;
        row.frac = f;
        row.pcorr = pcorr;
        row.t_resid = rec.training_residual;
        row.pt_corr = rec.payload_training_corr;
        row.pt_resid = rec.payload_training_residual;
        row.gain = rec.payload_gain_mag;
        row.phase = rec.payload_phase_deg;
        row.cfo = rec.cfo_hz;
        rows.push_back(row);
        if (row.pt_resid < min_resid) { min_resid = row.pt_resid; min_resid_frac = f; }
        if (row.pcorr > max_corr) { max_corr = row.pcorr; max_corr_frac = f; }
    }

    std::printf("# fractional_curve den=%d production=%.9f min_residual=%.9f "
                "max_corr=%.9f payload_best_fractional=%.9f\n",
                den, prod_frac, min_resid_frac, max_corr_frac,
                production.payload_best_fractional_timing_samples);
    std::printf("# cols: frac preamble_corr training_residual payload_training_corr "
                "payload_training_residual gain_mag phase_deg fine_cfo_hz mark\n");
    for (const Row& row : rows) {
        const char* mark = ".";
        if (near(row.frac, prod_frac, 0.5 / den + 1e-12)) mark = "production";
        else if (near(row.frac, min_resid_frac, 0.5 / den + 1e-12)) mark = "min_residual";
        else if (near(row.frac, max_corr_frac, 0.5 / den + 1e-12)) mark = "max_corr";
        std::printf("FRAC %.9f %.9f %.9f %.9f %.9f %.9f %.6f %.9f %s\n",
                    row.frac, row.pcorr, row.t_resid, row.pt_corr, row.pt_resid,
                    row.gain, row.phase, row.cfo, mark);
    }
    std::fflush(stdout);
}

// ---- self-test: clean single-burst recovery must be valid and near-perfect --------
inline int self_test() {
    // A deterministic non-zero payload, one full training-frame burst (single period).
    std::vector<std::int16_t> payload(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 37) / 37.0;
        payload[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1200.0 * std::cos(ph)));
        payload[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1200.0 * std::sin(ph)));
    }
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(payload);
    const auto rec = iqdual23fix10::recover_payload_with_coarse_cfo(
        iqrftrain::deinterleave(burst), config(2048.0), 1.0);
    if (!rec.rec.valid ||
        rec.payload_best_fractional_corr < 0.99 ||
        rec.rec.payload_training_residual > 1e-3) {
        std::fprintf(stderr,
                     "replay_fix10class24_failed_rx self-test: FAIL valid=%d failure=%s "
                     "payload_best_corr=%.9f payload_training_residual=%.9f\n",
                     rec.rec.valid ? 1 : 0, iqrfrec::failure_token(rec.rec.failure),
                     rec.payload_best_fractional_corr, rec.rec.payload_training_residual);
        return 1;
    }
    std::puts("replay_fix10class24_failed_rx self-test: PASS");
    return 0;
}

// ===========================================================================
// Canonical-reference replay mode (fix10class24-dualsdr2 Batch 2).
//
// The default (runtime) replay above uses iqrftrain::payload_gain_training_complex(),
// which is generated with runtime std::sqrt/std::lround and therefore DIVERGES across
// x86 (host) vs aarch64 (board): on the host that reference is da3fadf4... while the
// board (and the frozen canonical asset) is f06e9b3d....  The host therefore cannot
// reproduce the board's payload_training_corr/residual -- the cross-arch diagnostic
// blind spot that this mode fixes.
//
// This mode reproduces the BOARD's recovery by replacing the payload-training (and,
// for cleanliness, the preamble/tail) reference with the FROZEN CANONICAL components
// embedded in iq_fix10_canonical_frame_data.hpp (contracts/fix10_canonical_frame_v1,
// source_arch=aarch64).  No std::sqrt/std::lround dynamic reference generation is
// used, and the frozen bytes are verified (complex_count=1024, byte_count=4096,
// SHA256=f06e9b3d...) fail-closed at startup.  It REUSES the unchanged production
// recovery functions (iqrfrec::estimate / detail::ls_gain / fractional-timing /
// apply_fractional_advance) exactly like the Phase-D probe; the ONLY change vs the
// board is none -- the reference is made byte-identical to the board's aarch64 one.
// ===========================================================================

// Convert an interleaved int16 array (2N entries) to N complex doubles.
inline std::vector<std::complex<double>> canonical_complex(
        const std::array<std::int16_t, 2 * fix10canonical::kCanonicalComponentComplex>& v) {
    std::vector<std::complex<double>> out(fix10canonical::kCanonicalComponentComplex);
    for (std::size_t k = 0; k < out.size(); ++k)
        out[k] = std::complex<double>(static_cast<double>(v[2 * k]),
                                      static_cast<double>(v[2 * k + 1]));
    return out;
}

inline std::vector<std::complex<double>> canonical_preamble_complex() {
    return canonical_complex(fix10canonical::kCanonicalPreamble);
}
inline std::vector<std::complex<double>> canonical_payload_training_complex() {
    return canonical_complex(fix10canonical::kCanonicalPayloadTraining);
}

// Fail-closed verification of the frozen canonical components (the payload-training
// reference is the one whose cross-arch determinism matters; preamble/tail are also
// verified because canonical mode uses them as references).  Throws on any mismatch.
inline void verify_canonical_components() {
    if (fix10canonical::kCanonicalPayloadTraining.size() !=
        2 * fix10canonical::kCanonicalComponentComplex)
        throw std::runtime_error(
            "canonical: payload_training complex_count must be 1024 (int16 2048)");
    const std::string pt = sdr::Sha256::hex(
        fix10canonical::kCanonicalPayloadTraining.data(),
        fix10canonical::kCanonicalPayloadTraining.size() * sizeof(std::int16_t));
    if (pt != fix10canonical::kCanonicalPayloadTrainingSha)
        throw std::runtime_error("canonical: payload_training SHA256 mismatch: " + pt);
    const std::string pre = sdr::Sha256::hex(
        fix10canonical::kCanonicalPreamble.data(),
        fix10canonical::kCanonicalPreamble.size() * sizeof(std::int16_t));
    if (pre != fix10canonical::kCanonicalPreambleSha)
        throw std::runtime_error("canonical: preamble SHA256 mismatch: " + pre);
    const std::string tail = sdr::Sha256::hex(
        fix10canonical::kCanonicalTail.data(),
        fix10canonical::kCanonicalTail.size() * sizeof(std::int16_t));
    if (tail != fix10canonical::kCanonicalTailSha)
        throw std::runtime_error("canonical: tail SHA256 mismatch: " + tail);
}

// Fail-closed verification of an on-disk payload_training.ci16 asset against the frozen
// canonical component.  Rejects missing / wrong byte_count / wrong SHA / byte divergence.
inline void verify_canonical_file(const std::string& path) {
    const std::string raw = read_file(path);   // throws when missing
    if (raw.size() != 2 * fix10canonical::kCanonicalComponentInt16)
        throw std::runtime_error("canonical: byte_count must be 4096, got " +
                                 std::to_string(raw.size()));
    const std::string sha = sdr::Sha256::hex(raw.data(), raw.size());
    if (sha != fix10canonical::kCanonicalPayloadTrainingSha)
        throw std::runtime_error("canonical: payload_training SHA256 mismatch (tampered)");
    const std::vector<std::int16_t> v = read_ci16_le(path);
    if (v.size() != 2 * fix10canonical::kCanonicalComponentComplex)
        throw std::runtime_error("canonical: complex_count must be 1024");
    for (std::size_t i = 0; i < v.size(); ++i)
        if (v[i] != fix10canonical::kCanonicalPayloadTraining[i])
            throw std::runtime_error(
                "canonical: payload_training byte divergence at int16 index " +
                std::to_string(i));
}

// The canonical replay result + cross-check vs recovery_diagnostics.json.
struct CanonicalReplayResult {
    std::size_t timing_offset = 0;
    double coarse_cfo_hz = 0.0;
    double fine_cfo_hz = 0.0;
    double sro_ppm = 0.0;
    double fractional_timing_samples = 0.0;
    double payload_training_corr = 0.0;
    double payload_training_residual = 0.0;
    double payload_gain_mag = 0.0;
    double payload_phase_deg = 0.0;
    bool timing_ok = false;
    bool coarse_ok = false;
    bool fine_ok = false;
    bool corr_ok = false;
    bool resid_ok = false;
};

// Reproduce the board's recovery using the frozen canonical reference (the exact
// Phase-D probe logic), then cross-check the key fields against the dump's JSON.
// Documented tolerances (Phase-D probe on WSL g++ 15.2.0):
//   timing   exact
//   coarse   2e-2 Hz   (board -118.316 vs host -118.325)
//   fine     2e-2 Hz   (board -6.27395 vs host -6.26528)
//   corr     1e-5      (board 0.993317 vs host 0.9933165)
//   residual 1e-5      (board 0.116199 vs host 0.1161988)
inline CanonicalReplayResult replay_canonical_from_dir(const std::string& dir) {
    verify_canonical_components();
    const std::string raw_path = dir + "/raw_rx_ci16le.bin";
    const std::string json_path = dir + "/recovery_diagnostics.json";
    const std::string json = read_file(json_path);

    const double target_rms = json_num(json, "target_rms");
    const long long recorded_timing = json_int(json, "timing_offset");
    const double recorded_coarse = json_num(json, "coarse_cfo_hz");
    const double recorded_fine = json_num(json, "fine_cfo_hz");
    const double recorded_corr = json_num(json, "payload_training_corr");
    const double recorded_resid = json_num(json, "payload_training_residual");

    const std::vector<std::int16_t> iq = read_ci16_le(raw_path);
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(iq);
    const iqrfrec::EstimateConfig c = config(target_rms);

    const std::vector<std::complex<double>> pre_c = canonical_preamble_complex();
    const std::vector<std::complex<double>> pt_c = canonical_payload_training_complex();

    // Pass 1 (preamble is cross-arch deterministic, identical to the board's).
    const iqrfrec::PerFileRecovery r1 = iqrfrec::estimate(rx, c);
    const std::size_t best = r1.timing_offset;

    // Coarse CFO with the canonical payload-training reference (== the board's).
    const std::complex<double> a_pre = iqrfrec::detail::ls_gain(rx, best, pre_c);
    const std::complex<double> a_pt = iqrfrec::detail::ls_gain(
        rx, best + iqrftrain::kPayloadTrainingOffset, pt_c);
    const double coarse = std::arg(a_pt * std::conj(a_pre)) *
        static_cast<double>(iqrftrain::kFs) /
        (2.0 * iqrftrain::kPi * static_cast<double>(iqrftrain::kPayloadTrainingOffset));

    // De-rotate.
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * coarse *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }

    // Pass 2 + fractional timing (preamble deterministic).
    const iqrfrec::PerFileRecovery integer_rec = iqrfrec::estimate(derot, c);
    const iqdual23fix10::detail::FractionalTiming ft =
        iqdual23fix10::detail::estimate_fractional_timing(derot, integer_rec.timing_offset);
    const std::vector<std::complex<double>> aligned =
        iqdual23fix10::detail::apply_fractional_advance(derot, ft.samples);
    const iqrfrec::PerFileRecovery fin = iqrfrec::estimate(aligned, c);

    // Recompute the step-6.5 payload-training corr/residual with the canonical reference
    // (estimate() internally uses the runtime reference, so it is recomputed here exactly
    // as the board does, but with the canonical reference).
    const double sro_frac = fin.sro_ppm * 1e-6;
    const std::size_t bf = fin.timing_offset;
    const double cfo = fin.cfo_hz;
    const std::size_t ptoff = iqrftrain::kPayloadTrainingOffset;
    auto stretched = [&](std::size_t k) -> std::complex<double> {
        double x = static_cast<double>(ptoff + k) / (1.0 + sro_frac) -
                   static_cast<double>(ptoff);
        if (x < 0.0) x = 0.0;
        if (x > static_cast<double>(pt_c.size() - 1)) x = static_cast<double>(pt_c.size() - 1);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(x));
        const std::size_t i1 = i0 + 1;
        if (i1 < pt_c.size()) {
            const double fr = x - static_cast<double>(i0);
            return pt_c[i0] * (1.0 - fr) + pt_c[i1] * fr;
        }
        return pt_c[i0];
    };
    std::complex<double> num_pt(0.0, 0.0);
    double den_r_pt = 0.0, den_x_pt = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const std::complex<double> rk = stretched(k);
        const double ph = 2.0 * iqrftrain::kPi * cfo *
                          static_cast<double>(ptoff + k) / static_cast<double>(iqrftrain::kFs);
        const std::complex<double> derot_k(std::cos(ph), -std::sin(ph));
        const std::complex<double>& x = aligned[bf + ptoff + k];
        num_pt += x * std::conj(rk) * derot_k;
        den_r_pt += iqrfrec::detail::norm2(rk);
        den_x_pt += iqrfrec::detail::norm2(x);
    }
    const std::complex<double> a_pay = num_pt / den_r_pt;
    const double corr = std::abs(num_pt) / std::sqrt(den_x_pt * den_r_pt);
    double num_res = 0.0, den_res = 0.0;
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const std::complex<double> rk = stretched(k);
        const double ph = 2.0 * iqrftrain::kPi * cfo *
                          static_cast<double>(ptoff + k) / static_cast<double>(iqrftrain::kFs);
        const std::complex<double> rot(std::cos(ph), std::sin(ph));
        const std::complex<double> model = a_pay * rk * rot;
        const std::complex<double> err = aligned[bf + ptoff + k] - model;
        num_res += iqrfrec::detail::norm2(err);
        den_res += iqrfrec::detail::norm2(model);
    }
    const double residual = std::sqrt(num_res / den_res);

    CanonicalReplayResult r;
    r.timing_offset = fin.timing_offset;
    r.coarse_cfo_hz = coarse;
    r.fine_cfo_hz = fin.cfo_hz;
    r.sro_ppm = fin.sro_ppm;
    r.fractional_timing_samples = ft.samples;
    r.payload_training_corr = corr;
    r.payload_training_residual = residual;
    r.payload_gain_mag = std::abs(a_pay);
    r.payload_phase_deg = std::arg(a_pay) * 180.0 / iqrftrain::kPi;
    r.timing_ok = (fin.timing_offset == static_cast<std::size_t>(recorded_timing));
    r.coarse_ok = near(coarse, recorded_coarse, 2e-2);
    r.fine_ok = near(fin.cfo_hz, recorded_fine, 2e-2);
    r.corr_ok = near(corr, recorded_corr, 1e-5);
    r.resid_ok = near(residual, recorded_resid, 1e-5);
    return r;
}

inline void print_canonical_replay(const std::string& dir, const CanonicalReplayResult& r) {
    const bool ok = r.timing_ok && r.coarse_ok && r.fine_ok && r.corr_ok && r.resid_ok;
    std::printf("FIX10CLASS24_REPLAY_CANONICAL dump_dir=%s timing=%zu "
                "coarse_cfo_hz=%.9f fine_cfo_hz=%.9f sro_ppm=%.9f "
                "fractional_timing_samples=%.9f "
                "payload_training_corr=%.9f payload_training_residual=%.9f "
                "payload_gain_mag=%.9f payload_phase_deg=%.9f crosscheck=%s\n",
                dir.c_str(), r.timing_offset, r.coarse_cfo_hz, r.fine_cfo_hz, r.sro_ppm,
                r.fractional_timing_samples, r.payload_training_corr,
                r.payload_training_residual, r.payload_gain_mag, r.payload_phase_deg,
                ok ? "PASS" : "FAIL");
    if (!ok)
        std::printf("  canonical crosscheck: timing_ok=%d coarse_ok=%d fine_ok=%d "
                    "corr_ok=%d resid_ok=%d\n",
                    r.timing_ok ? 1 : 0, r.coarse_ok ? 1 : 0, r.fine_ok ? 1 : 0,
                    r.corr_ok ? 1 : 0, r.resid_ok ? 1 : 0);
    std::fflush(stdout);
}

// Compare the runtime (x86) training components against the frozen canonical ones.
// payload_training must GENUINELY DIFFER (that is the D1 cross-arch blind spot); the
// ZC preamble/tail are cross-arch byte-identical and must match.
struct ReferenceDiff {
    bool preamble_identical = false;
    bool payload_training_identical = false;
    bool tail_identical = false;
    std::size_t first_pt_diff_index = 0;
    std::int16_t runtime_value = 0;
    std::int16_t canonical_value = 0;
};

inline ReferenceDiff compare_canonical_vs_runtime() {
    const std::vector<std::int16_t> pre_rt = iqrftrain::preamble();
    const std::vector<std::int16_t> pt_rt = iqrftrain::payload_gain_training();
    const std::vector<std::int16_t> tail_rt = iqrftrain::tail();
    ReferenceDiff d;
    d.preamble_identical =
        (pre_rt.size() == fix10canonical::kCanonicalPreamble.size()) &&
        std::equal(pre_rt.begin(), pre_rt.end(), fix10canonical::kCanonicalPreamble.begin());
    d.payload_training_identical =
        (pt_rt.size() == fix10canonical::kCanonicalPayloadTraining.size()) &&
        std::equal(pt_rt.begin(), pt_rt.end(),
                   fix10canonical::kCanonicalPayloadTraining.begin());
    d.tail_identical =
        (tail_rt.size() == fix10canonical::kCanonicalTail.size()) &&
        std::equal(tail_rt.begin(), tail_rt.end(), fix10canonical::kCanonicalTail.begin());
    if (!d.payload_training_identical) {
        const std::size_t n = std::min(
            pt_rt.size(), fix10canonical::kCanonicalPayloadTraining.size());
        for (std::size_t i = 0; i < n; ++i)
            if (pt_rt[i] != fix10canonical::kCanonicalPayloadTraining[i]) {
                d.first_pt_diff_index = i;
                d.runtime_value = pt_rt[i];
                d.canonical_value = fix10canonical::kCanonicalPayloadTraining[i];
                break;
            }
    }
    return d;
}

inline void print_canonical_vs_runtime() {
    const ReferenceDiff d = compare_canonical_vs_runtime();
    std::printf("FIX10CLASS24_REFERENCE_DIFF preamble_identical=%d "
                "payload_training_identical=%d tail_identical=%d\n",
                d.preamble_identical ? 1 : 0, d.payload_training_identical ? 1 : 0,
                d.tail_identical ? 1 : 0);
    if (!d.payload_training_identical)
        std::printf("  payload_training FIRST_DIFF int16_index=%zu runtime=%d canonical=%d "
                    "delta=%d\n",
                    d.first_pt_diff_index, static_cast<int>(d.runtime_value),
                    static_cast<int>(d.canonical_value),
                    static_cast<int>(d.runtime_value) - static_cast<int>(d.canonical_value));
    std::fflush(stdout);
}

}  // namespace replay24
