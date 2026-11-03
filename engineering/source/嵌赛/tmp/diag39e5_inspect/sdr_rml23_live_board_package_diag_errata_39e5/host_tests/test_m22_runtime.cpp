// test_m22_runtime.cpp -- host tests for the M22 runtime-lifecycle / latency-spike
// fixes (task 39e5 M22 §五/§六).  The board hot path (board_gate9_full_chain_12class.cpp)
// is iCraft-only and cannot be compiled on the host, so this file unit-tests the
// PURE-LOGIC pieces the board runs with no iCraft type:
//
//   * m22::PercentileStats / m22::StageTiming  -- fixed-ring per-stage latency
//     statistics (mean/P50/P95/P99/max over >= 10000 frames, allocation-free hot path);
//   * chain::NpuLifecycleState                 -- open-once / apply-once / bounded
//     recovery / fail-closed / close-once discipline (§五.1);
//   * classify::softmax_into == classify::softmax (M22 buffer reuse is bit-identical);
//   * sdr::DspMeasure::measure_into == measure  (reused scratch is bit-identical);
//   * ui::UnixSocketSink non-blocking write     -- a full buffer / gone peer DROPS
//     the frame and never blocks the inference loop (§五.4, the spike root cause);
//   * m22::read_resources / ResourceSample      -- RSS / FD / thread / CPU sampling;
//   * ui::NullSink                              -- the default no-per-frame-stdout route;
//   * producer::Producer12 buffer reuse         -- one producer reused across 100
//     frames (cf_ / scaled_ / dsp_scratch_ reuse path).
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror (zero warnings required).

#include "../sdr_adapter/latency_stats.hpp"
#include "../sdr_adapter/npu_lifecycle_state.hpp"
#include "../sdr_adapter/classify.hpp"
#include "../sdr_adapter/dsp_measure.hpp"
#include "../sdr_adapter/resource_snapshot.hpp"
#include "../sdr_adapter/ui_report.hpp"
#include "../sdr_adapter/unix_socket_sink.hpp"

#include "../board_package/producer_12class.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#endif

namespace {

int g_fail = 0;
int g_pass = 0;

void check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s\n", what);
    }
}

bool near(double a, double b, double tol) {
    const double d = std::fabs(a - b);
    const double scale = std::max(1.0, std::max(std::fabs(a), std::fabs(b)));
    return d <= tol * scale;
}

// ---------------------------------------------------------------------------
// 1. PercentileStats / StageTiming (分阶段延迟统计测试, §十八.4).
// ---------------------------------------------------------------------------
void test_percentile_stats() {
    m22::PercentileStats ps;
    const double vals[5] = {10.0, 20.0, 30.0, 40.0, 50.0};
    for (double v : vals) ps.record(v);

    check(ps.count() == 5, "count == 5");
    check(ps.min_us() == 10.0, "min == 10");
    check(ps.max_us() == 50.0, "max == 50");
    check(near(ps.mean_us(), 30.0, 1e-12), "mean == 30");
    check(near(ps.percentile(0.50), 30.0, 1e-12), "p50 == 30");
    // nearest-rank linear interpolation: p95 over [10,20,30,40,50]
    check(near(ps.percentile(0.95), 48.0, 1e-12), "p95 == 48");
    check(near(ps.percentile(0.99), 49.6, 1e-12), "p99 == 49.6");
    check(near(ps.percentile(0.00), 10.0, 1e-12), "p0 == 10");
    check(near(ps.percentile(1.00), 50.0, 1e-12), "p100 == 50");

    // Empty ring => zeroes (never NaN).
    m22::PercentileStats empty;
    check(empty.count() == 0, "empty count == 0");
    check(empty.percentile(0.50) == 0.0, "empty p50 == 0 (no NaN)");
    check(empty.max_us() == 0.0, "empty max == 0");

    // Fixed-capacity ring: the ring overwrites the oldest sample (allocation-free)
    // and the retained count is capped at the capacity, while min/max stay exact
    // over ALL observations (running extrema, not just the retained window).
    m22::PercentileStats ring(4);
    for (double v : vals) ring.record(v);   // 5 samples into a capacity-4 ring
    check(ring.count() == 4, "ring retained count capped at capacity (4)");
    check(ring.min_us() == 10.0, "ring min stays exact over all 5 (10)");
    check(ring.max_us() == 50.0, "ring max stays exact over all 5 (50)");
}

void test_stage_timing() {
    m22::StageTiming st;
    // Record three NpuInfer samples and two FrameTotal samples.
    st.record(m22::StageId::NpuInfer, 100.0);
    st.record(m22::StageId::NpuInfer, 200.0);
    st.record(m22::StageId::NpuInfer, 300.0);
    st.record(m22::StageId::FrameTotal, 500.0);
    st.record(m22::StageId::FrameTotal, 700.0);

    check(st.stage(m22::StageId::NpuInfer).count() == 3, "npu_infer count == 3");
    check(near(st.stage(m22::StageId::NpuInfer).mean_us(), 200.0, 1e-12),
          "npu_infer mean == 200");
    check(st.stage(m22::StageId::FrameTotal).count() == 2, "frame_total count == 2");
    check(st.stage(m22::StageId::RfConfig).count() == 0, "rf_config count == 0 (unrecorded)");

    // The JSON summary names every fixed stage.
    const std::string j = st.json();
    check(j.find("\"device_open\"") != std::string::npos, "json has device_open");
    check(j.find("\"npu_infer\"") != std::string::npos, "json has npu_infer");
    check(j.find("\"frame_total\"") != std::string::npos, "json has frame_total");

    // Timer RAII records into a fixed stage.
    {
        m22::StageTiming::Timer t(st, m22::StageId::Postprocess);
    }
    check(st.stage(m22::StageId::Postprocess).count() == 1,
          "Timer RAII recorded one postprocess sample");
    check(st.stage(m22::StageId::Postprocess).max_us() >= 0.0,
          "Timer RAII sample is non-negative");
}

// ---------------------------------------------------------------------------
// 2. NpuLifecycleState (Device单次打开测试, §十八.1 + §五.1 discipline).
// ---------------------------------------------------------------------------
void test_lifecycle_clean_run() {
    chain::NpuLifecycleState s;
    check(s.state() == chain::NpuLifecycleState::State::Uninit, "fresh -> Uninit");
    check(!s.ready() && !s.failed(), "fresh: not ready, not failed");

    s.record_open();
    check(s.state() == chain::NpuLifecycleState::State::Opened, "open -> Opened");
    check(s.open_count() == 1, "open_count == 1");

    check(s.record_apply(), "first apply accepted (true)");
    check(s.apply_count() == 1, "apply_count == 1");

    s.record_ready();
    check(s.ready(), "ready after record_ready");

    for (int i = 0; i < 240; ++i) {
        check(s.begin_frame(), "frame N may run (begin_frame true)");
        s.record_frame_ok();
    }
    check(s.frame_count() == 240, "240 frames -> frame_count 240");
    check(s.discipline_ok(), "clean run -> discipline OK");
    check(s.open_count() == 1 && s.apply_count() == 1, "open once, apply once");
}

void test_lifecycle_double_open_fails() {
    chain::NpuLifecycleState s;
    s.record_open();
    s.record_open();   // a second open is a protocol violation
    check(s.failed(), "double open -> failed");
    check(s.open_count() == 1, "open_count stays 1 (second open rejected)");
    check(!s.discipline_ok(), "double open -> discipline FAIL");
}

void test_lifecycle_double_apply_fails() {
    chain::NpuLifecycleState s;
    s.record_open();
    check(s.record_apply(), "first apply accepted");
    check(!s.record_apply(), "second apply rejected (false)");
    // The second apply is rejected at the state gate BEFORE the counter, so the
    // recorded count stays 1 (a discipline violation never counts as an apply).
    check(s.apply_count() == 1, "apply_count stays 1 (double apply not counted)");
    check(!s.discipline_ok(), "double apply -> discipline FAIL");
}

void test_lifecycle_recovery_budget() {
    // recover_budget = 3: exactly 3 retries are granted, the 4th fails closed.
    chain::NpuLifecycleState s(3);
    s.record_open();
    s.record_apply();
    s.record_ready();
    check(s.begin_frame(), "frame starts");
    check(s.record_frame_failure(), "failure 1 -> retry (true)");
    check(s.record_frame_failure(), "failure 2 -> retry (true)");
    check(s.record_frame_failure(), "failure 3 -> retry (true)");
    check(!s.record_frame_failure(), "failure 4 -> over budget (false)");
    check(s.failed(), "budget overrun -> failed");
    check(!s.discipline_ok(), "failed recovery -> discipline FAIL");
}

void test_lifecycle_recovery_success_resets() {
    chain::NpuLifecycleState s(3);
    s.record_open();
    s.record_apply();
    s.record_ready();
    s.begin_frame();
    check(s.record_frame_failure(), "transient failure -> retry");
    s.record_frame_ok();   // the retry succeeded
    check(s.ready(), "recovery success -> Ready");
    check(s.recover_attempts() == 0, "recovery budget reset after success");
    check(s.discipline_ok(), "discipline OK after recovered frame");

    // A later frame still gets a fresh budget (not poisoned by the earlier failure).
    check(s.begin_frame(), "next frame may run");
    check(s.record_frame_failure(), "next frame failure -> fresh retry budget");
    check(s.record_frame_failure(), "fresh budget: failure 2 still within budget");
}

void test_lifecycle_fatal_no_retry() {
    chain::NpuLifecycleState s(3);
    s.record_open();
    s.record_apply();
    s.record_ready();
    s.begin_frame();
    s.record_fatal();   // e.g. a Device::reset(1) failure (poisons re-arm)
    check(s.failed(), "record_fatal -> failed");
    check(!s.record_frame_failure(), "no retry after fatal (false)");
    check(!s.discipline_ok(), "fatal -> discipline FAIL");
}

void test_lifecycle_close_from_any_state() {
    chain::NpuLifecycleState s;
    s.record_close();          // close is legal even before open (RAII)
    check(s.closed(), "close from Uninit is recorded");

    chain::NpuLifecycleState s2;
    s2.record_open();
    s2.record_apply();
    s2.record_ready();
    s2.record_close();
    check(s2.closed(), "close from Ready is recorded");
}

// ---------------------------------------------------------------------------
// 3. softmax_into == softmax (NPU输出一致性 / buffer reuse identical, §十八.19).
// ---------------------------------------------------------------------------
void test_softmax_into_parity() {
    const std::vector<float> x = {1.0f, 2.0f, 3.0f, -1.0f, 0.5f};
    const std::vector<float> ref = classify::softmax(x);
    std::vector<float> out;
    classify::softmax_into(x, out);
    check(out.size() == ref.size(), "softmax_into size matches");
    bool identical = true;
    for (std::size_t i = 0; i < ref.size(); ++i)
        if (out[i] != ref[i]) identical = false;
    check(identical, "softmax_into == softmax (bit-identical)");

    // Reuse the SAME out buffer across calls (M22: no per-frame realloc).
    const std::vector<float> y = {5.0f, -3.0f, 0.0f, 2.5f, -1.5f};
    classify::softmax_into(y, out);
    const std::vector<float> ref2 = classify::softmax(y);
    identical = true;
    for (std::size_t i = 0; i < ref2.size(); ++i)
        if (out[i] != ref2[i]) identical = false;
    check(identical, "softmax_into reuse == softmax (bit-identical)");

    // Empty input clears the output.
    std::vector<float> eout;
    classify::softmax_into(std::vector<float>{}, eout);
    check(eout.empty(), "empty softmax_into -> empty out");

    // Sums to ~1 (a valid probability distribution), max-shifted stability.
    double sum = 0.0;
    for (float p : ref) sum += p;
    check(near(sum, 1.0, 1e-5), "softmax sums to 1");
}

// ---------------------------------------------------------------------------
// 4. measure_into == measure (DSP buffer reuse identical, §十八.19).
// ---------------------------------------------------------------------------
void test_measure_into_parity() {
    const std::size_t n = 1024;
    std::vector<std::complex<float>> iq(n);
    for (std::size_t k = 0; k < n; ++k) {
        // A tone at bin 64 + a small deterministic "noise" (no RNG: reproducible).
        const double ang = 2.0 * 3.141592653589793 * 64.0 * static_cast<double>(k) /
                           static_cast<double>(n);
        const double noise = static_cast<double>((k * 7) % 13) - 6.0;
        iq[k] = std::complex<float>(static_cast<float>(500.0 * std::cos(ang) + noise),
                                    static_cast<float>(500.0 * std::sin(ang) + noise));
    }

    sdr::DspMeasureConfig cfg;
    cfg.sample_rate_hz = 128000.0;
    cfg.receiver_scale = 1.0f;
    sdr::DspMeasure m(cfg);

    const sdr::FrameMeasurements a = m.measure(iq.data(), n);
    sdr::MeasureScratch scratch;
    const sdr::FrameMeasurements b = m.measure_into(iq.data(), n, scratch);

    check(a.valid && b.valid, "both valid for a real tone");
    check(a.nan_inf == b.nan_inf, "nan_inf identical");
    check(a.rms_counts == b.rms_counts, "rms_counts identical");
    check(a.peak_counts == b.peak_counts, "peak_counts identical");
    check(a.papr_db == b.papr_db, "papr_db identical");
    check(a.clip_ratio == b.clip_ratio, "clip_ratio identical");
    check(a.power_dbfs == b.power_dbfs, "power_dbfs identical");
    check(a.noise_floor_dbfs == b.noise_floor_dbfs, "noise_floor_dbfs identical");
    check(a.psd_peak_prominence_db == b.psd_peak_prominence_db, "psd_peak_prominence_db identical");
    check(a.snr_est_db == b.snr_est_db, "snr_est_db identical");
    check(a.occupied_bins == b.occupied_bins, "occupied_bins identical");
    check(a.spectral_centroid_hz == b.spectral_centroid_hz, "spectral_centroid_hz identical");
    check(a.occupied_bw_hz == b.occupied_bw_hz, "occupied_bw_hz identical");
    check(a.model_rms == b.model_rms, "model_rms identical");

    // Reuse the SAME scratch across many calls (M22: no per-frame realloc).
    bool all_identical = true;
    for (int rep = 0; rep < 50; ++rep) {
        const sdr::FrameMeasurements c = m.measure_into(iq.data(), n, scratch);
        if (c.rms_counts != a.rms_counts || c.snr_est_db != a.snr_est_db ||
            c.spectral_centroid_hz != a.spectral_centroid_hz) {
            all_identical = false;
        }
    }
    check(all_identical, "reused scratch stable over 50 calls");

    // Empty input -> valid false (never NaN).
    const sdr::FrameMeasurements e = m.measure(iq.data(), 0);
    check(!e.valid, "empty input -> invalid");
}

// ---------------------------------------------------------------------------
// 5. UnixSocketSink non-blocking write (尖峰根因回归, §十八.5).
// ---------------------------------------------------------------------------
void test_socket_sink() {
#if defined(__unix__) || defined(__APPLE__)
    // (a) clean path: a connected reader receives the full JSON line, no drops.
    {
        int sv[2];
        check(::socketpair(AF_UNIX, SOCK_STREAM, 0, sv) == 0, "socketpair created");
        ui::UnixSocketSink sink(sv[1], true);   // sink owns the write end
        const std::string line = "{\"type\":\"result\",\"frame_id\":1}";
        sink.write(line);
        char buf[256];
        const ssize_t n = ::recv(sv[0], buf, sizeof(buf), 0);
        check(n == static_cast<ssize_t>(line.size() + 1), "reader got the full line + \\n");
        if (n > 0) {
            buf[n] = '\0';
            check(std::string(buf) == line + "\n", "framing (one JSON line + \\n) preserved");
        }
        check(sink.error_count() == 0, "clean write: 0 errors");
        check(sink.dropped_count() == 0, "clean write: 0 drops");
        ::close(sv[0]);
    }

    // (b) gone peer: send() fails (EPIPE/ECONNRESET) and the frame is dropped,
    //     the sink never throws and never blocks.
    {
        int sv[2];
        check(::socketpair(AF_UNIX, SOCK_STREAM, 0, sv) == 0, "socketpair created (b)");
        ui::UnixSocketSink sink(sv[1], true);
        ::close(sv[0]);   // peer goes away
        sink.write("{\"type\":\"result\",\"frame_id\":2}");
        sink.write("{\"type\":\"result\",\"frame_id\":3}");
        check(sink.error_count() + sink.dropped_count() > 0,
              "gone peer: frame dropped/errored, never threw");
    }

    // (c) full buffer (EAGAIN): a non-blocking full socket buffer drops the frame
    //     and keeps the connection, never blocking the inference loop.
    {
        int sv[2];
        check(::socketpair(AF_UNIX, SOCK_STREAM, 0, sv) == 0, "socketpair created (c)");
        int fl = ::fcntl(sv[1], F_GETFL, 0);
        check(fl >= 0, "F_GETFL ok");
        ::fcntl(sv[1], F_SETFL, fl | O_NONBLOCK);

        char chunk[512];
        std::memset(chunk, 'x', sizeof(chunk));
        bool filled = false;
        for (int i = 0; i < 200000; ++i) {
            const ssize_t w = ::send(sv[1], chunk, sizeof(chunk), 0);
            if (w < 0) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) { filled = true; }
                break;
            }
        }
        check(filled, "send buffer filled to EAGAIN");

        ui::UnixSocketSink sink(sv[1], true);
        const std::string big(4096, 'y');
        sink.write(big);
        check(sink.dropped_count() > 0, "full buffer: frame dropped (EAGAIN), no block");
        ::close(sv[0]);
    }
#else
    // Non-POSIX host: the socket body is compiled out; write() reports unsupported.
    ui::UnixSocketSink sink("/nonexistent.sock");
    sink.write("x");
    check(sink.error_count() > 0 || sink.dropped_count() == 0,
          "non-POSIX: write is a no-op / unsupported, never throws");
#endif
}

// A disabled (empty-path) socket sink is a no-op.
void test_socket_sink_disabled() {
    ui::UnixSocketSink sink("");
    check(!sink.enabled(), "empty-path sink disabled");
    sink.write("{\"type\":\"result\"}");
    check(sink.error_count() == 0 && sink.dropped_count() == 0,
          "disabled sink: no errors, no drops");
}

// ---------------------------------------------------------------------------
// 6. ResourceSample / read_resources (FD/RSS稳定, §十八.3).
// ---------------------------------------------------------------------------
void test_resource_snapshot() {
    const m22::ResourceSample s = m22::read_resources();
    if (m22::resource_sampling_supported()) {
        // On Linux the process has a real RSS/VM/FD/thread footprint.
        check(s.rss_kb > 0, "rss_kb > 0 on Linux");
        check(s.vm_kb > 0, "vm_kb > 0 on Linux");
        check(s.fd_count >= 3, "fd_count >= 3 (stdin/out/err) on Linux");
        check(s.thread_count >= 1, "thread_count >= 1 on Linux");
        check(s.cpu_seconds >= 0.0, "cpu_seconds >= 0 on Linux");
    } else {
        check(s.rss_kb == 0 && s.fd_count == 0 && s.thread_count == 0,
              "non-Linux: resource fields are 0");
    }
    const std::string j = s.json();
    check(j.find("\"rss_kb\"") != std::string::npos, "ResourceSample.json has rss_kb");
    check(j.find("\"fd_count\"") != std::string::npos, "ResourceSample.json has fd_count");

    // Two back-to-back samples are internally consistent (no throw, finite fields).
    const m22::ResourceSample s2 = m22::read_resources();
    check(!s2.json().empty(), "second sample json non-empty");
}

// ---------------------------------------------------------------------------
// 7. NullSink (串口静默, §五.3): the default per-frame route discards, no stdout.
// ---------------------------------------------------------------------------
void test_null_sink() {
    ui::NullSink sink;
    sink.write("{\"type\":\"result\",\"frame_id\":1}");   // must not throw / not print
    ++g_pass;   // reached here => no throw
}

// ---------------------------------------------------------------------------
// 8. Producer12 buffer reuse (稳态零堆分配 proxy, §十八.2): one producer reused
//    across many frames exercises the cf_ / scaled_ / dsp_scratch_ reuse path.
// ---------------------------------------------------------------------------
void test_producer_buffer_reuse() {
    struct FakeDev : producer::DeviceControl {
        void set_rx_lo(std::int64_t) override {}
        void set_rx_gain(double) override {}
    } dev;

    producer::ProducerConfig cfg;
    cfg.dsp.sample_rate_hz = 128000.0;
    cfg.dsp.receiver_scale = 1.0f;
    cfg.dsp.full_scale_counts = 2048.0;
    cfg.base_rf_gain_db = 10.0;
    cfg.stability_window = 5;
    cfg.batch_frames = 16;

    producer::Producer12 prod(cfg, dev);

    int classify_calls = 0;
    auto classify = [&](const float* /*t*/, std::vector<float>& lg) {
        ++classify_calls;
        lg.assign(12, 0.0f);
        lg[3] = 10.0f;   // deterministic argmax = 3
    };

    // A clean base tensor (RMS ~0.35 in model domain => ~720 counts, no clip).
    std::vector<float> base(producer::kTensorFloats);
    for (std::size_t k = 0; k < producer::kFrameComplex; ++k) {
        const double ang = 2.0 * 3.141592653589793 * 0.05 * static_cast<double>(k);
        base[k] = static_cast<float>(0.5 * std::cos(ang));
        base[producer::kFrameComplex + k] = static_cast<float>(0.5 * std::sin(ang));
    }

    producer::CaptureFlags flags;   // all false

    bool all_measured = true;
    bool all_logits_12 = true;
    for (int i = 0; i < 100; ++i) {
        producer::ProducerDecision d = prod.on_frame(base.data(), flags, classify);
        if (!d.has_measurements) all_measured = false;
        if (d.logits.size() != 12) all_logits_12 = false;
    }
    check(classify_calls == 100, "classify called once per frame (100)");
    check(all_measured, "every frame carried real measurements");
    check(all_logits_12, "every frame filled 12 logits in place");
}

}  // namespace

int main() {
    std::printf("test_m22_runtime\n");
    test_percentile_stats();
    test_stage_timing();
    test_lifecycle_clean_run();
    test_lifecycle_double_open_fails();
    test_lifecycle_double_apply_fails();
    test_lifecycle_recovery_budget();
    test_lifecycle_recovery_success_resets();
    test_lifecycle_fatal_no_retry();
    test_lifecycle_close_from_any_state();
    test_softmax_into_parity();
    test_measure_into_parity();
    test_socket_sink();
    test_socket_sink_disabled();
    test_resource_snapshot();
    test_null_sink();
    test_producer_buffer_reuse();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
