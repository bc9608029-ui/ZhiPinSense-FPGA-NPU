#pragma once

// fix10prep1 clean-IQ diagnostic primitives.  This header is deliberately
// iCraft-free and libiio-free so the exact board evidence/gate contracts are
// host-testable.

#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <sys/stat.h>

namespace iqclean23fix10diag {

constexpr std::size_t kTensorFloats = 2u * 1024u;
constexpr std::size_t kTensorBytes = kTensorFloats * sizeof(float);
constexpr std::size_t kLogitFloats = 24u;
constexpr std::size_t kLogitBytes = kLogitFloats * sizeof(float);

struct AtomicDumpResult {
    bool ok = false;
    std::string path;
    std::string sha256;
    std::size_t bytes = 0;
    std::string error;
};

inline void require_directory(const std::string& path) {
    if (path.empty()) throw std::runtime_error("clean diagnostic: empty directory");
    if (::mkdir(path.c_str(), 0777) != 0 && errno != EEXIST)
        throw std::runtime_error("clean diagnostic: mkdir failed for " + path +
                                 ": " + std::strerror(errno));
}

inline AtomicDumpResult write_atomic(const std::string& dir,
                                     const std::string& file_name,
                                     const void* data, std::size_t bytes) {
    AtomicDumpResult r;
    r.path = dir + "/" + file_name;
    r.bytes = bytes;
    if (data == nullptr || bytes == 0) {
        r.error = "null-or-empty";
        return r;
    }
    r.sha256 = sdr::Sha256::hex(data, bytes);
    const std::string tmp = r.path + ".tmp";
    std::FILE* f = std::fopen(tmp.c_str(), "wb");
    if (!f) {
        r.error = "open:" + std::string(std::strerror(errno));
        return r;
    }
    const std::size_t n = std::fwrite(data, 1, bytes, f);
    const bool flushed = (std::fflush(f) == 0);
    const bool closed = (std::fclose(f) == 0);
    if (n != bytes || !flushed || !closed) {
        std::remove(tmp.c_str());
        r.error = "short-write-or-flush";
        return r;
    }
    if (std::rename(tmp.c_str(), r.path.c_str()) != 0) {
        r.error = "rename:" + std::string(std::strerror(errno));
        std::remove(tmp.c_str());
        return r;
    }
    r.ok = true;
    return r;
}

inline std::string file_stem(const std::string& file_name) {
    const std::size_t slash = file_name.find_last_of("/\\");
    const std::string base = slash == std::string::npos
                                 ? file_name : file_name.substr(slash + 1);
    const std::size_t dot = base.find_last_of('.');
    return dot == std::string::npos ? base : base.substr(0, dot);
}

struct TensorDiff {
    double max_abs_error = 0.0;
    double rms_error = 0.0;
};

inline TensorDiff tensor_diff(const float* actual, const float* reference,
                              std::size_t count) {
    if (!actual || !reference || count == 0)
        throw std::runtime_error("clean diagnostic: invalid tensor_diff input");
    TensorDiff d;
    long double e2 = 0.0L;
    for (std::size_t i = 0; i < count; ++i) {
        const double e = static_cast<double>(actual[i]) - reference[i];
        if (!std::isfinite(e))
            throw std::runtime_error("clean diagnostic: non-finite tensor value");
        d.max_abs_error = std::max(d.max_abs_error, std::fabs(e));
        e2 += static_cast<long double>(e) * e;
    }
    d.rms_error = std::sqrt(static_cast<double>(e2 / count));
    return d;
}

struct CleanGateInput {
    bool error_empty = true;
    bool baseline_identity_ok = false;
    std::size_t holdout_files = 0;
    std::size_t baseline_rows = 0;
    std::size_t scored = 0;
    std::size_t excluded = 0;
    std::size_t prediction_agreement_count = 0;
    std::size_t tensor_dump_count = 0;
    std::size_t logits_dump_count = 0;
};

struct CleanGateResult {
    bool pass = false;
    std::string report;
};

inline CleanGateResult evaluate_clean_gate(const CleanGateInput& g) {
    CleanGateResult r;
    auto fail = [&](const std::string& s) {
        if (!r.report.empty()) r.report += ",";
        r.report += s;
    };
    if (!g.error_empty) fail("error_nonempty");
    if (!g.baseline_identity_ok) fail("baseline_identity_ok=0");
    if (g.holdout_files == 0) fail("holdout_files=0");
    if (g.baseline_rows != g.holdout_files)
        fail("baseline_rows=" + std::to_string(g.baseline_rows) +
             ",want=" + std::to_string(g.holdout_files));
    if (g.scored != g.holdout_files)
        fail("scored=" + std::to_string(g.scored) +
             ",want=" + std::to_string(g.holdout_files));
    if (g.excluded != 0)
        fail("excluded=" + std::to_string(g.excluded) + ",want=0");
    if (g.prediction_agreement_count != g.scored)
        fail("prediction_agreement_count=" +
             std::to_string(g.prediction_agreement_count) +
             ",want=" + std::to_string(g.scored));
    if (g.tensor_dump_count != g.scored)
        fail("tensor_dump_count=" + std::to_string(g.tensor_dump_count) +
             ",want=" + std::to_string(g.scored));
    if (g.logits_dump_count != g.scored)
        fail("logits_dump_count=" + std::to_string(g.logits_dump_count) +
             ",want=" + std::to_string(g.scored));
    r.pass = r.report.empty();
    if (r.pass) r.report = "OK";
    return r;
}

}  // namespace iqclean23fix10diag
