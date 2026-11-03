#pragma once

// iq_rf_loopback_24class_bf16_scalarwl_core.hpp -- fix10class24-scalarwl-4way
// (task 39e5): the iCraft-free / libiio-free / NPU-free CORE of the minimal
// single-SDR diagnostic.  It holds every pure function the diagnostic needs to
// (a) reconstruct the production `aligned` capture, (b) recompute the wide-linear
// (a, b) coefficients from that capture, (c) build the two model inputs, and
// (d) run the single-SDR negative control.  The board-only runner (which needs the
// iCraft NPU wrapper) lives in iq_rf_loopback_24class_bf16_scalarwl_diag.hpp and
// includes this core.  Splitting the two lets the host test exercise the exact
// recovery/input math WITHOUT the iCraft SDK, matching how chain_common.hpp is
// host-tested while npu_classifier24.hpp is board-only.
//
// It does NOT change the 0.100 gate, does NOT change production behaviour, and does
// NOT retrain.  RED LINE: iq_rf_sync_recovery.hpp / iq_dual_sdr_coarse_cfo_recovery.hpp
// / iq_pc_tx_board_rx_24class_bf16_fix10.hpp / the canonical frame are UNTOUCHED.
// This header is ADDITIVE.

#include "chain_common.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_rf_per_frame_recovery.hpp"        // iqrfrec (shim -> iq_rf_sync_recovery.hpp)
#include "iq_rf_frame_layout.hpp"
#include "iq_rf_loopback_transfer.hpp"         // iqrfloop_run::kRfDiscard* / kRfNoise*
#include "iq_dual_sdr_coarse_cfo_recovery.hpp" // iqdual23fix10::recover_payload_with_coarse_cfo
#include "iq_pc_tx_board_rx_transfer_fix10.hpp"// iqpctbrx::TxBurstBuild + CFO range fns
#include "iq_fix10_canonical_frame.hpp"         // fix10canonical::buildTxBurstFromFrozen
#include "iq_rf_loopback_transfer_24class_bf16_fix10.hpp" // single-SDR local TX transfer
#include "rml24_raw.hpp"                        // rml24::raw24_predict (NO merge)
#include "rml24_bf16_baseline.hpp"              // rml24bf16::load_baseline / BaselineRow
#include "rf_fix_helpers.hpp"                   // rf_fix::rf_readback_close
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/device_state_guard.hpp"

#include <sys/stat.h>

#include <algorithm>
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
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqdiagswl {

// Diagnostic measurement token (never a regression PASS).
constexpr const char* kMeasurementToken =
    "FIX10CLASS24_BF16_SCALARWL_DIAG";

constexpr std::size_t kDelayMarginDefault = 8192;  // capture margin past 2 periods

inline bool opt_flag(int argc, char** argv, const char* name) {
    for (int i = 1; i < argc; ++i)
        if (std::string(argv[i]) == name) return true;
    return false;
}

inline std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 2);
    for (char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += c;
                }
        }
    }
    return out;
}

inline std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

inline int argmax_of(const std::vector<float>& v) {
    if (v.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(v.size()); ++i)
        if (v[i] > v[best]) best = i;
    return best;
}

inline bool all_finite(const std::vector<float>& v) {
    for (float x : v)
        if (!std::isfinite(x)) return false;
    return true;
}

// Raw little-endian fp32 (IEEE-754) write.  Both the host test (x86) and the board
// (aarch64) are little-endian, so a raw write is the f32le contract the Windows
// icraft-run host consumes as `--input <bin>`.
inline void write_bytes(const std::string& path, const void* data, std::size_t nbytes) {
    std::ofstream f(path, std::ios::binary);
    if (!f)
        throw std::runtime_error("iqdiagswl: cannot open " + path);
    f.write(static_cast<const char*>(data), static_cast<std::ptrdiff_t>(nbytes));
    if (!f)
        throw std::runtime_error("iqdiagswl: short write " + path);
}

inline void write_f32le(const std::string& path, const std::vector<float>& v) {
    write_bytes(path, v.data(), v.size() * sizeof(float));
}

// Verbatim failure -> RF verdict mapping (same as the production runner's
// failure_rf_verdict; the fidelity gate is reproduced exactly below).
inline const char* failure_rf_verdict(iqrfrec::Failure f) {
    switch (f) {
        case iqrfrec::Failure::NONE:
            return "RF_PRESERVES_IQ";
        case iqrfrec::Failure::CAPTURE_TOO_SHORT:
        case iqrfrec::Failure::TRAINING_NOT_FOUND:
        case iqrfrec::Failure::TRAINING_PEAK_AMBIGUOUS:
            return "RF_TRAINING_ESTIMATE_FAILED";
        case iqrfrec::Failure::TRAINING_CORRELATION_TOO_LOW:
        case iqrfrec::Failure::TRAINING_RESIDUAL_TOO_HIGH:
        case iqrfrec::Failure::PAYLOAD_TRAINING_NOT_FOUND:
        case iqrfrec::Failure::PAYLOAD_TRAINING_CORRELATION_TOO_LOW:
        case iqrfrec::Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH:
        case iqrfrec::Failure::PAYLOAD_RMS_GAIN_NOT_FOUND:
        case iqrfrec::Failure::CFO_OUT_OF_RANGE:
        case iqrfrec::Failure::SRO_OUT_OF_RANGE:
            return "RF_DISTORTS_IQ";
        default:
            return "RF_TRAINING_ESTIMATE_FAILED";
    }
}

// ---------------------------------------------------------------------------
// Single-SDR negative control (byte-for-byte the production runner's helper): the
// runner OWNS the TX, so it must stop TX and CONFIRM it stopped before measuring the
// noise floor; the discard-refill / noise-window / stability logic is otherwise
// identical to iq_rf_loopback_24class_bf16_fix10.hpp::run_rx_negative_control.
// ---------------------------------------------------------------------------
struct NegativeControl {
    bool capture_ok = false;
    bool stable = false;
    bool tx_stopped_ok = false;
    double rms_min = 0.0;
    double rms_median = 0.0;
    double rms_max = 0.0;
    double stability_ratio = 0.0;
    std::vector<double> window_rms;
    std::vector<std::int16_t> noise;
};

inline NegativeControl run_rx_negative_control(pluto::Device& dev,
                                               std::size_t noise_complex) {
    NegativeControl nc;
    dev.tx_stop();
    nc.tx_stopped_ok = !dev.tx_running();
    for (std::size_t d = 0; d < iqrfloop_run::kRfDiscardRefills; ++d) {
        dev.recreate_rx_buffer();
        const iio::RawChunk c = dev.read_rx(iqrfloop_run::kRfDiscardComplex, 1000);
        (void)c;
    }
    std::vector<std::vector<std::int16_t>> windows(iqrfloop_run::kRfNoiseWindows);
    nc.window_rms.assign(iqrfloop_run::kRfNoiseWindows, 0.0);
    bool all_ok = true;
    for (std::size_t w = 0; w < iqrfloop_run::kRfNoiseWindows; ++w) {
        dev.recreate_rx_buffer();
        board::RxStats st;
        board::Continuity cont;
        const bool raw_ok = board::capture_contiguous(dev, noise_complex, windows[w], st, cont);
        if (!(raw_ok && cont.ok())) all_ok = false;
        double e = 0.0;
        for (std::int16_t s : windows[w])
            e += static_cast<double>(s) * static_cast<double>(s);
        nc.window_rms[w] = windows[w].empty()
            ? 0.0 : std::sqrt(e / static_cast<double>(windows[w].size()));
    }
    nc.capture_ok = all_ok;
    std::vector<std::size_t> order(iqrfloop_run::kRfNoiseWindows);
    for (std::size_t i = 0; i < order.size(); ++i) order[i] = i;
    std::sort(order.begin(), order.end(), [&](std::size_t a, std::size_t b) {
        return nc.window_rms[a] < nc.window_rms[b];
    });
    nc.rms_min = nc.window_rms[order.front()];
    nc.rms_median = nc.window_rms[order[order.size() / 2]];
    nc.rms_max = nc.window_rms[order.back()];
    nc.stability_ratio = (nc.rms_min > 0.0)
        ? (nc.rms_max / nc.rms_min)
        : (nc.rms_max > 0.0) ? 1.0e18 : 1.0;
    nc.stable = (nc.rms_max == 0.0) ||
                (nc.stability_ratio <= iqrfloop_run::kRfNoiseStableMaxRatio);
    nc.noise = std::move(windows[order[order.size() / 2]]);
    return nc;
}

// Reconstruct the LOCAL `aligned` capture that recover_payload_with_coarse_cfo builds
// internally (coarse de-rotate -> fractional advance).  Deterministic double-precision
// math identical to the recovery core, so the reconstructed `aligned` is byte-for-byte
// the vector estimate()/apply() saw.
inline std::vector<std::complex<double>> reconstruct_aligned(
        const std::vector<std::complex<double>>& rx,
        const iqdual23fix10::CoarseCfoRecovery& ccr) {
    std::vector<std::complex<double>> derot(rx.size());
    for (std::size_t n = 0; n < rx.size(); ++n) {
        const double ph = -2.0 * iqrftrain::kPi * ccr.coarse_cfo_hz *
                          static_cast<double>(n) / static_cast<double>(iqrftrain::kFs);
        derot[n] = rx[n] * std::complex<double>(std::cos(ph), std::sin(ph));
    }
    return iqdual23fix10::detail::apply_fractional_advance(
        derot, ccr.fractional_timing_samples);
}

// Recompute the wide-linear (a, b) coefficients from the reconstructed `aligned`
// capture, byte-for-byte replicating estimate()'s step 6.6 (first-half fit on the
// CFO-corrected payload-domain training block).  Used ONLY when estimate() did NOT
// enable wide-linear -- so the diagnostic can still produce a WL model input for the
// four-way comparison without touching the 0.100 gate or any production behaviour.
// Returns the zero pair (fail-closed) if the block would over-read the capture.
inline iqrfrec::detail::WideLinearCoeffs recompute_wide_linear_coeffs(
        const std::vector<std::complex<double>>& aligned,
        const iqrfrec::PerFileRecovery& rec) {
    iqrfrec::detail::WideLinearCoeffs out{};
    const std::size_t best = rec.timing_offset;
    const std::size_t ptoff = iqrftrain::kPayloadTrainingOffset;
    if (best + ptoff + iqrftrain::kPayloadTrainingComplex > aligned.size())
        return out;
    const double sro_frac = rec.sro_ppm * 1e-6;
    const std::vector<std::complex<double>> pt = iqrftrain::payload_gain_training_complex();
    auto stretched_pt = [&pt, ptoff, sro_frac](std::size_t k) -> std::complex<double> {
        double x = static_cast<double>(ptoff + k) / (1.0 + sro_frac) -
                   static_cast<double>(ptoff);
        if (x < 0.0) x = 0.0;
        if (x > static_cast<double>(pt.size() - 1)) x = static_cast<double>(pt.size() - 1);
        const std::size_t i0 = static_cast<std::size_t>(std::floor(x));
        const std::size_t i1 = i0 + 1;
        if (i1 < pt.size()) {
            const double fr = x - static_cast<double>(i0);
            return pt[i0] * (1.0 - fr) + pt[i1] * fr;
        }
        return pt[i0];
    };
    std::vector<std::complex<double>> xc(iqrftrain::kPayloadTrainingComplex);
    std::vector<std::complex<double>> rk(iqrftrain::kPayloadTrainingComplex);
    for (std::size_t k = 0; k < iqrftrain::kPayloadTrainingComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * rec.cfo_hz *
                          static_cast<double>(ptoff + k) /
                          static_cast<double>(iqrftrain::kFs);
        const std::complex<double> derot(std::cos(ph), -std::sin(ph));
        xc[k] = aligned[best + ptoff + k] * derot;
        rk[k] = stretched_pt(k);
    }
    const std::size_t half = iqrftrain::kPayloadTrainingComplex / 2;
    return iqrfrec::detail::wide_linear_fit(rk, xc, 0, half);
}

// ---------------------------------------------------------------------------
// build_model_input: recovered payload (complex) -> int16 -> PreprocessChain ->
// D2 restore -> select_classification_window -> the [2,1024] model tensor.  This is
// byte-for-byte the production classify path (iq_rf_loopback_24class_bf16_fix10.hpp
// lines 1046-1078); the ONLY difference is that the payload was produced by apply()
// with wide_linear toggled.
// ---------------------------------------------------------------------------
struct BuiltInput {
    bool valid = false;
    std::vector<float> aligned_tensor;   // [2,1024] == 2048 floats == 8192 bytes
};

inline BuiltInput build_model_input(const std::vector<std::complex<double>>& payload,
                                    const iqdloop::FrozenIq& fz,
                                    double nco_offset) {
    BuiltInput out;
    std::vector<std::int16_t> payload_iq(payload.size() * 2);
    for (std::size_t k = 0; k < payload.size(); ++k) {
        const double I = std::lround(payload[k].real());
        const double Q = std::lround(payload[k].imag());
        payload_iq[k * 2 + 0] = static_cast<std::int16_t>(
            std::max(-32768.0, std::min(32767.0, I)));
        payload_iq[k * 2 + 1] = static_cast<std::int16_t>(
            std::max(-32768.0, std::min(32767.0, Q)));
    }
    chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, 1.0f);
    chain.push_int16(payload_iq.data(), payload.size());
    std::vector<float> recovered_stream;
    {
        std::vector<float> t(chain::kTensorFloats);
        while (chain.ready() > 0) {
            if (!chain.pull_tensor(t.data())) break;
            recovered_stream.insert(recovered_stream.end(), t.begin(), t.end());
        }
    }
    iqdloop::apply_d2_restore_to_stream(recovered_stream, chain::kFrameComplex,
                                        fz.original_dc_i, fz.original_dc_q,
                                        fz.d2_rec_scale);
    const std::vector<float> ref =
        iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                       fz.recovered_tensor_sha256);
    const iqdloop::ClassificationWindow cw =
        iqdloop::select_classification_window(recovered_stream, ref);
    if (!cw.valid || cw.aligned_tensor.empty()) return out;
    out.aligned_tensor = cw.aligned_tensor;
    out.valid = true;
    return out;
}

inline bool payloads_equal(const std::vector<std::complex<double>>& a,
                           const std::vector<std::complex<double>>& b) {
    if (a.size() != b.size()) return false;
    for (std::size_t k = 0; k < a.size(); ++k)
        if (a[k] != b[k]) return false;
    return true;
}

// The BF16 baseline identifies the source RadioML sample, not the quantized CI16
// transmit artifact. FrozenIq deliberately carries both hashes; keep this check in
// one place so callers cannot confuse original_sha256 with sha256.
inline bool baseline_identity_matches(const rml24bf16::BaselineRow& baseline,
                                      const iqdloop::FrozenIq& frozen) {
    return baseline.original_sha256 == frozen.original_sha256 &&
           baseline.raw24_class == frozen.source_class &&
           baseline.modulation == frozen.modulation &&
           baseline.split_role == frozen.split_role;
}

// Select exactly one frozen sample by its manifest identity.  The scalar/WL
// diagnostic started as an OQPSK-only investigation, but --source-index is a
// general manifest key and is now used for the full 24-class comparison.
inline const iqdloop::FrozenIq* find_frozen_by_source_index(
        const std::vector<iqdloop::FrozenIq>& frozen,
        std::uint64_t source_index) {
    const iqdloop::FrozenIq* match = nullptr;
    for (const auto& item : frozen) {
        if (item.source_index != source_index) continue;
        if (match != nullptr)
            throw std::runtime_error("duplicate frozen source_index " +
                                     std::to_string(source_index));
        match = &item;
    }
    return match;
}

// ---------------------------------------------------------------------------
// ScalarWlDiagRunReport
// ---------------------------------------------------------------------------
struct ScalarWlDiagRunReport {
    std::string input_kind;
    std::string frozen_dir;
    std::string baseline_path;
    std::string model_json;
    std::string model_raw;
    std::string model_sha;

    std::uint64_t source_index = 0;
    int source_class = -1;
    std::string modulation;
    double snr_db = 0.0;
    std::string split_role;
    int baseline_pred = -1;

    // model identity (fail-closed)
    std::string model_raw_sha;
    std::size_t model_raw_size = 0;
    bool model_sha_verified = false;

    // frontend readback
    long long requested_rate = 0, rx_rate = 0, tx_rate = 0;
    bool sample_rate_ok = false;
    bool rx_lo_ok = false, rx_bw_ok = false, rx_gain_ok = false;
    bool tx_lo_ok = false, tx_bw_ok = false, tx_atten_ok = false, loopback_ok = false;

    // negative control
    bool negative_control_ok = false;
    bool tx_stopped_ok = false;
    bool tx_stopped_final_ok = false;

    // recovery / fidelity
    std::size_t capture_attempts = 0;
    std::string fidelity_verdict = "INSUFFICIENT_EVIDENCE";
    bool recovery_valid = false;
    std::string recovery_failure;
    std::size_t timing_offset = 0;
    double coarse_cfo_hz = 0.0, fine_cfo_hz = 0.0, total_cfo_hz = 0.0;
    bool cfo_in_range = false;
    double sro_ppm = 0.0;
    double payload_training_corr = 0.0;
    double payload_training_residual = 0.0;
    bool wide_linear_enabled = false;
    double wide_linear_image_ratio = 0.0;
    double wide_linear_validation_residual = 0.0;
    double wide_linear_scalar_validation_residual = 0.0;
    bool wl_recomputed = false;
    std::complex<double> wl_direct{1.0, 0.0};
    std::complex<double> wl_image{0.0, 0.0};

    // the four-way inputs (board produces scalar/WL inputs + the BF16 pair)
    bool inputs_produced = false;
    bool inputs_identical = false;
    std::string input_scalar_sha;
    std::string input_wl_sha;
    bool payload_scalar_equals_production = false;
    bool payload_wl_equals_production = false;
    bool bf16_finite = false;
    std::vector<float> logits_scalar;   // 24 floats
    std::vector<float> logits_wl;       // 24 floats
    int argmax_scalar = -1;
    int argmax_wl = -1;

    std::string out_dir;
    std::string manifest_path;

    bool device_not_found = false;
    std::string error;
    std::string detail;
    bool functional_pass = false;

    bool restore_ok = false;
    std::string restore_report;

    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;
};

// Minimal JSON object builder (full-precision floats, escaped strings).
struct JsonObj {
    std::ostringstream os;
    bool first = true;
    explicit JsonObj() { os << "{"; os.precision(17); }
    void comma() { if (!first) os << ','; first = false; }
    void str(const char* k, const std::string& v) {
        comma(); os << "\"" << k << "\":\"" << json_escape(v) << "\"";
    }
    void num(const char* k, double v) { comma(); os << "\"" << k << "\":" << v; }
    void integer(const char* k, long long v) { comma(); os << "\"" << k << "\":" << v; }
    void boolean(const char* k, bool v) {
        comma(); os << "\"" << k << "\":" << (v ? "true" : "false");
    }
    void f32arr(const char* k, const std::vector<float>& v) {
        comma(); os << "\"" << k << "\":[";
        for (std::size_t i = 0; i < v.size(); ++i) {
            if (i) os << ',';
            os << v[i];
        }
        os << ']';
    }
    std::string finish() { os << "}\n"; return os.str(); }
};

}  // namespace iqdiagswl
