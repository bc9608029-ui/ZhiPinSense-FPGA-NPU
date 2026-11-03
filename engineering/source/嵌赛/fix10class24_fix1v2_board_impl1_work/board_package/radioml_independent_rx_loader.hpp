#pragma once

// radioml_independent_rx_loader.hpp -- fix10class24-independent-rx-delivery-fix1
// (+ fix1v2 board impl1): the fail-closed loader for the public-protocol TX package
// that the independent-rx board runner re-feeds through the real RF chain.
//
// It is iCraft-free and libiio-free (host-testable): it only parses the 10-column
// public_protocol_tx_manifest.tsv and verifies every `<source_index>.burst.i16`
// byte-for-byte, and never opens a device or runs the NPU.
//
// Unlike radioml_dualsdr_ab_loader.hpp (18/22-col per-class scale), this loader is
// CLASS-INDEPENDENT: the amplitude contract is the SAME uniform S = 1600/max_peak
// for every source.  S is DERIVED from the manifest's (source_id, conversion_version)
// pair -- the exact same-source binding as the PC TX package -- so the two frozen
// conversions are:
//
//   fix1-public-protocol-24waveforms      / v1 -> S = 117.84922023433009
//   fix1v2-waveform-corrected-24waveforms / v2 -> S =  71.609111379029812
//
// A v2 burst is byte-DIFFERENT from a v1 burst (the 4 AM classes were corrected,
// so max_peak changed and S changed), but the layout + recovery are IDENTICAL.  The
// loader accepts BOTH, and every row in one manifest must agree on the pair (a
// manifest is a single conversion run -- no mixing v1 and v2 rows).

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

namespace iqindepfix1 {

constexpr int kSourceCount = 24;
constexpr std::size_t kTotalBurstComplex = 59904;              // iqrftrain::kTotalBurstComplex
constexpr std::size_t kTotalBurstInt16 = 2 * kTotalBurstComplex;  // 119808
constexpr std::size_t kTotalBurstBytes = kTotalBurstInt16 * 2;     // 239616

// ---- frozen uniform amplitude contracts (class-independent) -------------------
// v1 (fix1-public-protocol-24waveforms): S = 1600/max_peak, max_peak(AM-SSB-WC)=13.576670230134553
constexpr double kTxDigitalScaleV1 = 117.84922023433009;
// v2 (fix1v2-waveform-corrected-24waveforms): S = 1600/max_peak, max_peak(AM-SSB-SC)=22.343525414400659
constexpr double kTxDigitalScaleV2 = 71.609111379029812;

inline const char* kSourceIdV1() { return "fix1-public-protocol-24waveforms"; }
inline const char* kSourceIdV2() { return "fix1v2-waveform-corrected-24waveforms"; }
inline const char* kConversionVersionV1() { return "v1"; }
inline const char* kConversionVersionV2() { return "v2"; }

// The exact 10-column manifest header (must match byte-for-byte).
inline const char* manifest_header_line() {
    return "source_id\tconversion_version\tsource_index\tclass_index\tclass_name\t"
           "seed\tburst_file\tburst_sha256\tpayload_ci16_sha256\tmodel_input_sha256";
}

struct IndependentRxFrame {
    std::string source_id;
    std::string conversion_version;
    int source_index = -1;         // 1..24 (explicit == class_index+1, not shuffled)
    int class_index = -1;          // 0..23 (scorer label only, never enters recovery/pred)
    std::string class_name;
    long long seed = -1;           // SEED_BASE + class_index (provenance)
    std::string burst_file;        // flat filename, e.g. "1.burst.i16"
    std::string burst_sha256;      // 64-hex SHA of the full burst .i16
    std::string payload_ci16_sha256;   // 64-hex SHA of the 1024-complex quantized payload
    std::string model_input_sha256;    // 64-hex SHA of the ORIGINAL [2,1024] f32 (A layer)
    // derived (uniform amplitude contract)
    double tx_scale = 0.0;         // S
    double unscale = 0.0;          // 1/S
};

// Split on '\t', preserving empty trailing fields (same semantics as the board's
// own split_tab / rmldsab::split_tab).
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

// Uniform scale lookup from the same-source pair.  Throws on an unknown pair.
inline double uniform_scale(const std::string& source_id,
                            const std::string& conversion_version) {
    if (source_id == kSourceIdV1() && conversion_version == kConversionVersionV1())
        return kTxDigitalScaleV1;
    if (source_id == kSourceIdV2() && conversion_version == kConversionVersionV2())
        return kTxDigitalScaleV2;
    throw std::runtime_error(
        "independent-rx: unknown (source_id, conversion_version) pair '" +
        source_id + "' / '" + conversion_version +
        "' (want fix1-public-protocol-24waveforms/v1 or "
        "fix1v2-waveform-corrected-24waveforms/v2)");
}

// Parse the whole TX package fail-closed: header exact, 24 rows, contiguous
// source_index == class_index+1, uniform source identity, every .burst.i16 exists
// (239616 bytes) and its SHA matches the manifest.  Throws on ANY mismatch.
inline std::vector<IndependentRxFrame> load_independent_rx_manifest(
        const std::string& tsv_path) {
    std::ifstream tsv(tsv_path);
    if (!tsv)
        throw std::runtime_error("independent-rx: cannot open manifest " + tsv_path);

    std::vector<IndependentRxFrame> frames;
    std::set<int> seen_index;
    std::set<std::string> seen_burst_file;
    std::set<std::string> seen_burst_sha;
    std::string line;
    int expected = 1;
    bool first = true;
    std::string manifest_source_id;
    std::string manifest_version;
    while (std::getline(tsv, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();  // CRLF tolerance
        if (line.empty()) continue;
        if (first) {
            first = false;
            if (line != manifest_header_line())
                throw std::runtime_error(
                    "independent-rx: manifest header mismatch: " + line);
            continue;
        }
        const std::vector<std::string> f = split_tab(line);
        if (f.size() != 10)
            throw std::runtime_error(
                "independent-rx: malformed manifest line (expected 10 columns, got " +
                std::to_string(f.size()) + "): " + line);

        IndependentRxFrame fr;
        fr.source_id = f[0];
        fr.conversion_version = f[1];
        fr.source_index = std::atoi(f[2].c_str());
        fr.class_index = std::atoi(f[3].c_str());
        fr.class_name = f[4];
        fr.seed = static_cast<long long>(std::atoll(f[5].c_str()));
        fr.burst_file = f[6];
        fr.burst_sha256 = f[7];
        fr.payload_ci16_sha256 = f[8];
        fr.model_input_sha256 = f[9];

        // one manifest == one conversion run
        if (manifest_source_id.empty()) {
            manifest_source_id = fr.source_id;
            manifest_version = fr.conversion_version;
        } else if (fr.source_id != manifest_source_id ||
                   fr.conversion_version != manifest_version) {
            throw std::runtime_error(
                "independent-rx: manifest mixes (source_id, conversion_version): '" +
                manifest_source_id + "'/'" + manifest_version + "' vs '" +
                fr.source_id + "'/'" + fr.conversion_version + "'");
        }

        fr.tx_scale = uniform_scale(fr.source_id, fr.conversion_version);
        fr.unscale = 1.0 / fr.tx_scale;

        if (fr.source_index != expected)
            throw std::runtime_error(
                "independent-rx: non-contiguous source_index " +
                std::to_string(fr.source_index) + " (expected " +
                std::to_string(expected) + ")");
        if (fr.class_index != fr.source_index - 1)
            throw std::runtime_error(
                "independent-rx: source_index must be class_index+1 (explicit, not "
                "shuffled); got source_index=" + std::to_string(fr.source_index) +
                " class_index=" + std::to_string(fr.class_index));
        if (fr.class_index < 0 || fr.class_index >= kSourceCount)
            throw std::runtime_error("independent-rx: class_index out of range: " +
                                     std::to_string(fr.class_index));
        if (fr.class_name.empty())
            throw std::runtime_error("independent-rx: empty class_name for source " +
                                     std::to_string(fr.source_index));
        if (fr.burst_file.empty() || fr.burst_file.find('/') != std::string::npos ||
            fr.burst_file.find('\\') != std::string::npos ||
            fr.burst_file.find("..") != std::string::npos)
            throw std::runtime_error("independent-rx: unsafe burst_file: " +
                                     fr.burst_file);
        if (fr.burst_sha256.size() != 64 || fr.payload_ci16_sha256.size() != 64 ||
            fr.model_input_sha256.size() != 64)
            throw std::runtime_error("independent-rx: a SHA field is not 64 hex for "
                                     "source " + std::to_string(fr.source_index));

        if (!seen_index.insert(fr.source_index).second)
            throw std::runtime_error("independent-rx: duplicate source_index " +
                                     std::to_string(fr.source_index));
        if (!seen_burst_file.insert(fr.burst_file).second)
            throw std::runtime_error("independent-rx: duplicate burst_file " +
                                     fr.burst_file);
        if (!seen_burst_sha.insert(fr.burst_sha256).second)
            throw std::runtime_error("independent-rx: duplicate burst_sha256 " +
                                     fr.burst_sha256);

        ++expected;
        frames.push_back(fr);
    }
    if (static_cast<int>(frames.size()) != kSourceCount)
        throw std::runtime_error("independent-rx: manifest has " +
                                 std::to_string(frames.size()) + " rows (want 24)");
    return frames;
}

// Verify one burst file byte-for-byte (size + SHA).  Throws on mismatch.
inline void verify_burst_file(const std::string& burst_path,
                              const IndependentRxFrame& fr) {
    std::ifstream f(burst_path, std::ios::binary);
    if (!f)
        throw std::runtime_error("independent-rx: cannot read burst " + burst_path);
    std::vector<char> buf((std::istreambuf_iterator<char>(f)),
                          std::istreambuf_iterator<char>());
    if (buf.size() != kTotalBurstBytes)
        throw std::runtime_error("independent-rx: " + fr.burst_file + " size " +
                                 std::to_string(buf.size()) + " != " +
                                 std::to_string(kTotalBurstBytes));
    const std::string got = sdr::Sha256::hex(buf.data(), buf.size());
    if (got != fr.burst_sha256)
        throw std::runtime_error("independent-rx: SHA-256 mismatch for " +
                                 fr.burst_file + " (manifest " + fr.burst_sha256 +
                                 ", file " + got + ")");
}

}  // namespace iqindepfix1
