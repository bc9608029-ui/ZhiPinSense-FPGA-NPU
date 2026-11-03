// test_recovery_fix2.cpp -- A-line fix2 cross-language verification (C++ vs Python).
//
// Pure offline.  Reads the 24 sliced real v2 dual-SDR bursts (exact int16 bytes the
// Python export_fix2_cpp_reference.py wrote from <sid>.raw.i16 after preamble locate),
// runs the fix2 public-reference recovery (estimate_public_reference + recover_model_input),
// and verifies, per frame, the fix2 metrics and the recovered v2 model-input tensor SHA
// against the Python reference:
//
//   timing_offset        : exact int (0 for all 24 here)
//   coarse_cfo_hz        : joint (cfo,tau) estimate  -- grid coordinate (exact)
//   fractional_timing    : joint tau                 -- grid coordinate (exact)
//   cfo_preamble_legacy_hz : old preamble two-half CFO (diagnostic, data-derived)
//   training_residual    : wide-linear residual (TX-ref, data-derived)
//   training_residual_rel: gain-independent gate statistic (data-derived)
//   model_input_sha256   : recovered [2,1024] f32 tensor SHA (v2 norm 1/71.609...)
//
// The grid coordinates (cfo,tau) must match EXACTLY (they are argmin grid indices, not
// floats computed from data); the data-derived doubles and the recovered tensor may carry
// a last-ULP difference from numpy-vs-C++ summation / sin-cos, so those are compared with
// a tight tolerance and the tensor SHA is reported as a match count.
//
// This proves the C++ fix2 recovery is byte-identical (modulo last-ULP) to the validated
// Python fix2 contract -- the fix1 independent-receive CFO bug is fixed in C++ too.

#include "../board_package/radioml_independent_rx_public_recovery.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

constexpr double kV2Unscale = 1.0 / 71.609111379029812;

std::vector<std::string> split_tab(const std::string& line) {
    std::vector<std::string> f;
    std::size_t s = 0;
    while (true) {
        const std::size_t p = line.find('\t', s);
        if (p == std::string::npos) { f.push_back(line.substr(s)); break; }
        f.push_back(line.substr(s, p - s));
        s = p + 1;
    }
    return f;
}

std::string trim_cr(std::string s) {
    if (!s.empty() && s.back() == '\r') s.pop_back();
    return s;
}

struct RefMetric {
    int timing_offset = 0;
    double coarse_cfo_hz = 0.0;
    double fractional_timing = 0.0;
    double cfo_preamble_legacy_hz = 0.0;
    double training_residual = 0.0;
    double training_residual_rel = 0.0;
};

std::map<int, RefMetric> load_metrics(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open " + path);
    std::map<int, RefMetric> m;
    std::string line;
    bool first = true;
    while (std::getline(f, line)) {
        line = trim_cr(line);
        if (line.empty()) continue;
        if (first) { first = false; continue; }
        const std::vector<std::string> c = split_tab(line);
        if (c.size() != 7)
            throw std::runtime_error("bad metrics row: " + line);
        RefMetric r;
        r.timing_offset = std::atoi(c[1].c_str());
        r.coarse_cfo_hz = std::atof(c[2].c_str());
        r.fractional_timing = std::atof(c[3].c_str());
        r.cfo_preamble_legacy_hz = std::atof(c[4].c_str());
        r.training_residual = std::atof(c[5].c_str());
        r.training_residual_rel = std::atof(c[6].c_str());
        m[std::atoi(c[0].c_str())] = r;
    }
    if (m.size() != 24)
        throw std::runtime_error("metrics has " + std::to_string(m.size()) + " rows (want 24)");
    return m;
}

std::map<int, std::string> load_sha(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open " + path);
    std::map<int, std::string> m;
    std::string line;
    bool first = true;
    while (std::getline(f, line)) {
        line = trim_cr(line);
        if (line.empty()) continue;
        if (first) { first = false; continue; }
        const std::vector<std::string> c = split_tab(line);
        if (c.size() != 2) throw std::runtime_error("bad sha row: " + line);
        m[std::atoi(c[0].c_str())] = c[1];
    }
    if (m.size() != 24)
        throw std::runtime_error("sha has " + std::to_string(m.size()) + " rows (want 24)");
    return m;
}

std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

std::vector<std::int16_t> read_i16(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot read " + path);
    f.seekg(0, std::ios::end);
    const std::streampos sz = f.tellg();
    f.seekg(0, std::ios::beg);
    if (sz < 0 || (sz % 2) != 0)
        throw std::runtime_error("bad i16 size " + path);
    std::vector<std::int16_t> out(static_cast<std::size_t>(sz) / 2);
    f.read(reinterpret_cast<char*>(out.data()), static_cast<std::streamsize>(sz));
    if (f.gcount() != sz) throw std::runtime_error("short read " + path);
    return out;
}

}  // namespace

int main(int argc, char** argv) {
    std::printf("test_recovery_fix2\n");
    std::string ref_dir;
    for (int i = 1; i + 1 < argc; ++i)
        if (std::string(argv[i]) == "--ref-dir") ref_dir = argv[i + 1];
    if (ref_dir.empty()) {
        std::printf("usage: test_recovery_fix2 --ref-dir <results/fix2_cpp_ref>\n");
        return 2;
    }

    try {
        const std::map<int, RefMetric> metrics = load_metrics(join_path(ref_dir, "metrics.tsv"));
        const std::map<int, std::string> sha = load_sha(join_path(ref_dir, "model_input_sha.tsv"));

        int cfo_exact = 0, tau_exact = 0, sha_match = 0;
        double max_cfo_err = 0.0, max_tau_err = 0.0, max_rr_err = 0.0;
        double max_resid_err = 0.0, max_legacy_err = 0.0;

        for (int sid = 1; sid <= 24; ++sid) {
            const std::vector<std::int16_t> i16 =
                read_i16(join_path(ref_dir, std::to_string(sid) + ".burst.i16"));
            if (i16.size() != 2 * iqindepfix1::kTotalBurstComplexPub)
                throw std::runtime_error("burst " + std::to_string(sid) +
                    " int16 count " + std::to_string(i16.size()));

            const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(i16);
            const iqindepfix1::PublicReference est =
                iqindepfix1::estimate_public_reference(rx);
            const RefMetric& r = metrics.at(sid);

            const double cfo_err = std::fabs(est.coarse_cfo_hz - r.coarse_cfo_hz);
            const double tau_err = std::fabs(est.fractional_timing - r.fractional_timing);
            const double legacy_err = std::fabs(est.cfo_preamble_legacy_hz - r.cfo_preamble_legacy_hz);
            const double resid_err = std::fabs(est.training_residual - r.training_residual);
            const double rr_err = std::fabs(est.training_residual_rel - r.training_residual_rel);
            if (cfo_err < 1e-9) ++cfo_exact;
            if (tau_err < 1e-12) ++tau_exact;
            max_cfo_err = std::max(max_cfo_err, cfo_err);
            max_tau_err = std::max(max_tau_err, tau_err);
            max_legacy_err = std::max(max_legacy_err, legacy_err);
            max_resid_err = std::max(max_resid_err, resid_err);
            max_rr_err = std::max(max_rr_err, rr_err);

            // legacy CFO is the OLD preamble two-half diagnostic (~±1100 Hz, kept only
            // for the old-vs-new comparison); angle(cB/cA) amplifies last-ULP vdot
            // differences, so 1e-4 Hz (~1e-7 relative) is the right tolerance -- the
            // joint cfo/tau/residual_rel are the values the gate actually uses.
            const bool metrics_ok = est.timing_offset == r.timing_offset &&
                                    cfo_err < 1e-9 && tau_err < 1e-12 &&
                                    legacy_err < 1e-4 && resid_err < 1e-9 &&
                                    rr_err < 1e-9;
            check(metrics_ok, "sid=" + std::to_string(sid) + " metrics match (cfo=" +
                  std::to_string(est.coarse_cfo_hz) + " tau=" +
                  std::to_string(est.fractional_timing) + " rr=" +
                  std::to_string(est.training_residual_rel) + ")");

            // recovered v2 model-input tensor + SHA
            const std::vector<std::complex<double>> zi =
                iqindepfix1::recover_model_input(rx, est, kV2Unscale);
            std::vector<float> tensor(2048, 0.0f);
            for (int k = 0; k < 1024; ++k) {
                tensor[static_cast<std::size_t>(k)] = static_cast<float>(zi[static_cast<std::size_t>(k)].real());
                tensor[static_cast<std::size_t>(1024 + k)] = static_cast<float>(zi[static_cast<std::size_t>(k)].imag());
            }
            const std::string got =
                sdr::Sha256::hex(tensor.data(), tensor.size() * sizeof(float));
            if (got == sha.at(sid)) ++sha_match;

            std::printf("  sid=%02d cfo=%8.2f/%8.2f tau=%+7.2f/%+7.2f rr=%.6f/%.6f "
                        "sha=%s\n", sid, est.coarse_cfo_hz, r.coarse_cfo_hz,
                        est.fractional_timing, r.fractional_timing,
                        est.training_residual_rel, r.training_residual_rel,
                        got == sha.at(sid) ? "OK" : "MISMATCH");
        }

        check(cfo_exact == 24, "joint CFO grid coordinate exact 24/24 (got " +
              std::to_string(cfo_exact) + "; max_err=" + std::to_string(max_cfo_err) + ")");
        check(tau_exact == 24, "joint tau grid coordinate exact 24/24 (got " +
              std::to_string(tau_exact) + "; max_err=" + std::to_string(max_tau_err) + ")");
        check(sha_match == 24, "recovered v2 model-input SHA == Python 24/24 (got " +
              std::to_string(sha_match) + ")");

        std::printf("  max_err: cfo=%.3e tau=%.3e legacy_cfo=%.3e residual=%.3e "
                    "residual_rel=%.3e\n", max_cfo_err, max_tau_err, max_legacy_err,
                    max_resid_err, max_rr_err);
        std::printf("  sha_match=%d/24\n", sha_match);
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION: %s\n", e.what());
        ++g_fail;
    }

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
