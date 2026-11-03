// test_no_signal_ambient.cpp -- host tests for the Gate 9 ambient / rx-only
// no-signal phase (新增项2).  iCraft-free, libiio-free.
//
// Two halves:
//   (1) the no-fake-classification invariant -- driving the producer through a
//       full NO_SIGNAL -> SIGNAL_PRESENT -> NO_SIGNAL -> SIGNAL_PRESENT cycle
//       (hysteresis + consecutive-frame confirmation from SignalPresence), a frame
//       publishes a class IFF its presence_state == SIGNAL_PRESENT.  This is the
//       deterministic invariant the ambient gate hard-requires on the board
//       (published_while_not_present == 0), proven here across every frame.
//   (2) the --phase CLI surface -- gate9::valid_phase("ambient") is accepted and
//       bogus / empty phases are rejected, exercising the exact predicate
//       board_gate9_full_chain_12class.cpp::main() uses to dispatch.
//
// Build/run: see host_tests/build_host_tests.sh.

#include "../board_package/gate9_phase.hpp"
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

constexpr double kPi = 3.14159265358979323846;
constexpr std::size_t kComplex = 1024;
constexpr std::size_t kFloats = 2 * kComplex;

// [2,1024] base tensor holding a pure complex tone at `amp` (receiver_scale
// already applied).  With rec_scale == 1.0 the producer reconstructs count peak
// == amp * 2048; amp=0.5 -> ~-9 dBFS (present), amp=0.0005 -> ~-69 dBFS (below
// the -55 dBFS enter threshold -> NO_SIGNAL).
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

struct FakeDevice : producer::DeviceControl {
    void set_rx_lo(std::int64_t) override {}
    void set_rx_gain(double) override {}
};

struct FakeClassifier {
    int force_class = 3;
    void classify(const float*, std::vector<float>& lg) {
        lg.assign(12, 0.0f);
        lg[static_cast<std::size_t>(force_class)] = 5.0f;
    }
};

// (1) published iff SIGNAL_PRESENT, across a full present <-> absent cycle.
void test_no_fake_classification_cycle() {
    producer::ProducerConfig cfg;
    FakeDevice dev;
    FakeClassifier cls;
    producer::Producer12 prod(cfg, dev);
    auto classify = [&](const float* p, std::vector<float>& lg) { cls.classify(p, lg); };

    // quiet -> loud -> quiet -> loud.  The hysteresis hold (lost_frames=5) means
    // presence_state stays SIGNAL_PRESENT for a few frames after the signal drops;
    // the invariant (published iff SIGNAL_PRESENT) must hold on EVERY frame anyway.
    const double amp_seq[] = {
        0.0005, 0.0005, 0.0005, 0.0005, 0.0005,             // NO_SIGNAL baseline
        0.5,    0.5,    0.5,    0.5,    0.5,                // -> SIGNAL_PRESENT
        0.0005, 0.0005, 0.0005, 0.0005, 0.0005, 0.0005, 0.0005,   // -> NO_SIGNAL
        0.5,    0.5,    0.5                                 // -> SIGNAL_PRESENT again
    };

    int invariant_violations = 0;
    int present_frames = 0, absent_frames = 0;
    bool saw_present = false, saw_absent_after_present = false, saw_present_again = false;

    for (double amp : amp_seq) {
        std::vector<float> t = tone_tensor(amp);
        producer::CaptureFlags flags;
        const producer::ProducerDecision d = prod.on_frame(t.data(), flags, classify);
        const bool present = (d.presence_state == "SIGNAL_PRESENT");
        const bool published = (d.publish && d.published_class >= 0);
        if (published != present) ++invariant_violations;

        if (present) {
            ++present_frames;
            if (saw_absent_after_present) saw_present_again = true;
            saw_present = true;
        } else {
            ++absent_frames;
            if (saw_present) saw_absent_after_present = true;
        }
    }

    check(invariant_violations == 0,
          "no-fake-classification invariant: published iff SIGNAL_PRESENT on every frame");
    check(present_frames > 0, "SIGNAL_PRESENT frames observed");
    check(absent_frames > 0, "non-SIGNAL_PRESENT frames observed");
    check(saw_present && saw_absent_after_present && saw_present_again,
          "full SIGNAL_PRESENT -> NO_SIGNAL -> SIGNAL_PRESENT cycle observed");
}

// (2) the --phase dispatch predicate (the exact code main() uses).
void test_phase_cli_surface() {
    check(gate9::valid_phase("ambient"), "--phase=ambient is valid");
    check(gate9::valid_phase("offline"), "--phase=offline is valid");
    check(gate9::valid_phase("digital"), "--phase=digital is valid");
    check(gate9::valid_phase("rf"), "--phase=rf is valid");
    check(!gate9::valid_phase("bogus"), "--phase=bogus is rejected");
    check(!gate9::valid_phase(""), "empty --phase is rejected");
    check(!gate9::valid_phase("AMBIENT"), "phase is case-sensitive (AMBIENT rejected)");
}

}  // namespace

int main() {
    std::printf("test_no_signal_ambient\n");
    test_no_fake_classification_cycle();
    test_phase_cli_surface();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
