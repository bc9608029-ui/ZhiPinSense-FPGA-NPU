// test_producer_12class.cpp -- host tests for the Gate 9 twelve-class LIVE
// PRODUCER (producer_12class.hpp, task 39e5 UI v3 M6-M10).
//
// The producer is the single owner of the reverse control channel and of every
// runtime behaviour the MODE / PARAMETERS pages display.  This test drives it with
// a FAKE device (recording set_rx_lo / set_rx_gain) and a FAKE classifier
// (recording the scaled tensor's RMS), so the whole state machine runs on the
// host with no iCraft / libiio / Pluto.  It verifies the five decisive problems
// are actually fixed on the producer side:
//
//   (1) params non-placeholder -- a signal frame produces real FrameMeasurements
//       (has_measurements && valid && rms_counts > 0), presence state, level mode
//       and the producer-owned work_mode / run_state;
//   (2) NO_SIGNAL recovery   -- a non-present frame NEVER publishes a class;
//       once the signal returns the producer publishes again;
//   (3) AUTO LOCK            -- after stability_window consecutive same-class
//       frames the class lock holds and publishes that class; the engine's
//       model_scale is ACTUALLY applied to the model input before classification
//       (asserted via the fake classifier's recorded input RMS);
//   (4) actual LO sweep      -- BAND SCAN actually re-tunes the RX LO per step
//       (recorded set_rx_lo calls), resets the lock after each step, and reports
//       scan progress (scan_lo_hz / step_index / total_steps);
//   (5) mode control         -- SET_MODE / START / STOP / STATUS are fail-closed
//       and STOP really stops the producer (running()==false, publish==false).
//
// Build/run: see host_tests/build_host_tests.sh (g++ -O2 -Wall -Wextra -Werror).

#include "../board_package/producer_12class.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

bool near(double a, double b, double tol) { return std::fabs(a - b) <= tol; }

constexpr double kPi = 3.14159265358979323846;
constexpr std::size_t kFloats = 2048;
constexpr std::size_t kComplex = 1024;

// Build a [2,1024] base tensor (receiver_scale already applied) holding a pure
// complex tone at `amp`: I = amp*cos(ph), Q = amp*sin(ph).  The tensor's RMS is
// therefore amp/sqrt(2) (see tone_rms).  With rec_scale == 1.0 the producer
// reconstructs count peak == amp * 2048, so amp < 1.0 never clips.
std::vector<float> tone_tensor(double amp, double freq_hz = 10000.0,
                               double fs = 128000.0) {
    std::vector<float> t(kFloats);
    for (std::size_t k = 0; k < kComplex; ++k) {
        const double ph = 2.0 * kPi * freq_hz * static_cast<double>(k) / fs;
        t[k] = static_cast<float>(amp * std::cos(ph));
        t[kComplex + k] = static_cast<float>(amp * std::sin(ph));
    }
    return t;
}

// RMS of the base tensor a tone_tensor(amp) produces: mean-square is
// amp^2 * (cos^2 + sin^2)/2 = amp^2/2 over the [I|Q] halves, so RMS = amp/sqrt(2).
double tone_rms(double amp) { return amp / std::sqrt(2.0); }

// Fake device: records every LO/gain effect the producer requests (the ONLY two
// device effects the producer is allowed to perform).
struct FakeDevice : producer::DeviceControl {
    std::vector<std::int64_t> los;
    std::vector<double> gains;
    void set_rx_lo(std::int64_t hz) override { los.push_back(hz); }
    void set_rx_gain(double db) override { gains.push_back(db); }
};

// Fake classifier: always returns a fixed argmax, and records the RMS of the
// SCALED tensor it was given so tests can assert the engine's model_scale really
// acted on the model input.
struct FakeClassifier {
    int force_class = 3;
    int calls = 0;
    float last_input_rms = -1.0f;
    void classify(const float* t, std::vector<float>& lg) {
        ++calls;
        double s = 0.0;
        for (std::size_t i = 0; i < kFloats; ++i)
            s += static_cast<double>(t[i]) * static_cast<double>(t[i]);
        last_input_rms = static_cast<float>(std::sqrt(s / static_cast<double>(kFloats)));
        lg.assign(12, 0.0f);
        lg[static_cast<std::size_t>(force_class)] = 5.0f;
    }
};

// Feed `n` clean frames at `amp` through the producer; return the last decision.
template <typename Fn>
producer::ProducerDecision feed(producer::Producer12& prod, Fn classify, int n,
                                double amp) {
    producer::ProducerDecision d;
    for (int i = 0; i < n; ++i) {
        std::vector<float> t = tone_tensor(amp);
        producer::CaptureFlags flags;
        d = prod.on_frame(t.data(), flags, classify);
    }
    return d;
}

// (1) params non-placeholder + producer-owned mode/run state (FIXED, signal).
void test_params_non_placeholder() {
    producer::ProducerConfig cfg;
    FakeDevice dev;
    FakeClassifier cls;
    producer::Producer12 prod(cfg, dev);
    auto classify = [&](const float* p, std::vector<float>& lg) { cls.classify(p, lg); };

    const producer::ProducerDecision d = feed(prod, classify, 3, 0.5);  // presence confirms

    check(d.has_measurements, "signal frame carries measurements");
    check(d.measurements.valid, "measurements are valid");
    check(d.measurements.rms_counts > 0.0, "rms_counts is a real value (>0)");
    check(d.measurements.model_rms > 0.0, "model_rms is a real value (>0)");
    check(d.presence_state == "SIGNAL_PRESENT", "presence_state == SIGNAL_PRESENT");
    check(d.level_mode == "FIXED", "level_mode == FIXED");
    check(d.work_mode == "FIXED", "work_mode token == FIXED");
    check(d.run_state == "RUNNING", "run_state == RUNNING");
    check(d.publish, "a present signal publishes");
    check(d.published_class == cls.force_class, "published_class == fake argmax");
    check(near(d.model_scale, 1.0, 1e-6), "FIXED model_scale is identity (1.0)");
    check(near(d.rf_gain_db, cfg.base_rf_gain_db, 1e-9), "FIXED rf_gain == base gain");
    check(near(cls.last_input_rms, tone_rms(0.5) * d.model_scale, 1e-3),
          "FIXED scale 1.0 leaves the model input RMS == base RMS");
}

// (2) NO_SIGNAL -> no publish, then recovery -> publish again.
void test_no_signal_recovery() {
    producer::ProducerConfig cfg;
    FakeDevice dev;
    FakeClassifier cls;
    producer::Producer12 prod(cfg, dev);
    auto classify = [&](const float* p, std::vector<float>& lg) { cls.classify(p, lg); };

    producer::ProducerDecision quiet = feed(prod, classify, 3, 0.0005);  // < -55 dBFS enter
    check(quiet.presence_state != "SIGNAL_PRESENT", "quiet frames are not SIGNAL_PRESENT");
    check(!quiet.publish, "a non-present frame does NOT publish");
    check(quiet.published_class == -1, "non-present frame has no published class");

    producer::ProducerDecision loud = feed(prod, classify, 3, 0.5);
    check(loud.presence_state == "SIGNAL_PRESENT", "signal returns -> SIGNAL_PRESENT");
    check(loud.publish, "signal returns -> publish resumes");
    check(loud.published_class == cls.force_class, "recovered frame publishes the fake argmax");
}

// (3) AUTO LOCK: class stability lock + model_scale actually acts on the input.
void test_auto_lock() {
    producer::ProducerConfig cfg;
    cfg.stability_window = 5;   // set BEFORE constructing the producer
    FakeDevice dev;
    FakeClassifier cls;
    producer::Producer12 prod(cfg, dev);
    auto classify = [&](const float* p, std::vector<float>& lg) { cls.classify(p, lg); };

    const std::string resp = prod.apply_command("SET_MODE AUTO_LOCK");
    check(resp.rfind("OK", 0) == 0, "SET_MODE AUTO_LOCK -> OK");

    cls.force_class = 4;
    producer::ProducerDecision d = feed(prod, classify, 4, 0.5);  // window-1: acquiring
    check(d.work_mode == "AUTO_LOCK", "work_mode token == AUTO_LOCK");
    check(d.level_mode == "AUTO", "level_mode == AUTO");
    check(!d.publish, "acquiring frames do not publish yet");

    d = feed(prod, classify, 1, 0.5);   // the stability_window-th same-class frame
    check(d.class_locked, "class lock holds after stability_window frames");
    check(d.publish, "locked frame publishes");
    check(d.published_class == 4, "locked frame publishes the stable class");

    check(near(cls.last_input_rms, tone_rms(0.5) * d.model_scale, 1e-3),
          "AUTO model_scale is actually applied to the model input");
}

// (4) BAND SCAN: actual LO sweep (set_rx_lo per step), lock reset, scan progress.
void test_band_scan_lo_sweep() {
    producer::ProducerConfig cfg;
    cfg.band_scan.start_hz = 2400000000ULL;
    cfg.band_scan.stop_hz = 2500000000ULL;
    cfg.band_scan.step_hz = 10000000ULL;
    cfg.band_scan.dwell_frames = 4;   // set BEFORE constructing the producer
    FakeDevice dev;
    FakeClassifier cls;
    producer::Producer12 prod(cfg, dev);
    auto classify = [&](const float* p, std::vector<float>& lg) { cls.classify(p, lg); };

    const std::string resp = prod.apply_command("SET_MODE BAND_SCAN");
    check(resp.rfind("OK", 0) == 0, "SET_MODE BAND_SCAN -> OK");

    prod.before_capture();
    check(dev.los.size() == 1, "before_capture tunes the LO once");
    check(dev.los.back() == 2400000000LL, "first LO == start_hz");
    check(prod.lo_tune_count() == 1, "lo_tune_count == 1");

    producer::ProducerDecision d = feed(prod, classify, 4, 0.5);  // one full dwell
    check(d.band_scan_active, "band scan reports active on each frame");
    check(d.scan_total_steps == 11, "scan_total_steps == 11 ((stop-start)/step + 1)");
    check(d.scan_lo_hz != 0, "scan_lo_hz reported");
    check(prod.sweep_advances() == 1, "one dwell completes one sweep advance");

    prod.before_capture();
    check(dev.los.size() == 2, "advance triggers a second LO tune");
    check(dev.los.back() == 2410000000LL, "second LO == start_hz + step_hz");
    check(prod.lo_tune_count() == 2, "lo_tune_count == 2 after one step");
}

// (5) mode control fail-closed + STOP really stops the producer.
void test_mode_control() {
    producer::ProducerConfig cfg;
    FakeDevice dev;
    FakeClassifier cls;
    producer::Producer12 prod(cfg, dev);
    auto classify = [&](const float* p, std::vector<float>& lg) { cls.classify(p, lg); };

    check(prod.apply_command("SET_MODE BOGUS").rfind("ERR", 0) == 0,
          "unknown mode -> ERR");
    check(prod.apply_command("NONSENSE").rfind("ERR", 0) == 0,
          "unknown command -> ERR");
    check(prod.apply_command("STATUS").rfind("OK", 0) == 0,
          "STATUS -> OK");

    check(prod.apply_command("STOP").rfind("OK", 0) == 0, "STOP -> OK");
    check(!prod.running(), "STOP makes running()==false");

    std::vector<float> t = tone_tensor(0.5);
    producer::CaptureFlags flags;
    producer::ProducerDecision d = prod.on_frame(t.data(), flags, classify);
    check(d.run_state == "STOPPED", "stopped decision reports run_state STOPPED");
    check(!d.publish, "stopped producer never publishes");
    check(!d.has_measurements, "stopped producer skips measurements");

    check(prod.apply_command("START").rfind("OK", 0) == 0, "START -> OK");
    check(prod.running(), "START makes running()==true");
}

}  // namespace

int main() {
    std::printf("test_producer_12class\n");
    test_params_non_placeholder();
    test_no_signal_recovery();
    test_auto_lock();
    test_band_scan_lo_sweep();
    test_mode_control();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
