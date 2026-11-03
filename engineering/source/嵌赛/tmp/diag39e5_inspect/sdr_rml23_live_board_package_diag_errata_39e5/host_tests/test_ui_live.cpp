// test_ui_live.cpp -- host tests for the live UI server's data plane (task 39e5
// §四/§七): the AF_UNIX socket server line-buffering, the ResultFrame -> UiState
// mapping (MOCK/ERROR/LIVE/STALE semantics), and the 12-class Style A render.
//
// Links the REAL render stack (ui_sw/font_atlas.cpp + font_atlas_data.cpp +
// ui_render.cpp) so the 12-class page is exercised with the exact code the board
// runs.  The AF_UNIX loopback drives the exact ui::UnixSocketServer the server
// binary uses, and the exact ui::UnixSocketSink the Gate 8/9 producers use.
//
// Build/run: see host_tests/build_host_tests.sh.  Compiled with
// -O2 -Wall -Wextra -Werror; also run under ASan/UBSan to catch any render
// out-of-bounds write.

#include "../board_package/chain_common.hpp"          // fill_result (round-trip source)
#include "../board_package/result_frame_v2_parse.hpp"
#include "../board_package/ui_state_map.hpp"
#include "../board_package/unix_socket_server.hpp"
#include "../sdr_adapter/unix_socket_sink.hpp"
#include "../ui_sw/ui_render.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const char* what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what); }
}

// A clean Live result frame (no mock, no anomaly), valid against the §二.5
// contract (argmax_idx == 7 == QPSK, probabilities sum to 1).
rf::ResultFrame clean_frame() {
    rf::ResultFrame r;
    r.frame_id = 240;
    r.class_count = 12;
    r.mock = false;
    r.source = "fpga_npu";
    r.argmax_idx = 7;              // QPSK (index 7)
    r.argmax_class = "QPSK";
    r.confidence = 0.71f;
    r.e2e_us = 12400.0;
    r.classify_us = 9000.0;
    r.snr_db = 18.5;
    r.model_sha = "abcdef0123456789abcdef0123456789";
    r.probabilities.assign(12, 0.026363636f);   // (1 - 0.71) / 11
    r.probabilities[7] = 0.71f;   // QPSK
    return r;
}

// ---- (10-13) AF_UNIX loopback ----------------------------------------------
#if defined(__unix__) || defined(__APPLE__)
int raw_connect(const std::string& path) {
    const int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    if (path.size() >= sizeof(addr.sun_path)) { ::close(fd); return -1; }
    for (std::size_t i = 0; i < path.size(); ++i) addr.sun_path[i] = path[i];
    addr.sun_path[path.size()] = '\0';
    if (::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        ::close(fd);
        return -1;
    }
    return fd;
}

bool raw_send(int fd, const std::string& s) {
    std::size_t off = 0;
    while (off < s.size()) {
        const ssize_t n = ::send(fd, s.data() + off, s.size() - off, 0);
        if (n <= 0) return false;
        off += static_cast<std::size_t>(n);
    }
    return true;
}

// Poll the server until at least `target` lines have been delivered (appended to
// `out`), or the iteration budget is exhausted.
bool collect(ui::UnixSocketServer& srv, std::size_t target, std::size_t max_iters,
             std::vector<std::string>& out) {
    for (std::size_t it = 0; it < max_iters; ++it) {
        ui::UnixSocketServer::PollResult r = srv.poll(20);
        for (std::string& l : r.lines) out.push_back(std::move(l));
        if (out.size() >= target) return true;
    }
    return false;
}

void test_socket_loopback() {
    const std::string path =
        "/tmp/ui_live_test_" + std::to_string(::getpid()) + ".sock";

    // Basic: one client sends 3 complete lines in a single send.
    {
        ui::UnixSocketServer srv(path);
        check(srv.start(), "server start() succeeds");
        check(srv.listening(), "server is listening after start");

        const int fd = raw_connect(path);
        check(fd >= 0, "raw client connects");
        if (fd >= 0) {
            check(raw_send(fd, "alpha\nbeta\ngamma\n"), "send 3 complete lines");
            std::vector<std::string> lines;
            check(collect(srv, 3, 200, lines), "received 3 complete lines");
            check(lines.size() == 3, "exactly 3 lines delivered");
            if (lines.size() == 3) {
                check(lines[0] == "alpha" && lines[1] == "beta" && lines[2] == "gamma",
                      "line order/content preserved");
            }
            check(srv.received_lines() == 3, "received_lines() == 3");
            check(srv.received_bytes() >= 16, "received_bytes() counts payload");
            ::close(fd);
        }
    }

    // Half-line splice: a line split across two sends is rejoined.
    {
        ui::UnixSocketServer srv(path);
        check(srv.start(), "server start() (splice)");
        const int fd = raw_connect(path);
        check(fd >= 0, "client connects (splice)");
        if (fd >= 0) {
            check(raw_send(fd, "half1"), "send first half");
            check(raw_send(fd, "half2\n"), "send second half + newline");
            std::vector<std::string> lines;
            check(collect(srv, 1, 200, lines), "spliced line delivered");
            check(lines.size() == 1 && lines[0] == "half1half2",
                  "half-line is buffered and rejoined across reads");
            ::close(fd);
        }
    }

    // Multi-line split + partial tail carried across sends.
    {
        ui::UnixSocketServer srv(path);
        check(srv.start(), "server start() (split)");
        const int fd = raw_connect(path);
        check(fd >= 0, "client connects (split)");
        if (fd >= 0) {
            check(raw_send(fd, "a\nb\nc"), "send a,b,c (c has no newline)");
            check(raw_send(fd, "d\ne\n"), "complete c->cd then e");
            std::vector<std::string> lines;
            check(collect(srv, 4, 200, lines), "4 lines delivered (split)");
            if (lines.size() == 4) {
                check(lines[0] == "a" && lines[1] == "b" && lines[2] == "cd" &&
                          lines[3] == "e",
                      "multi-line split reassembled in order");
            }
            ::close(fd);
        }
    }

    // Disconnect with a truncated tail: the half-line is DISCARDED (never a
    // frame), then a fresh client reconnects and is served.
    {
        ui::UnixSocketServer srv(path);
        check(srv.start(), "server start() (reconnect)");
        int fd = raw_connect(path);
        check(fd >= 0, "first client connects");
        if (fd >= 0) {
            check(raw_send(fd, "orphan-no-newline"), "send unterminated tail");
            ::close(fd);   // EOF -> tail must be dropped
        }
        // Let the server observe the EOF.
        {
            std::vector<std::string> lines;
            for (int i = 0; i < 20; ++i) srv.poll(10);
            check(srv.received_lines() == 0, "truncated tail is never a line");
        }
        fd = raw_connect(path);
        check(fd >= 0, "second client reconnects after disconnect");
        if (fd >= 0) {
            check(raw_send(fd, "good\n"), "send one good line");
            std::vector<std::string> lines;
            check(collect(srv, 1, 200, lines), "good line delivered after reconnect");
            check(lines.size() == 1 && lines[0] == "good",
                  "reconnect serves a fresh client correctly");
            check(srv.received_lines() == 1, "received_lines() == 1 after reconnect");
            ::close(fd);
        }
    }

    // End-to-end through the REAL producer sink: N result_frame_v2 lines from a
    // ui::UnixSocketSink land at the server with zero sink errors.
    {
        ui::UnixSocketServer srv(path);
        check(srv.start(), "server start() (sink)");
        const std::size_t N = 20;
        ui::UnixSocketSink sink(path);
        std::vector<std::string> sent;
        for (std::size_t i = 0; i < N; ++i) {
            rf::ResultFrame f = clean_frame();
            f.frame_id = static_cast<std::uint64_t>(i + 1);
            const std::string line = ui::result_frame_v2_line(f);
            sent.push_back(line);
            sink.write(line);
        }
        check(sink.error_count() == 0, "sink wrote N lines with no errors");
        std::vector<std::string> lines;
        check(collect(srv, N, 400, lines), "server received all N sink lines");
        check(lines.size() == N, "server line count == N");
        // Every received line must parse and validate (round-trip the real sink).
        std::size_t valid = 0;
        for (const std::string& l : lines) {
            ui::ParseOutcome o = ui::parse_result_frame_v2(l);
            if (o.ok) ++valid;
        }
        check(valid == N, "all N sink lines parse as valid result_frame_v2");
        check(srv.received_lines() == N, "received_lines() == N");
    }
}
#else
void test_socket_loopback() {
    std::printf("  (skipped: no AF_UNIX on this platform)\n");
}
#endif

// ---- (14-16) ResultFrame -> UiState mapping ----------------------------------
void test_mapping() {
    // MOCK is never Live, and MOCK wins over anomalies.
    {
        rf::ResultFrame m = clean_frame();
        m.mock = true;
        ui::UiState st = ui::map_to_state(m);
        check(st.status == ui::Status::Mock, "mock -> Mock");
        check(st.source == "MOCK", "mock source forced to MOCK");
    }
    {
        rf::ResultFrame m = clean_frame();
        m.mock = true;
        m.overflow = true;   // a mock frame that also flags overflow
        ui::UiState st = ui::map_to_state(m);
        check(st.status == ui::Status::Mock, "mock + anomaly still Mock (mock wins)");
    }
    // Each anomaly flag alone -> Error.
    {
        rf::ResultFrame e = clean_frame();
        e.overflow = true;
        check(ui::map_to_state(e).status == ui::Status::Error, "overflow -> Error");
    }
    {
        rf::ResultFrame e = clean_frame();
        e.dropped = true;
        check(ui::map_to_state(e).status == ui::Status::Error, "dropped -> Error");
    }
    {
        rf::ResultFrame e = clean_frame();
        e.discontinuity = true;
        check(ui::map_to_state(e).status == ui::Status::Error, "discontinuity -> Error");
    }
    {
        rf::ResultFrame e = clean_frame();
        e.short_frame = true;
        check(ui::map_to_state(e).status == ui::Status::Error, "short_frame -> Error");
    }
    // Clean -> Live with source preserved.
    {
        rf::ResultFrame r = clean_frame();
        ui::UiState st = ui::map_to_state(r);
        check(st.status == ui::Status::Live, "clean -> Live");
        check(st.source == "fpga_npu", "clean source preserved");
    }
    {
        rf::ResultFrame r = clean_frame();
        r.source = "";
        check(ui::map_to_state(r).source == "SDR", "empty source -> SDR");
    }
    // Field pass-through: top1 / conf / frame / dist / classes / model.
    {
        ui::UiState st = ui::map_to_state(clean_frame());
        check(st.top1 == "QPSK", "top1 == argmax_class");
        check(std::fabs(st.conf - 0.71f) < 1e-6, "conf == confidence");
        check(st.frame == "240", "frame == frame_id string");
        check(st.dist.size() == 12, "dist width 12");
        check(st.classes == &ui::classes_12(), "classes == 12-class contract");
        check(st.model == "abcdef01", "model == short (8-char) sha");
    }
    // snr: null -> "--", finite -> "+18.5 dB".
    {
        rf::ResultFrame r = clean_frame();
        r.snr_db = std::numeric_limits<double>::quiet_NaN();
        check(ui::map_to_state(r).snr == "--", "snr NaN -> \"--\"");
    }
    {
        check(ui::map_to_state(clean_frame()).snr == "+18.5 dB", "snr 18.5 -> \"+18.5 dB\"");
    }
    // lat: prefer e2e_us, fall back to classify_us, else "--".
    {
        check(ui::map_to_state(clean_frame()).lat == "12.4 ms", "lat uses e2e_us");
        rf::ResultFrame r = clean_frame();
        r.e2e_us = 0.0;
        check(ui::map_to_state(r).lat == "9.0 ms", "lat falls back to classify_us");
        r.classify_us = 0.0;
        check(ui::map_to_state(r).lat == "--", "lat no timing -> \"--\"");
    }
    // short_sha.
    check(ui::short_sha("abcdef0123456789") == "abcdef01", "short_sha truncates to 8");
    check(ui::short_sha("abcd") == "abcd", "short_sha keeps short inputs");
    check(ui::short_sha("") == "", "short_sha of empty is empty");
}

// ---- LIVE -> STALE state machine helpers -------------------------------------
void test_staleness() {
    check(ui::should_be_stale(1000, 500, 500), "now-last == stale_ms -> stale");
    check(ui::should_be_stale(1001, 500, 500), "now-last > stale_ms -> stale");
    check(!ui::should_be_stale(999, 500, 500), "now-last < stale_ms -> not stale");
    check(!ui::should_be_stale(1000, 0, 500), "last_ms == 0 -> not stale");
    check(!ui::should_be_stale(1000, 500, 0), "stale_ms <= 0 -> disabled");

    check(ui::format_age(3200) == "3.2 s", "format_age 3200ms");
    check(ui::format_age(500) == "0.5 s", "format_age 500ms");
    check(ui::format_age(0) == "0.0 s", "format_age 0ms");
}

// ---- (17) 12-class render + geometry fits, no overflow -----------------------
void test_render_12class() {
    // Card grid must fit above the info strip (top 558) for every class count.
    for (int n = 8; n <= 16; ++n) {
        const ui::CardGrid g = ui::card_grid(n);
        const int last_bottom = g.y0 + (g.rows - 1) * g.row_pitch + g.card_h;
        check(last_bottom <= 556, ("card_grid(" + std::to_string(n) + ") fits").c_str());
        check(g.rows == (n + 1) / 2, ("card_grid(" + std::to_string(n) + ") rows").c_str());
    }

    // Status badge shape sits >=10px left of the text (never covers it).
    {
        const ui::font_t* f = ui::font_get(ui::Weight::Bold, 20);
        check(f != nullptr, "bold 20 font available");
        const int x_right = 1255;
        const ui::Status seq[4] = {ui::Status::Live, ui::Status::Stale,
                                   ui::Status::Error, ui::Status::Mock};
        for (ui::Status s : seq) {
            const int tw = ui::text_width(ui::status_label(s), f);
            const int r = (s == ui::Status::Error) ? 9 : 8;
            const int cx = ui::status_badge_shape_cx(s, x_right);
            check((x_right - tw) - (cx + r) >= 10, "badge shape >= 10px left of text");
        }
        check(std::string(ui::status_label(ui::Status::Live)) == "LIVE", "label Live");
        check(std::string(ui::status_label(ui::Status::Stale)) == "STALE", "label Stale");
        check(std::string(ui::status_label(ui::Status::Error)) == "ERROR", "label Error");
        check(std::string(ui::status_label(ui::Status::Mock)) == "MOCK", "label Mock");
    }

    // Render a 12-class Live page into a real 1280x720 RGB565 canvas and confirm
    // it produced output (ASan/UBSan guards the actual bounds).
    {
        ui::UiState st = ui::map_to_state(clean_frame());   // Live, 12 classes
        const int W = 1280, H = 720;
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H);
        ui::Canvas c{px.data(), W, H};
        const ui::Theme& pal = ui::theme_default();

        ui::render_main(c, pal, st);
        std::size_t non_bg = 0;
        for (const std::uint16_t p : px)
            if (p != pal.background) ++non_bg;
        check(non_bg > 10000, "render_main 12-class Live draws substantial content");

        ui::render_diag(c, pal, st);
        ui::render_touch(c, pal, st);
    }

    // A Mock / Error / Stale 12-class page also renders without issue.
    {
        ui::UiState st = ui::map_to_state(clean_frame());
        st.status = ui::Status::Stale;
        st.age = ui::format_age(3200);
        const int W = 1280, H = 720;
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H);
        ui::Canvas c{px.data(), W, H};
        ui::render_main(c, ui::theme_default(), st);   // STALE branch
    }
    {
        rf::ResultFrame e = clean_frame();
        e.overflow = true;
        ui::UiState st = ui::map_to_state(e);   // Error
        const int W = 1280, H = 720;
        std::vector<std::uint16_t> px(static_cast<std::size_t>(W) * H);
        ui::Canvas c{px.data(), W, H};
        ui::render_main(c, ui::theme_default(), st);   // ERROR branch (keeps nav)
    }
}

}  // namespace

int main() {
    std::printf("test_ui_live\n");
    test_socket_loopback();
    test_mapping();
    test_staleness();
    test_render_12class();
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
