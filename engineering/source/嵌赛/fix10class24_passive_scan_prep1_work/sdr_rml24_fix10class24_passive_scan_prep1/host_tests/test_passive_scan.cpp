// test_passive_scan.cpp -- host test for the passive RX frequency-scan feature
// (task fix10class24-passive-scan-prep1).  iCraft-free / libiio-free.
//
// Built with g++ -std=gnu++17 -O2 -Wall -Wextra -Werror.  Covers:
//   * config validation (band range, step, coverage-gap, frame counts);
//   * coverage plan (inclusive step schedule, overlap, no-gap fail-closed);
//   * energy detector (noise floor, DC/edge guard, candidate extraction,
//     min/max occupancy, min SNR, unresolved multi-signal);
//   * classification gate ALWAYS fails closed (CLASSIFICATION_UNAVAILABLE) and
//     only ever attaches an explicitly-marked UNVERIFIED candidate;
//   * the state machine end-to-end with a scripted fake device: LO write +
//     read-back verification, flush, settle (no old-frame bleed), detect ->
//     capture -> classify -> record, no-candidate step, complete, stop, and the
//     LO-read-back-mismatch Error path with restore;
//   * hard bounds (capture truncation + bounded history).

#include "../board_package/passive_scan.hpp"

#include <cstdio>
#include <cstdint>
#include <stdexcept>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

static void check(bool ok, const char* what) {
    if (ok) { ++g_pass; }
    else { ++g_fail; std::printf("FAIL: %s\n", what); }
}

template <typename F>
static bool throws(F&& f) {
    try { f(); return false; }
    catch (const std::invalid_argument&) { return true; }
    catch (...) { return false; }
}

// Scriptable fake device (no libiio).  Tracks every control effect so the test
// can assert the exact tune/flush/restore sequence.
struct FakeDevice : public pscan::ScanDeviceControl {
    std::int64_t lo = 0;
    std::int64_t lo_readback_delta = 0;   // simulate LO quantisation / mismatch
    std::int64_t bw = 0;
    double gain = 0.0;
    bool flush_ok = true;
    int set_lo = 0, set_bw = 0, set_gain = 0, flush = 0, save = 0, restore = 0;

    std::int64_t set_rx_lo(std::int64_t hz) override { ++set_lo; lo = hz + lo_readback_delta; return lo; }
    std::int64_t get_rx_lo() const override { return lo; }
    std::int64_t set_rx_bw(std::int64_t hz) override { ++set_bw; bw = hz; return bw; }
    double set_rx_gain(double db) override { ++set_gain; gain = db; return gain; }
    void save_params() override { ++save; }
    bool restore_params() override { ++restore; return true; }
    bool flush_rx() override { ++flush; return flush_ok; }
};

// Build a flat-noise spectrum with an optional peak at `peak_bin` (dB offset).
static pscan::PowerSpectrum make_spectrum(std::size_t bins, double center_hz,
                                          double bin_hz, float noise_dbfs,
                                          int peak_bin, float snr_db) {
    pscan::PowerSpectrum s;
    s.bin_power_dbfs.assign(bins, noise_dbfs);
    if (peak_bin >= 0 && peak_bin < static_cast<int>(bins))
        s.bin_power_dbfs[static_cast<std::size_t>(peak_bin)] = noise_dbfs + snr_db;
    s.bin_hz = bin_hz;
    s.center_hz = center_hz;
    return s;
}

int main() {
    using namespace pscan;

    // --- config validation ---------------------------------------------------
    {
        FakeDevice dev;
        PassiveScanConfig c;
        c.stop_hz = c.start_hz - 1;
        check(throws([&] { PassiveScanStateMachine m(c, dev); }),
              "stop < start throws");
        PassiveScanConfig c2; c2.start_hz = 100000000ULL;   // below 325 MHz
        check(throws([&] { PassiveScanStateMachine m(c2, dev); }),
              "band below 325 MHz throws");
        PassiveScanConfig c3; c3.stop_hz = 5000000000ULL;   // above 3.8 GHz
        check(throws([&] { PassiveScanStateMachine m(c3, dev); }),
              "band above 3.8 GHz throws");
        PassiveScanConfig c4; c4.step_hz = 0;
        check(throws([&] { PassiveScanStateMachine m(c4, dev); }),
              "step_hz == 0 throws");
        PassiveScanConfig c5; c5.step_hz = 5000000ULL;   // 5 MHz > 2.56*0.8 = 2.048 MHz
        check(throws([&] { PassiveScanStateMachine m(c5, dev); }),
              "step > coverage width (gap) throws");
        PassiveScanConfig c6; c6.detect_frames = 0;
        check(throws([&] { PassiveScanStateMachine m(c6, dev); }),
              "detect_frames == 0 throws");
        PassiveScanConfig c7; c7.min_occupied_bins = 0;
        check(throws([&] { PassiveScanStateMachine m(c7, dev); }),
              "min_occupied_bins == 0 throws");
    }

    // --- coverage plan -------------------------------------------------------
    {
        PassiveScanConfig c;   // default step 1 MHz, coverage ~2.048 MHz
        c.start_hz = 2400000000ULL; c.stop_hz = 2403000000ULL;  // 3 MHz band
        FakeDevice dev;
        PassiveScanStateMachine m(c, dev);
        check(m.plan().total_steps == 4, "2400..2403 @1MHz -> 4 steps");
        check(m.plan().center_hz(0) == 2400000000ULL &&
              m.plan().center_hz(3) == 2403000000ULL, "centres start..stop inclusive");
        check(m.plan().coverage_width_hz > 2.0e6, "coverage width ~2.048 MHz");
        check(m.plan().overlap_hz >= 0.0, "overlap >= 0");
    }

    // --- energy detector -----------------------------------------------------
    {
        PassiveScanConfig c;  // psd_bins=1024, dc_guard=8, edge_guard=8, threshold 6dB
        EnergyDetector det(c);
        const double center = 2400000000.0;
        const double bin_hz = 2.56e6 / 1024.0;  // 2.5 kHz bins
        const float nf = -80.0f;

        // Pure noise -> no candidate.
        {
            auto s = make_spectrum(1024, center, bin_hz, nf, -1, 0.0f);
            auto r = det.detect(s);
            check(!r.invalid && r.candidates.empty(), "noise-only -> no candidate");
        }
        // A tone at bin 200 -> one candidate.
        {
            auto s = make_spectrum(1024, center, bin_hz, nf, 200, 20.0f);
            auto r = det.detect(s);
            check(!r.invalid && r.candidates.size() == 1, "tone -> one candidate");
            check(r.candidates[0].occupied_bins >= 1 && r.candidates[0].snr_db >= 20.0f - 1e-3f,
                  "candidate snr/bins sane");
            check(r.candidates[0].peak_bin == 200, "candidate peak bin");
        }
        // DC/LO leakage (bin 512) is guarded out.
        {
            auto s = make_spectrum(1024, center, bin_hz, nf, 512, 30.0f);
            auto r = det.detect(s);
            check(r.candidates.empty(), "DC/LO bin guarded out");
        }
        // Edge roll-off (bin 2) is guarded out.
        {
            auto s = make_spectrum(1024, center, bin_hz, nf, 2, 30.0f);
            auto r = det.detect(s);
            check(r.candidates.empty(), "edge bin guarded out");
        }
        // Below min_snr -> not a candidate.
        {
            auto s = make_spectrum(1024, center, bin_hz, nf, 200, 3.0f);
            auto r = det.detect(s);
            check(r.candidates.empty(), "below min_snr -> no candidate");
        }
        // Two distinct tones -> two candidates.
        {
            auto s = make_spectrum(1024, center, bin_hz, nf, -1, 0.0f);
            s.bin_power_dbfs[200] = nf + 20.0f;
            s.bin_power_dbfs[800] = nf + 18.0f;
            auto r = det.detect(s);
            check(r.candidates.size() == 2 && !r.unresolved, "two tones -> two candidates");
        }
        // More clusters than max -> unresolved (bounded).
        {
            PassiveScanConfig c2; c2.max_candidates_per_step = 2;
            EnergyDetector det2(c2);
            auto s = make_spectrum(1024, center, bin_hz, nf, -1, 0.0f);
            for (int b : {100, 200, 300, 400})
                s.bin_power_dbfs[b] = nf + 20.0f;
            auto r = det2.detect(s);
            check(r.unresolved && r.candidates.size() == 2,
                  "over-max clusters -> unresolved + bounded to max");
        }
    }

    // --- classification gate (fail-closed) ----------------------------------
    {
        PassiveScanConfig c;
        FakeDevice dev;
        PassiveScanStateMachine m(c, dev, /*allow_unverified_argmax=*/false);
        ClassificationContractGate gate(c);
        auto v = gate.assess(false, 5);
        check(!v.contract_held && v.outcome == std::string("CLASSIFICATION_UNAVAILABLE"),
              "gate fails closed to CLASSIFICATION_UNAVAILABLE");
        check(!v.has_unverified_class && v.unverified_class == -1,
              "no unverified class when disallowed");

        auto v2 = gate.assess(true, 5);
        check(v2.outcome == std::string("UNVERIFIED_CANDIDATE") &&
              v2.unverified_class == 5 && !v2.contract_held,
              "unverified candidate is explicitly UNVERIFIED, never held");
    }

    // --- state machine end-to-end (candidate + no-candidate + complete) ------
    {
        PassiveScanConfig c;
        c.start_hz = 2400000000ULL; c.stop_hz = 2401000000ULL; c.step_hz = 1000000ULL; // 2 steps
        c.settle_frames = 2; c.detect_frames = 2; c.capture_frames = 2;
        FakeDevice dev;
        PassiveScanStateMachine m(c, dev);

        const double center0 = 2400000000.0;
        const double bin_hz = 2.56e6 / 1024.0;

        m.start();
        check(dev.save == 1 && m.state() == ScanState::Tuning, "start snapshots + enters Tuning");

        // step 0: Tuning (tune+flush) -> Settling x2 -> Detecting -> candidate
        pscan::FrameInput in;
        StepResult r = m.tick(in);
        check(r.lo_just_tuned && r.lo_verified && dev.set_lo == 1 && dev.flush == 1,
              "Tuning writes + verifies LO and flushes");
        check(m.state() == ScanState::Settling, "after Tuning -> Settling");

        m.tick(in);  // settle 1
        r = m.tick(in);  // settle 2 -> Detecting
        check(m.state() == ScanState::Detecting, "after settle -> Detecting");

        in.spectrum = make_spectrum(1024, center0, bin_hz, -80.0f, 200, 20.0f);
        r = m.tick(in);
        check(r.candidate_found && m.state() == ScanState::Capturing,
              "detector finds candidate -> Capturing");

        std::vector<std::int16_t> cap = {1, 2, 3, 4, 5, 6, 7, 8};
        in.capture_ci16 = cap;
        m.tick(in);  // capture 1
        r = m.tick(in);  // capture 2 -> Classifying
        check(m.state() == ScanState::Classifying, "after capture -> Classifying");

        in.capture_ci16.clear();
        r = m.tick(in);
        check(r.record_appended && m.store().size() == 1, "classify appends one record");
        const ScanRecord& rec = m.store().at(0);
        check(rec.classification_outcome == std::string("CLASSIFICATION_UNAVAILABLE") &&
              !rec.verified && rec.unverified_class == -1,
              "record outcome is CLASSIFICATION_UNAVAILABLE, never a class");
        check(rec.iq_captured && rec.iq_sample_count == 16 &&
              rec.iq_sha256.size() == 64, "captured IQ identity recorded");
        check(m.state() == ScanState::Tuning && m.step_index() == 1,
              "record -> advance to step 1 Tuning");

        // step 1: tune -> settle -> detect x2 (no candidate) -> complete
        r = m.tick(in);
        check(dev.set_lo == 2, "step 1 re-tunes LO");
        m.tick(in); m.tick(in);  // settle -> detecting
        in.spectrum = make_spectrum(1024, center0 + 1000000.0, bin_hz, -80.0f, -1, 0.0f);
        m.tick(in);  // detect 1
        r = m.tick(in);  // detect 2 -> no candidate -> complete
        check(m.state() == ScanState::Complete, "no-candidate last step -> Complete");
        check(dev.restore == 1, "complete restores device params exactly once");
        check(m.store().size() == 1, "only the candidate step recorded");
    }

    // --- settle discards frames (no old-frame bleed) --------------------------
    {
        PassiveScanConfig c;
        c.start_hz = 2400000000ULL; c.stop_hz = 2400000000ULL; // 1 step (default 1 MHz step)
        c.settle_frames = 3;
        FakeDevice dev;
        PassiveScanStateMachine m(c, dev);
        m.start();
        m.tick(pscan::FrameInput{});   // tune
        const double center = 2400000000.0;
        const double bin_hz = 2.56e6 / 1024.0;
        pscan::FrameInput in;
        in.spectrum = make_spectrum(1024, center, bin_hz, -80.0f, 200, 30.0f);  // strong peak
        m.tick(in);  // settle 1: must ignore the peak
        m.tick(in);  // settle 2: still ignore
        check(m.state() == ScanState::Settling && m.store().size() == 0,
              "settle discards frames (peak ignored during settle)");
        m.tick(in);  // settle 3 -> Detecting
        check(m.state() == ScanState::Detecting,
              "after settle -> Detecting (peak not captured during settle)");
    }

    // --- LO read-back mismatch -> Error + restore ----------------------------
    {
        PassiveScanConfig c; c.settle_frames = 1; c.detect_frames = 1;
        FakeDevice dev; dev.lo_readback_delta = 5000;   // 5 kHz > 1 kHz tolerance
        PassiveScanStateMachine m(c, dev);
        m.start();
        StepResult r = m.tick(pscan::FrameInput{});
        check(m.state() == ScanState::Error && !r.lo_verified && dev.restore == 1,
              "LO read-back mismatch fails closed to Error + restore");
    }

    // --- stop() -> Stopped + restore once ------------------------------------
    {
        PassiveScanConfig c; c.settle_frames = 10;
        FakeDevice dev;
        PassiveScanStateMachine m(c, dev);
        m.start();
        m.tick(pscan::FrameInput{});
        m.stop();
        check(m.state() == ScanState::Stopped && dev.restore == 1, "stop restores + Stopped");
        m.stop();  // idempotent
        check(dev.restore == 1, "stop is idempotent (restore once)");
    }

    // --- hard bounds: capture truncation + bounded history -------------------
    {
        // capture truncation: max_capture_samples=8, capture_frames=4, 4 samples/frame
        PassiveScanConfig c;
        c.start_hz = 2400000000ULL; c.stop_hz = 2400000000ULL; // 1 step (default 1 MHz step)
        c.settle_frames = 1; c.detect_frames = 1; c.capture_frames = 4;
        c.max_capture_samples = 8;
        FakeDevice dev;
        PassiveScanStateMachine m(c, dev);
        m.start();
        const double center = 2400000000.0;
        const double bin_hz = 2.56e6 / 1024.0;
        pscan::FrameInput in;
        m.tick(in);  // tune
        m.tick(in);  // settle -> detecting
        in.spectrum = make_spectrum(1024, center, bin_hz, -80.0f, 200, 20.0f);
        m.tick(in);  // detect -> capturing
        in.spectrum = pscan::PowerSpectrum{};
        std::vector<std::int16_t> cap = {1, 2, 3, 4};
        in.capture_ci16 = cap;
        m.tick(in); m.tick(in); m.tick(in); m.tick(in);  // 4 frames -> classify
        m.tick(in);  // classify + complete
        const ScanRecord& rec = m.store().at(0);
        check(rec.iq_sample_count == 8 && rec.iq_truncated,
              "capture truncated to max_capture_samples");

        // bounded history: max_history=2, three records -> oldest dropped
        ScanResultStore store(2);
        ScanRecord a, b, d;
        store.append(a); store.append(b); store.append(d);
        check(store.size() == 2 && store.at(0).record_id == 2 &&
              store.at(1).record_id == 3, "history bounded (oldest dropped)");
    }

    std::printf("test_passive_scan: %d pass, %d fail\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
