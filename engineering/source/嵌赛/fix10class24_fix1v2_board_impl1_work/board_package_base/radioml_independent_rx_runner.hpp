#pragma once

// radioml_independent_rx_runner.hpp -- fix10class24-independent-rx-delivery-fix1
// (+ fix1v2 board impl1): the INDEPENDENT-RX board runner (arm C).  It re-feeds the
// 24 frozen public-protocol bursts (fix1 v1 AND fix1v2 v2 -- same layout, only the
// uniform S differs) through the real RF chain and the frozen BF16 NPU, and recovers
// the model window with the CLASS-INDEPENDENT public-reference estimator -- NOT the
// per-class dualsdr chain.  This is the main acceptance arm that replaces blind-clean1's
// "no-frame blind capture + fixed window".
//
// The runner is a TEMPLATE on the classifier so a host test can inject a mock NPU and
// prove the IQ -> recovery -> model-input -> classification chain end to end with NO
// iCraft / libiio / hardware (file capture source).  The board instantiates it with the
// real chain::NpuClassifier24 via the gate9 shim (see board_gate9_full_chain_rml23.cpp).
//
// Two capture sources (the rx_int16 is REALY filled in both -- never a stub):
//   --capture-source=file   : read the burst .i16 (clean digital loopback) or a
//                             previously-captured --rx-i16; host-testable, no device.
//   --capture-source=device : board real capture via board::capture_contiguous +
//                             the PC-TX control channel (HELLO -> PREPARE -> START ->
//                             READY -> capture -> CAPTURED -> STOPPED).  Board-only.
//
// Recovery (CLASS-INDEPENDENT, mirrors scripts/radioml_independent_rx_contract.py
// byte-for-byte, in radioml_independent_rx_public_recovery.hpp):
//   timing (ZC preamble) -> coarse CFO (preamble two-half) -> wide-linear fit (16QAM
//   training block) -> wide-linear inverse -> payload[:1024] * (1/S).
// The uniform amplitude contract (three-way separated, class-independent):
//   tx_digital_scale S = 1600/max_peak   (v1 117.84922023433009 / v2 71.609111379029812)
//   rx_gain_estimate  a (wide-linear coeff from the KNOWN training block; digital a≈1)
//   model_input_norm  1/S (uniform inverse scaling)
// The receiver NEVER reads original IQ / DC / per-sample scale / label / reference
// window (offline alignment only) -- only the burst + the public reference.
//
// Honest boundary: digital a≈1, b≈0 only proves the TX->model-normalization link is
// self-consistent; it does NOT prove the RF analog gain G is recovered.  RF recovery is
// a board measurement, never a regression PASS; a gate-rejected frame is emitted with
// board_pred=-1 and is NEVER forced.
//
// Review fixes (fix1v2 board impl1 independent review, R1-R5):
//   R1  TX-restore result is propagated (tx_restore_ok=false is fatal for the run) and
//       an exception while TX is active always sends ABORT (fail-closed, not watchdog).
//   R2  capture >= 2*burst guarantees a full cyclic frame; full-range sync search;
//       symmetric timing fix lives in radioml_independent_rx_public_recovery.hpp.
//   R3  the gate now uses training_residual_rel (RX-energy normalized, gain-independent);
//       the old gain-dependent residual is retained as a named diagnostic column.
//   R4  RX write-then-readback, TX-off negative-control capture, clipping check, finite
//       model-input gate + finite fit-coefficient gate, singular/ill-conditioned inverse
//       rejection.
//   R5  raw RX, real 24-dim logits (infer-twice) and per-attempt diagnostics are
//       persisted; rows are flushed incrementally; completion requires all 24 sources.
//
// NOT aarch64-compiled (Windows host has no cross toolchain): the board must `make -j1`
// natively and verify against the host digital reference (scripts/radioml_independent_rx_replay.py).

#include "chain_common.hpp"
#include "board_common.hpp"
#include "iq_rf_training_frame.hpp"
#include "iq_pc_tx_board_rx_transfer_fix10.hpp"   // frozen PC-TX control protocol (iqpctbrx)
#include "rml24_raw.hpp"
#include "radioml_independent_rx_loader.hpp"
#include "radioml_independent_rx_public_recovery.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"
#include "../sdr_adapter/device_state_guard.hpp"
#include "../sdr_adapter/tcp_control_client.hpp"

#include <sys/stat.h>

#include <cerrno>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqindepfix1 {

using Clock = std::chrono::steady_clock;

constexpr const char* kMeasurementComplete =
    "ROUTE_F_RADIOML_INDEPENDENT_RX_PUBLIC_PROTOCOL_MEASUREMENT_COMPLETE";
constexpr const char* kMeasurementIncomplete =
    "ROUTE_F_RADIOML_INDEPENDENT_RX_PUBLIC_PROTOCOL_MEASUREMENT_INCOMPLETE";

// Production gate (frozen): 0.100 is now the GAIN-INDEPENDENT statistic
// training_residual_rel (RX-energy normalized) -- see the R3 fix.  The gain-dependent
// TX-reference residual is retained only as a named diagnostic column.
constexpr double kResidualGate = 0.100;
constexpr double kHardInvalidResidualCeiling = 0.30;   // on residual_rel (gain-independent)
constexpr int kRecaptureMaxAttempts = 3;               // bounded recapture (transient residual only)
constexpr double kSyncScoreThreshold = 0.50;           // normalized ZC-preamble corr (noise ~0.03)
constexpr double kClipRatioLimit = 0.001;              // >0.1% near-full-scale int16 => rx_clipped
constexpr std::int16_t kClipRail = 32766;              // |v| >= rail counts as clipped
constexpr double kInverseDenomMin = 1e-6;              // |a|^2-|b|^2 below this => ill-conditioned inverse
constexpr std::size_t kDeviceCaptureComplex = 2 * kTotalBurstComplex;  // guarantees a full cyclic frame

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

inline std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

// ---- result header (C layer; the offline judger verifies the recovered tensor SHA) ----
inline const char* independent_rx_result_header() {
    return "source_index\tclass_index\tclass_name\ttiming_offset\tcoarse_cfo_hz\t"
           "a_real\ta_imag\tb_real\tb_imag\ttraining_residual\ttraining_residual_rel\t"
           "gated\tfinite\trepeatable\tboard_pred\tcapture_ok\tno_sync\trx_clipped\t"
           "raw_rx_sha256\tlogits_sha256\tmodel_input_sha256";
}

struct IndependentRxRunReport {
    int n_sources = 0;
    int n_processed = 0;        // frames fully attempted (R5: completion requires == n_sources)
    int n_gated = 0;            // training_residual_rel <= 0.100
    int n_recovered = 0;        // finite + invertible public-reference estimate
    int n_classified = 0;       // gated + finite model input + finite logits
    int n_correct = 0;          // board_pred == class_index (scorer-only, never gates PASS)
    int gate_reject = 0;        // residual_rel in (0.100, 0.30] (forceable, NOT hard-invalid)
    int hard_invalid = 0;       // residual_rel > 0.30 / non-finite / ill-conditioned / no-sync
    int no_sync = 0;            // device capture with no ZC-preamble sync (R2/R4)
    int rx_clipped = 0;         // device capture with int16 clipping (R4)
    bool device_not_found = false;
    bool restore_ok = false;    // board RX device restored
    bool tx_restore_ok = true;  // PC TX device restored across the run (R1)
    bool completed = false;     // n_processed == n_sources == 24 (R5)
    bool aborted = false;
    bool rx_readback_ok = false;        // RX write-then-readback verified (R4)
    bool negative_control_pass = false; // TX-off noise window had no preamble sync (R4)
    bool functional_pass = false;
    double noise_rms = 0.0;
    double noise_sync_score = 0.0;
    std::string aborted_reason;
    std::string error;
    std::string detail;
    std::string out_dir;
    std::string results_path;
    std::string summary_path;
    std::string source_id;
    std::string conversion_version;
    m22::ResourceSample first_res, last_res, peak_res;
};

// Read a whole int16 file into interleaved int16.  REAL fill (never a stub).
inline bool read_i16_file(const std::string& path, std::vector<std::int16_t>& out,
                          std::string* err) {
    std::ifstream f(path, std::ios::binary);
    if (!f) { if (err) *err = "cannot open " + path; return false; }
    f.seekg(0, std::ios::end);
    const std::streampos sz = f.tellg();
    f.seekg(0, std::ios::beg);
    if (sz < 0 || (sz % 2) != 0) {
        if (err) *err = "bad int16 file size for " + path;
        return false;
    }
    out.resize(static_cast<std::size_t>(sz) / 2);
    f.read(reinterpret_cast<char*>(out.data()), static_cast<std::streamsize>(sz));
    if (f.gcount() != sz) {
        if (err) *err = "short read on " + path;
        return false;
    }
    return true;
}

// SHA-256 of the manifest file bytes.  Used as the session `manifest_sha256` so the
// PC TX service can fail-closed if its frozen public-protocol dir differs from the
// board's (same-source binding; the manifest bytes differ between v1 and v2).
inline std::string manifest_file_sha256(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f)
        throw std::runtime_error("independent-rx: cannot read manifest " + path);
    std::vector<char> buf((std::istreambuf_iterator<char>(f)),
                          std::istreambuf_iterator<char>());
    return sdr::Sha256::hex(buf.data(), buf.size());
}

// Fill the planar [2,1024] f32 model tensor from a recovered complex[1024]
// (plane 0 = real, plane 1 = imag -- the frozen model input contract).
inline void fill_model_window(const std::complex<double>* recovered,
                              std::size_t n, std::vector<float>& tensor) {
    tensor.assign(chain::kTensorFloats, 0.0f);
    for (std::size_t k = 0; k < n && k < chain::kFrameComplex; ++k) {
        tensor[k] = static_cast<float>(recovered[k].real());
        tensor[chain::kFrameComplex + k] = static_cast<float>(recovered[k].imag());
    }
}

// Fraction of interleaved int16 samples sitting at/near the full-scale rail (R4).
inline double clip_ratio(const std::vector<std::int16_t>& iq) {
    if (iq.empty()) return 0.0;
    std::size_t clipped = 0;
    for (const std::int16_t v : iq)
        if (v >= kClipRail || v <= -kClipRail) ++clipped;
    return static_cast<double>(clipped) / static_cast<double>(iq.size());
}

// Persist the raw interleaved int16 capture (BEFORE any alignment/recovery) and return
// its SHA-256 (R5).  In file mode this equals the manifest burst_sha256 (consistency).
inline std::string persist_raw_rx(const std::string& out_dir, int source_index,
                                  const std::vector<std::int16_t>& rx_int16) {
    const std::string path =
        join_path(out_dir, std::to_string(source_index) + ".raw.i16");
    {
        std::ofstream f(path, std::ios::binary);
        if (!f) throw std::runtime_error("independent-rx: cannot open " + path);
        f.write(reinterpret_cast<const char*>(rx_int16.data()),
                static_cast<std::streamsize>(rx_int16.size() * sizeof(std::int16_t)));
    }
    return sdr::Sha256::hex(rx_int16.data(),
                            rx_int16.size() * sizeof(std::int16_t));
}

// Persist the REAL 24-dim logits from BOTH inference passes (pass1 then pass2) as a
// deterministic TSV, and return the SHA-256 of the exact file bytes (R5: never a
// synthetic one-hot).
inline std::string persist_logits(const std::string& out_dir, int source_index,
                                  const std::vector<float>& logits1,
                                  const std::vector<float>& logits2) {
    const std::string path =
        join_path(out_dir, std::to_string(source_index) + ".logits.tsv");
    std::string buf;
    buf += "pass";
    for (std::size_t i = 0; i < 24; ++i) {
        buf += "\tlogit_";
        buf += (i < 10 ? "0" : "");
        buf += std::to_string(i);
    }
    buf += "\npass1";
    char n[64];
    for (const float v : logits1) {
        std::snprintf(n, sizeof(n), "%.9g", v);
        buf += "\t"; buf += n;
    }
    buf += "\npass2";
    for (const float v : logits2) {
        std::snprintf(n, sizeof(n), "%.9g", v);
        buf += "\t"; buf += n;
    }
    buf += "\n";
    {
        std::ofstream f(path, std::ios::binary);
        if (!f) throw std::runtime_error("independent-rx: cannot open " + path);
        f.write(buf.data(), static_cast<std::streamsize>(buf.size()));
    }
    return sdr::Sha256::hex(buf.data(), buf.size());
}

// Normalized ZC-preamble correlation score in [0,1] at offset `off` (R2/R4).
inline double preamble_sync_score(const std::vector<std::complex<double>>& rx,
                                  std::size_t off) {
    const std::vector<std::complex<double>> pre = preamble_ref();
    const std::size_t K = pre.size();
    if (off + K > rx.size()) return 0.0;
    const std::complex<double> v = vdot(rx.data() + off, pre.data(), K);
    double p_energy = 0.0, r_energy = 0.0;
    for (std::size_t k = 0; k < K; ++k) {
        p_energy += std::norm(pre[k]);
        r_energy += std::norm(rx[off + k]);
    }
    const double denom = std::sqrt(p_energy * r_energy);
    if (denom <= 0.0) return 0.0;
    return std::abs(v) / denom;
}

struct PreambleLocation {
    std::size_t offset = 0;
    double score = 0.0;   // normalized correlation in [0,1]
};

// Coarse ZC-preamble correlation over offsets [0, max_offset]; returns both the best
// offset and its normalized sync score so the caller can distinguish "no sync" (R2/R4).
inline PreambleLocation locate_preamble(const std::vector<std::complex<double>>& rx,
                                        std::size_t max_offset) {
    PreambleLocation out;
    if (rx.empty()) return out;
    const std::size_t max_end = rx.size() - preamble_ref().size();
    const std::size_t limit = max_offset < max_end ? max_offset : max_end;
    for (std::size_t off = 0; off <= limit; ++off) {
        const double v = preamble_sync_score(rx, off);
        if (v > out.score) { out.score = v; out.offset = off; }
    }
    return out;
}

// Recover + classify ONE captured burst (shared by file and device sources).
// Returns a machine-parseable row plus the recovery evidence the shim/judger need.
template <typename NpuT>
struct OneFrameResult {
    std::string row;
    bool gated = false;
    bool finite_est = false;    // finite fit coeffs + finite CFO + invertible inverse
    bool finite = false;        // finite model input + finite logits (R4)
    bool repeatable = false;    // infer-twice byte-identical logits (R5)
    bool forceable = false;
    bool hard_invalid = false;
    bool no_sync = false;
    bool rx_clipped = false;
    bool capture_ok = true;
    int board_pred = -1;
    double residual = 0.0;      // gain-dependent diagnostic (TX-ref), retained
    double residual_rel = 0.0;  // gain-independent gate statistic (R3)
    std::vector<float> logits1;
    std::vector<float> logits2;
    std::string raw_rx_sha256;
    std::string logits_sha256;
    std::string model_input_sha256;
};

template <typename NpuT>
inline OneFrameResult<NpuT> recover_and_classify_one(
        NpuT& npu, const std::vector<std::complex<double>>& rx,
        const IndependentRxFrame& fr, double unscale, const std::string& out_dir,
        bool capture_ok, bool no_sync, bool rx_clipped,
        const std::string& raw_rx_sha256) {
    OneFrameResult<NpuT> o;
    o.capture_ok = capture_ok;
    o.no_sync = no_sync;
    o.rx_clipped = rx_clipped;
    o.raw_rx_sha256 = raw_rx_sha256;

    const PublicReference est = estimate_public_reference(rx);
    const bool finite_est = std::isfinite(est.a.real()) && std::isfinite(est.a.imag()) &&
                            std::isfinite(est.b.real()) && std::isfinite(est.b.imag()) &&
                            std::isfinite(est.coarse_cfo_hz) &&
                            std::isfinite(est.training_residual) &&
                            std::isfinite(est.training_residual_rel);
    // Ill-conditioned wide-linear inverse rejection (R4): |a|^2-|b|^2 too small means
    // the inverse amplifies noise.  Treated as hard-invalid (never classified).
    const double inv_denom = std::norm(est.a) - std::norm(est.b);
    const bool invertible = std::isfinite(inv_denom) && (inv_denom >= kInverseDenomMin);
    o.finite_est = finite_est && invertible;

    const std::vector<std::complex<double>> zi =
        finite_est ? recover_model_input(rx, est, unscale)
                   : std::vector<std::complex<double>>(kModelWindowComplexPub,
                                                       std::complex<double>(0.0, 0.0));

    // Gate on the gain-independent statistic (R3).  no_sync is hard-invalid: a capture
    // with no ZC-preamble sync must never classify (R2).
    const double residual_rel = est.training_residual_rel;
    const double residual_tx = est.training_residual;
    const bool gated = !no_sync && finite_est && invertible &&
                       (residual_rel <= kResidualGate);
    const bool forceable = !no_sync && finite_est && invertible && !gated &&
                           (residual_rel <= kHardInvalidResidualCeiling);
    const bool hard_invalid = !gated && !forceable;
    o.residual = residual_tx;
    o.residual_rel = residual_rel;
    o.forceable = forceable;
    o.hard_invalid = hard_invalid;
    o.gated = gated;

    // Always emit the recovered model input .bin (gated AND rejected; the offline
    // reviewer re-runs recovery/classification on the EXACT recovered bytes).
    std::vector<float> tensor;
    fill_model_window(zi.data(), zi.size(), tensor);
    const std::string bin_path = join_path(out_dir,
        std::to_string(fr.source_index) + ".recovered.tensor.bin");
    {
        std::ofstream bf(bin_path, std::ios::binary);
        if (!bf) throw std::runtime_error("independent-rx: cannot open " + bin_path);
        bf.write(reinterpret_cast<const char*>(tensor.data()),
                 static_cast<std::streamsize>(tensor.size() * sizeof(float)));
    }
    o.model_input_sha256 = sdr::Sha256::hex(
        tensor.data(), tensor.size() * sizeof(float));

    // Finite model-input gate (R4): non-finite recovered samples (singular/ill-conditioned
    // inverse, NaN/Inf) must never reach the NPU.
    bool tensor_finite = true;
    for (const float v : tensor) {
        if (!std::isfinite(v)) { tensor_finite = false; break; }
    }

    // Classify (gated + finite input).  Infer TWICE for repeatability evidence; persist
    // the REAL 24-dim logits (never a synthetic one-hot -- R5).
    o.board_pred = -1;
    o.finite = false;
    if (gated && tensor_finite) {
        npu.infer(tensor.data(), o.logits1);
        npu.infer(tensor.data(), o.logits2);
        rml24::RML24Result pr1, pr2;
        const bool ok1 = rml24::raw24_predict(o.logits1.data(), &pr1);
        const bool ok2 = rml24::raw24_predict(o.logits2.data(), &pr2);
        o.finite = ok1 && ok2;
        bool same = ok1 && ok2 && (o.logits1.size() == o.logits2.size());
        for (std::size_t i = 0; same && i < o.logits1.size(); ++i)
            if (o.logits1[i] != o.logits2[i]) same = false;
        o.repeatable = same;   // stricter than top1: byte-identical 24 logits
        o.board_pred = ok1 ? pr1.raw_24_top1 : -1;
    }
    o.logits_sha256 = persist_logits(out_dir, fr.source_index, o.logits1, o.logits2);

    // 21-col row.
    char num[64];
    std::string row;
    row += std::to_string(fr.source_index) + "\t";
    row += std::to_string(fr.class_index) + "\t";
    row += fr.class_name + "\t";
    row += std::to_string(est.timing_offset) + "\t";
    std::snprintf(num, sizeof(num), "%.9g", est.coarse_cfo_hz); row += num; row += "\t";
    std::snprintf(num, sizeof(num), "%.9g", est.a.real()); row += num; row += "\t";
    std::snprintf(num, sizeof(num), "%.9g", est.a.imag()); row += num; row += "\t";
    std::snprintf(num, sizeof(num), "%.9g", est.b.real()); row += num; row += "\t";
    std::snprintf(num, sizeof(num), "%.9g", est.b.imag()); row += num; row += "\t";
    std::snprintf(num, sizeof(num), "%.9g", residual_tx); row += num; row += "\t";
    std::snprintf(num, sizeof(num), "%.9g", residual_rel); row += num; row += "\t";
    row += std::to_string(gated ? 1 : 0) + "\t";
    row += std::to_string(o.finite ? 1 : 0) + "\t";
    row += std::to_string(o.repeatable ? 1 : 0) + "\t";
    row += std::to_string(o.board_pred) + "\t";
    row += std::to_string(capture_ok ? 1 : 0) + "\t";
    row += std::to_string(no_sync ? 1 : 0) + "\t";
    row += std::to_string(rx_clipped ? 1 : 0) + "\t";
    row += raw_rx_sha256 + "\t";
    row += o.logits_sha256 + "\t";
    row += o.model_input_sha256;
    o.row = std::move(row);
    return o;
}

// ---------------------------------------------------------------------------
// Device-capture outcome (R1/R2/R4): one bounded recapture cycle's result.
// ---------------------------------------------------------------------------
struct CaptureOutcome {
    bool captured = false;
    bool fatal = false;          // control-channel/provenance failure -> abort run
    bool tx_restore_ok = true;   // PC TX state restored (R1); false is fatal
    double clipped_ratio = 0.0;
    bool rx_clipped = false;
    std::uint64_t overflow = 0;
    std::uint64_t dropped = 0;
    std::uint64_t discontinuity = 0;
    bool short_block = false;
    bool continuity_ok = false;
    std::string error;
};

// Run the full PC-TX control cycle (PREPARE -> START -> capture -> CAPTURED -> STOPPED)
// with bounded recapture.  ANY fatal control/provenance/TX-restore failure sends ABORT
// and closes the channel (R1: fail-closed, not watchdog).  Fills rx_int16 on success.
inline CaptureOutcome capture_device_frame(
        pluto::Device& dev, iqpctbrx::TcpControlClient& client,
        const iqpctbrx::SessionIdentity& sess, const iqpctbrx::SampleIdentity& smp,
        std::size_t capture, m22::StageTiming& timing,
        std::vector<std::int16_t>& rx_int16) {
    CaptureOutcome out;
    for (int attempt = 1; attempt <= kRecaptureMaxAttempts; ++attempt) {
        std::string ctrl_err;
        iqpctbrx::PreparedInfo prepared;
        iqpctbrx::ReadyInfo ready;
        iqpctbrx::StoppedInfo stopped;

        if (!iqpctbrx::send_prepare(client, sess, smp, &ctrl_err) ||
            !iqpctbrx::recv_prepared(client, sess, smp, prepared, &ctrl_err)) {
            out.fatal = true;
            out.error = "PREPARE failed: " + ctrl_err;
            iqpctbrx::send_abort(client, sess, "prepare_failed", &ctrl_err);
            client.close();
            return out;
        }
        if (prepared.payload_sha_pre != smp.payload_sha_pre ||
            prepared.payload_sha_post != smp.payload_sha_pre ||
            prepared.burst_sha != smp.payload_sha_pre ||
            std::fabs(prepared.tx_scale - 1.0) > 1e-6) {
            out.fatal = true;
            out.error = "prepared provenance mismatch (payload_sha_post=" +
                        prepared.payload_sha_post + " burst_sha=" + prepared.burst_sha +
                        " tx_scale=" + std::to_string(prepared.tx_scale) + ")";
            iqpctbrx::send_abort(client, sess, "prepared_provenance_mismatch", &ctrl_err);
            client.close();
            return out;
        }

        if (!iqpctbrx::send_start(client, sess, smp, &ctrl_err) ||
            !iqpctbrx::recv_ready(client, sess, smp, ready, &ctrl_err)) {
            out.fatal = true;
            out.error = "START failed: " + ctrl_err;
            iqpctbrx::send_abort(client, sess, "start_failed", &ctrl_err);
            client.close();
            return out;
        }
        if (ready.burst_sha != smp.payload_sha_pre ||
            std::fabs(ready.tx_scale - 1.0) > 1e-6) {
            out.fatal = true;
            out.error = "ready provenance mismatch (burst_sha=" + ready.burst_sha +
                        " tx_scale=" + std::to_string(ready.tx_scale) + ")";
            iqpctbrx::send_abort(client, sess, "ready_provenance_mismatch", &ctrl_err);
            client.close();
            return out;
        }

        // capture RX while the PC's TX is cyclic
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RxRefill);
            dev.recreate_rx_buffer();
            board::RxStats rxst;
            board::Continuity rxcont;
            const bool raw_ok =
                board::capture_contiguous(dev, capture, rx_int16, rxst, rxcont);
            out.captured = raw_ok && rxcont.ok();
            out.overflow += rxst.overflow;
            out.dropped += rxst.dropped;
            out.discontinuity += rxst.discontinuity;
            out.short_block = out.short_block || rxst.short_block;
            out.continuity_ok = rxcont.ok();
        }

        if (!iqpctbrx::send_captured(client, sess, smp, &ctrl_err) ||
            !iqpctbrx::recv_stopped(client, sess, stopped, &ctrl_err)) {
            out.fatal = true;
            out.error = "CAPTURED failed: " + ctrl_err;
            iqpctbrx::send_abort(client, sess, "captured_failed", &ctrl_err);
            client.close();
            return out;
        }
        // R1: propagate the PC's TX-restore result.  false is fatal for the run.
        if (!stopped.tx_restore_ok) {
            out.tx_restore_ok = false;
            out.fatal = true;
            out.error = "PC TX restore failed (tx_restore_ok=false) on source " +
                        std::to_string(smp.source_index);
            iqpctbrx::send_abort(client, sess, "tx_restore_failed", &ctrl_err);
            client.close();
            return out;
        }

        if (out.captured) {
            out.clipped_ratio = clip_ratio(rx_int16);
            out.rx_clipped = out.clipped_ratio > kClipRatioLimit;
            return out;
        }
        rx_int16.clear();
    }
    out.fatal = true;
    out.error = "capture failed after " + std::to_string(kRecaptureMaxAttempts) +
                " attempts";
    {
        std::string ctrl_err;
        iqpctbrx::send_abort(client, sess, "capture_exhausted", &ctrl_err);
        client.close();
    }
    return out;
}

// ---------------------------------------------------------------------------
// run_radioml_independent_rx
// ---------------------------------------------------------------------------
template <typename NpuT>
inline IndependentRxRunReport run_radioml_independent_rx(
        NpuT& npu, m22::StageTiming& timing, int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& on_frame) {
    IndependentRxRunReport rep;

    const std::string input_dir = board::get_opt(argc, argv, "--input-dir", "");
    if (input_dir.empty())
        throw std::runtime_error("radioml-independent-rx requires --input-dir=<public-"
                                 "protocol tx dir> (manifest + 24 bursts)");
    rep.out_dir = board::get_opt(argc, argv, "--out-dir", "");
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string capture_source =
        board::get_opt(argc, argv, "--capture-source", "device");
    if (capture_source != "file" && capture_source != "device")
        throw std::runtime_error("radioml-independent-rx: --capture-source must be "
                                 "file or device (got '" + capture_source + "').");

    // Load the manifest FIRST (fail-closed) so a bad manifest never creates an out_dir.
    const std::string manifest_path =
        join_path(input_dir, "public_protocol_tx_manifest.tsv");
    const std::vector<IndependentRxFrame> frames =
        load_independent_rx_manifest(manifest_path);
    rep.n_sources = static_cast<int>(frames.size());
    rep.source_id = frames.empty() ? "" : frames[0].source_id;
    rep.conversion_version = frames.empty() ? "" : frames[0].conversion_version;

    // fail-closed out dir (never overwrite)
    if (rep.out_dir.empty())
        throw std::runtime_error("radioml-independent-rx requires --out-dir=<fresh dir>");
    {
        struct stat st;
        if (::stat(rep.out_dir.c_str(), &st) == 0)
            throw std::runtime_error("radioml-independent-rx: --out-dir already exists: " +
                                     rep.out_dir + " (use a fresh timestamped dir)");
        if (::mkdir(rep.out_dir.c_str(), 0777) != 0)
            throw std::runtime_error("radioml-independent-rx: cannot create --out-dir " +
                                     rep.out_dir + ": " + std::strerror(errno));
    }
    rep.results_path = join_path(rep.out_dir, "board_independent_rx_results.tsv");
    rep.summary_path = join_path(rep.out_dir, "board_independent_rx_summary.tsv");

    // R5: open the results file NOW and flush the header, then flush each row as it is
    // produced, so an interruption/exception never loses already-computed rows.
    std::ofstream results_out(rep.results_path, std::ios::binary);
    if (!results_out)
        throw std::runtime_error("independent-rx: cannot open " + rep.results_path);
    results_out << independent_rx_result_header() << "\n";
    results_out.flush();

    rep.first_res = m22::read_resources();

    const long long sample_rate = static_cast<long long>(
        board::opt_u64(argc, argv, "--sample-rate", 2560000ULL));
    const double center_hz = board::opt_d(argc, argv, "--center-hz", 2400000000.0);
    const long long rx_bw = static_cast<long long>(
        board::opt_u64(argc, argv, "--rx-bw", 18000000ULL));
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 35.0);
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", 8192ULL));

    std::printf("RADIOML_INDEPENDENT_RX_START sources=%d source_id=%s version=%s "
                "capture_source=%s input_dir=%s out_dir=%s model_sha=%s\n",
                rep.n_sources, rep.source_id.c_str(), rep.conversion_version.c_str(),
                capture_source.c_str(), input_dir.c_str(), rep.out_dir.c_str(),
                model_sha.c_str());
    std::fflush(stdout);

    // ---- device-mode setup (board-only) ----
    std::unique_ptr<pluto::Device> dev;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    iqpctbrx::TcpControlClient client;
    iqpctbrx::SessionIdentity sess;   // frozen PC-TX session (HELLO .. STOPPED)
    if (capture_source == "device") {
        const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
        if (rx_uri.empty())
            throw std::runtime_error("radioml-independent-rx: --capture-source=device "
                                     "requires --rx-uri=<board RX uri>");
        const std::string tx_control = board::get_opt(argc, argv, "--tx-control", "");
        if (tx_control.empty())
            throw std::runtime_error("radioml-independent-rx: --capture-source=device "
                                     "requires --tx-control=tcp://<PC_IP>:39010");

        try {
            dev.reset(pluto::make_device(rx_uri));
        } catch (const std::exception& e) {
            rep.device_not_found = true;
            rep.error = e.what();
            rep.detail = "phase=radioml-independent-rx-public-protocol-24class-bf16-fix1 "
                         "error=device_not_found " + rep.error;
            results_out.close();
            return rep;
        }
        guard.reset(new pluto::DeviceStateGuard(*dev));

        std::string host;
        std::uint16_t port = iqpctbrx::kDefaultPort;
        std::string perr;
        if (!iqpctbrx::parse_tx_control_url(tx_control, host, port, &perr))
            throw std::runtime_error("radioml-independent-rx: " + perr);
        client.host = host;
        client.port = port;
        if (!client.connect(&perr))
            throw std::runtime_error("radioml-independent-rx: connect to " + tx_control +
                                     " failed: " + perr);

        // RX-only: configure the RX frontend (the PC owns the TX).  Write-THEN-READBACK
        // (R4): verify each write actually took effect, and gate the run on it.
        const long long set_rate = dev->set_sample_rate(sample_rate);
        const long long set_lo = dev->set_rx_lo(static_cast<long long>(center_hz));
        const long long set_bw = dev->set_rx_bw(rx_bw);
        const std::string set_mode = dev->set_rx_gain_mode("manual");
        const double set_gain = dev->set_rx_gain(gain_db);

        const long long rb_rate = dev->get_rx_sample_rate();
        const long long rb_lo = dev->get_rx_lo();
        const long long rb_bw = dev->get_rx_bw();
        const std::string rb_mode = dev->get_rx_gain_mode();
        const double rb_gain = dev->get_rx_gain();

        const bool rate_ok = std::llabs(rb_rate - set_rate) <= 1;
        const bool lo_ok = std::llabs(rb_lo - set_lo) <= 1000;
        const bool bw_ok = std::llabs(rb_bw - set_bw) <= 1000;
        const bool mode_ok = (rb_mode == "manual" && set_mode == "manual");
        const bool gain_ok = std::fabs(rb_gain - set_gain) <= 0.5;
        rep.rx_readback_ok = rate_ok && lo_ok && bw_ok && mode_ok && gain_ok;
        std::printf("RADIOML_INDEPENDENT_RX_READBACK rate=%lld/%lld lo=%lld/%lld "
                    "bw=%lld/%lld mode=%s gain=%.3f/%.3f readback_ok=%d\n",
                    static_cast<long long>(rb_rate), static_cast<long long>(set_rate),
                    static_cast<long long>(rb_lo), static_cast<long long>(set_lo),
                    static_cast<long long>(rb_bw), static_cast<long long>(set_bw),
                    rb_mode.c_str(), rb_gain, set_gain, rep.rx_readback_ok ? 1 : 0);
        std::fflush(stdout);

        // Session identity (frozen PC-TX protocol; the PC echoes these back on every
        // message).  manifest_sha256 binds the SAME public-protocol conversion (v1/v2
        // differ byte-wise); input_kind is version-agnostic (layout identical, S derived
        // from the manifest, the PC transmits the burst .i16 as-is).  tx_scale stays 1.0:
        // the public burst is ALREADY scaled to S, so the PC must NOT re-scale.
        sess.session_id = "radioml-independent-rx";
        sess.run_nonce = "nonce-" + std::to_string(
            std::chrono::steady_clock::now().time_since_epoch().count());
        sess.manifest_sha256 = manifest_file_sha256(manifest_path);
        sess.input_kind = "radioml-independent-rx-public-protocol-24class";
        sess.sample_rate = static_cast<std::uint64_t>(sample_rate);
        sess.center_hz = static_cast<std::uint64_t>(center_hz);
        sess.target_rms = 2048.0;   // unused: the public burst is pre-scaled to S

        // HELLO -> HELLO_ACK (the PC TX service confirms config + TX off).
        iqpctbrx::HelloAckInfo ack;
        if (!iqpctbrx::send_hello(client, sess, &perr) ||
            !iqpctbrx::recv_hello_ack(client, sess, ack, &perr)) {
            const std::string primary_error = perr;
            std::string cleanup_error;
            iqpctbrx::send_abort(client, sess, "hello_failed", &cleanup_error);
            client.close();
            if (!cleanup_error.empty())
                std::printf("RADIOML_INDEPENDENT_RX_HELLO_ABORT_CLEANUP_ERROR=%s "
                            "(primary=%s)\n", cleanup_error.c_str(), primary_error.c_str());
            throw std::runtime_error("radioml-independent-rx: HELLO failed: " +
                                     primary_error);
        }
        std::printf("RADIOML_INDEPENDENT_RX_HELLO_ACK tx_serial=%s tx_uri=%s "
                    "tx_atten_db=%.3f configuration_verified=%d\n",
                    ack.tx_serial.c_str(), ack.tx_uri.c_str(), ack.tx_atten_db,
                    ack.configuration_verified ? 1 : 0);
        std::fflush(stdout);

        // Negative control (R4): measure a TX-off noise window; a preamble must NOT sync.
        {
            std::vector<std::int16_t> noise_i16;
            board::RxStats nst;
            board::Continuity ncont;
            dev->recreate_rx_buffer();
            board::capture_contiguous(*dev, kTotalBurstComplex, noise_i16, nst, ncont);
            std::vector<std::complex<double>> noise = iqrftrain::deinterleave(noise_i16);
            double noise_energy = 0.0;
            for (const auto& s : noise) noise_energy += std::norm(s);
            rep.noise_rms = noise.empty()
                ? 0.0
                : std::sqrt(noise_energy / static_cast<double>(noise.size()));
            const std::size_t n_off =
                noise.size() > kTotalBurstComplex ? noise.size() - kTotalBurstComplex : 0;
            const PreambleLocation nloc = locate_preamble(noise, n_off);
            rep.noise_sync_score = nloc.score;
            rep.negative_control_pass = (nloc.score < kSyncScoreThreshold);
            std::printf("RADIOML_INDEPENDENT_RX_NEGATIVE_CONTROL noise_rms=%.6f "
                        "noise_sync_score=%.6f negative_control_pass=%d\n",
                        rep.noise_rms, rep.noise_sync_score,
                        rep.negative_control_pass ? 1 : 0);
            std::fflush(stdout);
        }
    }

    const std::size_t capture = kDeviceCaptureComplex + 2 * delay_margin;

    for (const auto& fr : frames) {
        if (board::g_stop_requested) {
            rep.aborted = true;
            rep.aborted_reason = "stop_requested";
            rep.error = "interrupted (stop requested) before all sources processed";
            break;
        }

        m22::StageTiming::Timer frame_t(timing, m22::StageId::FrameTotal);

        std::vector<std::int16_t> rx_int16;
        std::string perr;
        bool capture_ok = true;
        std::string capture_diag_path;   // device-mode per-attempt diagnostics (R5)

        if (capture_source == "file") {
            // REAL fill #1: read the burst .i16 (clean digital loopback), or a
            // previously-captured IQ via --rx-i16 (the capture-path test feeds the
            // EXACT captured IQ through recovery + classification).
            const std::string rx_i16 = board::get_opt(argc, argv, "--rx-i16", "");
            const std::string path = rx_i16.empty()
                ? join_path(input_dir, fr.burst_file) : rx_i16;
            if (!read_i16_file(path, rx_int16, &perr))
                throw std::runtime_error("radioml-independent-rx: " + perr);
        } else {
            // REAL fill #2: board capture via the frozen PC-TX control channel.
            const iqpctbrx::SampleIdentity smp{
                fr.source_index, fr.burst_file, fr.burst_sha256};
            CaptureOutcome c = capture_device_frame(*dev, client, sess, smp, capture,
                                                    timing, rx_int16);

            // Per-attempt diagnostics are captured inline (R5): persist a single-row
            // summary per frame for the reviewer.
            capture_diag_path = join_path(rep.out_dir,
                std::to_string(fr.source_index) + ".capture.diag.tsv");
            {
                std::ofstream df(capture_diag_path, std::ios::binary);
                if (df)
                    df << "capture_ok\toverflow\tdropped\tdiscontinuity\tshort_block\t"
                          "continuity_ok\tclipped_ratio\trx_clipped\ttx_restore_ok\n"
                       << (c.captured ? 1 : 0) << "\t" << c.overflow << "\t"
                       << c.dropped << "\t" << c.discontinuity << "\t"
                       << (c.short_block ? 1 : 0) << "\t" << (c.continuity_ok ? 1 : 0)
                       << "\t" << c.clipped_ratio << "\t" << (c.rx_clipped ? 1 : 0)
                       << "\t" << (c.tx_restore_ok ? 1 : 0) << "\n";
            }

            if (c.fatal) {
                rep.aborted = true;
                rep.aborted_reason = c.error;
                rep.error = c.error;
                rep.tx_restore_ok = c.tx_restore_ok;
                break;
            }
            capture_ok = c.captured;
        }

        // R5: persist the raw RX capture BEFORE any alignment/recovery, and record the
        // clipping health (R4) -- both modes.
        const std::string raw_rx_sha =
            persist_raw_rx(rep.out_dir, fr.source_index, rx_int16);
        const double clipped_ratio = clip_ratio(rx_int16);
        const bool rx_clipped = clipped_ratio > kClipRatioLimit;

        std::vector<std::complex<double>> rx = iqrftrain::deinterleave(rx_int16);
        bool no_sync = false;
        if (capture_source == "device") {
            // R2: full-range sync search over the whole margined capture; a complete
            // frame is guaranteed because capture >= 2*burst + 2*margin.
            const std::size_t max_off =
                rx.size() > kTotalBurstComplex ? rx.size() - kTotalBurstComplex : 0;
            const PreambleLocation loc = locate_preamble(rx, max_off);
            no_sync = (loc.score < kSyncScoreThreshold);
            if (loc.offset + kTotalBurstComplex > rx.size()) {
                rep.aborted = true;
                rep.aborted_reason = "burst_extends_past_capture";
                rep.error = "burst extends past capture (offset=" +
                            std::to_string(loc.offset) + ")";
                break;
            }
            rx = std::vector<std::complex<double>>(rx.begin() + loc.offset,
                                                   rx.begin() + loc.offset +
                                                       kTotalBurstComplex);
        }

        const auto o = recover_and_classify_one<NpuT>(
            npu, rx, fr, fr.unscale, rep.out_dir, capture_ok, no_sync, rx_clipped,
            raw_rx_sha);

        if (o.gated) {
            ++rep.n_gated;
            if (o.finite) {
                ++rep.n_classified;
                if (o.board_pred == fr.class_index) ++rep.n_correct;
            }
        } else if (o.hard_invalid) {
            ++rep.hard_invalid;
        } else {
            ++rep.gate_reject;   // forceable: residual_rel in (0.100, 0.30]
        }
        if (o.finite_est) ++rep.n_recovered;
        if (o.no_sync) ++rep.no_sync;
        if (o.rx_clipped) ++rep.rx_clipped;
        ++rep.n_processed;

        // R5: flush this row immediately (never lose it to a later exception/Ctrl-C).
        results_out << o.row << "\n";
        results_out.flush();

        std::printf("RADIOML_INDEPENDENT_RX_FILE source_index=%d class=%s gated=%d "
                    "finite=%d repeatable=%d board_pred=%d residual_rel=%.6f "
                    "residual_tx=%.6f no_sync=%d rx_clipped=%d\n",
                    fr.source_index, fr.class_name.c_str(), o.gated ? 1 : 0,
                    o.finite ? 1 : 0, o.repeatable ? 1 : 0, o.board_pred,
                    o.residual_rel, o.residual, o.no_sync ? 1 : 0,
                    o.rx_clipped ? 1 : 0);
        std::fflush(stdout);

        // UI result frame (only for gated+classified; rejections never fabricate one).
        // R5: use the REAL 24-dim logits, never a synthetic one-hot.
        if (o.gated && o.finite) {
            const cat::Contract contract = chain::contract_24();
            rf::ResultFrame r;
            r.frame_id = static_cast<std::uint64_t>(fr.source_index);
            r.timestamp_us = static_cast<std::uint64_t>(fr.source_index) * 8000ULL;
            r.source = "radioml_independent_rx";
            r.mock = (capture_source == "file");
            chain::fill_result_rml24(r, o.logits1, contract, model_sha,
                                     std::numeric_limits<double>::quiet_NaN());
            on_frame(r);
        }
    }

    // Close the control channel cleanly (the PC treats a clean close as session end).
    if (capture_source == "device" && client.connected()) {
        std::string perr;
        iqpctbrx::send_abort(client, sess, "board_done", &perr);
        client.close();
    }

    // Restore the device on the normal path (guard destructor is the catch-path backstop).
    if (guard) rep.restore_ok = guard->restore();
    else rep.restore_ok = true;   // file mode: no device to restore

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res : rep.first_res;

    results_out.close();

    // R5: completion requires every expected source to have been fully processed.
    rep.completed = !rep.aborted && (rep.n_processed == rep.n_sources) &&
                    (rep.n_sources == kSourceCount);

    // write summary (run-level outcome, explicit missing/aborted)
    {
        std::ofstream sf(rep.summary_path, std::ios::binary);
        if (!sf)
            throw std::runtime_error("independent-rx: cannot open " + rep.summary_path);
        sf << "sources\tprocessed\tgated\tgate_reject\thard_invalid\tno_sync\t"
              "rx_clipped\tclassified\tcorrect\tcompleted\taborted\taborted_reason\t"
              "restore_ok\ttx_restore_ok\trx_readback_ok\tnegative_control_pass\t"
              "noise_rms\tnoise_sync_score\tfunctional_pass\tsource_id\tversion\t"
              "capture_source\n";
        sf << rep.n_sources << "\t" << rep.n_processed << "\t" << rep.n_gated << "\t"
           << rep.gate_reject << "\t" << rep.hard_invalid << "\t" << rep.no_sync << "\t"
           << rep.rx_clipped << "\t" << rep.n_classified << "\t" << rep.n_correct << "\t"
           << (rep.completed ? 1 : 0) << "\t" << (rep.aborted ? 1 : 0) << "\t"
           << rep.aborted_reason << "\t" << (rep.restore_ok ? 1 : 0) << "\t"
           << (rep.tx_restore_ok ? 1 : 0) << "\t" << (rep.rx_readback_ok ? 1 : 0) << "\t"
           << (rep.negative_control_pass ? 1 : 0) << "\t" << rep.noise_rms << "\t"
           << rep.noise_sync_score << "\t" << (rep.functional_pass ? 1 : 0) << "\t"
           << rep.source_id << "\t" << rep.conversion_version << "\t"
           << capture_source << "\n";
    }

    const bool infra_ok = !rep.device_not_found && rep.error.empty();
    // functional_pass requires infra, board restore, PC TX restore, RX readback,
    // negative control, and full completion of all 24 sources (R1/R4/R5).
    rep.functional_pass = infra_ok && rep.restore_ok && rep.tx_restore_ok &&
                          rep.rx_readback_ok && rep.negative_control_pass &&
                          rep.completed;

    rep.detail = "mode=" + capture_source + " source_id=" + rep.source_id +
                 " version=" + rep.conversion_version +
                 " gated=" + std::to_string(rep.n_gated) +
                 " gate_reject=" + std::to_string(rep.gate_reject) +
                 " hard_invalid=" + std::to_string(rep.hard_invalid) +
                 " no_sync=" + std::to_string(rep.no_sync) +
                 " rx_clipped=" + std::to_string(rep.rx_clipped) +
                 " classified=" + std::to_string(rep.n_classified) +
                 " correct=" + std::to_string(rep.n_correct) +
                 " processed=" + std::to_string(rep.n_processed) +
                 " sources=" + std::to_string(rep.n_sources) +
                 " completed=" + (rep.completed ? "1" : "0") +
                 " aborted=" + (rep.aborted ? "1" : "0") +
                 " restore_ok=" + (rep.restore_ok ? "1" : "0") +
                 " tx_restore_ok=" + (rep.tx_restore_ok ? "1" : "0") +
                 " rx_readback_ok=" + (rep.rx_readback_ok ? "1" : "0") +
                 " negative_control_pass=" + (rep.negative_control_pass ? "1" : "0");
    if (!rep.aborted_reason.empty())
        rep.detail += " aborted_reason=" + rep.aborted_reason;

    std::printf("RADIOML_INDEPENDENT_RX_DONE sources=%d processed=%d gated=%d "
                "gate_reject=%d hard_invalid=%d no_sync=%d rx_clipped=%d classified=%d "
                "correct=%d completed=%d aborted=%d source_id=%s version=%s "
                "capture_source=%s functional_pass=%d\n",
                rep.n_sources, rep.n_processed, rep.n_gated, rep.gate_reject,
                rep.hard_invalid, rep.no_sync, rep.rx_clipped, rep.n_classified,
                rep.n_correct, rep.completed ? 1 : 0, rep.aborted ? 1 : 0,
                rep.source_id.c_str(), rep.conversion_version.c_str(),
                capture_source.c_str(), rep.functional_pass ? 1 : 0);
    std::fflush(stdout);
    return rep;
}

}  // namespace iqindepfix1
