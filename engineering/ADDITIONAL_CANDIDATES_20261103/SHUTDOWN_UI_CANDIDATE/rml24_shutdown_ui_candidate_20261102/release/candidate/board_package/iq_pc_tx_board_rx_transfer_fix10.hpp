#pragma once

// iq_pc_tx_board_rx_transfer_fix10.hpp -- fix10prep2: the per-sample control-channel
// state machine + provenance between the BOARD (RX SDR owner) and the PC (TX SDR
// owner).  This is the REAL dual-SDR topology (two free-running ADALM-Plutos): the
// board NEVER opens a TX device and the PC NEVER opens an RX device; the two ends
// exchange ONLY control messages + sample identity + SHA over TCP, never real-time IQ.
//
// Per-sample state machine (strict, single-direction, board-driven):
//   STOPPED   (HELLO_ACK received; PC TX confirmed off)
//     -> board runs the TX-off negative control (RX noise floor stable + quiet)
//   PREPARE   (board -> PC: source_index + file_name + payload_sha_pre)
//   PREPARED  (PC -> board: built + verified the burst, but did NOT transmit)
//   START     (board -> PC: explicit authorization to transmit)
//   READY     (PC -> board: cyclic TX running + all config read-backs passed)
//     -> board verifies READY provenance, then captures / recovers / classifies
//   CAPTURED  (board -> PC: stop TX)
//   STOPPED   (PC -> board: TX stopped) -> next sample or done
//
// Hard rules (task book §7): PREPARE/PREPARED may NEVER create a cyclic TX buffer;
// only a legal START may transmit; READY is sent only after TX is running AND every
// config read-back passed; a repeated START, a START before PREPARE, a STOPPED before
// CAPTURED, a duplicate / out-of-order / unknown-field message, a length over the hard
// limit, or a START->READY timeout all fail closed.
//
// Provenance: the board INDEPENDENTLY rebuilds the TX burst from the frozen ci16
// (same iq_rf_training_frame.hpp::build_burst + same --rf-tx-target-rms scaling as the
// single-SDR transfer) and compares payload_sha_pre / payload_sha_post / burst_sha /
// tx_scale against the PC's READY.  Both ends derive the burst from the SAME frozen
// artifact, so a mismatch means the two ends disagree on the waveform -> stop.
//
// iCraft-free and libiio-free: everything here is pure logic or an AF_INET socket, so
// the host tests exercise the exact state machine + provenance over a 127.0.0.1 link.

#include "iq_digital_loopback.hpp"       // iqdloop::load_ci16 / verify_loaded_tx / measure_refill
#include "iq_rf_training_frame.hpp"      // iqrftrain::build_burst / kPayloadComplex
#include "iq_rf_frame_layout.hpp"        // iqrflayout::capture_complex
#include "iq_rf_loopback_transfer.hpp"   // iqrfloop_run::kRfDiscard* / kRfNoise* (reuse)
#include "../sdr_adapter/tcp_control_client.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqpctbrx {

// ---------------------------------------------------------------------------
// CFO capture range (task book §8) -- the runner prints these per sample + in the
// aggregate, and the host tests assert the exact boundaries + the fail-closed
// behaviour when a dual-SDR CFO lands OUT of the unambiguous coarse range.
// ---------------------------------------------------------------------------
inline double coarse_cfo_unambiguous_range_hz() {
    return static_cast<double>(iqrftrain::kFs) /
           (2.0 * static_cast<double>(iqrftrain::kPayloadTrainingOffset));
}
inline double coarse_cfo_search_min_hz() { return -coarse_cfo_unambiguous_range_hz(); }
inline double coarse_cfo_search_max_hz() { return +coarse_cfo_unambiguous_range_hz(); }
// The single-SDR fine CFO (preamble-vs-tail) is unambiguous only over +/-fs/(2*kTailStart).
inline double fine_cfo_range_hz() {
    return static_cast<double>(iqrftrain::kFs) /
           (2.0 * static_cast<double>(iqrftrain::kTailStart));
}

// ---------------------------------------------------------------------------
// Pure TX-burst build (byte-identical to the single-SDR transfer's TX build).
// The board uses this to derive the EXPECTED provenance SHAs it compares against
// the PC's READY; the PC uses the identical build (via build_burst_cli, which
// #include's the same iq_rf_training_frame.hpp) to produce the bytes it transmits.
// ---------------------------------------------------------------------------
struct TxBurstBuild {
    std::vector<std::int16_t> payload;      // post-scale payload (interleaved int16)
    std::vector<std::int16_t> burst;        // full training-frame burst
    iqdloop::TxVerify tx_verify;            // pre-scale payload SHA + non-zero evidence
    std::string payload_sha_pre;            // SHA of the frozen ci16 bytes (== fz.sha256)
    std::string payload_sha_post;           // SHA of the scaled payload bytes
    std::string burst_sha;                  // SHA of the full burst
    double native_rms = 0.0;
    double target_rms = 0.0;
    double tx_scale = 1.0;
    double peak_pre = 0.0;
    double peak_post = 0.0;
    bool clip_pre = false;
    bool clip_post = false;
};

// Load + verify the frozen payload, apply --rf-tx-target-rms scaling (payload only,
// training frame stays at kTrainAmp), and build the training-frame burst.  Throws
// fail-closed on a SHA mismatch / empty waveform / wrong length.  This mirrors
// iqrfloop_run_fix9r::transfer_one_file_rf_fix9r's TX build EXACTLY (same load_ci16 /
// verify_loaded_tx / build_burst / Sha256), minus the device I/O.
inline TxBurstBuild build_tx_burst_from_frozen(const std::string& path,
                                               std::uint64_t complex_count,
                                               const std::string& expect_sha,
                                               double target_rms) {
    if (complex_count != iqrftrain::kPayloadComplex)
        throw std::runtime_error(
            "iq-pc-tx-board-rx: payload complex_count " + std::to_string(complex_count) +
            " != training-frame kPayloadComplex " +
            std::to_string(iqrftrain::kPayloadComplex));

    TxBurstBuild r;
    std::vector<std::int16_t> payload_iq = iqdloop::load_ci16(path, complex_count);
    r.tx_verify = iqdloop::verify_loaded_tx(payload_iq, expect_sha);
    r.target_rms = target_rms;
    r.payload_sha_pre = r.tx_verify.sha256;

    {
        double e = 0.0;
        int peak = 0;
        for (std::int16_t s : payload_iq) {
            e += static_cast<double>(s) * static_cast<double>(s);
            peak = std::max(peak, std::abs(static_cast<int>(s)));
        }
        r.native_rms = payload_iq.empty()
            ? 0.0 : std::sqrt(e / static_cast<double>(payload_iq.size()));
        r.peak_pre = static_cast<double>(peak);
        r.clip_pre = (r.peak_pre >= 32767.0);
        r.peak_post = r.peak_pre;
        if (target_rms > 0.0 && r.native_rms > 0.0) {
            const double want = target_rms / r.native_rms;
            r.peak_post = r.peak_pre * want;
            r.clip_post = (r.peak_post >= 32767.0);
            if (!r.clip_post) {
                r.tx_scale = want;
                for (std::size_t k = 0; k < payload_iq.size(); ++k) {
                    const double v = std::llround(
                        static_cast<double>(payload_iq[k]) * r.tx_scale);
                    payload_iq[k] = static_cast<std::int16_t>(
                        std::max(-32768.0, std::min(32767.0, v)));
                }
            }
        }
        r.payload_sha_post = sdr::Sha256::hex(payload_iq.data(),
                                              payload_iq.size() * sizeof(std::int16_t));
    }
    r.payload = payload_iq;

    const std::vector<std::int16_t> burst = iqrftrain::build_burst(payload_iq);
    r.burst = burst;
    r.burst_sha = sdr::Sha256::hex(burst.data(), burst.size() * sizeof(std::int16_t));
    return r;
}

// Manifest identity shared over the control channel: the SHA-256 of the frozen
// sidecar manifest (route_d2_rf_manifest.tsv for radioml-d2-2p56m), so the PC can
// fail-closed if its frozen dir does not match the board's.
inline std::string d2_manifest_path(const std::string& frozen_dir) {
    if (frozen_dir.empty()) return "route_d2_rf_manifest.tsv";
    const char c = frozen_dir.back();
    return (c == '/' || c == '\\') ? frozen_dir + "route_d2_rf_manifest.tsv"
                                   : frozen_dir + "/route_d2_rf_manifest.tsv";
}

// ---------------------------------------------------------------------------
// Session + sample identity structs.
// ---------------------------------------------------------------------------
struct SessionIdentity {
    std::string session_id;
    std::string run_nonce;
    std::string manifest_sha256;
    std::string input_kind;
    std::uint64_t sample_rate = iqrftrain::kFs;
    std::uint64_t center_hz = 2400000000ULL;
    double target_rms = 2048.0;
};

struct SampleIdentity {
    std::int64_t source_index = -1;
    std::string file_name;
    std::string payload_sha_pre;
};

struct HelloAckInfo {
    std::string tx_serial;
    std::string tx_uri;
    double tx_atten_db = 0.0;
    bool configuration_verified = false;
};

struct PreparedInfo {
    std::string payload_sha_pre;
    std::string payload_sha_post;
    std::string burst_sha;
    double tx_scale = 0.0;
};

struct ReadyInfo {
    std::string payload_sha_pre;
    std::string payload_sha_post;
    std::string burst_sha;
    double tx_scale = 0.0;
    std::int64_t sample_rate_readback = 0;
    std::int64_t tx_lo_readback = 0;
    std::int64_t tx_bw_readback = 0;
    double tx_atten_readback = 0.0;
    bool tx_running = false;
};

// STOPPED (PC -> board) carries the PC's TX-state restore result so the board can
// report tx_restore_ok alongside its own rx_restore_ok in the two-sample acceptance.
struct StoppedInfo {
    bool tx_restore_ok = false;
};

// ---------------------------------------------------------------------------
// Strict message validation.  `expect` is the exact set of keys a message of the
// given type must carry (including the common keys); any extra key (unknown field),
// missing key, or wrong type is a fail-closed rejection.
// ---------------------------------------------------------------------------
inline bool validate_exact_fields(const Json& obj,
                                  const std::vector<std::string>& expect,
                                  std::string* err) {
    if (!obj.is_object()) { if (err) *err = "message is not a JSON object"; return false; }
    for (const std::string& k : expect)
        if (!obj.has(k)) { if (err) *err = "missing field '" + k + "'"; return false; }
    for (const auto& kv : obj.object) {
        bool found = false;
        for (const std::string& k : expect) if (k == kv.first) { found = true; break; }
        if (!found) { if (err) *err = "unknown field '" + kv.first + "'"; return false; }
    }
    return true;
}

inline bool validate_common(const Json& obj, const std::string& expected_type,
                            const SessionIdentity& s, std::string* err) {
    const Json* t = obj.get("type");
    if (!t || !t->is_string() || t->as_string() != expected_type) {
        if (err) *err = "wrong message type (expected " + expected_type + ")";
        return false;
    }
    const Json* p = obj.get("protocol");
    if (!p || !p->is_number() || p->as_int() != kProtocolVersion) {
        if (err) *err = "protocol version mismatch";
        return false;
    }
    const Json* sid = obj.get("session_id");
    if (!sid || !sid->is_string() || sid->as_string() != s.session_id) {
        if (err) *err = "session_id mismatch";
        return false;
    }
    const Json* rn = obj.get("run_nonce");
    if (!rn || !rn->is_string() || rn->as_string() != s.run_nonce) {
        if (err) *err = "run_nonce mismatch";
        return false;
    }
    const Json* ms = obj.get("manifest_sha256");
    if (!ms || !ms->is_string() || ms->as_string() != s.manifest_sha256) {
        if (err) *err = "manifest_sha256 mismatch";
        return false;
    }
    return true;
}

// Check a SHA field is 64 lowercase hex.
inline bool valid_sha64(const std::string& v) {
    if (v.size() != 64) return false;
    for (char c : v)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

// Build a Json object from key/value pairs (helper for the senders).
inline Json obj(std::vector<std::pair<std::string, Json>> kv) {
    return Json::make_object(std::move(kv));
}
inline Json num(double v) { return Json::make_number(v); }
inline Json str(std::string v) { return Json::make_string(std::move(v)); }
inline Json boolean(bool b) { return Json::make_boolean(b); }

// ---------------------------------------------------------------------------
// Senders (board -> PC) and receivers (PC -> board), each strict and fail-closed.
// ---------------------------------------------------------------------------
inline Json common_fields(const std::string& type, const SessionIdentity& s) {
    return obj({{"type", str(type)},
                {"protocol", num(kProtocolVersion)},
                {"session_id", str(s.session_id)},
                {"run_nonce", str(s.run_nonce)},
                {"manifest_sha256", str(s.manifest_sha256)}});
}

inline bool send_hello(TcpControlClient& c, const SessionIdentity& s, std::string* err) {
    Json m = common_fields("HELLO", s);
    m.object.emplace_back("input_kind", str(s.input_kind));
    m.object.emplace_back("sample_rate", num(static_cast<double>(s.sample_rate)));
    m.object.emplace_back("center_hz", num(static_cast<double>(s.center_hz)));
    m.object.emplace_back("target_rms", num(s.target_rms));
    return c.send_json(m, err);
}

inline bool recv_hello_ack(TcpControlClient& c, const SessionIdentity& s,
                           HelloAckInfo& out, std::string* err) {
    std::string text;
    if (!c.recv_json(text, err)) return false;
    const JsonParseResult pr = json_parse(text);
    if (!pr.ok) { if (err) *err = "HELLO_ACK parse: " + pr.error; return false; }
    static const std::vector<std::string> expect = {
        "type", "protocol", "session_id", "run_nonce", "manifest_sha256",
        "tx_serial", "tx_uri", "tx_atten_db", "configuration_verified"};
    if (!validate_exact_fields(pr.value, expect, err)) return false;
    if (!validate_common(pr.value, "HELLO_ACK", s, err)) return false;
    const Json* ts = pr.value.get("tx_serial");
    const Json* tu = pr.value.get("tx_uri");
    const Json* ta = pr.value.get("tx_atten_db");
    const Json* cv = pr.value.get("configuration_verified");
    if (!ts || !ts->is_string() || !tu || !tu->is_string() ||
        !ta || !ta->is_number() || !cv || !cv->is_bool()) {
        if (err) *err = "HELLO_ACK field type error";
        return false;
    }
    if (!cv->as_bool()) { if (err) *err = "PC configuration not verified"; return false; }
    out.tx_serial = ts->as_string();
    out.tx_uri = tu->as_string();
    out.tx_atten_db = ta->as_number();
    out.configuration_verified = true;
    return true;
}

inline bool send_prepare(TcpControlClient& c, const SessionIdentity& s,
                         const SampleIdentity& smp, std::string* err) {
    Json m = common_fields("PREPARE", s);
    m.object.emplace_back("source_index", num(static_cast<double>(smp.source_index)));
    m.object.emplace_back("file_name", str(smp.file_name));
    m.object.emplace_back("payload_sha_pre", str(smp.payload_sha_pre));
    return c.send_json(m, err);
}

inline bool recv_prepared(TcpControlClient& c, const SessionIdentity& s,
                          const SampleIdentity& smp, PreparedInfo& out, std::string* err) {
    std::string text;
    if (!c.recv_json(text, err)) return false;
    const JsonParseResult pr = json_parse(text);
    if (!pr.ok) { if (err) *err = "PREPARED parse: " + pr.error; return false; }
    static const std::vector<std::string> expect = {
        "type", "protocol", "session_id", "run_nonce", "manifest_sha256",
        "source_index", "file_name", "payload_sha_pre", "payload_sha_post",
        "burst_sha", "tx_scale", "configuration_verified"};
    if (!validate_exact_fields(pr.value, expect, err)) return false;
    if (!validate_common(pr.value, "PREPARED", s, err)) return false;
    const Json* si = pr.value.get("source_index");
    const Json* fn = pr.value.get("file_name");
    const Json* ppre = pr.value.get("payload_sha_pre");
    const Json* ppost = pr.value.get("payload_sha_post");
    const Json* bs = pr.value.get("burst_sha");
    const Json* tsc = pr.value.get("tx_scale");
    const Json* cv = pr.value.get("configuration_verified");
    if (!si || !si->is_number() || !fn || !fn->is_string() ||
        !ppre || !ppre->is_string() || !ppost || !ppost->is_string() ||
        !bs || !bs->is_string() || !tsc || !tsc->is_number() ||
        !cv || !cv->is_bool()) {
        if (err) *err = "PREPARED field type error";
        return false;
    }
    if (!cv->as_bool()) {
        if (err) *err = "PREPARED configuration not verified";
        return false;
    }
    if (si->as_int() != smp.source_index || fn->as_string() != smp.file_name) {
        if (err) *err = "PREPARED sample identity mismatch";
        return false;
    }
    if (!valid_sha64(ppre->as_string()) || !valid_sha64(ppost->as_string()) ||
        !valid_sha64(bs->as_string())) {
        if (err) *err = "PREPARED SHA not 64-hex";
        return false;
    }
    if (ppre->as_string() != smp.payload_sha_pre) {
        if (err) *err = "PREPARED payload_sha_pre mismatch";
        return false;
    }
    out.payload_sha_pre = ppre->as_string();
    out.payload_sha_post = ppost->as_string();
    out.burst_sha = bs->as_string();
    out.tx_scale = tsc->as_number();
    return true;
}

inline bool send_start(TcpControlClient& c, const SessionIdentity& s,
                       const SampleIdentity& smp, std::string* err) {
    Json m = common_fields("START", s);
    m.object.emplace_back("source_index", num(static_cast<double>(smp.source_index)));
    m.object.emplace_back("file_name", str(smp.file_name));
    return c.send_json(m, err);
}

inline bool recv_ready(TcpControlClient& c, const SessionIdentity& s,
                       const SampleIdentity& smp, ReadyInfo& out, std::string* err) {
    std::string text;
    if (!c.recv_json(text, err)) return false;
    const JsonParseResult pr = json_parse(text);
    if (!pr.ok) { if (err) *err = "READY parse: " + pr.error; return false; }
    static const std::vector<std::string> expect = {
        "type", "protocol", "session_id", "run_nonce", "manifest_sha256",
        "source_index", "file_name", "payload_sha_pre", "payload_sha_post",
        "burst_sha", "tx_scale", "sample_rate_readback", "tx_lo_readback",
        "tx_bw_readback", "tx_atten_readback", "tx_running"};
    if (!validate_exact_fields(pr.value, expect, err)) return false;
    if (!validate_common(pr.value, "READY", s, err)) return false;
    const Json* si = pr.value.get("source_index");
    const Json* fn = pr.value.get("file_name");
    const Json* ppre = pr.value.get("payload_sha_pre");
    const Json* ppost = pr.value.get("payload_sha_post");
    const Json* bs = pr.value.get("burst_sha");
    const Json* tsc = pr.value.get("tx_scale");
    const Json* sr = pr.value.get("sample_rate_readback");
    const Json* lo = pr.value.get("tx_lo_readback");
    const Json* bw = pr.value.get("tx_bw_readback");
    const Json* att = pr.value.get("tx_atten_readback");
    const Json* run = pr.value.get("tx_running");
    if (!si || !si->is_number() || !fn || !fn->is_string() ||
        !ppre || !ppre->is_string() || !ppost || !ppost->is_string() ||
        !bs || !bs->is_string() || !tsc || !tsc->is_number() ||
        !sr || !sr->is_number() || !lo || !lo->is_number() ||
        !bw || !bw->is_number() || !att || !att->is_number() ||
        !run || !run->is_bool()) {
        if (err) *err = "READY field type error";
        return false;
    }
    if (si->as_int() != smp.source_index || fn->as_string() != smp.file_name) {
        if (err) *err = "READY sample identity mismatch";
        return false;
    }
    if (!valid_sha64(ppre->as_string()) || !valid_sha64(ppost->as_string()) ||
        !valid_sha64(bs->as_string())) {
        if (err) *err = "READY SHA not 64-hex";
        return false;
    }
    if (ppre->as_string() != smp.payload_sha_pre) {
        if (err) *err = "READY payload_sha_pre mismatch";
        return false;
    }
    if (!run->as_bool()) { if (err) *err = "READY tx_running is false"; return false; }
    out.payload_sha_pre = ppre->as_string();
    out.payload_sha_post = ppost->as_string();
    out.burst_sha = bs->as_string();
    out.tx_scale = tsc->as_number();
    out.sample_rate_readback = sr->as_int();
    out.tx_lo_readback = lo->as_int();
    out.tx_bw_readback = bw->as_int();
    out.tx_atten_readback = att->as_number();
    out.tx_running = true;
    return true;
}

inline bool send_captured(TcpControlClient& c, const SessionIdentity& s,
                          const SampleIdentity& smp, std::string* err) {
    Json m = common_fields("CAPTURED", s);
    m.object.emplace_back("source_index", num(static_cast<double>(smp.source_index)));
    m.object.emplace_back("file_name", str(smp.file_name));
    return c.send_json(m, err);
}

inline bool recv_stopped(TcpControlClient& c, const SessionIdentity& s,
                         StoppedInfo& out, std::string* err) {
    std::string text;
    if (!c.recv_json(text, err)) return false;
    const JsonParseResult pr = json_parse(text);
    if (!pr.ok) { if (err) *err = "STOPPED parse: " + pr.error; return false; }
    static const std::vector<std::string> expect = {
        "type", "protocol", "session_id", "run_nonce", "manifest_sha256",
        "tx_restore_ok"};
    if (!validate_exact_fields(pr.value, expect, err)) return false;
    if (!validate_common(pr.value, "STOPPED", s, err)) return false;
    const Json* tro = pr.value.get("tx_restore_ok");
    if (!tro || !tro->is_bool()) { if (err) *err = "STOPPED tx_restore_ok not bool"; return false; }
    out.tx_restore_ok = tro->as_bool();
    return true;
}

inline bool send_abort(TcpControlClient& c, const SessionIdentity& s,
                       const std::string& reason, std::string* err) {
    Json m = common_fields("ABORT", s);
    m.object.emplace_back("reason", str(reason));
    return c.send_json(m, err);
}

// ---------------------------------------------------------------------------
// Provenance check: compare the PC's declared SHAs/scale against the board's
// INDEPENDENT rebuild of the burst from the frozen ci16 + target_rms.
// ---------------------------------------------------------------------------
struct ProvenanceCheck {
    bool ok = false;
    std::string report;
};

inline ProvenanceCheck check_readiness_provenance(const TxBurstBuild& expected,
                                                  const PreparedInfo& prepared,
                                                  const ReadyInfo& ready,
                                                  double tx_scale_tol) {
    ProvenanceCheck r;
    r.ok = true;
    const auto mismatch = [&](const std::string& field, const std::string& got,
                              const std::string& want) {
        r.ok = false;
        if (!r.report.empty()) r.report += ";";
        r.report += field + "_mismatch(want=" + want + " got=" + got + ")";
    };
    if (prepared.payload_sha_post != expected.payload_sha_post)
        mismatch("payload_sha_post", prepared.payload_sha_post, expected.payload_sha_post);
    if (prepared.burst_sha != expected.burst_sha)
        mismatch("burst_sha_prepared", prepared.burst_sha, expected.burst_sha);
    if (ready.payload_sha_post != expected.payload_sha_post)
        mismatch("payload_sha_post", ready.payload_sha_post, expected.payload_sha_post);
    if (ready.burst_sha != expected.burst_sha)
        mismatch("burst_sha", ready.burst_sha, expected.burst_sha);
    const double scale_err = std::fabs(ready.tx_scale - expected.tx_scale);
    const double scale_tol = tx_scale_tol * std::max(1.0, std::fabs(expected.tx_scale));
    if (!(scale_err <= scale_tol))
        mismatch("tx_scale", std::to_string(ready.tx_scale),
                 std::to_string(expected.tx_scale));
    if (expected.clip_pre) { r.ok = false; r.report += (r.report.empty() ? "" : ";") +
        std::string("tx_clip_pre"); }
    if (expected.clip_post) { r.ok = false; r.report += (r.report.empty() ? "" : ";") +
        std::string("tx_clip_post"); }
    return r;
}

// The board-side per-sample control flow, returned as a state token so the runner
// can report exactly where a fail-closed stop happened.
enum class ControlOutcome {
    Ok,             // full PREPARE -> ... -> STOPPED cycle completed
    NegativeControlFailed,
    PrepareFailed,
    PreparedRejected,
    StartFailed,
    ReadyRejected,
    CaptureFailed,
    CapturedFailed,
    StoppedFailed,
    Aborted,
};

inline const char* control_outcome_token(ControlOutcome o) {
    switch (o) {
        case ControlOutcome::Ok: return "CONTROL_OK";
        case ControlOutcome::NegativeControlFailed: return "NEGATIVE_CONTROL_FAIL";
        case ControlOutcome::PrepareFailed: return "PREPARE_FAIL";
        case ControlOutcome::PreparedRejected: return "PREPARED_REJECTED";
        case ControlOutcome::StartFailed: return "START_FAIL";
        case ControlOutcome::ReadyRejected: return "READY_REJECTED";
        case ControlOutcome::CaptureFailed: return "CAPTURE_FAIL";
        case ControlOutcome::CapturedFailed: return "CAPTURED_FAIL";
        case ControlOutcome::StoppedFailed: return "STOPPED_FAIL";
        case ControlOutcome::Aborted: return "ABORTED";
    }
    return "UNKNOWN";
}

}  // namespace iqpctbrx
