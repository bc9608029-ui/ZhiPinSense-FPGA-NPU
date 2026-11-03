// test_iq_digital_loopback.cpp -- host tests for the Stage H-E / Route E pure-logic
// half (board_package/iq_digital_loopback.hpp).
//
//   * int16-domain alignment/measurement: a pure cyclic delay, a +90 deg rotation,
//     and a bounded delay search are recovered exactly (delay/gain/phase/NMSE);
//   * fidelity verdict mapping (all five tokens, observation-only);
//   * classification verdict mapping (all four tokens, measurement-only);
//   * fail-closed loaders: missing manifest, unknown --input-kind, unsafe file
//     name, bad dtype, bad sample rate, SHA/size mismatch;
//   * (POSIX) end-to-end generated-2p56m and radioml-reconstructed-2p56m sidecar
//     round-trips (write a real .ci16 + manifest, load it back, assert every field).
//
// iCraft-free and libiio-free: exercises only iq_digital_loopback.hpp +
// chain_common.hpp / rml23_merged.hpp / sha256.hpp (the same code the board runs).
// Build/run: see host_tests/build_host_tests.sh (no extra link units).

#include "../board_package/iq_digital_loopback.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

constexpr double kPiT = 3.14159265358979323846;

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

// Deterministic interleaved int16 waveform (non-trivial I/Q, no clipping).
//
// The waveform is a multi-tone with BOTH even and odd cycle counts on each axis.
// This matters for the alignment tests: a single odd-tone sinusoid (e.g. only
// 13.0 / 7.0) is ANTI-periodic -- shifting by N/2 samples flips the sign of every
// sample, so the aligner cannot distinguish a delay of d from d+N/2 (they differ
// only by a -1 complex gain).  Mixing an even cycle count in breaks that
// degeneracy, giving the waveform a unique cyclic autocorrelation peak so the
// wrap test can recover the exact near-period delay.
std::vector<std::int16_t> make_tx(std::size_t N) {
    std::vector<std::int16_t> iq(N * 2);
    for (std::size_t k = 0; k < N; ++k) {
        const double th = 2.0 * kPiT * static_cast<double>(k) / static_cast<double>(N);
        const double I = 9000.0 * std::sin(13.0 * th) + 4500.0 * std::sin(6.0 * th);
        const double Q = 9000.0 * std::cos(7.0 * th) + 4500.0 * std::cos(4.0 * th);
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::lround(I));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::lround(Q));
    }
    return iq;
}

// rx[k] = tx[(k - d) mod N] (pure cyclic delay).
std::vector<std::int16_t> rx_delay(const std::vector<std::int16_t>& tx, int d) {
    const std::size_t N = tx.size() / 2;
    std::vector<std::int16_t> rx(tx.size());
    for (std::size_t k = 0; k < N; ++k) {
        const std::size_t src = (k + N - static_cast<std::size_t>(d)) % N;
        rx[k * 2 + 0] = tx[src * 2 + 0];
        rx[k * 2 + 1] = tx[src * 2 + 1];
    }
    return rx;
}

// rx[k] = rot90(tx[(k - d) mod N]) = (-Q, I) -- a +90 deg phase rotation, exact in
// the integer domain.
std::vector<std::int16_t> rx_rotate90(const std::vector<std::int16_t>& tx, int d) {
    const std::size_t N = tx.size() / 2;
    std::vector<std::int16_t> rx(tx.size());
    for (std::size_t k = 0; k < N; ++k) {
        const std::size_t src = (k + N - static_cast<std::size_t>(d)) % N;
        rx[k * 2 + 0] = static_cast<std::int16_t>(-tx[src * 2 + 1]);
        rx[k * 2 + 1] = tx[src * 2 + 0];
    }
    return rx;
}

// ---------------------------------------------------------------------------
// Alignment + measurement.
// ---------------------------------------------------------------------------
void test_align_pure_delay() {
    const std::size_t N = 1024;
    const auto tx = make_tx(N);
    const int d = 37;
    const auto rx = rx_delay(tx, d);
    const auto m = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    check(m.tx_complex == N && m.rx_complex == N, "align: tx/rx complex counts");
    check(m.delay == d, "align: pure cyclic delay recovered exactly");
    check(m.nmse < 1e-9, "align: NMSE ~ 0 for a pure cyclic delay");
    check(m.corr > 0.999999, "align: correlation ~ 1.0");
    check_near(m.gain_db, 0.0, 0.01, "align: gain ~ 0 dB");
    check_near(m.phase_deg, 0.0, 0.1, "align: phase ~ 0 deg");
    std::printf("  align delay: delay=%d gain=%.4f dB phase=%.3f deg nmse=%.3e corr=%.7f\n",
                m.delay, m.gain_db, m.phase_deg, m.nmse, m.corr);
}

void test_align_rotate() {
    const std::size_t N = 1024;
    const auto tx = make_tx(N);
    const int d = 13;
    const auto rx = rx_rotate90(tx, d);
    const auto m = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    check(m.delay == d, "align: delay recovered under +90 deg rotation");
    check(m.nmse < 1e-9, "align: NMSE ~ 0 for pure delay + rotation");
    check(m.corr > 0.999999, "align: rotation correlation ~ 1.0");
    check_near(m.gain_db, 0.0, 0.01, "align: rotation gain ~ 0 dB");
    check_near(m.phase_deg, 90.0, 0.5, "align: rotation phase ~ +90 deg");
    check_near(m.cfo_hz, 0.0, 1e-3, "align: no CFO on a shared-clock copy");
    std::printf("  align rotate: delay=%d phase=%.3f deg nmse=%.3e cfo=%.4f Hz\n",
                m.delay, m.phase_deg, m.nmse, m.cfo_hz);
}

void test_align_bounded() {
    const std::size_t N = 1024;
    const auto tx = make_tx(N);
    const int d = 5;
    const auto rx = rx_delay(tx, d);
    // Bounded search [0, 64) must still find the true delay (and never search past
    // the bound).
    const auto m = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 64);
    check(m.delay == d, "align: bounded search finds the true delay");
    // Full search agrees.
    const auto mf = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    check(mf.delay == d, "align: full search agrees with bounded search");
    check_near(mf.nmse, m.nmse, 1e-12, "align: bounded/full NMSE identical");
}

void test_align_fail_closed() {
    check_throws([]() {
        std::vector<std::int16_t> tx;
        std::vector<std::int16_t> rx(2048);
        (void)iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    }, "align: empty TX throws");
    check_throws([]() {
        std::vector<std::int16_t> tx(2048);
        std::vector<std::int16_t> rx;
        (void)iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    }, "align: empty RX throws");
}

// fix2 req 4: circular alignment must handle an arbitrary start point and ring
// wrap.  A delay near the end of the period wraps across the cyclic boundary, and
// a capture of MULTIPLE TX periods must still find the true delay.
void test_align_wrap_arbitrary_start() {
    const std::size_t N = 1024;
    const auto tx = make_tx(N);
    const int d = static_cast<int>(N) - 7;   // 1017: wraps across the boundary
    const auto rx = rx_delay(tx, d);
    const auto m = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    check(m.delay == d, "align: near-period wrap delay recovered exactly");
    check(m.nmse < 1e-9, "align: wrap NMSE ~ 0");
    check(m.corr > 0.999999, "align: wrap corr ~ 1.0");
}

void test_align_multi_period_capture() {
    const std::size_t N = 1024;
    const auto tx = make_tx(N);
    const int d = 37;
    std::vector<std::int16_t> rx((2 * N) * 2);
    for (std::size_t k = 0; k < 2 * N; ++k) {
        const std::size_t src = (k + N - static_cast<std::size_t>(d)) % N;
        rx[k * 2 + 0] = tx[src * 2 + 0];
        rx[k * 2 + 1] = tx[src * 2 + 1];
    }
    const auto m = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    check(m.delay == d, "align: multi-period capture delay recovered");
    check(m.nmse < 1e-9, "align: multi-period NMSE ~ 0");
    check(m.corr > 0.999999, "align: multi-period corr ~ 1.0");
}

// fix2 req 5: an all-zero RX must never be reported as nmse=0/evm=0 success.
void test_align_all_zero_rx() {
    const std::size_t N = 1024;
    const auto tx = make_tx(N);
    std::vector<std::int16_t> rx(N * 2, 0);
    const auto m = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    check(m.rx_all_zero, "align: all-zero RX detected");
    check(m.rx_nonzero == 0, "align: all-zero rx_nonzero == 0");
    check(m.nmse == 0.0, "align: all-zero nmse is 0 (but NOT success)");
    check(m.corr == 0.0, "align: all-zero corr is 0");
    check(std::string(iqdloop::fidelity_verdict(m)) == "RX_ALL_ZERO",
          "align: all-zero -> RX_ALL_ZERO (never success)");
}

void test_align_low_amplitude_rx() {
    const std::size_t N = 1024;
    const auto tx = make_tx(N);
    std::vector<std::int16_t> rx(N * 2, 0);
    for (std::size_t k = 0; k < N; ++k)
        if (k % 2 == 0) rx[k * 2 + 0] = 1;   // a handful of counts -> dead loopback
    const auto m = iqdloop::align_and_measure_int16(tx, rx, iqdloop::kFrozenFsIn, 0);
    check(m.rms_rx < iqdloop::kRxLowAmplitudeCounts,
          "align: low-amplitude rms below the 2.0 floor");
    check(!m.rx_all_zero, "align: low-amplitude is not all-zero");
    check(std::string(iqdloop::fidelity_verdict(m)) == "RX_LOW_AMPLITUDE",
          "align: low amplitude -> RX_LOW_AMPLITUDE");
}

// fix2 req 2: verify_loaded_tx hashes the loaded bytes, counts non-zeros, and
// fails closed on a SHA mismatch / empty waveform.
void test_verify_loaded_tx() {
    const std::vector<std::int16_t> iq = make_tx(64);
    const std::string sha = sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
    const auto v = iqdloop::verify_loaded_tx(iq, sha);
    check(v.sha256 == sha, "verify_loaded_tx: SHA round-trips");
    check(v.int16_total == iq.size(), "verify_loaded_tx: int16_total");
    check(v.nonzero > 0, "verify_loaded_tx: non-zero waveform");
    check(v.nonzero_rate > 0.0 && v.nonzero_rate <= 1.0, "verify_loaded_tx: nonzero_rate");
    check(v.rms > 0.0, "verify_loaded_tx: rms > 0");
    check(v.first_i == iq[0] && v.first_q == iq[1], "verify_loaded_tx: first samples");
    check(v.last_i == iq[iq.size() - 2] && v.last_q == iq[iq.size() - 1],
          "verify_loaded_tx: last samples");

    check_throws([&]() { (void)iqdloop::verify_loaded_tx(iq, std::string(64, '0')); },
                 "verify_loaded_tx: SHA mismatch throws");
    check_throws([]() { (void)iqdloop::verify_loaded_tx({}, ""); },
                 "verify_loaded_tx: empty waveform throws");
}

// fix2 req 3: measure_refill records non-zero rate / RMS / first / last per refill.
void test_measure_refill() {
    const std::vector<std::int16_t> iq = make_tx(32);
    const auto r = iqdloop::measure_refill(iq, "capture");
    check(r.kind == "capture", "measure_refill: kind");
    check(r.complex == 32, "measure_refill: complex count");
    check(r.nonzero > 0, "measure_refill: non-zero count");
    check(r.rms > 0.0, "measure_refill: rms > 0");
    check(r.first_i == iq[0] && r.first_q == iq[1], "measure_refill: first samples");
    check(r.last_i == iq[iq.size() - 2] && r.last_q == iq[iq.size() - 1],
          "measure_refill: last samples");

    const auto e = iqdloop::measure_refill({}, "discard");
    check(e.complex == 0 && e.nonzero == 0 && e.rms == 0.0, "measure_refill: empty refill");
}

// ---------------------------------------------------------------------------
// Verdict mappings (observation-only).
// ---------------------------------------------------------------------------
void test_fidelity_verdicts() {
    iqdloop::FidelityMetrics m;

    m.rx_complex = 512;
    check(std::string(iqdloop::fidelity_verdict(m)) == "INSUFFICIENT_EVIDENCE",
          "fidelity: short capture -> INSUFFICIENT_EVIDENCE");

    // fix2 req 5: all-zero RX is its own token (never "nmse=0 success").
    m.rx_complex = 2000; m.rx_all_zero = true;
    check(std::string(iqdloop::fidelity_verdict(m)) == "RX_ALL_ZERO",
          "fidelity: all-zero -> RX_ALL_ZERO");

    // fix2 req 5: low-amplitude (dead loopback) is distinct from all-zero.
    m.rx_complex = 2000; m.rx_all_zero = false; m.rms_rx = 0.5;
    check(std::string(iqdloop::fidelity_verdict(m)) == "RX_LOW_AMPLITUDE",
          "fidelity: low amplitude -> RX_LOW_AMPLITUDE");

    m.rx_complex = 2000; m.rms_rx = 10.0; m.corr = 0.1;
    check(std::string(iqdloop::fidelity_verdict(m)) == "SYNC_OR_WRAP_INCONCLUSIVE",
          "fidelity: low corr -> SYNC_OR_WRAP_INCONCLUSIVE");

    m.corr = 0.999; m.nmse = 0.001; m.cfo_hz = 0.5;
    check(std::string(iqdloop::fidelity_verdict(m)) == "DIGITAL_LOOPBACK_PRESERVES_IQ",
          "fidelity: clean -> PRESERVES_IQ");

    m.corr = 0.95; m.nmse = 0.10; m.cfo_hz = 1.0;
    check(std::string(iqdloop::fidelity_verdict(m)) == "DIGITAL_LOOPBACK_DISTORTS_IQ",
          "fidelity: high NMSE -> DISTORTS_IQ");

    m.corr = 0.8; m.nmse = 0.03; m.cfo_hz = 1.0;
    check(std::string(iqdloop::fidelity_verdict(m)) ==
              "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
          "fidelity: middle -> NOT_PROVEN");
}

// fix2 req 6: only PRESERVES_IQ may contribute to a PASS gate.
void test_fidelity_gate() {
    check(iqdloop::fidelity_gate_ok("DIGITAL_LOOPBACK_PRESERVES_IQ"),
          "fidelity_gate_ok: PRESERVES_IQ -> ok");
    check(!iqdloop::fidelity_gate_ok("RX_ALL_ZERO"), "fidelity_gate_ok: RX_ALL_ZERO -> fail");
    check(!iqdloop::fidelity_gate_ok("RX_LOW_AMPLITUDE"), "fidelity_gate_ok: RX_LOW_AMPLITUDE -> fail");
    check(!iqdloop::fidelity_gate_ok("SYNC_OR_WRAP_INCONCLUSIVE"),
          "fidelity_gate_ok: SYNC_OR_WRAP_INCONCLUSIVE -> fail");
    check(!iqdloop::fidelity_gate_ok("DIGITAL_LOOPBACK_DISTORTS_IQ"),
          "fidelity_gate_ok: DISTORTS_IQ -> fail");
    check(!iqdloop::fidelity_gate_ok("DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN"),
          "fidelity_gate_ok: NOT_PROVEN -> fail");
    check(!iqdloop::fidelity_gate_ok("INSUFFICIENT_EVIDENCE"),
          "fidelity_gate_ok: INSUFFICIENT_EVIDENCE -> fail");
    check(!iqdloop::fidelity_gate_ok(""), "fidelity_gate_ok: empty -> fail");
}

void test_classification_verdicts() {
    check(iqdloop::classification_verdict(0, 0, false, 0, 0) == "INSUFFICIENT_EVIDENCE",
          "class: no frames -> INSUFFICIENT_EVIDENCE");
    check(iqdloop::classification_verdict(100, 80, true, 100, 70) ==
              "CLASS_CONSISTENT_WITH_FROZEN_REFERENCE",
          "class: recovered >= frozen -> CONSISTENT");
    check(iqdloop::classification_verdict(100, 60, true, 100, 70) ==
              "CLASS_FLIPPED_PREPROCESS_DIVERGENCE",
          "class: recovered < frozen -> FLIPPED");
    check(iqdloop::classification_verdict(100, 60, false, 0, 0) ==
              "CLASS_MAJORITY_DEPLOYED",
          "class: no ref, >= 0.5 -> MAJORITY");
    check(iqdloop::classification_verdict(100, 40, false, 0, 0) == "CLASS_DIVERGENT",
          "class: no ref, < 0.5 -> DIVERGENT");
}

// ---------------------------------------------------------------------------
// Fail-closed loaders (no filesystem needed).
// ---------------------------------------------------------------------------
void test_load_fail_closed() {
    check_throws([]() {
        (void)iqdloop::load_frozen_iq("/nonexistent_rml23_iqdir_zzz", "generated-2p56m");
    }, "load: missing manifest -> STAGE_G_FROZEN_IQ_REQUIRED");
    check_throws([]() {
        (void)iqdloop::load_frozen_iq("/nonexistent_rml23_iqdir_zzz",
                                      "radioml-reconstructed-2p56m");
    }, "load: missing roundtrip manifest -> STAGE_G_FROZEN_IQ_REQUIRED");
    check_throws([]() {
        (void)iqdloop::load_frozen_iq("/tmp", "bogus-kind");
    }, "load: unknown --input-kind throws");
    check_throws([]() {
        std::uint64_t c = 0;
        (void)iqdloop::verify_frozen_file("/tmp", "../evil.ci16", 0, "", &c);
    }, "verify: unsafe file name throws");
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

void rm_tmp_dir(const std::string& dir, const std::vector<std::string>& files) {
    for (const auto& f : files) ::unlink((dir + "/" + f).c_str());
    ::unlink((dir + "/iq_loopback_manifest.tsv").c_str());
    ::unlink((dir + "/roundtrip_manifest.tsv").c_str());
    ::rmdir(dir.c_str());
}
#endif

void test_generated_sidecar_roundtrip() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_iqdloop_gen");

    // 16 complex samples == 64 bytes, deterministic.
    const std::size_t n_complex = 16;
    const std::size_t n_bytes = n_complex * 4;
    std::vector<std::uint8_t> bytes(n_bytes);
    for (std::size_t i = 0; i < n_bytes; ++i) bytes[i] = static_cast<std::uint8_t>((i * 13 + 5) & 0xFF);
    const std::string sha = sdr::Sha256::hex(bytes.data(), bytes.size());
    const std::string file = "generated_2p56m_QPSK.ci16";

    std::FILE* f = std::fopen((dir + "/" + file).c_str(), "wb");
    check(f != nullptr, "gen: write .ci16");
    if (f) { std::fwrite(bytes.data(), 1, bytes.size(), f); std::fclose(f); }

    // 24-column row (loader reads cols 4,5,6,7,8,9,10..23).
    std::string row;
    row += file; row += "\tci16le\tinterleaved_iq\t2560000\t2560000\t";
    row += std::to_string(n_complex); row += "\t";
    row += std::to_string(n_bytes); row += "\t14821\t4\tQPSK\t16000\t0.35\t8\t160\tnone\t16.0\t128.0\t0\t0.0\t";
    row += sha; row += "\t";
    row += std::string(64, 'a'); row += "\t";          // tensor_sha
    row += std::string(64, 'b'); row += "\t240\t180";  // logits_sha, frozen_frames, frozen_correct

    std::FILE* mf = std::fopen((dir + "/iq_loopback_manifest.tsv").c_str(), "w");
    check(mf != nullptr, "gen: write manifest");
    if (mf) {
        std::fprintf(mf, "# file\tdtype\tlayout\tsr_req\tsr_act\tcomplex\tbyte\tseed\t"
                         "source\tmod\tsymrate\tbeta\tspan\tsps\tnorm\trms\tquant_scale\t"
                         "clip\tclip_ratio\tsha\ttensor_sha\tlogits_sha\tfrozen_frames\t"
                         "frozen_deployed_correct\n%s\n", row.c_str());
        std::fclose(mf);
    }

    const auto out = iqdloop::load_generated_sidecar(dir);
    check(out.size() == 1, "gen: one frozen entry");
    if (out.size() == 1) {
        const auto& q = out[0];
        check(q.file_name == file, "gen: file_name");
        check(q.dtype == "ci16le", "gen: dtype");
        check(q.layout == "interleaved_iq", "gen: layout");
        check(q.sample_rate == iqdloop::kFrozenFsIn, "gen: sample_rate == 2560000");
        check(q.complex_count == n_complex, "gen: complex_count");
        check(q.byte_count == n_bytes, "gen: byte_count");
        check(q.seed == 14821, "gen: seed");
        check(q.source_class == 4, "gen: source_class == QPSK");
        check(q.modulation == "QPSK", "gen: modulation");
        check(q.symbol_rate_hz == 16000, "gen: symbol_rate_hz");
        check_near(q.rrc_beta, 0.35, 1e-12, "gen: rrc_beta");
        check(q.rrc_span == 8, "gen: rrc_span");
        check(q.sps == 160, "gen: sps");
        check(q.normalization == "none", "gen: normalization");
        check_near(q.raw_complex_rms_counts, 16.0, 1e-12, "gen: rms");
        check_near(q.quant_scale, 128.0, 1e-12, "gen: quant_scale");
        check(q.clip_count == 0, "gen: clip_count");
        check_near(q.clip_ratio, 0.0, 1e-12, "gen: clip_ratio");
        check(q.sha256 == sha, "gen: sha256");
        check(q.tensor_sha256 == std::string(64, 'a'), "gen: tensor_sha256");
        check(q.logits_sha256 == std::string(64, 'b'), "gen: logits_sha256");
        check(q.frozen_frames == 240, "gen: frozen_frames");
        check(q.frozen_deployed_correct == 180, "gen: frozen_deployed_correct");
        check(q.has_frozen_ref, "gen: has_frozen_ref");
        check(q.deployed_class == rml23::kSourceToDeployed[4], "gen: deployed_class");
    }

    rm_tmp_dir(dir, {file});
#else
    (void)0;
#endif
}

void test_generated_sidecar_negative() {
#if defined(__unix__) || defined(__APPLE__)
    // bad dtype must fail closed.
    const std::string dir = make_tmp_dir("rml23_iqdloop_neg");
    const std::size_t n_complex = 8;
    const std::string file = "generated_2p56m_QPSK.ci16";
    std::vector<std::uint8_t> bytes(n_complex * 4, 0x11);
    const std::string sha = sdr::Sha256::hex(bytes.data(), bytes.size());
    std::FILE* f = std::fopen((dir + "/" + file).c_str(), "wb");
    if (f) { std::fwrite(bytes.data(), 1, bytes.size(), f); std::fclose(f); }
    std::string row;
    row += file; row += "\tcfloat\tinterleaved_iq\t2560000\t2560000\t";
    row += std::to_string(n_complex); row += "\t32\t14821\t4\tQPSK\t16000\t0.35\t8\t160\t";
    row += "none\t16.0\t128.0\t0\t0.0\t"; row += sha; row += "\t";
    row += std::string(64, 'a'); row += "\t"; row += std::string(64, 'b'); row += "\t8\t8";
    std::FILE* mf = std::fopen((dir + "/iq_loopback_manifest.tsv").c_str(), "w");
    if (mf) { std::fprintf(mf, "# hdr\n%s\n", row.c_str()); std::fclose(mf); }
    check_throws([&]() { (void)iqdloop::load_generated_sidecar(dir); },
                 "gen: unexpected dtype fails closed");

    // bad sample rate (3840000 fallback) must fail closed.
    row.clear();
    row += file; row += "\tci16le\tinterleaved_iq\t2560000\t3840000\t";
    row += std::to_string(n_complex); row += "\t32\t14821\t4\tQPSK\t16000\t0.35\t8\t160\t";
    row += "none\t16.0\t128.0\t0\t0.0\t"; row += sha; row += "\t";
    row += std::string(64, 'a'); row += "\t"; row += std::string(64, 'b'); row += "\t8\t8";
    std::FILE* mf2 = std::fopen((dir + "/iq_loopback_manifest.tsv").c_str(), "w");
    if (mf2) { std::fprintf(mf2, "# hdr\n%s\n", row.c_str()); std::fclose(mf2); }
    check_throws([&]() { (void)iqdloop::load_generated_sidecar(dir); },
                 "gen: 3840000 sample rate fails closed");

    rm_tmp_dir(dir, {file});
#else
    (void)0;
#endif
}

void test_radioml_sidecar_roundtrip() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_iqdloop_rm");
    const std::size_t n_complex = 8;
    const std::string file = "quantized_raw_rx_0.ci16";
    std::vector<std::uint8_t> bytes(n_complex * 4, 0x22);
    std::FILE* f = std::fopen((dir + "/" + file).c_str(), "wb");
    if (f) { std::fwrite(bytes.data(), 1, bytes.size(), f); std::fclose(f); }
    const std::string sha = sdr::Sha256::hex(bytes.data(), bytes.size());

    // fix6 requirement 7: Route D also persists recovered_tensor_<idx>.f32 -- the
    // [2,1024] fp32 reference the naive Route E decimated stream aligns against.
    // The loader must hash its 8192 bytes fail-closed.
    const std::string recov_file = "recovered_tensor_0.f32";
    std::vector<float> recov(chain::kTensorFloats, 0.0f);
    for (std::size_t k = 0; k < chain::kTensorFloats; ++k)
        recov[k] = static_cast<float>(k) * 0.5f;
    std::FILE* rf = std::fopen((dir + "/" + recov_file).c_str(), "wb");
    if (rf) { std::fwrite(recov.data(), sizeof(float), recov.size(), rf); std::fclose(rf); }
    const std::string recov_sha =
        sdr::Sha256::hex(recov.data(), recov.size() * sizeof(float));

    // 13-column Route D row (the exact board format):
    //   index source_index hdf5_label snr_db class_index class_name original_file
    //   interp_file quant_file recovered_file raw24_a_file raw24_d_file original_sha256
    std::string row = "0\t42\t4\t18.0\t4\tQPSK\tradioml_original_0.f32\t";
    row += "interpolated_2p56m_0.f32\t"; row += file; row += "\t";
    row += recov_file; row += "\traw24_a_0.f32\traw24_d_0.f32\t"; row += sha;
    std::FILE* mf = std::fopen((dir + "/roundtrip_manifest.tsv").c_str(), "w");
    if (mf) { std::fprintf(mf, "# hdr\n%s\n", row.c_str()); std::fclose(mf); }

    const auto out = iqdloop::load_radioml_sidecar(dir);
    check(out.size() == 1, "rm: one frozen entry");
    if (out.size() == 1) {
        const auto& q = out[0];
        check(q.source_index == 42, "rm: source_index");
        check_near(q.snr_db, 18.0, 1e-12, "rm: snr_db");
        check(q.source_class == 4, "rm: source_class");
        check(q.modulation == "QPSK", "rm: modulation");
        check(q.file_name == file, "rm: quant_file");
        check(q.complex_count == n_complex, "rm: complex_count");
        check(q.byte_count == n_complex * 4, "rm: byte_count");
        check(q.sample_rate == iqdloop::kFrozenFsIn, "rm: sample_rate == 2560000");
        check(q.dtype == "ci16le", "rm: dtype");
        check(q.layout == "interleaved_iq", "rm: layout");
        check(q.sha256 == sha, "rm: sha computed on the fly");
        check(q.recovered_tensor_file == recov_file, "rm: recovered_file");
        check(q.recovered_tensor_sha256 == recov_sha, "rm: recovered tensor sha");
        check(q.has_recovered_ref, "rm: has_recovered_ref (recovered_file present)");
        check(q.deployed_class == rml23::kSourceToDeployed[4], "rm: deployed_class");
    }

    rm_tmp_dir(dir, {file, recov_file});
#else
    (void)0;
#endif
}

}  // namespace

int main() {
    std::printf("test_iq_digital_loopback\n");
    test_align_pure_delay();
    test_align_rotate();
    test_align_bounded();
    test_align_fail_closed();
    test_align_wrap_arbitrary_start();
    test_align_multi_period_capture();
    test_align_all_zero_rx();
    test_align_low_amplitude_rx();
    test_verify_loaded_tx();
    test_measure_refill();
    test_fidelity_verdicts();
    test_fidelity_gate();
    test_classification_verdicts();
    test_load_fail_closed();
    test_generated_sidecar_roundtrip();
    test_generated_sidecar_negative();
    test_radioml_sidecar_roundtrip();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
