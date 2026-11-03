// test_iq_rf_loopback_fix9r2g1_baseline_e2e.cpp -- fix9r2g1 end-to-end test of the
// baseline PRODUCTION/CONSUMPTION contract (this fix changes NO RF math, training
// block, model, threshold, or R8 condition).
//
// fix9r2g shipped a 5-column baseline generator (scripts/build_route_f_fix9r_exact_baseline.py)
// but the C++ loader (iq_rf_fix9r_baseline.hpp) requires 6 columns and fails closed on
// a 5-column row, so R8 would necessarily fail BEFORE any RF.  fix9r2g1 delivers the
// 6-column generator and a REAL frozen-model prediction TSV; this test proves the two
// ends agree end-to-end:
//
//   1. a REAL-format 24-column D2 manifest (46 holdout + 184 calibration) + a REAL-format
//      3-column prediction TSV are written;
//   2. the FORMAL Python generator is invoked (python3 -I, same argv the board uses);
//   3. its output is read back with the FORMAL C++ loader iqrffix9r::load_baseline()
//      and asserted to be 46 rows x 6 columns with the predictions preserved exactly;
//   4. a missing and a duplicate prediction are each shown to fail closed (non-zero
//      generator exit) -- the generator must NOT fall back to deployed_class.
//
// iCraft-free and libiio-free; the C++ side compiles identically on host and board.

#include "../board_package/iq_rf_fix9r_baseline.hpp"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

const char* kManifestHeader =
    "sample_index\tsource_index\traw24_class\tdeployed23_class\tmodulation\tsnr_db"
    "\tsplit_role\tglobal_K\toriginal_dc_i\toriginal_dc_q\tac_rms\trec_scale"
    "\tcomplex_count\tsample_rate\ttx_rms\ttx_peak\tclip_count\tedge_policy\tguard"
    "\toriginal_sha256\tquantized_sha256\trecovered_tensor_sha256\tquantized_file"
    "\trecovered_tensor_file";

const char* kPredHeader = "source_index\tfile_name\tfrozen_baseline_pred";

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

void write_text(const std::string& path, const std::string& text) {
    std::ofstream f(path, std::ios::binary);
    f.write(text.data(), static_cast<std::streamsize>(text.size()));
    f.close();
}

std::string hex64(std::uint64_t n) {
    static const char* d = "0123456789abcdef";
    std::string s(64, '0');
    for (int i = 63; i >= 0; --i) { s[static_cast<std::size_t>(i)] = d[n & 0xfu]; n >>= 4; }
    return s;
}

// Real-format 24-column D2 manifest row (same column order as
// build_route_d2_rf_artifacts.py MANIFEST_HEADER).  The generator only validates
// sample_index/deployed23_class/split_role/original_sha256/modulation, but every
// column is populated so the fixture matches the real board manifest shape.
std::string manifest_row(int sample, std::uint64_t source, int dep, const std::string& role,
                         const std::string& mod) {
    std::string sha = hex64(static_cast<std::uint64_t>(sample) + 1u);
    std::ostringstream o;
    o << sample << "\t" << source << "\t" << dep << "\t" << dep << "\t" << mod << "\t22.0\t"
      << role << "\t2048\t0.0\t0.0\t1.0\t128.0\t53760\t2560000\t2048.0\t2048.0\t0\tzero\t832\t"
      << sha << "\t" << sha << "\t" << sha << "\t"
      << "quantized_d2_2p56m_" << sample << ".ci16\t"
      << "recovered_tensor_d2_" << sample << ".f32";
    return o.str();
}

std::string write_manifest(const std::string& dir) {
    std::ostringstream o;
    o << kManifestHeader << "\n";
    for (int i = 0; i < 46; ++i)
        o << manifest_row(i, 1000u + static_cast<std::uint64_t>(i), i % 23, "holdout", "QPSK") << "\n";
    for (int i = 0; i < 184; ++i)
        o << manifest_row(1000 + i, 2000u + static_cast<std::uint64_t>(i), i % 23, "calibration", "QPSK") << "\n";
    const std::string path = dir + "/route_d2_rf_manifest.tsv";
    write_text(path, o.str());
    return path;
}

// 3-column prediction TSV.  `frozen` is deliberately DIFFERENT from the deployed
// label (i*7+3)%23, proving the generator attaches a model prediction rather than
// falling back to deployed_class.  `drop` omits one source_index; `dup` duplicates
// the first source_index (both must make the generator fail closed).
std::string write_predictions(const std::string& dir, bool drop, bool dup) {
    std::ostringstream o;
    o << kPredHeader << "\n";
    for (int i = 0; i < 46; ++i) {
        if (drop && i == 5) continue;  // omit source_index 1005
        o << (1000 + i) << "\tq_" << i << ".ci16\t" << ((i + 1) % 23) << "\n";
        if (dup && i == 0)             // duplicate source_index 1000
            o << "1000\tq_dup.ci16\t9\n";
    }
    const std::string path = dir + "/route_f_fix9r_predictions.tsv";
    write_text(path, o.str());
    return path;
}

// Run `python -I <generator> --d2-manifest m --predictions p --out o --expect-holdout 46`.
// Returns the child's exit status (WEXITSTATUS).
int run_generator(const std::string& python, const std::string& generator,
                  const std::string& manifest, const std::string& pred,
                  const std::string& out) {
    std::string cmd = python + " -I \"" + generator + "\" --d2-manifest \"" + manifest +
                      "\" --predictions \"" + pred + "\" --out \"" + out +
                      "\" --expect-holdout 46 >/dev/null 2>&1";
    const int status = ::system(cmd.c_str());
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return -1;
}

// The generator needs a python3 interpreter.  argv[2] (or FIX9R2G1_PYTHON) overrides
// the default "python3".
std::string pick_python(int argc, char** argv) {
    if (argc > 2) return argv[2];
    const char* env = std::getenv("FIX9R2G1_PYTHON");
    if (env && env[0]) return env;
    return "python3";
}

void test_roundtrip(const std::string& python, const std::string& generator) {
    const std::string dir = make_tmp_dir("rml23_fix9r2g1_e2e");
    const std::string manifest = write_manifest(dir);
    const std::string pred = write_predictions(dir, /*drop=*/false, /*dup=*/false);
    const std::string out = dir + "/route_f_fix9r_exact_baseline.tsv";

    const int code = run_generator(python, generator, manifest, pred, out);
    check(code == 0, "e2e: generator exit 0 (got " + std::to_string(code) + ")");
    if (code != 0) { ::rmdir(dir.c_str()); return; }

    // raw-file shape: header + 46 rows, every line 6 columns.
    {
        std::ifstream f(out);
        std::string line;
        int rows = 0;
        bool header6 = false;
        bool all6 = true;
        bool first = true;
        while (std::getline(f, line)) {
            if (line.empty()) continue;
            int cols = 1;
            for (char c : line) if (c == '\t') ++cols;
            if (first) { header6 = (cols == 6); first = false; }
            else { if (cols != 6) all6 = false; ++rows; }
        }
        check(header6, "e2e: baseline header has 6 columns");
        check(rows == 46, "e2e: baseline has 46 rows (got " + std::to_string(rows) + ")");
        check(all6, "e2e: every baseline row has 6 columns");
    }

    // formal C++ loader reads it back and preserves the model predictions exactly.
    const auto m = iqrffix9r::load_baseline(out, 23);
    check(m.size() == 46, "e2e: load_baseline() returns 46 rows");
    bool pred_ok = true;
    bool not_fallback = true;
    for (int i = 0; i < 46; ++i) {
        const std::uint64_t src = 1000u + static_cast<std::uint64_t>(i);
        auto it = m.find(src);
        if (it == m.end()) { pred_ok = false; continue; }
        const int frozen = (i + 1) % 23;
        if (it->second.frozen_baseline_pred != frozen) pred_ok = false;
        if (it->second.frozen_baseline_pred == it->second.deployed_class) not_fallback = false;
    }
    check(pred_ok, "e2e: frozen_baseline_pred preserved for all 46 sources");
    check(not_fallback, "e2e: frozen_baseline_pred != deployed_class (never a label fallback)");

    ::unlink(out.c_str());
    ::unlink(manifest.c_str());
    ::unlink(pred.c_str());
    ::rmdir(dir.c_str());
}

void test_missing_fail_closed(const std::string& python, const std::string& generator) {
    const std::string dir = make_tmp_dir("rml23_fix9r2g1_miss");
    const std::string manifest = write_manifest(dir);
    const std::string pred = write_predictions(dir, /*drop=*/true, /*dup=*/false);
    const std::string out = dir + "/baseline_missing.tsv";
    const int code = run_generator(python, generator, manifest, pred, out);
    check(code != 0, "e2e: missing prediction fails closed (exit " + std::to_string(code) + ")");
    ::unlink(manifest.c_str());
    ::unlink(pred.c_str());
    ::rmdir(dir.c_str());
}

void test_duplicate_fail_closed(const std::string& python, const std::string& generator) {
    const std::string dir = make_tmp_dir("rml23_fix9r2g1_dup");
    const std::string manifest = write_manifest(dir);
    const std::string pred = write_predictions(dir, /*drop=*/false, /*dup=*/true);
    const std::string out = dir + "/baseline_dup.tsv";
    const int code = run_generator(python, generator, manifest, pred, out);
    check(code != 0, "e2e: duplicate prediction fails closed (exit " + std::to_string(code) + ")");
    ::unlink(manifest.c_str());
    ::unlink(pred.c_str());
    ::rmdir(dir.c_str());
}
#else
void test_roundtrip(const std::string&, const std::string&) {}
void test_missing_fail_closed(const std::string&, const std::string&) {}
void test_duplicate_fail_closed(const std::string&, const std::string&) {}
#endif

}  // namespace

int main(int argc, char** argv) {
    std::printf("test_iq_rf_loopback_fix9r2g1_baseline_e2e\n");
    const std::string generator = (argc > 1 && argv[1][0])
            ? argv[1]
            : "../scripts/build_route_f_fix9r_exact_baseline.py";
    const std::string python = pick_python(argc, argv);

    test_roundtrip(python, generator);
    test_missing_fail_closed(python, generator);
    test_duplicate_fail_closed(python, generator);

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
