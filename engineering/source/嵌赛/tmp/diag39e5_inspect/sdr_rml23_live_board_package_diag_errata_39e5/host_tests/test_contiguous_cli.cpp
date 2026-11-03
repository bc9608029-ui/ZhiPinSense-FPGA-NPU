// test_contiguous_cli.cpp -- host tests for the Gate 6/9 multi-refill phase-jump
// fix + the CLI systematic-error fix (39e5 second batch follow-up).
//
// Covers:
//   (1) board::get_opt / board::opt_u64 / board::opt_d : both --key=value and
//       --key value spellings, later-occurrence-wins, and fail-closed on
//       missing / empty / invalid / out-of-range values.
//   (2) board::Continuity + board::capture_contiguous : the ONE shared
//       continuity rule Gate 6, Gate 9 and the §九 calibrator all gate on
//       (single refill into a large enough buffer).
//   (3) chain::PreprocessChain : a single contiguous push of a pure 10 kHz tone
//       yields `frames` clean tensors (ratio > 0.3), while the same tone pushed
//       in 8192-sample blocks with a phase discontinuity at each seam REPRODUCES
//       the low ratio (must NOT pass).
//
// iCraft-free and libiio-free (FakePlutoDevice only).  Build/run: see
// host_tests/build_host_tests.sh.  Compiled with -O2 -Wall -Wextra -Werror.

#include "../sdr_adapter/pluto_device.hpp"
#include "../board_package/board_common.hpp"
#include "../board_package/chain_common.hpp"

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s\n", what);
    }
}

void check_near(double got, double want, double tol, const char* what) {
    const bool ok = std::fabs(got - want) <= tol;
    if (ok) ++g_pass;
    else {
        ++g_fail;
        std::printf("  FAIL: %s (got %.9g want %.9g tol %.9g)\n", what, got, want, tol);
    }
}

// ---- CLI parsing ------------------------------------------------------------

// A stable argv built from string tokens (argv[0] is the program name).
struct Cli {
    std::vector<std::string> storage;
    std::vector<char*> argv;
    explicit Cli(const std::vector<std::string>& args) : storage(args) {
        argv.reserve(storage.size());
        for (auto& s : storage) argv.push_back(const_cast<char*>(s.c_str()));
    }
    int argc() const { return static_cast<int>(argv.size()); }
    char** ptr() { return argv.data(); }
};

void test_get_opt_forms() {
    Cli eq({"p", "--frames=32"});
    check(board::get_opt(eq.argc(), eq.ptr(), "--frames", "16") == "32",
          "get_opt: --key=value form");

    Cli sp({"p", "--frames", "32"});
    check(board::get_opt(sp.argc(), sp.ptr(), "--frames", "16") == "32",
          "get_opt: --key value form");

    Cli absent({"p"});
    check(board::get_opt(absent.argc(), absent.ptr(), "--frames", "16") == "16",
          "get_opt: absent returns default");
}

void test_get_opt_override() {
    Cli a({"p", "--frames=16", "--frames=32"});
    check(board::get_opt(a.argc(), a.ptr(), "--frames", "0") == "32",
          "get_opt: later = overrides earlier =");

    Cli b({"p", "--frames", "16", "--frames=32"});
    check(board::get_opt(b.argc(), b.ptr(), "--frames", "0") == "32",
          "get_opt: later = overrides earlier space");

    Cli c({"p", "--frames=32", "--frames", "16"});
    check(board::get_opt(c.argc(), c.ptr(), "--frames", "0") == "16",
          "get_opt: later space overrides earlier =");
}

void test_get_opt_missing() {
    Cli at_end({"p", "--frames"});
    bool threw = false;
    try { board::get_opt(at_end.argc(), at_end.ptr(), "--frames", "16"); }
    catch (const std::exception&) { threw = true; }
    check(threw, "get_opt: missing value at end throws");

    Cli then_flag({"p", "--frames", "--loopback=1"});
    threw = false;
    try { board::get_opt(then_flag.argc(), then_flag.ptr(), "--frames", "16"); }
    catch (const std::exception&) { threw = true; }
    check(threw, "get_opt: missing value before another --flag throws");
}

void test_opt_u64() {
    Cli ok({"p", "--frames=32"});
    check(board::opt_u64(ok.argc(), ok.ptr(), "--frames", 16) == 32ULL,
          "opt_u64: valid");

    Cli ov({"p", "--frames=16", "--frames=32"});
    check(board::opt_u64(ov.argc(), ov.ptr(), "--frames", 0) == 32ULL,
          "opt_u64: later value wins");

    Cli empty({"p", "--frames="});
    bool threw = false;
    try { board::opt_u64(empty.argc(), empty.ptr(), "--frames", 16); }
    catch (const std::exception&) { threw = true; }
    check(threw, "opt_u64: empty value throws (fail-closed)");

    Cli junk({"p", "--frames=abc"});
    threw = false;
    try { board::opt_u64(junk.argc(), junk.ptr(), "--frames", 16); }
    catch (const std::exception&) { threw = true; }
    check(threw, "opt_u64: non-integer throws");

    Cli trail({"p", "--frames=32x"});
    threw = false;
    try { board::opt_u64(trail.argc(), trail.ptr(), "--frames", 16); }
    catch (const std::exception&) { threw = true; }
    check(threw, "opt_u64: trailing junk throws");

    Cli range({"p", "--frames=99999999999999999999999"});
    threw = false;
    try { board::opt_u64(range.argc(), range.ptr(), "--frames", 16); }
    catch (const std::exception&) { threw = true; }
    check(threw, "opt_u64: out-of-range (ERANGE) throws");
}

void test_opt_d() {
    Cli ok({"p", "--rec-scale=4.096"});
    check_near(board::opt_d(ok.argc(), ok.ptr(), "--rec-scale", 1.0), 4.096, 1e-9,
               "opt_d: valid");

    Cli junk({"p", "--rec-scale=xyz"});
    bool threw = false;
    try { board::opt_d(junk.argc(), junk.ptr(), "--rec-scale", 1.0); }
    catch (const std::exception&) { threw = true; }
    check(threw, "opt_d: non-float throws");

    Cli empty({"p", "--rec-scale="});
    threw = false;
    try { board::opt_d(empty.argc(), empty.ptr(), "--rec-scale", 1.0); }
    catch (const std::exception&) { threw = true; }
    check(threw, "opt_d: empty value throws");
}

// ---- continuity rule --------------------------------------------------------

void test_continuity() {
    board::Continuity c;
    c.requested = 100; c.capacity = 200; c.refill_delta = 1; c.single_refill = true;
    check(c.ok(), "Continuity::ok() true when single_refill && capacity >= requested");
    check(c.capacity_ok(), "Continuity::capacity_ok() true when capacity >= requested");

    c.capacity = 50;
    check(!c.ok(), "Continuity::ok() false when capacity < requested");
    check(!c.capacity_ok(), "Continuity::capacity_ok() false when capacity < requested");

    c.capacity = 200; c.refill_delta = 2; c.single_refill = false;
    check(!c.ok(), "Continuity::ok() false when multi-refill (refill_delta != 1)");

    const std::string r = c.report();
    check(r.find("requested_input_complex=100") != std::string::npos, "report has requested");
    check(r.find("rx_buffer_capacity=200") != std::string::npos, "report has capacity");
    check(r.find("rx_refill_count_delta=2") != std::string::npos, "report has refill_delta");
    check(r.find("single_refill=0") != std::string::npos, "report has single_refill=0");
}

// ---- capture_contiguous (single refill + fail-closed) ------------------------

void test_capture_contiguous_ok() {
    pluto::FakePlutoDevice d;
    d.rx_tone_len = 400000;   // allow a large single refill
    std::vector<std::int16_t> iq;
    board::RxStats st;
    board::Continuity cont;
    const bool ok = board::capture_contiguous(d, 1000, iq, st, cont);
    check(ok, "capture_contiguous: single refill returns true");
    check(cont.single_refill, "capture_contiguous: single_refill=1");
    check(cont.refill_delta == 1, "capture_contiguous: refill_delta == 1");
    check(cont.capacity_ok(), "capture_contiguous: capacity >= requested");
    check(iq.size() / 2 == 1000, "capture_contiguous: delivered exactly requested");
}

void test_capture_contiguous_buffer_insufficient() {
    pluto::FakePlutoDevice d;
    d.rx_tone_len = 400000;
    d.rx_max_capacity = 500;   // request > capacity -> broken (ensure_rx_buffer fails)
    std::vector<std::int16_t> iq;
    board::RxStats st;
    board::Continuity cont;
    const bool ok = board::capture_contiguous(d, 1000, iq, st, cont);
    check(!ok, "capture_contiguous: buffer insufficient -> false (broken)");
    check(!cont.single_refill, "capture_contiguous: no refill attempted (broken)");
    check(cont.refill_delta == 0, "capture_contiguous: refill_delta == 0 (broken)");
}

void test_capture_contiguous_short() {
    pluto::FakePlutoDevice d;
    d.rx_tone_len = 100;   // returns fewer than requested -> short
    std::vector<std::int16_t> iq;
    board::RxStats st;
    board::Continuity cont;
    const bool ok = board::capture_contiguous(d, 1000, iq, st, cont);
    check(!ok, "capture_contiguous: short refill -> false");
    check(st.short_block, "capture_contiguous: short_block set");
    check(cont.single_refill, "capture_contiguous: one refill but short");
}

void test_capture_contiguous_timeout() {
    pluto::FakePlutoDevice d;
    d.rx_timed_out = true;
    std::vector<std::int16_t> iq;
    board::RxStats st;
    board::Continuity cont;
    const bool ok = board::capture_contiguous(d, 1000, iq, st, cont);
    check(!ok, "capture_contiguous: timeout -> false");
    check(st.timeouts == 1, "capture_contiguous: timeouts incremented");
}

// ---- PreprocessChain single-push vs multi-push phase-jump --------------------

constexpr double kPi = 3.14159265358979323846;

// Continuous interleaved int16 CW tone of length n.
std::vector<std::int16_t> tone_iq(double freq, double fs, std::size_t n, double amp = 1500.0) {
    std::vector<std::int16_t> iq(n * 2);
    const double ph = 2.0 * kPi * freq / fs;
    for (std::size_t k = 0; k < n; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(amp * std::cos(ph * k)));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::llround(amp * std::sin(ph * k)));
    }
    return iq;
}

// Goertzel ratio at freq on one reconstructed [2,1024] tensor.
double tensor_ratio(const std::vector<float>& t, double freq) {
    std::vector<std::complex<float>> x(chain::kFrameComplex);
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k)
        x[k] = std::complex<float>(t[k], t[chain::kFrameComplex + k]);
    return std::max(sdr::goertzel_ratio(x, freq, 128000.0),
                    sdr::goertzel_ratio(x, -freq, 128000.0));
}

void test_required_input() {
    chain::PreprocessChain chain(2560000, 0.0, 1.0f);
    check(chain.required_input(16) == 339661ULL,
          "required_input(16) @ 2.56M == 339661 (transient 600 + 16 frames)");
}

void test_single_refill_ratio() {
    const std::uint32_t fs_in = 2560000;
    const std::size_t frames = 16;
    chain::PreprocessChain chain(fs_in, 0.0, 1.0f);
    const std::size_t required = chain.required_input(frames);

    const std::vector<std::int16_t> iq = tone_iq(10000.0, static_cast<double>(fs_in), required);
    chain.push_int16(iq.data(), required);
    check(chain.ready() >= frames, "single push yields >= frames tensors");

    double ratio_min = 1e9;
    for (std::size_t i = 0; i < frames; ++i) {
        std::vector<float> t(chain::kTensorFloats);
        check(chain.pull_tensor(t.data()), "single push: pull tensor");
        const double r = tensor_ratio(t, 10000.0);
        if (r < ratio_min) ratio_min = r;
    }
    check(ratio_min > 0.3, "single-refill: every frame ratio > 0.3 (PASS)");
    check(ratio_min > 0.9, "single-refill: pure tone ratio > 0.9 (clean)");
}

// Reproduce the multi-refill bug: push 8192-sample blocks where each block is a
// clean tone but the phase DISCONTINUOUS at each seam (alternating +pi), which is
// what concatenating independent iio_buffer_refill results does.  The result must
// NOT pass the ratio_min > 0.3 gate.
void test_multi_refill_phase_jump() {
    const std::uint32_t fs_in = 2560000;
    const std::size_t frames = 16;
    chain::PreprocessChain chain(fs_in, 0.0, 1.0f);
    const std::size_t required = chain.required_input(frames);

    const double ph = 2.0 * kPi * 10000.0 / static_cast<double>(fs_in);
    const std::size_t chunk = 8192;
    std::size_t pushed = 0;
    std::size_t c = 0;
    std::vector<std::int16_t> buf;
    while (pushed < required) {
        const std::size_t n = std::min<std::size_t>(chunk, required - pushed);
        const double phase_off = (c % 2) ? kPi : 0.0;   // pi phase jump at each seam
        buf.resize(n * 2);
        for (std::size_t k = 0; k < n; ++k) {
            const double arg = ph * static_cast<double>(k) + phase_off;
            buf[k * 2 + 0] = static_cast<std::int16_t>(std::llround(1500.0 * std::cos(arg)));
            buf[k * 2 + 1] = static_cast<std::int16_t>(std::llround(1500.0 * std::sin(arg)));
        }
        chain.push_int16(buf.data(), n);
        pushed += n;
        ++c;
    }

    double ratio_min = 1e9;
    std::size_t pulled = 0;
    while (chain.ready() > 0 && pulled < frames) {
        std::vector<float> t(chain::kTensorFloats);
        if (!chain.pull_tensor(t.data())) break;
        ++pulled;
        const double r = tensor_ratio(t, 10000.0);
        if (r < ratio_min) ratio_min = r;
    }
    check(pulled == frames, "multi-refill: still produced frames");
    check(ratio_min < 0.3, "multi-refill phase-jump: ratio drops below 0.3 (must NOT pass)");
}

}  // namespace

int main() {
    std::printf("test_contiguous_cli\n");
    test_get_opt_forms();
    test_get_opt_override();
    test_get_opt_missing();
    test_opt_u64();
    test_opt_d();
    test_continuity();
    test_capture_contiguous_ok();
    test_capture_contiguous_buffer_insufficient();
    test_capture_contiguous_short();
    test_capture_contiguous_timeout();
    test_required_input();
    test_single_refill_ratio();
    test_multi_refill_phase_jump();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
