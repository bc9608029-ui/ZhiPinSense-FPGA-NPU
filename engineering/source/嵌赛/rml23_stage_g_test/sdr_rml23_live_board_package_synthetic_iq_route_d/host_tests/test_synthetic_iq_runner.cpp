// test_synthetic_iq_runner.cpp -- host tests for the Stage G injection tensor
// source (board_package/synthetic_iq_runner.hpp):
//   * route-A manifest parsing + fail-closed byte/SHA/label/size/index checks;
//   * route-B (model-input) and route-C (raw-rx) generated tensor production;
//   * the B-vs-C waveform fidelity through the runner's own functions (the
//     production 2.56M -> 128k chain, rec_scale = 2048/rms_counts = 128, so the
//     C tensors land at the same model-domain scale as B).
//
// iCraft-free and libiio-free: exercises only chain_common.hpp / resampler.cpp
// (the same code the board runs) plus the runner header.
//
// Build/run: see host_tests/build_host_tests.sh (links ../sdr_adapter/resampler.cpp).

#include "../board_package/synthetic_iq_runner.hpp"
#include "../board_package/synthetic_iq_generator.hpp"

#include <complex>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <unistd.h>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

void check_near(double got, double want, double tol, const char* what) {
    if (std::fabs(got - want) <= tol) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (got %.9g want %.9g)\n", what, got, want); }
}

template <typename F>
void check_throws(F fn, const char* what) {
    bool threw = false;
    try { fn(); } catch (...) { threw = true; }
    if (threw) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s (did not throw)\n", what); }
}

// --- split_tab --------------------------------------------------------------

void test_split_tab() {
    const auto f = syniq_run::split_tab("0\t100\tabc\t");
    check(f.size() == 4, "split_tab: 4 fields");
    check(f[0] == "0" && f[1] == "100" && f[2] == "abc" && f[3] == "",
          "split_tab: values + trailing empty preserved");
    const auto g = syniq_run::split_tab("x");
    check(g.size() == 1 && g[0] == "x", "split_tab: single field");
}

// --- source_class_index -----------------------------------------------------

void test_source_class_index() {
    check(syniq_run::source_class_index(syniq::Modulation::BPSK) == 3, "BPSK -> 3");
    check(syniq_run::source_class_index(syniq::Modulation::QPSK) == 4, "QPSK -> 4");
    check(syniq_run::source_class_index(syniq::Modulation::ASK4) == 1, "4ASK -> 1");
    check(syniq_run::source_class_index(syniq::Modulation::QAM16) == 12, "16QAM -> 12");
}

// --- route A fixture --------------------------------------------------------

std::string make_fixture_dir() {
    char tmpl[] = "/tmp/syniq_route_a_XXXXXX";
    char* d = mkdtemp(tmpl);
    if (!d) { std::printf("  mkdtemp failed\n"); std::exit(1); }
    return std::string(d);
}

void write_bin(const std::string& path, const std::vector<float>& floats) {
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(floats.data()),
            static_cast<std::streamsize>(floats.size() * sizeof(float)));
}

std::string sha_of_floats(const std::vector<float>& floats) {
    return sdr::Sha256::hex(floats.data(), floats.size() * sizeof(float));
}

// Build a minimal valid manifest (2 frames) and return the dir.
std::string make_valid_fixture(std::vector<float>& t0, std::vector<float>& t1,
                               std::string& sha0, std::string& sha1) {
    const std::string dir = make_fixture_dir();
    t0.assign(chain::kTensorFloats, 0.0f);
    t1.assign(chain::kTensorFloats, 0.0f);
    for (std::size_t k = 0; k < chain::kTensorFloats; ++k) {
        t0[k] = static_cast<float>(k) * 0.25f;
        t1[k] = static_cast<float>(k) * 0.5f + 1.0f;
    }
    sha0 = sha_of_floats(t0);
    sha1 = sha_of_floats(t1);
    write_bin(dir + "/input_0000.bin", t0);
    write_bin(dir + "/input_0001.bin", t1);
    std::ofstream tsv(dir + "/manifest_a.tsv");
    tsv << "0\t1000\t3\t20.0\t3\tBPSK\tinput_0000.bin\t" << sha0 << "\n";
    tsv << "1\t1001\t4\t22.0\t4\tQPSK\tinput_0001.bin\t" << sha1 << "\n";
    tsv.close();
    return dir;
}

void test_route_a_ok() {
    std::vector<float> t0, t1;
    std::string sha0, sha1;
    const std::string dir = make_valid_fixture(t0, t1, sha0, sha1);
    const auto frames = syniq_run::load_route_a(dir);
    check(frames.size() == 2, "route A: 2 frames loaded");
    check(frames[0].index == 0 && frames[0].source_index == 1000 &&
          frames[0].hdf5_label == 3 && frames[0].class_index == 3 &&
          frames[0].class_name == "BPSK" && frames[0].bin_sha256 == sha0,
          "route A: frame 0 fields parsed + SHA matched");
    check(std::fabs(frames[0].snr_db - 20.0) < 1e-9, "route A: frame 0 snr 20.0");
    check(frames[1].class_name == "QPSK" && frames[1].hdf5_label == 4,
          "route A: frame 1 fields");

    // Tensor load round-trips the exact bytes.
    std::vector<float> got(chain::kTensorFloats);
    syniq_run::load_route_a_tensor(frames[0], dir, got.data());
    check(got == t0, "route A: load_route_a_tensor round-trips frame 0");
    syniq_run::load_route_a_tensor(frames[1], dir, got.data());
    check(got == t1, "route A: load_route_a_tensor round-trips frame 1");

    std::remove((dir + "/manifest_a.tsv").c_str());
    std::remove((dir + "/input_0000.bin").c_str());
    std::remove((dir + "/input_0001.bin").c_str());
    ::rmdir(dir.c_str());
}

void test_route_a_fail_closed() {
    // missing manifest
    {
        const std::string dir = make_fixture_dir();
        check_throws([&]() { (void)syniq_run::load_route_a(dir); },
                     "route A: missing manifest_a.tsv throws");
        ::rmdir(dir.c_str());
    }
    // SHA mismatch
    {
        std::vector<float> t0, t1; std::string sha0, sha1;
        const std::string dir = make_valid_fixture(t0, t1, sha0, sha1);
        std::ofstream tsv(dir + "/manifest_a.tsv");  // rewrite with wrong sha
        tsv << "0\t1000\t3\t20.0\t3\tBPSK\tinput_0000.bin\t" << std::string(64, '0') << "\n";
        tsv.close();
        check_throws([&]() { (void)syniq_run::load_route_a(dir); },
                     "route A: SHA mismatch throws");
        std::remove((dir + "/manifest_a.tsv").c_str());
        std::remove((dir + "/input_0000.bin").c_str());
        std::remove((dir + "/input_0001.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // size mismatch (write a short bin)
    {
        std::vector<float> t0, t1; std::string sha0, sha1;
        const std::string dir = make_valid_fixture(t0, t1, sha0, sha1);
        write_bin(dir + "/input_0000.bin", std::vector<float>(100, 1.0f));
        check_throws([&]() { (void)syniq_run::load_route_a(dir); },
                     "route A: size != 8192 throws");
        std::remove((dir + "/manifest_a.tsv").c_str());
        std::remove((dir + "/input_0000.bin").c_str());
        std::remove((dir + "/input_0001.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // label mismatch (hdf5_label != class_index)
    {
        std::vector<float> t0, t1; std::string sha0, sha1;
        const std::string dir = make_valid_fixture(t0, t1, sha0, sha1);
        std::ofstream tsv(dir + "/manifest_a.tsv");
        tsv << "0\t1000\t4\t20.0\t3\tBPSK\tinput_0000.bin\t" << sha0 << "\n";
        tsv.close();
        check_throws([&]() { (void)syniq_run::load_route_a(dir); },
                     "route A: hdf5_label != class_index throws");
        std::remove((dir + "/manifest_a.tsv").c_str());
        std::remove((dir + "/input_0000.bin").c_str());
        std::remove((dir + "/input_0001.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // non-contiguous index
    {
        std::vector<float> t0, t1; std::string sha0, sha1;
        const std::string dir = make_valid_fixture(t0, t1, sha0, sha1);
        std::ofstream tsv(dir + "/manifest_a.tsv");
        tsv << "0\t1000\t3\t20.0\t3\tBPSK\tinput_0000.bin\t" << sha0 << "\n";
        tsv << "2\t1001\t4\t22.0\t4\tQPSK\tinput_0001.bin\t" << sha1 << "\n";
        tsv.close();
        check_throws([&]() { (void)syniq_run::load_route_a(dir); },
                     "route A: non-contiguous index throws");
        std::remove((dir + "/manifest_a.tsv").c_str());
        std::remove((dir + "/input_0000.bin").c_str());
        std::remove((dir + "/input_0001.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // unsafe bin_file ("../")
    {
        std::vector<float> t0, t1; std::string sha0, sha1;
        const std::string dir = make_valid_fixture(t0, t1, sha0, sha1);
        std::ofstream tsv(dir + "/manifest_a.tsv");
        tsv << "0\t1000\t3\t20.0\t3\tBPSK\t../secret.bin\t" << sha0 << "\n";
        tsv.close();
        check_throws([&]() { (void)syniq_run::load_route_a(dir); },
                     "route A: unsafe bin_file throws");
        std::remove((dir + "/manifest_a.tsv").c_str());
        std::remove((dir + "/input_0000.bin").c_str());
        std::remove((dir + "/input_0001.bin").c_str());
        ::rmdir(dir.c_str());
    }
    // empty manifest
    {
        const std::string dir = make_fixture_dir();
        std::ofstream tsv(dir + "/manifest_a.tsv");
        tsv << "\n";
        tsv.close();
        check_throws([&]() { (void)syniq_run::load_route_a(dir); },
                     "route A: empty manifest throws");
        std::remove((dir + "/manifest_a.tsv").c_str());
        ::rmdir(dir.c_str());
    }
}

// --- route B ----------------------------------------------------------------

void test_route_b() {
    syniq_run::GeneratedConfig cfg;
    cfg.mod = syniq::Modulation::QPSK;
    cfg.sps = 8;
    cfg.seed = 0x39e5ULL;
    cfg.norm = "none";

    const int frames = 4;
    const auto t = syniq_run::generate_model_input_tensors(cfg, frames);
    check(static_cast<int>(t.size()) == frames, "route B: frames count");
    bool all2048 = true;
    for (const auto& v : t) if (v.size() != chain::kTensorFloats) all2048 = false;
    check(all2048, "route B: every tensor has 2048 floats");

    // natural RMS ~ 1.0 (unit-power constellation + unit-energy RRC)
    double e = 0.0;
    std::size_t n = 0;
    for (const auto& v : t)
        for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
            e += static_cast<double>(v[k]) * v[k] + static_cast<double>(v[chain::kFrameComplex + k]) * v[chain::kFrameComplex + k];
            ++n;
        }
    check_near(std::sqrt(e / n), 1.0, 0.05, "route B: complex RMS ~ 1.0");

    // determinism
    const auto t2 = syniq_run::generate_model_input_tensors(cfg, frames);
    check(t == t2, "route B: deterministic");

    // complex-rms-1 sets RMS exactly 1.0
    cfg.norm = "complex-rms-1";
    const auto tr = syniq_run::generate_model_input_tensors(cfg, frames);
    double er = 0.0;
    for (const auto& v : tr)
        for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
            er += static_cast<double>(v[k]) * v[k] + static_cast<double>(v[chain::kFrameComplex + k]) * v[chain::kFrameComplex + k];
    check_near(std::sqrt(er / n), 1.0, 1e-6, "route B: complex-rms-1 RMS == 1.0");

    // fail-closed
    cfg.sps = 160;
    check_throws([&]() { (void)syniq_run::generate_model_input_tensors(cfg, frames); },
                 "route B: sps != 8 throws");
    cfg.sps = 8;
    check_throws([&]() { (void)syniq_run::generate_model_input_tensors(cfg, 0); },
                 "route B: frames < 1 throws");
}

// --- route C ----------------------------------------------------------------

void test_route_c() {
    syniq_run::GeneratedConfig cfg;
    cfg.mod = syniq::Modulation::QPSK;
    cfg.sps = 160;
    cfg.seed = 0x39e5ULL;
    cfg.norm = "none";
    cfg.rms_counts = 16.0;

    const int frames = 4;
    const auto out = syniq_run::generate_raw_rx_tensors(cfg, frames);
    check(static_cast<int>(out.tensors.size()) == frames, "route C: frames count");
    bool all2048 = true;
    for (const auto& v : out.tensors) if (v.size() != chain::kTensorFloats) all2048 = false;
    check(all2048, "route C: every tensor has 2048 floats");
    check_near(out.quant.rms_counts, 16.0, 1.0, "route C: quant RMS ~ 16 counts");
    check(out.quant.peak_counts < 32768.0, "route C: quant peak within int16");
    check(out.quant.clip == 0, "route C: no clipping at 16 counts");

    const auto out2 = syniq_run::generate_raw_rx_tensors(cfg, frames);
    check(out.tensors == out2.tensors, "route C: deterministic tensors");

    cfg.sps = 8;
    check_throws([&]() { (void)syniq_run::generate_raw_rx_tensors(cfg, frames); },
                 "route C: sps != 160 throws");
    cfg.sps = 160;
    check_throws([&]() { (void)syniq_run::generate_raw_rx_tensors(cfg, 0); },
                 "route C: frames < 1 throws");
}

// --- B-vs-C fidelity through the runner functions ---------------------------

std::vector<std::complex<double>> concat_complex(
        const std::vector<std::vector<float>>& tensors) {
    std::vector<std::complex<double>> out;
    for (const auto& v : tensors)
        for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
            out.emplace_back(static_cast<double>(v[k]),
                             static_cast<double>(v[chain::kFrameComplex + k]));
    return out;
}

struct AlignResult { double nmse; int offset; double gain_db; };

AlignResult align_nmse(const std::vector<std::complex<double>>& ref,
                       const std::vector<std::complex<double>>& meas,
                       int max_offset) {
    const std::size_t Lr = ref.size(), Lm = meas.size();
    double best = 1e300; int best_o = 0; double best_g = 0.0;
    for (int o = -max_offset; o <= max_offset; ++o) {
        const int lo = std::max(0, -o);
        const int hi = static_cast<int>(std::min(
            static_cast<long long>(Lr),
            static_cast<long long>(Lm) - static_cast<long long>(o)));
        if (hi - lo < 1024) continue;
        std::complex<double> num(0, 0), den(0, 0);
        for (int i = lo; i < hi; ++i) {
            const auto& r = ref[static_cast<std::size_t>(i)];
            const auto& m = meas[static_cast<std::size_t>(i + o)];
            num += r * std::conj(m);
            den += m * std::conj(m);
        }
        if (std::abs(den) < 1e-30) continue;
        const std::complex<double> g = num / den;
        double err = 0.0, refl = 0.0;
        for (int i = lo; i < hi; ++i) {
            const auto e = ref[static_cast<std::size_t>(i)] -
                           g * meas[static_cast<std::size_t>(i + o)];
            err += std::norm(e);
            refl += std::norm(ref[static_cast<std::size_t>(i)]);
        }
        const double nmse = err / refl;
        if (nmse < best) { best = nmse; best_o = o; best_g = std::abs(g); }
    }
    return {best, best_o, 20.0 * std::log10(best_g)};
}

void test_bc_fidelity_runner() {
    const syniq::Modulation m = syniq::Modulation::QPSK;
    const int frames = 8;

    syniq_run::GeneratedConfig cb;
    cb.mod = m; cb.sps = 8; cb.seed = 0x39e5ULL; cb.norm = "none";
    const auto b = concat_complex(syniq_run::generate_model_input_tensors(cb, frames));

    syniq_run::GeneratedConfig cc;
    cc.mod = m; cc.sps = 160; cc.seed = 0x39e5ULL; cc.norm = "none"; cc.rms_counts = 16.0;
    const auto c = concat_complex(syniq_run::generate_raw_rx_tensors(cc, frames).tensors);

    check(c.size() >= b.size(), "runner B-vs-C: C long enough to cover B");
    const AlignResult r = align_nmse(b, c, 2048);
    std::printf("  runner B-vs-C: nmse=%.3e (%.1f dB) offset=%d gain=%.3f dB\n",
                r.nmse, 10.0 * std::log10(r.nmse), r.offset, r.gain_db);
    check(r.offset == -585, "runner B-vs-C: offset == -585 (transient discard)");
    // rec_scale = 2048/rms_counts = 128 maps the 16-count int16 back to unit RMS,
    // so C's tensors land at the SAME model-domain scale as B -> gain == 1.0 (0 dB).
    check_near(r.gain_db, 0.0, 0.5, "runner B-vs-C: gain == 1.0 (0 dB) at model domain");
    check(r.nmse < 0.005, "runner B-vs-C: NMSE < 0.005 (decimation preserved the waveform)");
}

}  // namespace

int main() {
    std::printf("test_synthetic_iq_runner\n");
    test_split_tab();
    test_source_class_index();
    test_route_a_ok();
    test_route_a_fail_closed();
    test_route_b();
    test_route_c();
    test_bc_fidelity_runner();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
