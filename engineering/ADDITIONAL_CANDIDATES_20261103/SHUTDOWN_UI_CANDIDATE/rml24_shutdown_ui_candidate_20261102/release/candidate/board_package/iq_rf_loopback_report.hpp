#pragma once

// iq_rf_loopback_report.hpp -- Stage H-F / Route F: the per-file SUMMARY type and
// the memory-safe summary sink, split out of iq_rf_loopback_runner.hpp so the host
// test can exercise the EXACT same struct + push function the board runner uses
// WITHOUT pulling in npu_classifier24.hpp (which needs the iCraft SDK headers that
// are unavailable on the host).
//
// fix7 Task A (memory): the retained summary must not keep the per-file large
// buffers.  rf.sync.aligned_rx is 2P int16; 240 files would retain ~51 MiB and trip
// the M22 RSS-growth gate.  push_rf_file_summary releases aligned_rx (swap to an
// empty vector, which also drops its capacity) BEFORE the move, so the retained
// RfPerFileResult keeps only scalars + short SHAs.

#include "iq_digital_loopback.hpp"   // iqdloop::TxVerify / iqdloop::RefillStat
#include "iq_rf_loopback.hpp"        // iqrfloop::RfFidelityMetrics

#include <cstdint>
#include <string>
#include <vector>

namespace iqrfloop_run {

// One frozen file TX'd -> RX'd -> measured -> (calibrated | classified).  This is
// the summary kept per file; everything large (tx / rx / noise / aligned_rx) is
// released on the way in (see push_rf_file_summary).
struct RfPerFileResult {
    std::string file_name;
    std::uint64_t tx_complex = 0;
    std::uint64_t rx_captured = 0;
    bool capture_ok = false;
    std::string capture_detail;
    bool is_calibration = false;

    iqrfloop::RfFidelityMetrics rf;
    std::string rf_verdict;

    std::string tx_dma_payload_sha;
    bool tx_dma_payload_ok = false;
    int loopback_readback = -1;
    double tx_atten_requested_db = 0.0;
    double tx_atten_readback_db = 0.0;
    bool noise_capture_ok = false;

    // fix8 Task B: 3-window negative-control summary (scalars only, no buffers).
    bool tx_stopped_readback = false;
    bool noise_stable = false;
    double noise_rms_median = 0.0;
    double noise_rms_min = 0.0;
    double noise_rms_max = 0.0;

    bool has_recovered_ref = false;
    int window_delay_offset = -1;
    double window_corr = 0.0;
    double window_nmse = 0.0;
    double window_gain_db = 0.0;
    bool window_sha_ok = false;
    std::string window_aligned_sha;
    std::string window_ref_sha;

    iqdloop::TxVerify tx_verify;
    std::vector<iqdloop::RefillStat> refills;
    std::uint64_t tx_create_delta = 0;
    std::uint64_t tx_destroy_delta = 0;
    std::uint64_t rx_create_delta = 0;
    std::uint64_t rx_destroy_delta = 0;

    std::uint64_t frames = 0;
    std::uint64_t correct = 0;
    int source_class = -1;
    int deployed_class = -1;
};

// fix7 Task A (memory): the retained summary must not keep the per-file large
// buffers.  rf.sync.aligned_rx is 2P int16; 240 files would retain ~51 MiB and trip
// the M22 RSS-growth gate.  Release it here so the summary keeps only scalars + SHAs.
inline void push_rf_file_summary(std::vector<RfPerFileResult>& files,
                                 RfPerFileResult&& pf) {
    std::vector<std::int16_t>().swap(pf.rf.sync.aligned_rx);
    files.push_back(std::move(pf));
}

}  // namespace iqrfloop_run
