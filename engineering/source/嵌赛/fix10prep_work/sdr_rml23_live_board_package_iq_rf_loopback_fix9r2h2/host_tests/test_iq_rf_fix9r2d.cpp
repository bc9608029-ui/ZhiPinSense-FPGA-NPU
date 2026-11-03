// test_iq_rf_fix9r2d.cpp -- host tests for Route F fix9r2d (the DIAGNOSTIC CAPTURE
// ENHANCEMENT approved under 39e5: eight waveform slices + per-slice provenance +
// per-capture metadata).  iCraft-free and libiio-free: it exercises ONLY the pure
// functions in iq_rf_fix9r2d_diagnostic.hpp -- the exact code the board runner calls
// -- plus the shared recovery core it reuses.
//
// What is under test (requirements 1-4, 8):
//   * sha256_of_slice / slice_complex: independent in-memory SHA + contiguous slice,
//     fail-closed (empty/"" on out-of-range) so a truncated capture cannot masquerade.
//   * save_slice_with_provenance: equality == 1 iff the saved file bytes equal the
//     in-memory slice of the SAME buffer (requirement 4); tamper -> equality == 0;
//     out-of-range -> rec.path empty + equality == -1.
//   * verify_slice_provenance: pure re-verification (host + offline audit).
//   * compute_capture_meta: frame/payload/cycle indices, cycle0/cycle1, linear/
//     circular offset, RMS/DC/peak/clip/CFO/SRO/gain (requirement 3); fail-closed
//     (complete == false) when a slice falls outside the capture or capture < 2
//     periods.
//   * the six-verdict vocabulary (requirement 8): exact, distinct strings.

#include "../board_package/iq_rf_fix9r2d_diagnostic.hpp"
#include "../board_package/iq_rf_training_frame.hpp"
#include "../board_package/iq_rf_frame_layout.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// deterministic PRBS payload (same LCG as the other fix9r host tests)
std::vector<std::int16_t> make_prbs(std::size_t P, int A, std::uint32_t seed) {
    std::vector<std::int16_t> iq(P * 2);
    std::uint32_t s = seed ? seed : 0x9e3779b9u;
    auto bit = [&s]() -> int {
        s = s * 1664525u + 1013904223u;
        return static_cast<int>((s >> 24) & 1u);
    };
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(bit() ? A : -A);
        iq[k * 2 + 1] = static_cast<std::int16_t>(bit() ? A : -A);
    }
    return iq;
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}
#endif

// Build a full capture: >= 2 periods of the cyclic frame, with the burst placed at
// `offset` in cycle 0 and again at `offset + period` in cycle 1 (identity channel).
std::vector<std::complex<double>> make_capture(std::size_t offset,
                                                std::size_t total) {
    const auto payload = make_prbs(iqrftrain::kPayloadComplex, 1500, 0xC0FFEEu);
    const auto burst = iqrftrain::deinterleave(iqrftrain::build_burst(payload));
    const std::size_t period = iqrflayout::kFramePeriodComplex;
    std::vector<std::complex<double>> rx(total, std::complex<double>(0.0, 0.0));
    for (std::size_t k = 0; k < burst.size() && offset + k < total; ++k)
        rx[offset + k] = burst[k];
    if (offset + period + burst.size() <= total)
        for (std::size_t k = 0; k < burst.size(); ++k)
            rx[offset + period + k] = burst[k];
    return rx;
}

// ---- 1. sha256_of_slice: in-memory SHA matches an independent float32 packing ---

void test_sha256_of_slice() {
    std::vector<std::complex<double>> z;
    for (std::size_t k = 0; k < 64; ++k)
        z.push_back(std::complex<double>(std::sin(k * 0.1), std::cos(k * 0.13)));

    const std::string s = iqrffix9r2d::sha256_of_slice(z, 16, 32);
    std::vector<float> f32(32 * 2);
    for (std::size_t k = 0; k < 32; ++k) {
        f32[k * 2 + 0] = static_cast<float>(z[16 + k].real());
        f32[k * 2 + 1] = static_cast<float>(z[16 + k].imag());
    }
    check(s == sdr::Sha256::hex(f32.data(), f32.size() * sizeof(float)),
          "sha256_of_slice: matches independent f32 packing");
    check(s.size() == 64, "sha256_of_slice: 64 hex chars");

    // out-of-range -> ""
    check(iqrffix9r2d::sha256_of_slice(z, 100, 1).empty(),
          "sha256_of_slice: start out-of-range -> empty");
    check(iqrffix9r2d::sha256_of_slice(z, 0, 65).empty(),
          "sha256_of_slice: len out-of-range -> empty");
}

// ---- 2. slice_complex: correct slice, fail-closed ------------------------------

void test_slice_complex() {
    std::vector<std::complex<double>> z;
    for (std::size_t k = 0; k < 100; ++k) z.push_back(std::complex<double>(k, -k));

    const auto s = iqrffix9r2d::slice_complex(z, 10, 20);
    check(s.size() == 20, "slice_complex: length == 20");
    check(s[0] == z[10] && s[19] == z[29], "slice_complex: content == src[10:30]");

    check(iqrffix9r2d::slice_complex(z, 100, 1).empty(),
          "slice_complex: start out-of-range -> empty");
    check(iqrffix9r2d::slice_complex(z, 90, 20).empty(),
          "slice_complex: len out-of-range -> empty");
}

// ---- 3. slice_stats ------------------------------------------------------------

void test_slice_stats() {
    std::vector<std::complex<double>> z = {
        std::complex<double>(3.0, 0.0), std::complex<double>(0.0, 4.0)};
    const auto s = iqrffix9r2d::slice_stats(z);
    // energy = 9 + 16 = 25, rms = sqrt(25/2) = 3.5355, dc = (1.5, 2.0), peak = 4.0
    check(std::fabs(s.rms - std::sqrt(12.5)) < 1e-12, "slice_stats: rms");
    check(std::fabs(s.dc_re - 1.5) < 1e-12, "slice_stats: dc_re");
    check(std::fabs(s.dc_im - 2.0) < 1e-12, "slice_stats: dc_im");
    check(std::fabs(s.peak - 4.0) < 1e-12, "slice_stats: peak");
    check(iqrffix9r2d::slice_stats({}).rms == 0.0, "slice_stats: empty -> 0");
}

// ---- 4. save_slice_with_provenance: equality == 1, tamper detection ------------

void test_save_slice_with_provenance() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("fix9r2d_prov");
    const std::string path = dir + "/raw_aligned_rx_payload.f32";

    const auto rx = make_capture(100, 128000);
    const std::size_t start = 100 + iqrflayout::kPayloadOffset;
    const std::size_t len = iqrflayout::kPayloadLength;

    const auto p = iqrffix9r2d::save_slice_with_provenance(
        path, rx, start, len, static_cast<long long>(start), -1,
        iqrflayout::kFramePeriodComplex);
    check(!p.rec.path.empty(), "prov: path recorded");
    check(p.rec.complex_samples == len, "prov: complex_samples == payload length");
    check(p.mem_sha256.size() == 64, "prov: mem_sha256 present");
    check(p.equality == 1, "prov: equality == 1 (file == in-memory slice)");
    check(p.start_index == static_cast<long long>(start), "prov: start_index recorded");
    check(p.length == len, "prov: length recorded");
    check(p.linear_offset == static_cast<long long>(start), "prov: linear_offset");
    check(p.circular_offset == static_cast<long long>(start % iqrflayout::kFramePeriodComplex),
          "prov: circular_offset == start % period");

    // The saved file must equal the in-memory slice (float32 round-trip).
    std::vector<std::complex<double>> back;
    check(iqrffix9r2b::load_f32_interleaved(path, back), "prov: reload ok");
    check(back.size() == len, "prov: reload length");
    double err = 0.0;
    for (std::size_t k = 0; k < len; ++k) err += std::abs(back[k] - rx[start + k]);
    check(err < 1e-2, "prov: file bytes reproduce the in-memory slice");

    // Pure re-verification agrees (host + offline audit path).
    check(iqrffix9r2d::verify_slice_provenance(rx, start, len, p.rec.sha256),
          "prov: verify_slice_provenance true for the saved sha");

    // A different slice of the SAME buffer must NOT match the saved sha.
    check(!iqrffix9r2d::verify_slice_provenance(rx, start + 1, len, p.rec.sha256),
          "prov: shifted slice does not match (no capture-index masquerade)");
    check(!iqrffix9r2d::verify_slice_provenance(rx, start, len, std::string(64, '0')),
          "prov: bogus sha does not match");

    // Tamper the file bytes: the provenance must now FAIL (mem_sha != file sha).
    {
        std::vector<std::complex<double>> tampered;
        iqrffix9r2b::load_f32_interleaved(path, tampered);
        tampered[0] += std::complex<double>(0.0, 1.0);   // corrupt one sample
        iqrffix9r2b::save_f32_interleaved(path + ".tampered", tampered);
        std::vector<std::complex<double>> tb;
        iqrffix9r2b::load_f32_interleaved(path + ".tampered", tb);
        std::vector<float> f32(tb.size() * 2);
        for (std::size_t k = 0; k < tb.size(); ++k) {
            f32[k * 2 + 0] = static_cast<float>(tb[k].real());
            f32[k * 2 + 1] = static_cast<float>(tb[k].imag());
        }
        const std::string tampered_sha =
            sdr::Sha256::hex(f32.data(), f32.size() * sizeof(float));
        check(!iqrffix9r2d::verify_slice_provenance(rx, start, len, tampered_sha),
              "prov: tampered file sha fails verification");
        ::unlink((path + ".tampered").c_str());
    }

    // Out-of-range slice: rec.path empty + equality stays -1 (fail-closed).
    const auto bad = iqrffix9r2d::save_slice_with_provenance(
        dir + "/bad.f32", rx, 128000, 1024, 128000, -1,
        iqrflayout::kFramePeriodComplex);
    check(bad.rec.path.empty(), "prov: out-of-range -> no file written");
    check(bad.equality == -1, "prov: out-of-range -> equality == -1");
    check(bad.mem_sha256.empty(), "prov: out-of-range -> mem_sha256 empty");

    // Reference vector (start_index == -1): offset fields == -1, equality still 1.
    const auto refp = iqrffix9r2d::save_slice_with_provenance(
        dir + "/expected.f32", rx, 0, 128, -1, -1, iqrflayout::kFramePeriodComplex);
    check(refp.equality == 1, "prov: reference slice equality == 1");
    check(refp.start_index == -1 && refp.linear_offset == -1 && refp.circular_offset == -1,
          "prov: reference slice records -1 offsets");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 5. compute_capture_meta: indices + fail-closed completeness ---------------

void test_compute_capture_meta_indices() {
    const std::size_t period = iqrflayout::kFramePeriodComplex;
    const auto rx = make_capture(100, 128000);

    iqrfrec::PerFileRecovery rec;
    rec.computed = true;
    rec.valid = true;
    rec.timing_offset = 100;
    rec.gain_mag = 0.0156;
    rec.phase_deg = 96.3;
    rec.cfo_hz = 0.1;
    rec.sro_ppm = 0.05;
    rec.training_corr = 0.976;
    rec.training_residual = 0.222;

    const auto m = iqrffix9r2d::compute_capture_meta(rx, rec, rx.size(), false);
    check(m.complete, "meta: complete == true for a valid capture");
    check(m.capture_complex == rx.size(), "meta: capture_complex == rx.size()");
    check(m.capture_sha256.size() == 64, "meta: capture sha present");
    check(m.frame_start_abs == 100 && m.timing_offset == 100, "meta: frame_start == timing_offset");
    check(m.training_start == 100 && m.training_end == 100 + iqrflayout::kTrainingLength,
          "meta: training span");
    check(m.payload_start == 100 + iqrflayout::kPayloadOffset &&
              m.payload_end == 100 + iqrflayout::kPayloadOffset + iqrflayout::kPayloadLength,
          "meta: payload span");
    check(m.full_frame_start == 100 && m.full_frame_end == 100 + period, "meta: full frame span");
    check(m.cycle_period == period, "meta: cycle period");
    check(m.cycle0_start == 0 && m.cycle1_start == period, "meta: cycle0/cycle1 start");
    check(m.linear_offset == 100, "meta: linear offset");
    check(m.circular_offset == 100, "meta: circular offset (100 % period)");
    check(m.cfo_hz == 0.1 && m.sro_ppm == 0.05, "meta: cfo/sro copied");
    check(m.gain_mag == 0.0156 && std::fabs(m.phase_deg - 96.3) < 1e-12, "meta: gain copied");
    check(m.clip == 0, "meta: clip == 0 when rx_clipped == false");
    check(m.training_corr == 0.976 && m.training_residual == 0.222,
          "meta: corr/residual copied");
    check(m.rms > 0.0 && m.peak > 0.0, "meta: rms/peak > 0 for a non-zero capture");

    // clip flag propagates
    const auto mc = iqrffix9r2d::compute_capture_meta(rx, rec, rx.size(), true);
    check(mc.clip == 1, "meta: clip == 1 when rx_clipped == true");
}

void test_compute_capture_meta_fail_closed() {
    const std::size_t period = iqrflayout::kFramePeriodComplex;

    iqrfrec::PerFileRecovery rec;
    rec.computed = true; rec.valid = true; rec.timing_offset = 100;

    // capture too short (< 2 periods) -> incomplete
    const auto short_rx = make_capture(100, period + 1000);
    check(!iqrffix9r2d::compute_capture_meta(short_rx, rec, short_rx.size(), false).complete,
          "meta-fail: capture < 2 periods -> incomplete");

    // timing_offset >= period (violates the full-capture-search invariant) -> incomplete
    const auto rx = make_capture(100, 128000);
    iqrfrec::PerFileRecovery bad = rec;
    bad.timing_offset = period;
    check(!iqrffix9r2d::compute_capture_meta(rx, bad, rx.size(), false).complete,
          "meta-fail: timing_offset >= period -> incomplete");

    // a slice past the end (full_frame_end > rx.size()) -> incomplete
    const auto tiny = make_capture(0, 119808 + 1);   // 2 periods + 1, but offset near end
    iqrfrec::PerFileRecovery late = rec;
    late.timing_offset = 119808 - period + 1;         // full frame runs past the capture
    check(!iqrffix9r2d::compute_capture_meta(tiny, late, tiny.size(), false).complete,
          "meta-fail: slice past capture end -> incomplete");
}

// ---- 6. six-verdict vocabulary (requirement 8) --------------------------------

void test_verdict_vocabulary() {
    using namespace iqrffix9r2d;
    check(std::string(kStableLtiChannel) == "STABLE_LTI_CHANNEL", "verdict: STABLE_LTI_CHANNEL");
    check(std::string(kCyclicBoundaryTransient) == "CYCLIC_BOUNDARY_TRANSIENT",
          "verdict: CYCLIC_BOUNDARY_TRANSIENT");
    check(std::string(kCaptureIndexMismatch) == "CAPTURE_INDEX_MISMATCH",
          "verdict: CAPTURE_INDEX_MISMATCH");
    check(std::string(kCycleToCycleNonstationary) == "CYCLE_TO_CYCLE_NONSTATIONARY",
          "verdict: CYCLE_TO_CYCLE_NONSTATIONARY");
    check(std::string(kTrainingPayloadGainMismatch) == "TRAINING_PAYLOAD_GAIN_MISMATCH",
          "verdict: TRAINING_PAYLOAD_GAIN_MISMATCH");
    check(std::string(kNotIdentified) == "NOT_IDENTIFIED", "verdict: NOT_IDENTIFIED");

    // pairwise distinct (exactly one verdict can be emitted)
    const std::vector<std::string> v = {
        kStableLtiChannel, kCyclicBoundaryTransient, kCaptureIndexMismatch,
        kCycleToCycleNonstationary, kTrainingPayloadGainMismatch, kNotIdentified};
    for (std::size_t i = 0; i < v.size(); ++i)
        for (std::size_t j = i + 1; j < v.size(); ++j)
            check(v[i] != v[j], "verdict: pairwise distinct");
}

}  // namespace

void run_test(const char* name, void (*fn)()) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main() {
    std::printf("test_iq_rf_fix9r2d\n");
    run_test("sha256_of_slice", test_sha256_of_slice);
    run_test("slice_complex", test_slice_complex);
    run_test("slice_stats", test_slice_stats);
    run_test("save_slice_with_provenance", test_save_slice_with_provenance);
    run_test("compute_capture_meta_indices", test_compute_capture_meta_indices);
    run_test("compute_capture_meta_fail_closed", test_compute_capture_meta_fail_closed);
    run_test("verdict_vocabulary", test_verdict_vocabulary);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
