#pragma once

// iq_digital_loopback_runner.hpp — Stage H-E / Route E: same-device modulated-IQ
// digital loopback, *board-only* orchestration half.
//
// This header is the iCraft + libiio side of Route E.  It composes the pure-logic
// half (iq_digital_loopback.hpp) with the real device + the NPU:
//
//   device open -> DeviceStateGuard -> force sample rate 2560000 (abs(actual -
//   2560000) <= 5 Hz, fail-closed; 3840000 is NOT accepted) -> TX the FROZEN
//   Stage G int16 cyclically (PlutoTx: RX gain manual/low, LO align, loopback=1,
//   TX atten max-safe + read-back) -> one contiguous RX refill -> int16 fidelity
//   alignment / measurement -> production PreprocessChain (frozen nominal
//   2560000) -> NPU -> merge23 -> per-frame result -> three SEPARATE verdicts.
//
// The three verdicts are kept apart by design (Stage H-E hard requirement 11):
//   * infrastructure  -- device config / TX / RX / sync / capture / restore (gates)
//   * fidelity        -- NMSE / EVM / CFO / correlation (observation tokens)
//   * classification  -- tensor / logits / class consistency (measurement only)
// A classification error never fails infrastructure and vice versa.
//
// RF safety (requirement 7): the TX attenuation is written to the maximum safe
// value and read back inside PlutoTx::prepare(); no antenna, no coax;
// RF_LEAKAGE_NOT_PROVEN is logged continuously; the code never claims RF silence.
// ENSM is NOT in the Device interface (DeviceParams has no ENSM field), so this
// code does not touch it and records "ensm=not_managed_by_this_code".
//
// arbitrary_modulated_iq_fidelity=BOARD_REQUIRED (requirement 10): the host-tone
// digital path has proven TX DMA -> internal loopback -> RX DMA structure, but NOT
// arbitrary modulated-IQ fidelity.  That fact is only established by this board
// run and is reported as BOARD_REQUIRED, never as PROVEN by host tests.

#include "chain_common.hpp"
#include "npu_classifier24.hpp"
#include "board_common.hpp"
#include "iq_digital_loopback.hpp"
#include "iq_digital_loopback_sync.hpp"
#include "iq_digital_loopback_transfer.hpp"
#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqdloop_run {

using Clock = std::chrono::steady_clock;

// Local merge + argmax (the board runner's own copies live in the anonymous
// namespace of board_gate9_full_chain_rml23.cpp, which this header cannot see).
inline std::vector<float> merge23(const std::vector<float>& raw24) {
    if (raw24.size() != static_cast<std::size_t>(rml23::kNpuOutputDim))
        throw std::runtime_error("rml23: raw logits width != 24");
    float m23[rml23::kDeployedClassCount];
    if (!rml23::merge_logits_23(raw24.data(), m23))
        throw std::runtime_error("rml23: merge fail-closed (non-finite logits)");
    return std::vector<float>(m23, m23 + rml23::kDeployedClassCount);
}

inline int argmax_of(const std::vector<float>& v) {
    if (v.empty()) return -1;
    int best = 0;
    for (int i = 1; i < static_cast<int>(v.size()); ++i)
        if (v[i] > v[best]) best = i;
    return best;
}

inline double elapsed_us(Clock::time_point t0) {
    return std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
}

// One frozen file TX'd -> RX'd -> measured -> classified.
struct PerFileResult {
    std::string file_name;
    std::uint64_t tx_complex = 0;      // cyclic TX period actually loaded
    std::uint64_t rx_captured = 0;     // RX complex samples captured (one refill)
    bool capture_ok = false;
    std::string capture_detail;        // continuity evidence

    iqdloop::FidelityMetrics fid;
    std::string fidelity_verdict;

    // fix5: full-period FFT circular sync + scale-independent fidelity (replaces the
    // fix4 bounded delay search), plus the TX DMA payload verify evidence.
    iqdloop_sync::SyncFidelityMetrics sync;
    std::string tx_dma_payload_sha;
    bool tx_dma_payload_ok = false;

    // fix6 requirement 7: classification-window selection + Route D tensor compare.
    bool has_recovered_ref = false;
    int window_delay_offset = -1;
    double window_corr = 0.0;
    double window_nmse = 0.0;
    double window_gain_db = 0.0;
    bool window_sha_ok = false;
    std::string window_aligned_sha;
    std::string window_ref_sha;

    // fix2 per-file evidence: TX-content verification (req 2), per-refill stats
    // (req 3), and TX/RX buffer lifecycle deltas (req 1).
    iqdloop::TxVerify tx_verify;
    std::vector<iqdloop::RefillStat> refills;
    std::uint64_t tx_create_delta = 0;
    std::uint64_t tx_destroy_delta = 0;
    std::uint64_t rx_create_delta = 0;
    std::uint64_t rx_destroy_delta = 0;

    std::uint64_t frames = 0;          // output frames produced from this file
    std::uint64_t correct = 0;         // merged23 argmax == deployed class
    int source_class = -1;
    int deployed_class = -1;
};

struct RunReport {
    // input provenance
    std::string input_kind;
    std::string frozen_dir;
    std::uint64_t frozen_files = 0;
    std::string model_sha;

    // fail-closed signalling for the thin .cpp wrapper
    bool device_not_found = false;
    std::string error;                 // non-empty => the run failed closed

    // infrastructure (device config / TX / RX / sync / capture / restore)
    long long requested_rate = 0;
    long long rx_rate = 0;
    long long tx_rate = 0;
    double rate_err_hz = 0.0;
    double rate_err_ppm = 0.0;
    bool sample_rate_ok = false;
    int loopback_readback = -1;
    double tx_atten_requested = 0.0;
    double tx_atten_readback = 0.0;
    bool restore_ok = false;
    std::string restore_report;

    std::vector<PerFileResult> files;

    // classification aggregate (one input kind; kinds are never mixed)
    std::uint64_t frames = 0;
    std::uint64_t correct = 0;
    std::string classification_verdict;
    std::uint64_t frozen_frames = 0;      // generated-2p56m sidecar reference
    std::uint64_t frozen_correct = 0;
    bool has_frozen_ref = false;

    // M22 runtime baseline handoff (the wrapper calls finish_m22_runtime with it)
    bool have_resources = false;
    m22::ResourceSample first_res, last_res, peak_res;

    // final gate (infrastructure gates ONLY; restore folded by the wrapper)
    bool functional_pass = false;
    std::string detail;
};

// fix7 Task A (memory): a PerFileResult retained in RunReport::files must NOT keep
// the per-file large buffers.  sync.aligned_rx is 2P int16 (~215 KB per file); 240
// files would retain ~51 MiB and trip the M22 RSS-growth gate.  Release it here so
// the retained summary keeps only scalars + short SHAs, and the per-file loop reuses
// the same freed block (RSS stays bounded across the whole run).
inline void push_file_summary(std::vector<PerFileResult>& files, PerFileResult&& pf) {
    std::vector<std::int16_t>().swap(pf.sync.aligned_rx);
    files.push_back(std::move(pf));
}

// ---------------------------------------------------------------------------
// run_iq_digital_loopback
// ---------------------------------------------------------------------------
inline RunReport run_iq_digital_loopback(
    chain::NpuClassifier24& npu, m22::StageTiming& timing, int argc, char** argv,
    const std::function<void(const rf::ResultFrame&)>& on_frame) {
    RunReport rep;

    // ---- args ----
    rep.input_kind = board::get_opt(argc, argv, "--input-kind", "");
    rep.frozen_dir = board::get_opt(argc, argv, "--frozen-dir", "");
    if (rep.frozen_dir.empty())
        throw std::runtime_error("Route E requires --frozen-dir=<Stage G artifacts dir>");
    rep.model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const std::uint64_t center_hz =
        board::opt_u64(argc, argv, "--center", 2400000000ULL);
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
    const double tx_atten = board::opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
    const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
    const double rms_counts = board::opt_d(argc, argv, "--raw-complex-rms-counts", 16.0);
    const float rec_scale = static_cast<float>(board::opt_d(
        argc, argv, "--rec-scale",
        static_cast<double>(chain::calibrate_rec_scale(rms_counts, chain::kTargetModelRms))));
    const std::size_t delay_margin = static_cast<std::size_t>(
        board::opt_u64(argc, argv, "--delay-margin", 16384));
    const std::uint64_t tx_complex_cap =
        board::opt_u64(argc, argv, "--tx-complex", 0);   // 0 = full frozen file
    // fix2 requirement 7 (on-board sequence diagnostics): reorder / repeat / filter
    // the frozen files so the user can run "single file x4", "manifest order", and
    // "reverse order" and see whether a "first two have data, last two zero" leak is
    // order-dependent (state leak) or modulation-dependent (content).
    const std::string file_order = board::get_opt(argc, argv, "--file-order", "manifest");
    const std::uint64_t file_repeat =
        board::opt_u64(argc, argv, "--file-repeat", 1);
    const std::string file_filter = board::get_opt(argc, argv, "--file-filter", "");
    if (file_order != "manifest" && file_order != "reverse")
        throw std::runtime_error("Route E: --file-order must be manifest|reverse (got '" +
                                 file_order + "')");
    if (file_repeat == 0)
        throw std::runtime_error("Route E: --file-repeat must be >= 1");

    // fix3 requirement 6: an explicit, test-fixture-only TX scale to compensate a
    // PROVEN fixed digital-loopback attenuation (--phase=iq-digital-loopback-sweep
    // diagnoses it and prints the recommended value).  Scale 1.0 (default) is a no-op
    // and changes nothing; it never touches the production preprocess chain.
    const double tx_scale = board::opt_d(argc, argv, "--digital-loopback-tx-scale", 1.0);
    if (tx_scale <= 0.0)
        throw std::runtime_error("Route E: --digital-loopback-tx-scale must be > 0");

    // fix3 requirement 5: explicit FORMAT corrections (bit position), never an
    // empirical multiplier.  The sweep discovers these; passing them here makes the
    // TX/RX convert paths use the host-side mirror with the corrected format.  A
    // negative shift default means "absent" (no override).
    const long long rx_shift = board::opt_i64(argc, argv, "--rx-format-shift", -1);
    const long long tx_shift = board::opt_i64(argc, argv, "--tx-format-shift", -1);
    const long long rx_bits = board::opt_i64(argc, argv, "--rx-format-bits", 0);
    const long long tx_bits = board::opt_i64(argc, argv, "--tx-format-bits", 0);
    if (rx_shift >= 0 && rx_shift > 15) throw std::runtime_error(
        "Route E: --rx-format-shift must be 0..15");
    if (tx_shift >= 0 && tx_shift > 15) throw std::runtime_error(
        "Route E: --tx-format-shift must be 0..15");
    if (rx_bits < 0 || rx_bits > 16) throw std::runtime_error(
        "Route E: --rx-format-bits must be 0..16 (0 = absent)");
    if (tx_bits < 0 || tx_bits > 16) throw std::runtime_error(
        "Route E: --tx-format-bits must be 0..16 (0 = absent)");

    // ---- load frozen IQ (fail-closed: never re-generate) ----
    std::vector<iqdloop::FrozenIq> frozen =
        iqdloop::load_frozen_iq(rep.frozen_dir, rep.input_kind);

    // filter (substring on file_name), then order, then repeat.
    if (!file_filter.empty()) {
        std::vector<iqdloop::FrozenIq> kept;
        for (const auto& fz : frozen)
            if (fz.file_name.find(file_filter) != std::string::npos)
                kept.push_back(fz);
        frozen = std::move(kept);
    }
    if (file_order == "reverse")
        std::reverse(frozen.begin(), frozen.end());
    if (file_repeat > 1) {
        const std::vector<iqdloop::FrozenIq> base = frozen;
        frozen.clear();
        for (std::uint64_t i = 0; i < file_repeat; ++i)
            frozen.insert(frozen.end(), base.begin(), base.end());
    }
    if (frozen.empty())
        throw std::runtime_error("STAGE_G_FROZEN_IQ_REQUIRED: no frozen files after "
                                 "file-order/file-filter/file-repeat selection");

    rep.frozen_files = static_cast<std::uint64_t>(frozen.size());
    const cat::Contract contract = chain::contract_23();

    std::printf("ARBITRARY_MODULATED_IQ_FIDELITY BOARD_REQUIRED input_kind=%s "
                "frozen_dir=%s frozen_files=%llu rec_scale=%.6f "
                "file_order=%s file_repeat=%llu file_filter=%s\n",
                rep.input_kind.c_str(), rep.frozen_dir.c_str(),
                static_cast<unsigned long long>(rep.frozen_files),
                static_cast<double>(rec_scale),
                file_order.c_str(),
                static_cast<unsigned long long>(file_repeat),
                file_filter.c_str());
    std::fflush(stdout);

    // ---- device open (device-not-found is exit code 2, not a throw) ----
    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        rep.device_not_found = true;
        rep.error = e.what();
        return rep;
    }

    rep.first_res = m22::read_resources();
    rep.have_resources = m22::resource_sampling_supported();

    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        // ---- sample rate: force 2560000, fail-closed abs(actual-2560000) <= 5 Hz ----
        const long long requested = static_cast<long long>(iqdloop::kFrozenFsIn);
        {
            m22::StageTiming::Timer rf_t(timing, m22::StageId::RfConfig);
            dev->set_sample_rate(requested);
        }
        rep.requested_rate = requested;
        rep.rx_rate = dev->get_rx_sample_rate();
        rep.tx_rate = dev->get_tx_sample_rate();
        rep.rate_err_hz = static_cast<double>(rep.rx_rate - requested);
        rep.rate_err_ppm = 1e6 * rep.rate_err_hz / static_cast<double>(requested);
        const bool rx_ok = std::llabs(rep.rx_rate - requested) <= 5;
        const bool tx_ok = std::llabs(rep.tx_rate - requested) <= 5;
        rep.sample_rate_ok = rx_ok && tx_ok;
        if (!rep.sample_rate_ok) {
            rep.error = "sample_rate_mismatch: requested=" + std::to_string(requested) +
                        " rx=" + std::to_string(rep.rx_rate) +
                        " tx=" + std::to_string(rep.tx_rate) +
                        " (abs(actual-requested) must be <= 5 Hz; 3840000 fallback "
                        "is fail-closed)";
            return rep;
        }

        // ---- fix3 requirement 1: audit the TX/RX channel data format ----
        // Print the libiio-reported length/bits/shift/is_signed/is_be for BOTH
        // directions, then apply an explicit FORMAT override only when one was
        // requested (requirement 5).  The override is a bit-position correction
        // (shift/bits), never an empirical multiplier.
        const pluto::DataFormatInfo rx_fmt = dev->rx_data_format();
        const pluto::DataFormatInfo tx_fmt = dev->tx_data_format();
        std::printf("IQ_DIGITAL_LOOPBACK_FORMAT dir=tx %s\n",
                    pluto::describe_data_format(tx_fmt).c_str());
        std::printf("IQ_DIGITAL_LOOPBACK_FORMAT dir=rx %s\n",
                    pluto::describe_data_format(rx_fmt).c_str());
        std::fflush(stdout);

        const bool have_rx_override = (rx_shift >= 0) || (rx_bits > 0);
        const bool have_tx_override = (tx_shift >= 0) || (tx_bits > 0);
        if (have_tx_override) {
            pluto::DataFormatInfo o = tx_fmt;
            if (tx_shift >= 0) o.shift = static_cast<std::uint32_t>(tx_shift);
            if (tx_bits > 0) o.bits = static_cast<std::uint32_t>(tx_bits);
            dev->set_tx_data_format_override(o);
            std::printf("IQ_DIGITAL_LOOPBACK_FORMAT_OVERRIDE dir=tx %s\n",
                        pluto::describe_data_format(o).c_str());
            std::fflush(stdout);
        }
        if (have_rx_override) {
            pluto::DataFormatInfo o = rx_fmt;
            if (rx_shift >= 0) o.shift = static_cast<std::uint32_t>(rx_shift);
            if (rx_bits > 0) o.bits = static_cast<std::uint32_t>(rx_bits);
            dev->set_rx_data_format_override(o);
            std::printf("IQ_DIGITAL_LOOPBACK_FORMAT_OVERRIDE dir=rx %s\n",
                        pluto::describe_data_format(o).c_str());
            std::fflush(stdout);
        }

        // ---- per-file loop ----
        std::uint64_t global_frame_id = 0;
        bool all_preserves = true;   // fix5: every file must reach PRESERVES_IQ
        rep.has_frozen_ref = !frozen.empty() && frozen[0].has_frozen_ref;
        rep.frozen_frames = 0;
        rep.frozen_correct = 0;
        for (const auto& fz : frozen) {
            if (board::g_stop_requested) break;
            if (fz.has_frozen_ref) {
                rep.frozen_frames += fz.frozen_frames;
                rep.frozen_correct += fz.frozen_deployed_correct;
            }

            PerFileResult pf;
            pf.file_name = fz.file_name;
            pf.source_class = fz.source_class;
            pf.deployed_class = fz.deployed_class;

            std::printf("IQ_DIGITAL_LOOPBACK file=%s input_kind=%s source_class=%d "
                        "deployed_class=%d modulation=%s frozen_complex=%llu "
                        "frozen_frames=%llu frozen_correct=%llu\n",
                        fz.file_name.c_str(), rep.input_kind.c_str(), fz.source_class,
                        fz.deployed_class, fz.modulation.c_str(),
                        static_cast<unsigned long long>(fz.complex_count),
                        static_cast<unsigned long long>(fz.frozen_frames),
                        static_cast<unsigned long long>(fz.frozen_deployed_correct));
            std::fflush(stdout);

            // fix2: ONE shared transfer path -- load+verify the FROZEN bytes (req 2),
            // a fresh cyclic TX buffer per file (req 1), a stale-RX flush (recreate +
            // discard refill, req 3), then ONE contiguous capture refill.  This is the
            // exact code the host sequence test exercises (no drift between runner and
            // test).  The -40 dB ceiling is still enforced inside PlutoTx::prepare()
            // (req 8).
            const iqdloop_run::TransferResult tr = iqdloop_run::transfer_one_file(
                *dev, fz.path, fz.complex_count, fz.sha256, center_hz, gain_db,
                tx_atten, delay_margin, tx_complex_cap, &timing, tx_scale,
                tx_fmt, rx_fmt);

            pf.tx_complex = static_cast<std::uint64_t>(tr.tx.size() / 2);
            pf.tx_verify = tr.tx_verify;
            pf.refills = tr.refills;
            pf.tx_create_delta = tr.tx_create_delta;
            pf.tx_destroy_delta = tr.tx_destroy_delta;
            pf.rx_create_delta = tr.rx_create_delta;
            pf.rx_destroy_delta = tr.rx_destroy_delta;
            pf.capture_ok = tr.capture_ok;
            pf.rx_captured = static_cast<std::uint64_t>(tr.rx.size() / 2);
            pf.capture_detail = tr.cont.report();

            rep.tx_atten_requested = tr.tx_atten_requested_db;
            rep.tx_atten_readback = tr.tx_atten_readback_db;
            rep.loopback_readback = tr.loopback_readback;

            // fix5: record the TX DMA payload evidence (post-convert, pre-push SHA).
            pf.tx_dma_payload_sha = tr.tx_dma_payload_sha;
            pf.tx_dma_payload_ok = tr.tx_dma_payload_ok;

            // req 2: the LOADED TX bytes actually pushed to the cyclic buffer hash
            // to the frozen-file SHA and are non-zero.  verify_loaded_tx throws on a
            // SHA mismatch / empty waveform, so reaching here proves those bytes are
            // the frozen bytes verbatim.
            std::printf("IQ_DIGITAL_LOOPBACK_TX_VERIFY file=%s sha=%s nonzero=%llu "
                        "nonzero_rate=%.6f rms=%.3f first_i=%d first_q=%d "
                        "last_i=%d last_q=%d\n",
                        fz.file_name.c_str(), pf.tx_verify.sha256.c_str(),
                        static_cast<unsigned long long>(pf.tx_verify.nonzero),
                        pf.tx_verify.nonzero_rate, pf.tx_verify.rms,
                        pf.tx_verify.first_i, pf.tx_verify.first_q,
                        pf.tx_verify.last_i, pf.tx_verify.last_q);
            std::fflush(stdout);

            // fix3 requirement 6 + fix4 domain mapping: --digital-loopback-tx-scale
            // evidence.  When scale != 1, the frozen bytes are loaded + verified
            // FIRST (pre-scale SHA == frozen SHA), then mapped RX-domain -> TX-domain
            // in the int16 host domain (test fixture only); the post-scale SHA,
            // domain/bits, peaks, and 12-bit clip counts are recorded so a scale can
            // never be confused with a format correction.
            std::printf("IQ_DIGITAL_LOOPBACK_TX_SCALE file=%s scale=%.6f "
                        "sha_pre=%s sha_post=%s clip_pre=%llu clip_post=%llu "
                        "rms_pre=%.3f rms_post=%.3f src_domain=%s dst_domain=%s "
                        "src_bits=%d dst_bits=%d peak_pre=%d peak_post=%d "
                        "scale_clipped=%d\n",
                        fz.file_name.c_str(), tr.tx_scale,
                        tr.tx_sha_pre_scale.c_str(), tr.tx_sha_post_scale.c_str(),
                        static_cast<unsigned long long>(tr.tx_clip_pre_scale),
                        static_cast<unsigned long long>(tr.tx_clip_post_scale),
                        tr.tx_rms_pre_scale, tr.tx_rms_post_scale,
                        tr.src_domain.c_str(), tr.dst_domain.c_str(),
                        tr.src_bits, tr.dst_bits,
                        tr.tx_peak_pre_scale, tr.tx_peak_post_scale,
                        tr.scale_clipped ? 1 : 0);
            std::fflush(stdout);

            // fix5: prove the bytes actually handed to iio_buffer_push (the DMA) are
            // the scaled bytes -- not merely "load + verify + start".  A mismatch is
            // reported here and gated on below (TX_DMA_PAYLOAD_MISMATCH).
            std::printf("IQ_DIGITAL_LOOPBACK_TX_DMA_PAYLOAD file=%s sha=%s "
                        "sha_post=%s ok=%d\n",
                        fz.file_name.c_str(), pf.tx_dma_payload_sha.c_str(),
                        tr.tx_sha_post_scale.c_str(), pf.tx_dma_payload_ok ? 1 : 0);
            std::fflush(stdout);

            // req 3: per-refill evidence for the stale-flush discard refill and the
            // capture refill (non-zero rate / RMS / first / last samples).
            for (const auto& rs : pf.refills) {
                std::printf("IQ_DIGITAL_LOOPBACK_REFILL file=%s kind=%s complex=%llu "
                            "nonzero_rate=%.6f rms=%.3f first_i=%d first_q=%d "
                            "last_i=%d last_q=%d\n",
                            fz.file_name.c_str(), rs.kind.c_str(),
                            static_cast<unsigned long long>(rs.complex),
                            rs.nonzero_rate, rs.rms, rs.first_i, rs.first_q,
                            rs.last_i, rs.last_q);
                std::fflush(stdout);
            }

            // req 1: buffer lifecycle evidence -- one fresh TX buffer created and
            // destroyed per file, and the RX buffer recreated (stale flush) per file.
            std::printf("IQ_DIGITAL_LOOPBACK_BUFFER file=%s tx_create=%llu "
                        "tx_destroy=%llu rx_create=%llu rx_destroy=%llu\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(pf.tx_create_delta),
                        static_cast<unsigned long long>(pf.tx_destroy_delta),
                        static_cast<unsigned long long>(pf.rx_create_delta),
                        static_cast<unsigned long long>(pf.rx_destroy_delta));
            std::fflush(stdout);

            std::printf("RF_LEAKAGE_NOT_PROVEN file=%s tx_atten_requested_db=%.3f "
                        "tx_atten_readback_db=%.3f loopback=%d antenna=none coax=none "
                        "ensm=not_managed_by_this_code\n",
                        fz.file_name.c_str(), rep.tx_atten_requested,
                        rep.tx_atten_readback, rep.loopback_readback);
            std::fflush(stdout);

            // Continuity evidence (stream anomalies + single-refill evidence).
            {
                const board::RxStats& st = tr.st;
                std::string& cd = pf.capture_detail;
                if (st.interrupted) cd += " interrupted=1";
                if (st.overflow) cd += " overflow=" + std::to_string(st.overflow);
                if (st.dropped) cd += " dropped=" + std::to_string(st.dropped);
                if (st.discontinuity) cd += " discontinuity=" + std::to_string(st.discontinuity);
                if (st.timeouts) cd += " timeouts=" + std::to_string(st.timeouts);
            }

            if (board::g_stop_requested || tr.st.interrupted) {
                pf.fidelity_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_DIGITAL_LOOPBACK file=%s interrupted\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                push_file_summary(rep.files, std::move(pf));
                break;
            }

            if (!pf.capture_ok) {
                pf.fidelity_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_DIGITAL_LOOPBACK file=%s capture=FAIL %s\n",
                            fz.file_name.c_str(), pf.capture_detail.c_str());
                std::fflush(stdout);
                push_file_summary(rep.files, std::move(pf));
                continue;
            }

            // Local aliases to the shared transfer's TX (capped waveform) and RX
            // capture, so the fidelity + classification code below is unchanged.
            const std::vector<std::int16_t>& tx_iq = tr.tx;
            const std::vector<std::int16_t>& rx = tr.rx;

            // ---- fidelity (fix5 full-period FFT circular sync) ----
            pf.sync = iqdloop_sync::measure_fidelity_fix5(
                tx_iq, rx, iqdloop::kFrozenFsIn, tr.dst_bits, tr.src_bits,
                iqdloop_sync::kTransientDiscardComplex);
            if (!pf.tx_dma_payload_ok) {
                pf.fidelity_verdict = "TX_DMA_PAYLOAD_MISMATCH";
            } else {
                pf.fidelity_verdict = iqdloop_sync::fidelity_verdict_fix6(pf.sync);
            }
            if (!iqdloop_sync::fidelity_gate_ok_fix6(pf.fidelity_verdict.c_str()))
                all_preserves = false;
            std::printf("IQ_DIGITAL_LOOPBACK file=%s fidelity=%s linear_delay=%llu "
                        "circular_shift=%llu wrap_count=%llu aligned_start=%llu "
                        "compared_samples=%llu transient_discard=%llu peak_corr=%.6f "
                        "second_peak_corr=%.6f peak_ratio=%.3f gain_db=%.3f "
                        "phase_deg=%.3f gain_normalized_db=%.3f normalized_gain_ok=%d "
                        "normalized_residual=%.6f evm_pct=%.3f corr=%.6f "
                        "nmse_evm_consistent=%d nmse_dc_preserved=%.6f "
                        "nmse_dc_removed=%.6f nmse_active_region=%.6f rms_tx=%.3f "
                        "rms_rx=%.3f cfo_hz=%.3f phase_drift_deg=%.3f corr_swap=%.6f "
                        "corr_conj=%.6f "
                        "tx_peak=%d tx_bits=%d tx_positive_rail=%d tx_negative_rail=%d "
                        "tx_clip_count=%llu tx_clipped=%d "
                        "rx_peak=%d rx_bits=%d rx_positive_rail=%d rx_negative_rail=%d "
                        "rx_clip_count=%llu rx_clipped=%d capture_too_short=%d\n",
                        fz.file_name.c_str(), pf.fidelity_verdict.c_str(),
                        static_cast<unsigned long long>(pf.sync.sync.linear_delay),
                        static_cast<unsigned long long>(pf.sync.sync.circular_shift),
                        static_cast<unsigned long long>(pf.sync.sync.wrap_count),
                        static_cast<unsigned long long>(pf.sync.sync.aligned_start),
                        static_cast<unsigned long long>(pf.sync.sync.compared_samples),
                        static_cast<unsigned long long>(pf.sync.sync.transient_discard_samples),
                        pf.sync.sync.peak_corr, pf.sync.sync.second_peak_corr,
                        pf.sync.sync.peak_ratio, pf.sync.gain_db, pf.sync.phase_deg,
                        pf.sync.gain_normalized_db, pf.sync.normalized_gain_ok ? 1 : 0,
                        pf.sync.normalized_residual, pf.sync.evm_pct, pf.sync.corr,
                        pf.sync.nmse_evm_consistent ? 1 : 0, pf.sync.nmse_dc_preserved,
                        pf.sync.nmse_dc_removed, pf.sync.nmse_active_region,
                        pf.sync.rms_tx, pf.sync.rms_rx, pf.sync.cfo_hz,
                        pf.sync.phase_drift_deg, pf.sync.corr_swap, pf.sync.corr_conj,
                        pf.sync.tx_peak, pf.sync.tx_bits,
                        pf.sync.tx_positive_rail, pf.sync.tx_negative_rail,
                        static_cast<unsigned long long>(pf.sync.tx_clip_count),
                        pf.sync.tx_clipped ? 1 : 0,
                        pf.sync.rx_peak, pf.sync.rx_bits,
                        pf.sync.rx_positive_rail, pf.sync.rx_negative_rail,
                        static_cast<unsigned long long>(pf.sync.rx_clip_count),
                        pf.sync.rx_clipped ? 1 : 0,
                        pf.sync.capture_too_short ? 1 : 0);
            // fix6 requirement 1: circular-origin uniqueness is a SEPARATE conclusion.
            // AMBIGUOUS_EQUIVALENT (multiple equivalent origins) must be reported
            // independently and must never read as waveform distortion.
            std::printf("IQ_DIGITAL_LOOPBACK_SYNC_ORIGIN file=%s sync_origin=%s "
                        "tx_autocorr_second=%.6f competing_peaks=%llu "
                        "equivalent_peaks=%llu unexplained_peaks=%llu "
                        "best_unexplained_corr=%.6f\n",
                        fz.file_name.c_str(),
                        iqdloop_sync::sync_origin_name(pf.sync.sync.origin),
                        pf.sync.sync.tx_autocorr_second,
                        static_cast<unsigned long long>(pf.sync.sync.competing_peaks),
                        static_cast<unsigned long long>(pf.sync.sync.equivalent_peaks),
                        static_cast<unsigned long long>(pf.sync.sync.unexplained_peaks),
                        pf.sync.sync.best_unexplained_corr);
            std::fflush(stdout);

            // fix5: a fidelity failure forbids classification (INVALID_DUE_TO_FIDELITY_GATE).
            if (!iqdloop_sync::fidelity_gate_ok_fix6(pf.fidelity_verdict.c_str())) {
                std::printf("IQ_DIGITAL_LOOPBACK file=%s classification=SKIPPED "
                            "reason=fidelity_gate fidelity=%s\n",
                            fz.file_name.c_str(), pf.fidelity_verdict.c_str());
                std::fflush(stdout);
                push_file_summary(rep.files, std::move(pf));
                continue;
            }

            // ---- classification: feed the CYCLICALLY-ALIGNED RX period (exactly the
            //      TX'd samples) through the production chain (frozen nominal
            //      2560000), then NPU -> merge23.  aligned_rx[m] ~= g * tx[m] was
            //      produced by measure_fidelity_fix5 via a mod-P wrap, so a contiguous
            //      rx[d..] read can never run past the end of the capture.
            const std::vector<std::int16_t>& win = pf.sync.aligned_rx;
            const std::size_t win_complex = win.size() / 2;
            if (win_complex == 0) {
                pf.fidelity_verdict = "INSUFFICIENT_EVIDENCE";
                std::printf("IQ_DIGITAL_LOOPBACK file=%s aligned window empty\n",
                            fz.file_name.c_str());
                std::fflush(stdout);
                push_file_summary(rep.files, std::move(pf));
                continue;
            }

            chain::PreprocessChain chain(iqdloop::kFrozenFsIn, nco_offset, rec_scale);
            {
                m22::StageTiming::Timer t(timing, m22::StageId::Preprocess);
                chain.push_int16(win.data(), win_complex);
            }

            // Collect every naive tensor the chain emitted (>= 1 frame).  For
            // radioml-reconstructed, fix6 requirement 7 selects the ONE window that
            // matches Route D's aligned recovered tensor instead of classifying the
            // naive frames (which may straddle the zero-guard / cyclic boundary).
            std::vector<float> recovered_stream;
            {
                std::vector<float> t(chain::kTensorFloats);
                while (chain.ready() > 0) {
                    if (board::g_stop_requested) break;
                    if (!chain.pull_tensor(t.data())) break;
                    recovered_stream.insert(recovered_stream.end(), t.begin(), t.end());
                }
            }

            // classify ONE tensor (infer -> merge23 -> argmax -> record).
            const auto classify_one = [&](const float* tptr) {
                const auto t0 = Clock::now();
                std::vector<float> raw24;
                npu.infer(tptr, raw24);
                const double classify_us = elapsed_us(t0);
                timing.record(m22::StageId::NpuInfer, classify_us);

                const std::vector<float> m23 = merge23(raw24);
                const int merged_top = argmax_of(m23);
                const bool correct = (merged_top == fz.deployed_class);
                ++pf.frames;
                if (correct) ++pf.correct;
                ++global_frame_id;

                rf::ResultFrame r;
                r.frame_id = global_frame_id;
                r.timestamp_us = global_frame_id * 8000ULL;   // 1024/128k = 8 ms/frame
                r.source = "iq_digital_loopback";
                r.mock = false;
                chain::fill_result_rml23(r, raw24, m23, contract, rep.model_sha,
                                         std::numeric_limits<double>::quiet_NaN());
                r.classify_us = classify_us;
                r.e2e_us = classify_us;
                on_frame(r);
            };

            // fix6 requirement 7: for radioml-reconstructed, select the model window
            // from the original RadioML 1024-point valid region using Route D's
            // recovered tensor, and compare SHA/value frame-by-frame.
            pf.has_recovered_ref = fz.has_recovered_ref;
            if (fz.has_recovered_ref) {
                const std::vector<float> ref =
                    iqdloop::load_recovered_tensor(fz.recovered_tensor_path,
                                                   fz.recovered_tensor_sha256);
                const iqdloop::ClassificationWindow cw =
                    iqdloop::select_classification_window(recovered_stream, ref);
                pf.window_delay_offset = cw.delay_offset;
                pf.window_corr = cw.tensor_corr;
                pf.window_nmse = cw.tensor_nmse;
                pf.window_gain_db = cw.tensor_gain_db;
                pf.window_sha_ok = cw.sha_equal;
                pf.window_aligned_sha = cw.aligned_sha256;
                pf.window_ref_sha = cw.ref_sha256;
                std::printf("IQ_DIGITAL_LOOPBACK_WINDOW file=%s recovered_frames=%llu "
                            "delay_offset=%d corr=%.6f nmse=%.6f gain_db=%.3f "
                            "sha_equal=%d aligned_sha=%s ref_sha=%s\n",
                            fz.file_name.c_str(),
                            static_cast<unsigned long long>(cw.recovered_frames),
                            cw.delay_offset, cw.tensor_corr, cw.tensor_nmse,
                            cw.tensor_gain_db, cw.sha_equal ? 1 : 0,
                            cw.aligned_sha256.c_str(), cw.ref_sha256.c_str());
                std::fflush(stdout);

                if (cw.valid && !cw.aligned_tensor.empty())
                    classify_one(cw.aligned_tensor.data());
                else
                    std::printf("IQ_DIGITAL_LOOPBACK file=%s classification=SKIPPED "
                                "reason=no_valid_window\n", fz.file_name.c_str());
            } else {
                // generated-2p56m: classify each naive frame (unchanged fix5 path).
                std::size_t off = 0;
                while (off + chain::kTensorFloats <= recovered_stream.size()) {
                    if (board::g_stop_requested) break;
                    classify_one(recovered_stream.data() + off);
                    off += chain::kTensorFloats;
                }
            }

            std::printf("IQ_DIGITAL_LOOPBACK file=%s frames=%llu correct=%llu "
                        "deployed=%d source=%d%s\n",
                        fz.file_name.c_str(),
                        static_cast<unsigned long long>(pf.frames),
                        static_cast<unsigned long long>(pf.correct),
                        fz.deployed_class, fz.source_class,
                        (fz.has_frozen_ref && pf.frames != fz.frozen_frames)
                            ? " (frames != frozen_frames)"
                            : "");
            std::fflush(stdout);

            push_file_summary(rep.files, std::move(pf));
        }

        // ---- classification aggregate ----
        for (const auto& pf : rep.files) {
            rep.frames += pf.frames;
            rep.correct += pf.correct;
        }
        // fix5: classification is only meaningful when EVERY frozen file passed the
        // fidelity gate.  Otherwise it is marked INVALID_DUE_TO_FIDELITY_GATE (a
        // distorted loopback must never be scored as if it were clean).
        rep.classification_verdict =
            all_preserves
                ? iqdloop::classification_verdict(rep.frames, rep.correct,
                                                  rep.has_frozen_ref,
                                                  rep.frozen_frames, rep.frozen_correct)
                : "INVALID_DUE_TO_FIDELITY_GATE";

        guard->restore();
    } catch (const std::exception& e) {
        rep.error = e.what();
    }

    // Restore is idempotent; fold the post-restore read-back into the detail.
    if (guard) {
        guard->restore();
        rep.restore_ok = guard->restore_ok();
        rep.restore_report = board::restore_report(*dev, *guard);
    }

    rep.last_res = m22::read_resources();
    rep.peak_res = (rep.last_res.rss_kb > rep.first_res.rss_kb)
                       ? rep.last_res
                       : rep.first_res;

    // ---- infrastructure verdict (device config / TX / RX / sync / capture) ----
    bool infra_ok = rep.error.empty() && rep.sample_rate_ok && !frozen.empty();
    // fix2 requirement 6 + fix5: a fidelity failure (RX_ALL_ZERO / RX_LOW_AMPLITUDE /
    // CAPTURE_TOO_SHORT / CIRCULAR_SYNC_AMBIGUOUS / DISTORTS_IQ / NOT_PROVEN /
    // INSUFFICIENT_EVIDENCE / TX_DMA_PAYLOAD_MISMATCH) must force the total gate to
    // FAIL -- never PASS on a fidelity failure.  Classification runs only on
    // PRESERVES_IQ (else INVALID_DUE_TO_FIDELITY_GATE), so frames==0 is NOT itself an
    // infra failure here (it is the expected skip on a fidelity-gate miss).
    bool fidelity_ok = !rep.files.empty();
    for (const auto& pf : rep.files) {
        if (!pf.capture_ok) infra_ok = false;
        if (!iqdloop_sync::fidelity_gate_ok_fix6(pf.fidelity_verdict.c_str()))
            fidelity_ok = false;
    }
    rep.functional_pass = infra_ok && fidelity_ok;

    // ---- detail string (infra + fidelity + classification, all separable) ----
    std::string detail = "input_kind=" + rep.input_kind +
                         " frozen_files=" + std::to_string(rep.frozen_files) +
                         " requested_rate=" + std::to_string(rep.requested_rate) +
                         " rx_rate=" + std::to_string(rep.rx_rate) +
                         " tx_rate=" + std::to_string(rep.tx_rate) +
                         " rate_err_hz=" + std::to_string(rep.rate_err_hz) +
                         " rate_err_ppm=" + std::to_string(rep.rate_err_ppm) +
                         " loopback=" + std::to_string(rep.loopback_readback) +
                         " tx_atten_requested_db=" + std::to_string(rep.tx_atten_requested) +
                         " tx_atten_readback_db=" + std::to_string(rep.tx_atten_readback) +
                         " arbitrary_modulated_iq_fidelity=BOARD_REQUIRED";
    for (const auto& pf : rep.files) {
        detail += " file=" + pf.file_name +
                  " fidelity=" + pf.fidelity_verdict +
                  " normalized_residual=" + std::to_string(pf.sync.normalized_residual) +
                  " corr=" + std::to_string(pf.sync.corr) +
                  " frames=" + std::to_string(pf.frames) +
                  " correct=" + std::to_string(pf.correct) +
                  " capture_ok=" + std::to_string(pf.capture_ok ? 1 : 0);
    }
    detail += " classification_verdict=" + rep.classification_verdict +
              " classification_frames=" + std::to_string(rep.frames) +
              " classification_correct=" + std::to_string(rep.correct) +
              " has_frozen_ref=" + std::to_string(rep.has_frozen_ref ? 1 : 0) +
              " frozen_frames=" + std::to_string(rep.frozen_frames) +
              " frozen_correct=" + std::to_string(rep.frozen_correct);
    if (!rep.error.empty())
        detail += " error=" + rep.error;
    detail += rep.restore_report;
    rep.detail = detail;

    return rep;
}

}  // namespace iqdloop_run
