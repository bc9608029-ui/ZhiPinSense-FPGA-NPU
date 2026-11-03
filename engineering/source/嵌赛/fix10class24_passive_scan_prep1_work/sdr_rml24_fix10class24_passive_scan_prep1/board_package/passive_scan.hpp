#pragma once

// passive_scan.hpp -- task fix10class24-passive-scan-prep1: a single-SDR
// RECEIVE-ONLY frequency-scan feature (prepare-only; no board run).
//
// The feature walks a user-set band with a single RX SDR: tune the RX LO to a
// step centre, settle + flush stale frames, run an energy/spectrum candidate
// detector, dwell + capture any candidate's IQ, and then ATTEMPT classification
// ONLY when the frozen model-input contract holds -- which, for an arbitrary
// passive signal, it never provably does.  So the classification gate FAILS
// CLOSED to CLASSIFICATION_UNAVAILABLE and the scan records a DETECTED candidate,
// never a fabricated modulation label.  (An optional raw argmax may be attached
// ONLY as an explicitly-marked UNVERIFIED candidate -- it is never a reliable
// identification.)
//
// Pure-logic, iCraft-free, libiio-free, header-only: the ONLY device effects are
// the methods of the injectable ScanDeviceControl interface (set_rx_lo / set_rx_bw
// / set_rx_gain / flush / save+restore), so the whole state machine is
// host-testable with a scripted fake device + synthetic spectra (see
// host_tests/test_passive_scan.cpp).  The board producer (a later integration
// step, NOT this task) backs ScanDeviceControl with pluto::Device and supplies one
// PowerSpectrum per detection frame and one interleaved-I16 capture buffer per
// capture frame.
//
// Red lines honoured here by construction:
//   * no TX path, no loopback, no training, no re-capture of the controlled path;
//   * the 0.100 fidelity gate and the frozen receiver_scale / recovery chain are
//     untouched (this header does not include or modify them);
//   * candidate count, IQ-save size and history length are all HARD-BOUNDED;
//   * classification is never conflated with detection -- a detection is a
//     DETECTED candidate, a classification is only ever CLASSIFICATION_UNAVAILABLE
//     (contract not held) or an explicitly-marked UNVERIFIED candidate.

#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace pscan {

// PlutoSDR (AD9364) tuneable RX range the feature is bounded to.  A user-set band
// must lie wholly inside this range.
constexpr std::uint64_t kPlutoMinHz = 325000000ULL;    // 325 MHz
constexpr std::uint64_t kPlutoMaxHz = 3800000000ULL;   // 3.8 GHz

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
struct PassiveScanConfig {
    std::uint64_t start_hz = 2400000000ULL;   // band low edge
    std::uint64_t stop_hz  = 2430000000ULL;   // band high edge (>= start)
    std::uint64_t step_hz  = 1000000ULL;      // LO step between step centres (> 0, <= coverage width)

    double rx_sample_rate_hz = 2560000.0;     // RX baseband sample rate (Hz)
    double usable_bw_ratio = 0.8;             // usable fraction of the sample rate

    std::int64_t lo_tolerance_hz = 1000;      // LO write/read-back tolerance (fail-closed)

    int settle_frames = 8;                    // frames discarded after flush (AGC/PLL settle)
    int detect_frames = 16;                   // detection frames per step
    int capture_frames = 8;                   // dwell/capture frames per candidate
    int psd_bins = 1024;                      // spectrum bins per detection frame (power of two)

    double noise_percentile = 0.5;            // PSD percentile used as the noise floor
    double threshold_dbfs = 6.0;              // candidate threshold above the noise floor (dB)
    double min_snr_db = 6.0;                  // minimum peak prominence above the floor (dB)
    int dc_guard_bins = 8;                    // bins around the centre (LO/DC leakage) ignored
    int edge_guard_bins = 8;                  // bins at the band edges (filter roll-off) ignored
    int min_occupied_bins = 1;                // minimum contiguous above-threshold bins (>= 1)
    int max_occupied_bins = 0;                // 0 = disabled; else reject wider (broadband junk)

    std::size_t max_candidates_per_step = 8;  // hard cap on candidates per step
    std::size_t max_capture_samples = 8192;   // hard cap on interleaved-I16 samples per candidate
    std::size_t max_history = 1000;           // hard cap on retained scan records
};

// ---------------------------------------------------------------------------
// Coverage plan (derived from config)
// ---------------------------------------------------------------------------
struct CoveragePlan {
    int total_steps = 0;
    std::uint64_t start_hz = 0;
    std::uint64_t stop_hz = 0;
    std::uint64_t step_hz = 0;
    double coverage_width_hz = 0.0;   // rx_sample_rate * usable_bw_ratio
    double overlap_hz = 0.0;          // coverage_width - step (>= 0; gaps are forbidden)
    double frame_period_s = 0.0;      // 1024 / rx_sample_rate
    double step_duration_s = 0.0;     // worst-case (settle+detect+capture) frames * frame_period
    double total_duration_s = 0.0;    // step_duration_s * total_steps

    std::uint64_t center_hz(int step) const {
        const std::uint64_t f = start_hz + static_cast<std::uint64_t>(step) * step_hz;
        return f <= stop_hz ? f : stop_hz;
    }
};

// ---------------------------------------------------------------------------
// Device control (the ONLY device effects the scan is allowed to perform)
// ---------------------------------------------------------------------------
struct ScanDeviceControl {
    virtual ~ScanDeviceControl() = default;
    virtual std::int64_t set_rx_lo(std::int64_t hz) = 0;   // returns the read-back LO
    virtual std::int64_t get_rx_lo() const = 0;
    virtual std::int64_t set_rx_bw(std::int64_t hz) = 0;   // returns the read-back BW
    virtual double set_rx_gain(double db) = 0;             // returns the read-back gain
    virtual void save_params() = 0;                        // snapshot LO/BW/gain for restore
    virtual bool restore_params() = 0;                     // write the snapshot back (false if any write failed)
    virtual bool flush_rx() = 0;                           // discard stale RX samples (recreate buffer)
};

// ---------------------------------------------------------------------------
// Detection inputs / outputs
// ---------------------------------------------------------------------------
// One detection frame's power spectrum (the board producer derives this from the
// RX frame with its existing PSD; the host test synthesises it directly).
struct PowerSpectrum {
    std::vector<float> bin_power_dbfs;   // [psd_bins]; bin i covers [i*bin_hz,(i+1)*bin_hz)
    double bin_hz = 0.0;                 // width of one bin (Hz); fs = psd_bins * bin_hz
    double center_hz = 0.0;              // spectrum centre == LO (so bin i freq = center - fs/2 + i*bin_hz)
    bool nan_inf = false;                // any NaN/Inf in the bin powers
};

// One detected candidate within a step.
struct ScanCandidate {
    std::uint64_t freq_hz = 0;           // detected centre frequency
    double bandwidth_hz = 0.0;           // occupied span (contiguous above-threshold bins)
    double peak_power_dbfs = 0.0;
    double noise_floor_dbfs = 0.0;
    double snr_db = 0.0;                 // peak power - noise floor
    int occupied_bins = 0;
    int peak_bin = -1;
};

// Result of one detection frame.
struct DetectionResult {
    std::vector<ScanCandidate> candidates;  // bounded by max_candidates_per_step
    double noise_floor_dbfs = 0.0;
    bool unresolved = false;               // >max_candidates_per_step distinct clusters
    bool invalid = false;                  // empty spectrum / NaN / capture fault
};

// ---------------------------------------------------------------------------
// Energy detector (pure, per-frame; no internal state)
// ---------------------------------------------------------------------------
class EnergyDetector {
public:
    explicit EnergyDetector(const PassiveScanConfig& cfg) : cfg_(cfg) {
        if (cfg.psd_bins < 4)
            throw std::invalid_argument("passive_scan: psd_bins >= 4");
    }

    // Extract candidates from one spectrum.  Robust to a handful of strong peaks:
    // the noise floor is the configured percentile of the bin powers, and bins in
    // the DC/LO guard and the edge guards are excluded.  Contiguous above-threshold
    // runs become candidates; a run wider than max_occupied_bins (when set) is
    // rejected as broadband junk.  If more distinct runs than max_candidates_per_step
    // are found, unresolved is set and only the top-N by peak power are kept.
    DetectionResult detect(const PowerSpectrum& s) const {
        DetectionResult r;
        const std::size_t n = s.bin_power_dbfs.size();
        if (n == 0 || s.nan_inf || !(s.bin_hz > 0.0)) {
            r.invalid = true;
            return r;
        }

        // Noise floor = percentile of bin powers.
        std::vector<float> sorted = s.bin_power_dbfs;
        std::sort(sorted.begin(), sorted.end());
        const std::size_t pidx = static_cast<std::size_t>(
            std::round(cfg_.noise_percentile * static_cast<double>(n - 1)));
        const float noise_floor = sorted[pidx];
        const float threshold = noise_floor + static_cast<float>(cfg_.threshold_dbfs);
        r.noise_floor_dbfs = static_cast<double>(noise_floor);

        // Guard bins: centre (LO/DC leakage) and both band edges.
        const std::size_t dc_lo = n / 2;
        const std::size_t dc_g = static_cast<std::size_t>(cfg_.dc_guard_bins);
        const std::size_t edge_g = static_cast<std::size_t>(cfg_.edge_guard_bins);
        const std::size_t lo_dc = (dc_lo >= dc_g) ? (dc_lo - dc_g) : 0;
        const std::size_t hi_dc = std::min(n, dc_lo + dc_g + 1);
        const std::size_t lo_edge = std::min(n, edge_g);
        const std::size_t hi_edge = (n >= edge_g) ? (n - edge_g) : 0;

        auto guarded = [&](std::size_t i) {
            return i < lo_edge || i >= hi_edge || (i >= lo_dc && i < hi_dc);
        };

        // Walk contiguous above-threshold runs.
        std::vector<ScanCandidate> cands;
        std::size_t i = 0;
        while (i < n) {
            if (guarded(i) || s.bin_power_dbfs[i] < threshold) { ++i; continue; }
            std::size_t j = i;
            while (j < n && !guarded(j) && s.bin_power_dbfs[j] >= threshold) ++j;
            const std::size_t width = j - i;
            float peak = s.bin_power_dbfs[i];
            std::size_t peak_bin = i;
            for (std::size_t k = i; k < j; ++k) {
                if (s.bin_power_dbfs[k] > peak) { peak = s.bin_power_dbfs[k]; peak_bin = k; }
            }
            if (static_cast<int>(width) >= cfg_.min_occupied_bins &&
                (cfg_.max_occupied_bins <= 0 ||
                 static_cast<int>(width) <= cfg_.max_occupied_bins) &&
                static_cast<double>(peak - noise_floor) >= cfg_.min_snr_db) {
                ScanCandidate c;
                c.peak_bin = static_cast<int>(peak_bin);
                c.occupied_bins = static_cast<int>(width);
                c.peak_power_dbfs = static_cast<double>(peak);
                c.noise_floor_dbfs = static_cast<double>(noise_floor);
                c.snr_db = static_cast<double>(peak - noise_floor);
                c.bandwidth_hz = static_cast<double>(width) * s.bin_hz;
                const double fs = s.bin_hz * static_cast<double>(n);
                c.freq_hz = static_cast<std::uint64_t>(
                    std::llround(s.center_hz - fs / 2.0 +
                                 (static_cast<double>(peak_bin) + 0.5) * s.bin_hz));
                cands.push_back(c);
            }
            i = j;
        }

        if (cands.size() > cfg_.max_candidates_per_step) {
            r.unresolved = true;
            std::sort(cands.begin(), cands.end(), [](const ScanCandidate& a,
                                                     const ScanCandidate& b) {
                return a.peak_power_dbfs > b.peak_power_dbfs;
            });
            cands.resize(cfg_.max_candidates_per_step);
        }
        r.candidates = std::move(cands);
        return r;
    }

private:
    PassiveScanConfig cfg_;
};

// ---------------------------------------------------------------------------
// Classification contract gate (the anti-fabrication mechanism)
// ---------------------------------------------------------------------------
// The frozen 24-class model input contract (established by the controlled
// dual-SDR / canonical-frame chain, NOT by a passive scan) requires, among other
// things: the exact post-decimation model-domain sample rate; a single coherent
// source with CFO recovered; window/symbol alignment to the canonical preamble;
// and the calibrated receiver_scale amplitude domain.  For an arbitrary passive
// signal NONE of these can be established, so the gate fails closed.
struct ContractClauses {
    bool sampling_rate_known = false;   // model-domain sample rate established
    bool cfo_coherent = false;          // single coherent source, CFO recovered
    bool window_aligned = false;        // canonical preamble / symbol alignment
    bool amplitude_domain = false;      // receiver_scale / RMS domain holds
    bool controlled_reference = false;  // a controlled TX reference exists
    bool held() const {
        return sampling_rate_known && cfo_coherent && window_aligned &&
               amplitude_domain && controlled_reference;
    }
};

inline const char* classification_outcome_name(bool contract_held,
                                               bool has_unverified_class) {
    if (contract_held) return "CONTRACT_HELD";
    if (has_unverified_class) return "UNVERIFIED_CANDIDATE";
    return "CLASSIFICATION_UNAVAILABLE";
}

struct ClassificationVerdict {
    ContractClauses clauses;
    bool contract_held = false;         // clauses.held() -- NEVER true for passive scan
    bool has_unverified_class = false;  // an optional raw argmax was attached
    int unverified_class = -1;          // raw argmax, clearly UNVERIFIED (never a reliable id)
    std::string outcome;                // "CLASSIFICATION_UNAVAILABLE" / "UNVERIFIED_CANDIDATE"
};

class ClassificationContractGate {
public:
    explicit ClassificationContractGate(const PassiveScanConfig&) {}

    // Assess whether the model-input contract holds for a passive candidate.  With
    // no controlled reference supplied, every clause fails and the verdict is
    // CLASSIFICATION_UNAVAILABLE.  `unverified_argmax` (>= 0) is accepted ONLY when
    // `allow_unverified_argmax` is true, and is then labelled UNVERIFIED_CANDIDATE,
    // never a reliable identification.
    ClassificationVerdict assess(bool allow_unverified_argmax,
                                 int unverified_argmax) const {
        ClassificationVerdict v;
        // A passive scan supplies no controlled reference, so the contract clauses
        // can never be established.  This is the fail-closed default, not a
        // per-signal decision.
        v.contract_held = false;
        if (allow_unverified_argmax && unverified_argmax >= 0) {
            v.has_unverified_class = true;
            v.unverified_class = unverified_argmax;
        }
        v.outcome = classification_outcome_name(v.contract_held, v.has_unverified_class);
        return v;
    }
};

// ---------------------------------------------------------------------------
// Scan record + bounded history
// ---------------------------------------------------------------------------
struct ScanRecord {
    std::uint64_t record_id = 0;         // monotonic, 1-based
    int step_index = 0;
    std::uint64_t step_lo_hz = 0;        // LO centre of the step
    std::uint64_t candidate_freq_hz = 0; // detected signal centre (best candidate)
    double candidate_bw_hz = 0.0;
    double peak_power_dbfs = 0.0;
    double noise_floor_dbfs = 0.0;
    double snr_db = 0.0;
    int occupied_bins = 0;
    bool unresolved = false;             // UNRESOLVED_MULTISIGNAL
    std::size_t candidates_in_step = 0;
    bool iq_captured = false;
    std::size_t iq_sample_count = 0;     // interleaved I16 samples stored
    bool iq_truncated = false;
    std::string iq_sha256;               // SHA-256 of the stored interleaved bytes (identity)
    std::string classification_outcome;  // "CLASSIFICATION_UNAVAILABLE" / "UNVERIFIED_CANDIDATE"
    bool verified = false;               // NEVER true for a passive scan
    int unverified_class = -1;           // raw argmax only when explicitly allowed
    std::uint64_t frame_ts = 0;          // frame counter at record time
};

// Bounded scan-result history.  Append drops the oldest record past max_history;
// candidate count, IQ-save size and history length are all hard-capped.
class ScanResultStore {
public:
    explicit ScanResultStore(std::size_t max_history = 1000)
        : max_(max_history > 0 ? max_history : 1) {}

    std::size_t size() const { return records_.size(); }
    std::size_t max_history() const { return max_; }
    bool empty() const { return records_.empty(); }

    const ScanRecord& at(std::size_t i) const { return records_.at(i); }
    const std::vector<ScanRecord>& records() const { return records_; }

    std::uint64_t next_id() const { return next_id_; }

    // Append a record, assigning the next monotonic record_id (1-based).  Drops
    // the oldest record past max_history.
    void append(const ScanRecord& rec) {
        ScanRecord r = rec;
        r.record_id = next_id_++;
        records_.push_back(r);
        if (records_.size() > max_)
            records_.erase(records_.begin(), records_.begin() +
                              static_cast<std::ptrdiff_t>(records_.size() - max_));
    }

    void clear() { records_.clear(); next_id_ = 1; }

private:
    std::size_t max_;
    std::uint64_t next_id_ = 1;
    std::vector<ScanRecord> records_;
};

// ---------------------------------------------------------------------------
// Scan state machine
// ---------------------------------------------------------------------------
enum class ScanState {
    Idle = 0,        // before start()
    Tuning = 1,      // LO write + read-back + flush (one tick)
    Settling = 2,    // flush dwell (discard frames; no detection)
    Detecting = 3,   // energy/spectrum candidate detection
    Capturing = 4,   // dwell + buffered IQ capture for a candidate
    Classifying = 5, // contract gate + record append
    Next = 6,        // advancing to the next step (retune)
    Stopping = 7,    // stop() requested; restoring params
    Complete = 8,    // all steps done, params restored
    Stopped = 9,     // stop() finished, params restored
    Error = 10,      // device/fail-closed fault, params restored
};

inline const char* scan_state_name(ScanState s) {
    switch (s) {
        case ScanState::Idle: return "IDLE";
        case ScanState::Tuning: return "TUNING";
        case ScanState::Settling: return "SETTLING";
        case ScanState::Detecting: return "DETECTING";
        case ScanState::Capturing: return "CAPTURING";
        case ScanState::Classifying: return "CLASSIFYING";
        case ScanState::Next: return "NEXT";
        case ScanState::Stopping: return "STOPPING";
        case ScanState::Complete: return "COMPLETE";
        case ScanState::Stopped: return "STOPPED";
        case ScanState::Error: return "ERROR";
    }
    return "UNKNOWN";
}

// One RX frame worth of inputs the producer supplies each tick.
struct FrameInput {
    PowerSpectrum spectrum;            // consumed only while Detecting
    std::vector<std::int16_t> capture_ci16; // interleaved I16, consumed only while Capturing
    bool capture_error = false;        // overflow/drop/discontinuity/short frame
};

// Per-tick result.
struct StepResult {
    ScanState state = ScanState::Idle;
    int step_index = 0;
    std::uint64_t lo_hz = 0;           // LO for THIS step
    std::uint64_t next_lo_hz = 0;      // LO for the NEXT step (0 when complete)
    bool lo_just_tuned = false;        // this tick wrote + verified the LO
    bool lo_verified = false;          // read-back landed within tolerance
    bool candidate_found = false;
    std::size_t candidates_in_step = 0;
    bool record_appended = false;
    std::uint64_t record_id = 0;
    const char* reason = "";           // short log tag (string literal)
};

class PassiveScanStateMachine {
public:
    PassiveScanStateMachine(const PassiveScanConfig& cfg, ScanDeviceControl& dev,
                            bool allow_unverified_argmax = false)
        : cfg_(cfg), dev_(dev), detector_(cfg), gate_(cfg),
          store_(cfg.max_history),
          allow_unverified_(allow_unverified_argmax) {
        validate();
        plan_ = build_plan(cfg_);
    }

    // ---- configuration -------------------------------------------------------
    const PassiveScanConfig& config() const { return cfg_; }
    const CoveragePlan& plan() const { return plan_; }
    ScanState state() const { return state_; }
    int step_index() const { return step_index_; }
    std::uint64_t current_lo_hz() const { return current_lo_hz_; }
    std::uint64_t lo_tune_count() const { return lo_tune_count_; }
    std::uint64_t frame_ts() const { return frame_ts_; }
    const ScanResultStore& store() const { return store_; }
    bool allow_unverified_argmax() const { return allow_unverified_; }

    bool running() const {
        return state_ == ScanState::Tuning || state_ == ScanState::Settling ||
               state_ == ScanState::Detecting || state_ == ScanState::Capturing ||
               state_ == ScanState::Classifying || state_ == ScanState::Next;
    }

    // ---- lifecycle -----------------------------------------------------------
    // Snapshot device params, reset the sweep and enter the first Tuning tick.
    // Safe to re-call after Complete/Stopped/Error (restarts the scan).
    void start() {
        dev_.save_params();
        store_.clear();
        step_index_ = 0;
        current_lo_hz_ = plan_.center_hz(0);
        restored_ = false;
        state_ = ScanState::Tuning;
    }

    // Request a graceful stop: restore params and go Stopped.  Idempotent.
    void stop() {
        if (state_ == ScanState::Idle || state_ == ScanState::Stopped ||
            state_ == ScanState::Complete) {
            return;
        }
        finish(ScanState::Stopped);
    }

    // ---- per-frame tick ------------------------------------------------------
    // `unverified_argmax` is an optional raw-argmax the CALLER computed; it is
    // attached to a record ONLY when allow_unverified_argmax is set and the
    // contract does not hold (i.e. always here), and is labelled UNVERIFIED.
    StepResult tick(const FrameInput& in, int unverified_argmax = -1) {
        StepResult r;
        r.state = state_;
        r.step_index = step_index_;
        r.lo_hz = current_lo_hz_;
        ++frame_ts_;

        if (state_ == ScanState::Idle || state_ == ScanState::Complete ||
            state_ == ScanState::Stopped || state_ == ScanState::Error) {
            r.reason = "not_running";
            return r;
        }
        if (state_ == ScanState::Stopping) {
            finish(ScanState::Stopped);
            r.state = state_;
            r.reason = "stopped";
            return r;
        }

        switch (state_) {
            case ScanState::Tuning: do_tuning(r); break;
            case ScanState::Settling: do_settling(r); break;
            case ScanState::Detecting: do_detecting(in, r); break;
            case ScanState::Capturing: do_capturing(in, r); break;
            case ScanState::Classifying: do_classifying(r, unverified_argmax); break;
            default: break;
        }
        r.state = state_;
        r.step_index = step_index_;
        r.lo_hz = current_lo_hz_;
        return r;
    }

private:
    void validate() const {
        if (cfg_.stop_hz < cfg_.start_hz)
            throw std::invalid_argument("passive_scan: stop_hz >= start_hz");
        if (cfg_.start_hz < kPlutoMinHz || cfg_.stop_hz > kPlutoMaxHz)
            throw std::invalid_argument("passive_scan: band must lie within 325..3800 MHz");
        if (cfg_.step_hz == 0)
            throw std::invalid_argument("passive_scan: step_hz > 0");
        if (!(cfg_.rx_sample_rate_hz > 0.0))
            throw std::invalid_argument("passive_scan: rx_sample_rate_hz > 0");
        if (!(cfg_.usable_bw_ratio > 0.0) || cfg_.usable_bw_ratio > 1.0)
            throw std::invalid_argument("passive_scan: 0 < usable_bw_ratio <= 1");
        if (cfg_.settle_frames < 0 || cfg_.detect_frames <= 0 || cfg_.capture_frames <= 0)
            throw std::invalid_argument("passive_scan: settle/detect/capture frames");
        if (cfg_.psd_bins < 4)
            throw std::invalid_argument("passive_scan: psd_bins >= 4");
        if (cfg_.lo_tolerance_hz < 0)
            throw std::invalid_argument("passive_scan: lo_tolerance_hz >= 0");
        if (cfg_.min_occupied_bins <= 0)
            throw std::invalid_argument("passive_scan: min_occupied_bins > 0");
    }

    static CoveragePlan build_plan(const PassiveScanConfig& cfg) {
        CoveragePlan p;
        p.start_hz = cfg.start_hz;
        p.stop_hz = cfg.stop_hz;
        p.step_hz = cfg.step_hz;
        p.coverage_width_hz = cfg.rx_sample_rate_hz * cfg.usable_bw_ratio;
        if (static_cast<double>(cfg.step_hz) > p.coverage_width_hz)
            throw std::invalid_argument("passive_scan: step_hz <= coverage width "
                                        "(no gaps allowed)");
        p.overlap_hz = p.coverage_width_hz - static_cast<double>(cfg.step_hz);
        p.total_steps = static_cast<int>((cfg.stop_hz - cfg.start_hz) / cfg.step_hz) + 1;
        p.frame_period_s = 1024.0 / cfg.rx_sample_rate_hz;
        p.step_duration_s = static_cast<double>(cfg.settle_frames + cfg.detect_frames +
                                                cfg.capture_frames) * p.frame_period_s;
        p.total_duration_s = p.step_duration_s * static_cast<double>(p.total_steps);
        return p;
    }

    void do_tuning(StepResult& r) {
        const std::int64_t want = static_cast<std::int64_t>(plan_.center_hz(step_index_));
        const std::int64_t got = dev_.set_rx_lo(want);
        ++lo_tune_count_;
        r.lo_just_tuned = true;
        r.lo_verified = (std::llabs(got - want) <= cfg_.lo_tolerance_hz);
        if (!r.lo_verified) {
            r.reason = "lo_readback_mismatch";
            finish(ScanState::Error);
            return;
        }
        if (!dev_.flush_rx()) {
            r.reason = "flush_failed";
            finish(ScanState::Error);
            return;
        }
        settle_frame_ = 0;
        state_ = ScanState::Settling;
        r.reason = "tuned";
    }

    void do_settling(StepResult& r) {
        ++settle_frame_;
        if (settle_frame_ >= cfg_.settle_frames) {
            detect_frame_ = 0;
            state_ = ScanState::Detecting;
            r.reason = "settled";
        } else {
            r.reason = "settling";
        }
    }

    void do_detecting(const FrameInput& in, StepResult& r) {
        DetectionResult d;
        if (in.capture_error || in.spectrum.nan_inf) {
            d.invalid = true;
        } else {
            d = detector_.detect(in.spectrum);
        }
        if (!d.invalid && !d.candidates.empty()) {
            current_candidates_ = d.candidates;
            current_noise_floor_dbfs_ = d.noise_floor_dbfs;
            current_unresolved_ = d.unresolved;
            capture_.clear();
            capture_truncated_ = false;
            capture_frame_ = 0;
            r.candidate_found = true;
            r.candidates_in_step = current_candidates_.size();
            state_ = ScanState::Capturing;
            r.reason = "candidate";
            return;
        }
        ++detect_frame_;
        if (detect_frame_ >= cfg_.detect_frames) {
            r.reason = "no_candidate";
            advance_step(r);
        } else {
            r.reason = "detecting";
        }
    }

    void do_capturing(const FrameInput& in, StepResult& r) {
        // Bounded capture: stop appending once max_capture_samples would be exceeded.
        if (!in.capture_ci16.empty()) {
            const std::size_t room = cfg_.max_capture_samples - capture_.size();
            const std::size_t take = std::min(room, in.capture_ci16.size());
            if (take > 0)
                capture_.insert(capture_.end(), in.capture_ci16.begin(),
                                in.capture_ci16.begin() + static_cast<std::ptrdiff_t>(take));
            if (in.capture_ci16.size() > room) capture_truncated_ = true;
        }
        ++capture_frame_;
        if (capture_frame_ >= cfg_.capture_frames) {
            state_ = ScanState::Classifying;
            r.reason = "captured";
        } else {
            r.reason = "capturing";
        }
    }

    void do_classifying(StepResult& r, int unverified_argmax) {
        // Build + append the record (bounded store), then advance.
        ScanRecord rec;
        rec.step_index = step_index_;
        rec.step_lo_hz = current_lo_hz_;
        rec.unresolved = current_unresolved_;
        rec.candidates_in_step = current_candidates_.size();
        if (!current_candidates_.empty()) {
            const ScanCandidate& c = current_candidates_[0];  // strongest (sorted)
            rec.candidate_freq_hz = c.freq_hz;
            rec.candidate_bw_hz = c.bandwidth_hz;
            rec.peak_power_dbfs = c.peak_power_dbfs;
            rec.noise_floor_dbfs = c.noise_floor_dbfs;
            rec.snr_db = c.snr_db;
            rec.occupied_bins = c.occupied_bins;
        }
        rec.iq_captured = !capture_.empty();
        rec.iq_sample_count = capture_.size();
        rec.iq_truncated = capture_truncated_;
        if (rec.iq_captured)
            rec.iq_sha256 = sdr::Sha256::hex(capture_.data(),
                                             capture_.size() * sizeof(std::int16_t));
        const ClassificationVerdict v = gate_.assess(allow_unverified_,
                                                     unverified_argmax);
        rec.classification_outcome = v.outcome;
        rec.verified = v.contract_held;   // always false here
        rec.unverified_class = v.unverified_class;
        rec.frame_ts = frame_ts_;
        store_.append(rec);

        r.record_appended = true;
        r.record_id = store_.records().back().record_id;
        r.reason = "recorded";
        advance_step(r);
    }

    void advance_step(StepResult& r) {
        if (step_index_ + 1 < plan_.total_steps) {
            ++step_index_;
            current_lo_hz_ = plan_.center_hz(step_index_);
            state_ = ScanState::Tuning;
            r.reason = "next_step";
        } else {
            current_lo_hz_ = 0;
            finish(ScanState::Complete);
            r.reason = "complete";
        }
        r.next_lo_hz = (state_ == ScanState::Complete) ? 0 : current_lo_hz_;
    }

    void finish(ScanState terminal) {
        if (!restored_) {
            dev_.restore_params();   // best-effort (never throws per contract)
            restored_ = true;
        }
        state_ = terminal;
    }

    PassiveScanConfig cfg_;
    ScanDeviceControl& dev_;
    EnergyDetector detector_;
    ClassificationContractGate gate_;
    ScanResultStore store_;
    bool allow_unverified_ = false;

    CoveragePlan plan_;
    ScanState state_ = ScanState::Idle;
    int step_index_ = 0;
    std::uint64_t current_lo_hz_ = 0;
    std::uint64_t lo_tune_count_ = 0;
    std::uint64_t frame_ts_ = 0;
    bool restored_ = false;

    int settle_frame_ = 0;
    int detect_frame_ = 0;
    int capture_frame_ = 0;
    std::vector<ScanCandidate> current_candidates_;
    double current_noise_floor_dbfs_ = 0.0;
    bool current_unresolved_ = false;
    std::vector<std::int16_t> capture_;
    bool capture_truncated_ = false;
};

}  // namespace pscan
