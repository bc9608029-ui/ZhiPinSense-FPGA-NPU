// Host/board unit tests for the non-model system layer (sdr_adapter).
// No iCraft, no SDR, no board required.  Build with g++ -std=gnu++17.
//
//   g++ -std=gnu++17 -Wall -Wextra -I../sdr_adapter
//       test_all.cpp ../sdr_adapter/iq_source.cpp -o test_all && ./test_all
//
// Exits 0 iff every CHECK passes.

#include "iq_frame.hpp"
#include "sequence_monitor.hpp"
#include "iq_source.hpp"
#include "perf_stats.hpp"
#include "config.hpp"
#include "ui_report.hpp"
#include "pipeline.hpp"
#include "logging.hpp"

#include "categories.hpp"
#include "preprocess.hpp"
#include "classify.hpp"
#include "result_frame.hpp"
#include "iio_backend.hpp"
#include "mock_iio.hpp"
#include "pluto.hpp"
#include "offline_chain.hpp"
#include "unix_socket_sink.hpp"

#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond)                                                    \
    do {                                                               \
        if (cond) {                                                    \
            ++g_pass;                                                  \
        } else {                                                       \
            ++g_fail;                                                  \
            std::fprintf(stderr, "FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
        }                                                              \
    } while (0)

template <typename F>
static bool throws(F f) {
    try {
        f();
        return false;
    } catch (...) {
        return true;
    }
}

template <typename F>
static void run_case(const char* name, F f) {
    std::fprintf(stderr, "-- %s\n", name);
    try {
        f();
    } catch (const std::exception& e) {
        ++g_fail;
        std::fprintf(stderr, "EXCEPTION in %s: %s\n", name, e.what());
    }
}

// ---- FileIqSource -----------------------------------------------------------

static void test_file_iq_source() {
    const std::size_t nframes = 3;
    std::vector<char> buf(nframes * iq::kFrameBytes);
    for (std::size_t i = 0; i < buf.size(); ++i) buf[i] = static_cast<char>(i & 0xff);

    FileIqSource src(buf, nframes, /*loop=*/true);
    CHECK(src.frame_count() == nframes);

    iq::Frame f0, f1, f2, f3;
    CHECK(src.next(f0));
    CHECK(f0.frame_id == 0);
    CHECK(!f0.short_frame && !f0.overflow && !f0.dropped && !f0.discontinuity);
    CHECK(f0.iq == reinterpret_cast<const std::int16_t*>(buf.data()));
    CHECK(src.next(f1) && f1.frame_id == 1);
    CHECK(f1.iq == reinterpret_cast<const std::int16_t*>(buf.data() + iq::kFrameBytes));
    CHECK(src.next(f2) && f2.frame_id == 2);
    CHECK(src.next(f3) && f3.frame_id == 0);   // loop wraps
    CHECK(f3.iq == reinterpret_cast<const std::int16_t*>(buf.data()));

    src.rewind();
    iq::Frame fr;
    CHECK(src.next(fr) && fr.frame_id == 0);

    // single-shot exhausts cleanly
    FileIqSource once(buf, nframes, /*loop=*/false);
    iq::Frame g;
    CHECK(once.next(g) && once.next(g) && once.next(g));
    CHECK(!once.next(g));

    // constructor validation
    CHECK(throws([] { FileIqSource s(std::vector<char>(10), 0, true); }));
    CHECK(throws([] { FileIqSource s(std::vector<char>(10), 2, true); }));
}

// ---- SyntheticIqSource ------------------------------------------------------

static void test_synthetic_iq_source() {
    SyntheticIqSource src(/*frame_count=*/2, /*loop=*/false);
    CHECK(src.frame_count() == 2);

    iq::Frame a, b, c;
    CHECK(src.next(a));
    CHECK(a.frame_id == 0);
    CHECK(a.iq != nullptr);
    CHECK(!a.short_frame && !a.overflow && !a.dropped && !a.discontinuity);
    CHECK(src.next(b) && b.frame_id == 1);
    CHECK(!src.next(c));   // single-shot exhausted

    // determinism: two sources produce identical frame bytes
    SyntheticIqSource s1(1, false), s2(1, false);
    iq::Frame x, y;
    CHECK(s1.next(x) && s2.next(y));
    CHECK(std::memcmp(x.iq, y.iq, iq::kFrameBytes) == 0);
}

// ---- SequenceMonitor --------------------------------------------------------

static void test_sequence_monitor() {
    auto mk = [](std::uint64_t id, bool ov = false, bool dr = false,
                 bool disc = false, bool sf = false) {
        iq::Frame f;
        f.frame_id = id;
        f.overflow = ov;
        f.dropped = dr;
        f.discontinuity = disc;
        f.short_frame = sf;
        return f;
    };

    // clean stream
    {
        iq::SequenceMonitor m;
        for (std::uint64_t i = 0; i < 10; ++i) m.observe(mk(i));
        CHECK(m.healthy());
        CHECK(m.stats().total == 10);
        CHECK(m.stats().duplicate == 0 && m.stats().reorder == 0);
        CHECK(m.stats().gap == 0 && m.stats().dropped == 0);
    }

    // gap (inferred drop)
    {
        iq::SequenceMonitor m;
        m.observe(mk(0));
        m.observe(mk(2));
        CHECK(!m.healthy());
        CHECK(m.stats().gap == 1);
        CHECK(m.stats().dropped == 1);
    }

    // duplicate
    {
        iq::SequenceMonitor m;
        m.observe(mk(0));
        m.observe(mk(1));
        m.observe(mk(1));
        CHECK(m.stats().duplicate == 1);
        CHECK(m.stats().reorder == 0);
    }

    // reorder (backward id)
    {
        iq::SequenceMonitor m;
        m.observe(mk(0));
        m.observe(mk(1));
        m.observe(mk(0));
        CHECK(m.stats().reorder == 1);
        CHECK(m.stats().duplicate == 0);
    }

    // producer flags
    {
        iq::SequenceMonitor m;
        m.observe(mk(0, /*ov=*/true));
        m.observe(mk(1, false, /*dr=*/true));
        m.observe(mk(2, false, false, /*disc=*/true));
        m.observe(mk(3, false, false, false, /*sf=*/true));
        CHECK(m.stats().overflow == 1);
        CHECK(m.stats().dropped == 1);
        CHECK(m.stats().discontinuity == 1);
        CHECK(m.stats().short_frame == 1);
        CHECK(!m.healthy());
    }

    // reset
    {
        iq::SequenceMonitor m;
        m.observe(mk(0));
        m.observe(mk(2));
        m.reset();
        CHECK(m.healthy());
        CHECK(m.stats().total == 0);
    }
}

// ---- PerfStats --------------------------------------------------------------

static void test_perf_stats() {
    perf::PerfStats p;
    p.record(perf::Stage::kNpuInfer, 10.0);
    p.record(perf::Stage::kNpuInfer, 20.0);
    p.record(perf::Stage::kNpuInfer, 30.0);

    CHECK(p.count(perf::Stage::kNpuInfer) == 3);
    CHECK(p.avg_us(perf::Stage::kNpuInfer) == 20.0);
    CHECK(p.count(perf::Stage::kFpgaProcess) == 0);
    CHECK(p.avg_us(perf::Stage::kFpgaProcess) == 0.0);

    const std::string s = p.summary();
    CHECK(s.find("npu_infer") != std::string::npos);
    CHECK(s.find("cnt=3") != std::string::npos);

    p.reset();
    CHECK(p.count(perf::Stage::kNpuInfer) == 0);
}

// ---- cfg::Config ------------------------------------------------------------

static void test_config() {
    const std::string def = cfg::write_default_config();
    CHECK(def.find("target_sample_rate = 128000") != std::string::npos);

    // parse a temp file round-trip
    const std::string path = "test_config.tmp";
    {
        std::ofstream out(path, std::ios::binary);
        out << def;
    }
    cfg::Config c = cfg::parse_config_file(path);
    CHECK(c.target_sample_rate == 128000);
    CHECK(c.symbol_rate == 16000);
    CHECK(c.frame_length == 1024);
    CHECK(c.receiver_scale == 1.0);
    CHECK(c.sdr_raw_sample_rate == 0);       // TBD placeholder
    CHECK(c.pluto_sample_rate_hz == 0);      // Pluto runtime: unspecified
    CHECK(c.pluto_uri == "");
    CHECK(c.abort_on_fpga_failure == true);
    CHECK(c.ui_json_lines == true);
    std::remove(path.c_str());

    // type coercion + unknown-key / malformed rejection
    cfg::Config t;
    cfg::apply_override(t, "fpga_timeout_ms", "2500");
    CHECK(t.fpga_timeout_ms == 2500);
    cfg::apply_override(t, "abort_on_fpga_failure", "false");
    CHECK(t.abort_on_fpga_failure == false);
    cfg::apply_override(t, "abort_on_fpga_failure", "1");
    CHECK(t.abort_on_fpga_failure == true);
    cfg::apply_override(t, "log_level", "debug");
    CHECK(t.log_level == "debug");
    cfg::apply_override(t, "pluto_center_freq_hz", "2400000000");
    CHECK(t.pluto_center_freq_hz == 2400000000ULL);
    cfg::apply_override(t, "pluto_gain_mode", "manual");
    CHECK(t.pluto_gain_mode == "manual");
    cfg::apply_override(t, "pluto_gain_db", "37.5");
    CHECK(t.pluto_gain_db == 37.5);
    CHECK(throws([&] { cfg::apply_override(t, "no_such_key", "1"); }));
    CHECK(throws([&] { cfg::apply_override(t, "fpga_timeout_ms", "not_a_number"); }));
}

// ---- ui:: -------------------------------------------------------------------

static void test_ui_report() {
    const std::string esc = ui::json_escape("a\"b\\c\nd");
    CHECK(esc.find("\\\"") != std::string::npos);
    CHECK(esc.find("\\\\") != std::string::npos);
    CHECK(esc.find("\\n") != std::string::npos);

    const std::string r = ui::result_line(7, "QPSK", "QPSK", true, 1.5, 0.7);
    CHECK(r.find("\"type\":\"result\"") != std::string::npos);
    CHECK(r.find("\"frame_id\":7") != std::string::npos);
    CHECK(r.find("\"match\":true") != std::string::npos);

    const std::string st = ui::status_line("fpga", "done");
    CHECK(st.find("\"type\":\"status\"") != std::string::npos);

    const std::string m = ui::metric_line("npu_infer", 0.67, "ms");
    CHECK(m.find("\"type\":\"metric\"") != std::string::npos);
    CHECK(m.find("\"npu_infer\"") != std::string::npos);
}

// ---- pipeline::policy -------------------------------------------------------

static void test_pipeline_policy() {
    using namespace pipeline;
    CHECK(policy_for(FailureClass::IqDrop) == RecoveryAction::Continue);
    CHECK(policy_for(FailureClass::IqOverflow) == RecoveryAction::Continue);
    CHECK(policy_for(FailureClass::FpgaTimeout) == RecoveryAction::AbortRun);
    CHECK(policy_for(FailureClass::FpgaError) == RecoveryAction::AbortRun);
    CHECK(policy_for(FailureClass::FpgaMismatch) == RecoveryAction::AbortRun);
    CHECK(policy_for(FailureClass::NpuTimeout) == RecoveryAction::AbortRun);
    CHECK(policy_for(FailureClass::NpuError) == RecoveryAction::AbortRun);
    CHECK(policy_for(FailureClass::VersionMismatch) == RecoveryAction::AbortRun);
    CHECK(policy_for(FailureClass::None) == RecoveryAction::Continue);
    CHECK(is_fatal(FailureClass::NpuTimeout));
    CHECK(!is_fatal(FailureClass::IqDrop));
}

// ---- logging -----------------------------------------------------------------

static void test_logging() {
    const std::string path = "test_log.tmp";
    std::remove(path.c_str());
    logx::Logger::instance().set_file(path);
    logx::Logger::instance().set_level(logx::Level::Error);

    // suppressed at Error level (Info < Error)
    LOG_INFO("should not appear %d", 1);
    {
        std::ifstream in(path, std::ios::binary);
        CHECK(!in.is_open());   // file not yet created
    }

    LOG_ERROR("hello %d", 42);
    {
        std::ifstream in(path, std::ios::binary);
        std::string all((std::istreambuf_iterator<char>(in)),
                        std::istreambuf_iterator<char>());
        CHECK(all.find("hello 42") != std::string::npos);
        CHECK(all.find("ERROR") != std::string::npos);
    }

    std::remove(path.c_str());
    logx::Logger::instance().set_file("");
}

// ---- cat:: categories -------------------------------------------------------

static void test_categories() {
    cat::Contract f8 = cat::frozen_8();
    CHECK(f8.class_count == 8);
    CHECK(f8.class_names.size() == 8);
    CHECK(f8.class_names[0] == "BPSK" && f8.class_names[7] == "OFDM");
    CHECK(std::string(f8.provenance) == "frozen");

    cat::Contract c10 = cat::current_10();
    CHECK(c10.class_count == 10);
    CHECK(c10.class_names[0] == "AM-DSB" && c10.class_names[9] == "OFDM");
    CHECK(std::string(c10.provenance) == "current");

    cat::Contract t12 = cat::target_12();
    CHECK(t12.class_count == 12);
    CHECK(t12.class_names[0] == "OOK" && t12.class_names[11] == "OFDM");
    CHECK(t12.class_names[5] == "GFSK");
    CHECK(std::string(t12.provenance) == "target");

    CHECK(cat::is_valid(f8) && cat::is_valid(c10) && cat::is_valid(t12));

    cat::Contract bad = t12;
    bad.class_count = 4;                 // below kMinClasses
    CHECK(!cat::is_valid(bad));
    bad.class_count = 12;
    bad.class_names.pop_back();          // name/count mismatch
    CHECK(!cat::is_valid(bad));
    cat::Contract empty = c10;
    empty.class_names[3] = "";           // empty name
    CHECK(!cat::is_valid(empty));

    CHECK(cat::label(c10, 0) == "AM-DSB");
    CHECK(cat::label(c10, 99) == "<99>");
}

// ---- preproc:: physical frontend --------------------------------------------

static void test_preprocess() {
    std::int16_t iq[8] = {1000, 2000, 3000, 4000, -1000, 500, 0, 0};
    preproc::PhysicalPlane p = preproc::physical_frontend(iq, 4);
    CHECK(p.power.size() == 4 && p.lag1_real.size() == 4 && p.lag1_imag.size() == 4);

    CHECK(p.power[0] == 1000 * 1000 + 2000 * 2000);   // 5,000,000
    CHECK(p.power[1] == 3000 * 3000 + 4000 * 4000);   // 25,000,000
    CHECK(p.lag1_real[0] == 0.0f);                    // first sample deterministic 0
    CHECK(p.lag1_imag[0] == 0.0f);

    // n=1: lag1_real = I1*I0 + Q1*Q0 = 3e6 + 8e6 = 11e6
    CHECK(p.lag1_real[1] == 11000000.0f);
    // lag1_imag = Q1*I0 - I1*Q0 = 4e6 - 6e6 = -2e6
    CHECK(p.lag1_imag[1] == -2000000.0f);
    // n=2: prev = (3000,4000); I2=-1000, Q2=500
    CHECK(p.lag1_real[2] == -1000000.0f);
    CHECK(p.lag1_imag[2] == 5500000.0f);
    CHECK(p.lag1_real[3] == 0.0f && p.lag1_imag[3] == 0.0f);
}

// ---- classify:: MockClassifier ----------------------------------------------

static void test_classify() {
    classify::MockClassifier mc(cat::current_10());
    std::vector<std::int16_t> iq(iq::kComplexSamplesPerFrame * 2, 0);
    preproc::PhysicalPlane feat =
        preproc::physical_frontend(iq.data(), iq::kComplexSamplesPerFrame);
    iq::Frame f;
    f.frame_id = 0;
    f.iq = iq.data();

    classify::Logits l1 = mc.classify(f, feat);
    CHECK(l1.mock == true);
    CHECK(l1.source == "mock");
    CHECK(static_cast<int>(l1.values.size()) == 10);

    const int a = classify::argmax(l1);
    CHECK(a >= 0 && a < 10);
    const auto top = classify::top1(l1);
    CHECK(top.first == a);
    CHECK(top.second > 0.0f && top.second <= 1.0f);

    // determinism: same frame_id -> identical logits
    classify::Logits l2 = mc.classify(f, feat);
    CHECK(l2.values == l1.values);

    // class-count agnostic: 8 and 12 contracts give matching widths
    classify::MockClassifier m8(cat::frozen_8());
    classify::MockClassifier m12(cat::target_12());
    CHECK(static_cast<int>(m8.classify(f, feat).values.size()) == 8);
    CHECK(static_cast<int>(m12.classify(f, feat).values.size()) == 12);

    // softmax sums to 1
    const std::vector<float> sm = classify::softmax(l1.values);
    double sum = 0.0;
    for (float v : sm) sum += v;
    CHECK(sum > 0.999 && sum < 1.001);
}

// ---- rf::ResultFrame + ui::result_frame_line ---------------------------------

static void test_result_frame() {
    rf::ResultFrame r;
    r.frame_id = 42;
    r.argmax_idx = 3;
    r.argmax_class = "16QAM";
    r.confidence = 0.85f;
    r.class_count = 10;
    r.mock = true;
    r.source = "mock";
    r.e2e_us = 1.25;
    const std::string j = ui::result_frame_line(r);
    CHECK(j.find("\"type\":\"result\"") != std::string::npos);
    CHECK(j.find("\"frame_id\":42") != std::string::npos);
    CHECK(j.find("\"argmax_class\":\"16QAM\"") != std::string::npos);
    CHECK(j.find("\"mock\":true") != std::string::npos);
    CHECK(j.find("\"confidence\":0.850000") != std::string::npos);
    CHECK(j.find("\"class_count\":10") != std::string::npos);
}

// ---- iio::MockBackend: continuous buffering ---------------------------------

static void test_mock_iio_continuous() {
    iio::MockBackend b;
    b.advance(2048);  // two frames' worth
    iio::RawChunk c = b.read(1024, 0);
    CHECK(c.samples_available == 1024);
    CHECK(!c.overflow && !c.discontinuity && !c.timed_out && !c.broken && !c.eos);
    iio::RawChunk c2 = b.read(1024, 0);
    CHECK(c2.samples_available == 1024);
    iio::RawChunk c3 = b.read(1024, 0);  // drained, not finished -> no data, no EOS
    CHECK(c3.samples_available == 0);
    CHECK(!c3.eos && !c3.timed_out);
    b.finish();
    iio::RawChunk c4 = b.read(1024, 0);
    CHECK(c4.eos == true);
}

static void test_mock_iio_short_read() {
    iio::MockBackend b;
    b.advance(2048);
    b.inject_short_read(100);
    iio::RawChunk c = b.read(1024, 0);
    CHECK(c.samples_available == 100);
    iio::RawChunk c2 = b.read(1024, 0);  // back to normal
    CHECK(c2.samples_available == 1024);
}

static void test_mock_iio_timeout() {
    iio::MockBackend b;
    b.inject_timeout();
    iio::RawChunk c = b.read(1024, 0);
    CHECK(c.timed_out == true);
    CHECK(c.samples_available == 0);
    b.advance(1024);
    iio::RawChunk c2 = b.read(1024, 0);  // one-shot cleared
    CHECK(!c2.timed_out && c2.samples_available == 1024);
}

static void test_mock_iio_overflow() {
    iio::MockBackend b;
    b.inject_overflow();
    b.advance(1024);
    iio::RawChunk c = b.read(1024, 0);
    CHECK(c.overflow == true);
    CHECK(c.samples_available == 1024);
}

static void test_mock_iio_discontinuity() {
    iio::MockBackend b;
    b.inject_discontinuity();
    b.advance(1024);
    iio::RawChunk c = b.read(1024, 0);
    CHECK(c.discontinuity == true);
}

static void test_mock_iio_break_recover() {
    iio::MockBackend b;
    CHECK(b.is_open());
    b.break_stream();
    CHECK(!b.is_open());
    iio::RawChunk c = b.read(1024, 0);
    CHECK(c.broken == true);
    b.reopen();
    CHECK(b.is_open());
    b.advance(1024);
    iio::RawChunk c2 = b.read(1024, 0);
    CHECK(!c2.broken && c2.samples_available == 1024);
}

static void test_mock_iio_backpressure() {
    iio::MockOptions opt;
    opt.ring_complex = 1024;
    iio::MockBackend b(opt);
    b.advance(3 * 1024);  // overrun the ring without draining
    CHECK(b.dropped_samples() == 2 * 1024);
    iio::RawChunk c = b.read(1024, 0);
    CHECK(c.overflow == true);             // overrun flagged
    CHECK(c.samples_available == 1024);    // latest 1024 remain
}

// ---- pluto::PlutoIqSource ----------------------------------------------------

static void test_pluto_framing() {
    iio::MockBackend b;
    b.advance(4 * 1024);
    pluto::PlutoIqSource src(pluto::Config{}, b);

    iq::Frame f0, f1, f2, f3;
    CHECK(src.next(f0));
    CHECK(f0.frame_id == 0);
    CHECK(!f0.short_frame && !f0.overflow && !f0.discontinuity && !f0.dropped);
    CHECK(f0.iq != nullptr);
    CHECK(f0.iq[0] == 10000 && f0.iq[1] == 0);  // tone: cos(0)=1, sin(0)=0
    CHECK(src.next(f1) && f1.frame_id == 1);
    CHECK(src.next(f2) && f2.frame_id == 2);
    CHECK(src.next(f3) && f3.frame_id == 3);
}

static void test_pluto_short_read_assemble() {
    iio::MockBackend b;
    b.inject_short_read(512);   // first read returns only 512
    b.advance(1536);            // enough for one full frame after the short read
    pluto::PlutoIqSource src(pluto::Config{}, b);
    iq::Frame f;
    CHECK(src.next(f));
    CHECK(!f.short_frame);       // adapter accumulates across short reads
    CHECK(f.frame_id == 0);
}

static void test_pluto_short_frame_at_eos() {
    iio::MockBackend b;
    b.advance(512);              // half a frame, then EOS
    b.finish();
    pluto::PlutoIqSource src(pluto::Config{}, b);
    iq::Frame f;
    CHECK(src.next(f));
    CHECK(f.short_frame == true);
    CHECK(f.frame_id == 0);
    CHECK(!src.next(f));         // then clean EOS
}

static void test_pluto_timeout_transient() {
    iio::MockBackend b;
    b.advance(1024);
    b.inject_timeout();          // one read times out, then recovers
    pluto::PlutoIqSource src(pluto::Config{}, b);
    iq::Frame f;
    CHECK(src.next(f));
    CHECK(f.frame_id == 0);
    CHECK(src.timeouts() >= 1);
}

static void test_pluto_timeout_persistent() {
    iio::MockBackend b;
    b.advance(1024);
    b.set_sticky_timeout(true);  // every read times out
    pluto::PlutoIqSource src(pluto::Config{}, b);
    iq::Frame f;
    CHECK(throws([&] { src.next(f); }));
}

static void test_pluto_discontinuity() {
    iio::MockBackend b;
    b.inject_discontinuity();
    b.advance(1024);
    pluto::PlutoIqSource src(pluto::Config{}, b);
    iq::Frame f;
    CHECK(src.next(f));
    CHECK(f.discontinuity == true);
    CHECK(f.frame_id == 0);
}

static void test_pluto_break_recovery() {
    iio::MockBackend b;
    b.advance(1024);
    b.break_stream();
    b.advance(1024);
    pluto::PlutoIqSource src(pluto::Config{}, b);
    iq::Frame f;
    CHECK(src.next(f));                  // recovers
    CHECK(f.frame_id == 0);
    CHECK(f.discontinuity == true);      // gap flagged
    CHECK(src.recovered() >= 1);
}

static void test_pluto_backpressure() {
    iio::MockOptions opt;
    opt.ring_complex = 1024;
    iio::MockBackend b(opt);
    b.advance(3 * 1024);                 // overrun
    pluto::PlutoIqSource src(pluto::Config{}, b);
    iq::Frame f;
    CHECK(src.next(f));
    CHECK(f.overflow == true);
    CHECK(f.frame_id == 0);
    CHECK(b.dropped_samples() == 2048);
}

// ---- chain:: offline end-to-end ---------------------------------------------

struct StringSink : ui::Sink {
    std::vector<std::string> lines;
    void write(const std::string& l) override { lines.push_back(l); }
};

static void test_offline_chain() {
    const std::size_t nframes = 3;
    std::vector<char> buf(nframes * iq::kFrameBytes);
    std::int16_t* p = reinterpret_cast<std::int16_t*>(buf.data());
    for (std::size_t i = 0; i < nframes * iq::kComplexSamplesPerFrame; ++i) {
        p[2 * i] = static_cast<std::int16_t>(1000 + (i % 1000));
        p[2 * i + 1] = static_cast<std::int16_t>(-500 + (i % 800));
    }
    FileIqSource src(buf, nframes, /*loop=*/false);
    classify::MockClassifier cls(cat::current_10());
    StringSink sink;

    chain::ChainStats st = chain::run(src, cls, cat::current_10(), sink);
    CHECK(st.frames == nframes);
    CHECK(st.classified == nframes);
    CHECK(st.short_frames == 0);
    CHECK(st.overflow == 0 && st.dropped == 0 && st.discontinuity == 0);
    CHECK(sink.lines.size() == nframes);

    for (const std::string& l : sink.lines) {
        CHECK(l.find("\"type\":\"result\"") != std::string::npos);
        CHECK(l.find("\"mock\":true") != std::string::npos);
        CHECK(l.find("\"source\":\"mock\"") != std::string::npos);
        CHECK(l.find("\"argmax_class\":\"") != std::string::npos);
    }
    CHECK(sink.lines[0].find("\"frame_id\":0") != std::string::npos);
}

// ---- ui::UnixSocketSink -------------------------------------------------------

static void test_unix_socket() {
#if defined(__unix__) || defined(__APPLE__)
    int sv[2];
    CHECK(::socketpair(AF_UNIX, SOCK_STREAM, 0, sv) == 0);
    {
        ui::UnixSocketSink sink(sv[0], /*owns=*/true);
        sink.write("{\"type\":\"result\",\"frame_id\":1}");
        char rbuf[256];
        ssize_t n = ::recv(sv[1], rbuf, sizeof(rbuf) - 1, 0);
        CHECK(n > 0);
        rbuf[n] = '\0';
        const std::string got(rbuf);
        CHECK(got.find("\"frame_id\":1") != std::string::npos);
        CHECK(got.find('\n') != std::string::npos);
        CHECK(sink.error_count() == 0);
    }
    ::close(sv[1]);

    // disabled sink (empty path) is a no-op
    ui::UnixSocketSink none("");
    CHECK(!none.enabled());
    none.write("should be dropped");
    CHECK(none.error_count() == 0);

    // bad path: no listener -> error recorded, no throw
    ui::UnixSocketSink bad("/nonexistent_dir_xyz/no.sock");
    bad.write("x");
    CHECK(bad.error_count() == 1);
#else
    CHECK(true);
#endif
}

int main() {
    run_case("FileIqSource", test_file_iq_source);
    run_case("SyntheticIqSource", test_synthetic_iq_source);
    run_case("SequenceMonitor", test_sequence_monitor);
    run_case("PerfStats", test_perf_stats);
    run_case("Config", test_config);
    run_case("UIReport", test_ui_report);
    run_case("PipelinePolicy", test_pipeline_policy);
    run_case("Logging", test_logging);
    run_case("Categories", test_categories);
    run_case("Preprocess", test_preprocess);
    run_case("Classify", test_classify);
    run_case("ResultFrame", test_result_frame);
    run_case("MockIioContinuous", test_mock_iio_continuous);
    run_case("MockIioShortRead", test_mock_iio_short_read);
    run_case("MockIioTimeout", test_mock_iio_timeout);
    run_case("MockIioOverflow", test_mock_iio_overflow);
    run_case("MockIioDiscontinuity", test_mock_iio_discontinuity);
    run_case("MockIioBreakRecover", test_mock_iio_break_recover);
    run_case("MockIioBackpressure", test_mock_iio_backpressure);
    run_case("PlutoFraming", test_pluto_framing);
    run_case("PlutoShortReadAssemble", test_pluto_short_read_assemble);
    run_case("PlutoShortFrameAtEos", test_pluto_short_frame_at_eos);
    run_case("PlutoTimeoutTransient", test_pluto_timeout_transient);
    run_case("PlutoTimeoutPersistent", test_pluto_timeout_persistent);
    run_case("PlutoDiscontinuity", test_pluto_discontinuity);
    run_case("PlutoBreakRecovery", test_pluto_break_recovery);
    run_case("PlutoBackpressure", test_pluto_backpressure);
    run_case("OfflineChain", test_offline_chain);
    run_case("UnixSocket", test_unix_socket);

    std::fprintf(stderr, "\nRESULT pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
