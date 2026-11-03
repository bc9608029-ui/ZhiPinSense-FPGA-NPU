// test_m27_1_metrics.cpp — offline host unit tests for the SDK-free measurement
// and result-JSON helpers shared by the M27.1 probes (m27_1_metrics.hpp).
//
// Builds WITHOUT any iCraft SDK: it validates latency statistics, argmax,
// finite-check, JSON escaping, the ProbeResult JSON shape, and that both the
// emitted JSON and results/M27_1_RESULT_TEMPLATE.json are well-formed JSON.

#include "../probes/m27_1_metrics.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>

static int g_pass = 0, g_fail = 0, g_assert = 0;
#define CHECK(cond)                                                        \
    do {                                                                   \
        ++g_assert;                                                        \
        if (cond) { ++g_pass; }                                            \
        else { ++g_fail; std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); } \
    } while (0)

// ---- minimal recursive-descent JSON validator (test-only, no deps) ----
namespace jsoncheck {
struct P { const char* s; std::size_t n; std::size_t i = 0; };
static void ws(P& p) {
    while (p.i < p.n && (p.s[p.i] == ' ' || p.s[p.i] == '\t' ||
                         p.s[p.i] == '\n' || p.s[p.i] == '\r'))
        ++p.i;
}
static bool value(P& p);
static bool str(P& p) {
    if (p.i >= p.n || p.s[p.i] != '"') return false;
    ++p.i;
    while (p.i < p.n && p.s[p.i] != '"') {
        if (p.s[p.i] == '\\') { p.i += 2; } else { ++p.i; }
    }
    if (p.i >= p.n) return false;
    ++p.i;  // closing quote
    return true;
}
static bool num(P& p) {
    const std::size_t start = p.i;
    if (p.i < p.n && (p.s[p.i] == '-' || p.s[p.i] == '+')) ++p.i;
    while (p.i < p.n && (p.s[p.i] >= '0' && p.s[p.i] <= '9')) ++p.i;
    if (p.i < p.n && p.s[p.i] == '.') { ++p.i; while (p.i < p.n && p.s[p.i] >= '0' && p.s[p.i] <= '9') ++p.i; }
    if (p.i < p.n && (p.s[p.i] == 'e' || p.s[p.i] == 'E')) {
        ++p.i;
        if (p.i < p.n && (p.s[p.i] == '-' || p.s[p.i] == '+')) ++p.i;
        while (p.i < p.n && p.s[p.i] >= '0' && p.s[p.i] <= '9') ++p.i;
    }
    return p.i > start;
}
static bool lit(P& p, const char* w) {
    const std::size_t len = std::strlen(w);
    if (p.i + len > p.n) return false;
    if (std::strncmp(p.s + p.i, w, len) != 0) return false;
    p.i += len;
    return true;
}
static bool arr(P& p) {
    ++p.i; ws(p);
    if (p.i < p.n && p.s[p.i] == ']') { ++p.i; return true; }
    for (;;) {
        if (!value(p)) return false;
        ws(p);
        if (p.i < p.n && p.s[p.i] == ']') { ++p.i; return true; }
        if (p.i >= p.n || p.s[p.i] != ',') return false;
        ++p.i; ws(p);
    }
}
static bool obj(P& p) {
    ++p.i; ws(p);
    if (p.i < p.n && p.s[p.i] == '}') { ++p.i; return true; }
    for (;;) {
        ws(p);
        if (!str(p)) return false;
        ws(p);
        if (p.i >= p.n || p.s[p.i] != ':') return false;
        ++p.i;
        if (!value(p)) return false;
        ws(p);
        if (p.i < p.n && p.s[p.i] == '}') { ++p.i; return true; }
        if (p.i >= p.n || p.s[p.i] != ',') return false;
        ++p.i;
    }
}
static bool value(P& p) {
    ws(p);
    if (p.i >= p.n) return false;
    const char c = p.s[p.i];
    if (c == '"') return str(p);
    if (c == '{') return obj(p);
    if (c == '[') return arr(p);
    if (c == 't') return lit(p, "true");
    if (c == 'f') return lit(p, "false");
    if (c == 'n') return lit(p, "null");
    return num(p);
}
bool valid(const std::string& s) {
    P p{s.c_str(), s.size(), 0};
    const bool ok = value(p);
    ws(p);
    return ok && p.i == p.n;
}
}  // namespace jsoncheck

int main() {
    using namespace m27_1;

    // ---- LatencyStats ----
    {
        LatencyStats s;
        for (double v : {1.0, 2.0, 3.0, 4.0, 5.0}) s.add(v);
        CHECK(s.count == 5);
        CHECK(std::fabs(s.mean() - 3.0) < 1e-9);
        CHECK(std::fabs(s.max - 5.0) < 1e-9);
        CHECK(std::fabs(s.p99() - 5.0) < 1e-9);
    }
    {
        LatencyStats s;
        for (int i = 1; i <= 100; ++i) s.add(static_cast<double>(i));
        // p99 = 99th percentile of 1..100 -> 99.0
        CHECK(std::fabs(s.p99() - 99.0) < 1e-9);
        CHECK(s.count == 100);
    }
    { LatencyStats s; CHECK(s.mean() == 0.0); CHECK(s.p99() == 0.0); }

    // ---- argmax ----
    { const float v[] = {1.0f, 5.0f, 3.0f}; CHECK(argmax(v, 3) == 1); }
    { const float v[] = {2.0f, 2.0f, 2.0f}; CHECK(argmax(v, 3) == 0); }
    CHECK(argmax(nullptr, 0) == -1);
    CHECK(argmax(nullptr, 5) == -1);

    // ---- all_finite ----
    { const float v[] = {1.0f, -2.5f, 0.0f}; CHECK(all_finite(v, 3)); }
    { const float v[] = {1.0f, std::numeric_limits<float>::quiet_NaN(), 3.0f}; CHECK(!all_finite(v, 3)); }
    { const float v[] = {std::numeric_limits<float>::infinity()}; CHECK(!all_finite(v, 1)); }

    // ---- Json emitter: string escaping + exact output ----
    {
        Json j;
        j.str("k", "a\"b\\c\nd");
        const std::string s = j.done();
        CHECK(s == "{\"k\":\"a\\\"b\\\\c\\nd\"}\n");
        CHECK(jsoncheck::valid(s));
    }
    {
        Json j;
        j.str("s", "plain").num("x", 1.5).integer("i", -3).boolean("b", true);
        const std::string s = j.done();
        CHECK(s == "{\"s\":\"plain\",\"x\":1.500000,\"i\":-3,\"b\":true}\n");
        CHECK(jsoncheck::valid(s));
    }

    // ---- ProbeResult.to_json: all keys present + valid JSON + bool/num format ----
    {
        ProbeResult r;
        r.probe = "probe_single_model";
        r.status = "PASS";
        r.conclusion = "";
        r.device_open_us = 1.25;
        r.fwd_a.add(10.0); r.fwd_a.add(20.0);
        r.correctness_pass = true;
        r.error_count = 7;
        r.return_codes = "0x0,0x1";
        r.notes = "note with \"quote\"";
        const std::string s = r.to_json();
        CHECK(jsoncheck::valid(s));
        CHECK(s.find("\"probe\":\"probe_single_model\"") != std::string::npos);
        CHECK(s.find("\"status\":\"PASS\"") != std::string::npos);
        CHECK(s.find("\"device_open_us\":1.250000") != std::string::npos);
        CHECK(s.find("\"forward_a_mean_us\":15.000000") != std::string::npos);
        CHECK(s.find("\"forward_a_max_us\":20.000000") != std::string::npos);
        CHECK(s.find("\"forward_a_p99_us\":20.000000") != std::string::npos);
        CHECK(s.find("\"correctness_pass\":true") != std::string::npos);
        CHECK(s.find("\"repeatability_pass\":false") != std::string::npos);
        CHECK(s.find("\"error_count\":7") != std::string::npos);
        CHECK(s.find("\"mem_etm_used_bytes\":-1") != std::string::npos);
        CHECK(s.find("\"notes\":\"note with \\\"quote\\\"\"") != std::string::npos);
    }

    // ---- results/M27_1_RESULT_TEMPLATE.json is well-formed JSON ----
    {
        std::ifstream f("../results/M27_1_RESULT_TEMPLATE.json");
        CHECK(static_cast<bool>(f));
        if (f) {
            std::ostringstream ss; ss << f.rdbuf();
            const std::string s = ss.str();
            CHECK(jsoncheck::valid(s));
            CHECK(s.find("\"probe\"") != std::string::npos);
            CHECK(s.find("\"forward_a_mean_us\"") != std::string::npos);
            CHECK(s.find("\"concurrent_throughput_fps\"") != std::string::npos);
        }
    }

    std::printf("== result: assertions=%d passed=%d failed=%d ==\n", g_assert, g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
