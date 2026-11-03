// test_pc_tx_protocol_fix10.cpp -- fix10prep2 protocol-layer host test: the frozen
// wire-protocol constants, the strict JSON value/parser/serializer, the exact-field
// / common-field / SHA-64 validation helpers, the --tx-control URL parser, and the
// CFO capture-range boundaries (task book §7 / §8).  iCraft-free and libiio-free.
//
// This is PURE logic (no socket): the full state machine over a real 127.0.0.1 link
// lives in test_pc_tx_board_rx_fix10.cpp, and the byte-identical burst provenance in
// test_pc_tx_provenance_fix10.cpp.

#include "../board_package/iq_pc_tx_board_rx_transfer_fix10.hpp"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

using iqpctbrx::Json;
using iqpctbrx::json_parse;
using iqpctbrx::json_dump;
using iqpctbrx::validate_exact_fields;
using iqpctbrx::validate_common;
using iqpctbrx::valid_sha64;
using iqpctbrx::parse_tx_control_url;
using iqpctbrx::SessionIdentity;

// ---- wire-protocol hard limits (task book §7) --------------------------------

void test_protocol_constants() {
    check(iqpctbrx::kProtocolVersion == 1, "const: protocol version == 1");
    check(iqpctbrx::kDefaultPort == 39010, "const: default port == 39010");
    check(iqpctbrx::kMaxMessageBytes == (1u << 20), "const: max message bytes == 1 MiB");
    check(iqpctbrx::kWatchdogTimeoutMs > 0, "const: watchdog timeout > 0");
    check(iqpctbrx::kWatchdogTimeoutMs <= 2000, "const: watchdog timeout <= 2000 ms");
    check(iqpctbrx::kDefaultConnectTimeoutMs > 0, "const: connect timeout > 0");
    check(iqpctbrx::kDefaultConnectTimeoutMs <= 2000, "const: connect timeout <= 2000 ms");
    check(iqpctbrx::kDefaultMessageTimeoutMs > 0, "const: message timeout > 0");
    check(iqpctbrx::kDefaultMessageTimeoutMs <= 2000, "const: message timeout <= 2000 ms");
}

// ---- CFO capture-range boundaries (task book §8) ------------------------------

void test_cfo_range_constants() {
    const double unambiguous = iqpctbrx::coarse_cfo_unambiguous_range_hz();
    const double lo = iqpctbrx::coarse_cfo_search_min_hz();
    const double hi = iqpctbrx::coarse_cfo_search_max_hz();
    const double fine = iqpctbrx::fine_cfo_range_hz();
    // fs=2.56e6 / (2*kPayloadTrainingOffset=2048) == exactly 625.0 Hz.
    check(std::fabs(unambiguous - 625.0) < 1e-9, "cfo: unambiguous coarse range == 625.0 Hz");
    check(std::fabs(lo + 625.0) < 1e-9, "cfo: search min == -625.0 Hz");
    check(std::fabs(hi - 625.0) < 1e-9, "cfo: search max == +625.0 Hz");
    check(lo < hi, "cfo: search min < search max");
    check(lo == -hi, "cfo: search range symmetric");
    // fs=2.56e6 / (2*kTailStart=58880) == 21.7391... Hz.
    check(fine > 21.7 && fine < 21.8, "cfo: fine range ~21.74 Hz (got " +
        std::to_string(fine) + ")");
    check(fine < unambiguous, "cfo: fine range < coarse range");
}

// ---- JSON value / parser / serializer -----------------------------------------

void test_json_roundtrip() {
    Json obj = iqpctbrx::obj({{"s", iqpctbrx::str("hi")},
                              {"n", iqpctbrx::num(3.5)},
                              {"b", iqpctbrx::boolean(true)},
                              {"z", iqpctbrx::num(0.0)}});
    const std::string text = json_dump(obj);
    const auto pr = json_parse(text);
    check(pr.ok, "json: round-trip parses (" + pr.error + ")");
    if (!pr.ok) return;
    check(pr.value.is_object(), "json: round-trip is object");
    check(pr.value.get("s")->as_string() == "hi", "json: string field round-trips");
    check(std::fabs(pr.value.get("n")->as_number() - 3.5) < 1e-12,
          "json: number field round-trips");
    check(pr.value.get("b")->as_bool(), "json: bool field round-trips");
    check(pr.value.get("z")->as_int() == 0, "json: integer zero round-trips");
}

void test_json_reject_malformed() {
    const char* bad[] = {"", "   ", "{", "{\"a\":}", "{\"a\":1", "[1,2",
                         "{\"a\":1}x", "{\"a\":01}", "{\"a\":\"unterminated}",
                         "tru", "nul"};
    bool all_rejected = true;
    for (const char* s : bad) {
        const auto pr = json_parse(s);
        if (pr.ok) { all_rejected = false; std::printf("    (accepted: '%s')\n", s); }
    }
    check(all_rejected, "json: malformed inputs all rejected");
}

void test_json_escape_roundtrip() {
    Json obj = iqpctbrx::obj({{"x", iqpctbrx::str("a\"b\\c\nd\te")}});
    const auto pr = json_parse(json_dump(obj));
    check(pr.ok && pr.value.get("x")->as_string() == "a\"b\\c\nd\te",
          "json: escapes round-trip");
}

// ---- exact-field validation ---------------------------------------------------

void test_validate_exact_fields() {
    Json good = iqpctbrx::obj({{"a", iqpctbrx::num(1)}, {"b", iqpctbrx::str("x")}});
    std::string err;
    check(validate_exact_fields(good, {"a", "b"}, &err), "exact: matching fields ok");

    Json missing = iqpctbrx::obj({{"a", iqpctbrx::num(1)}});
    check(!validate_exact_fields(missing, {"a", "b"}, &err), "exact: missing field rejected");

    Json extra = iqpctbrx::obj({{"a", iqpctbrx::num(1)}, {"b", iqpctbrx::str("x")},
                                {"c", iqpctbrx::num(2)}});
    check(!validate_exact_fields(extra, {"a", "b"}, &err), "exact: unknown field rejected");

    Json nonobj = iqpctbrx::num(5);
    check(!validate_exact_fields(nonobj, {"a"}, &err), "exact: non-object rejected");
}

// ---- common-field validation ---------------------------------------------------

void test_validate_common() {
    SessionIdentity s{"sid-1", "nonce-1", std::string(64, 'a'), "radioml-d2-2p56m",
                      2560000ULL, 2400000000ULL, 2048.0};
    Json good = iqpctbrx::common_fields("HELLO", s);
    std::string err;
    check(validate_common(good, "HELLO", s, &err), "common: matching fields ok");

    // wrong type
    Json wt = good;
    wt.object[0].second = iqpctbrx::str("START");
    check(!validate_common(wt, "HELLO", s, &err), "common: wrong type rejected");

    // protocol version mismatch
    Json pv = good;
    pv.object[1].second = iqpctbrx::num(999);
    check(!validate_common(pv, "HELLO", s, &err), "common: protocol version mismatch rejected");

    // session_id mismatch
    Json si = good;
    si.object[2].second = iqpctbrx::str("other-sid");
    check(!validate_common(si, "HELLO", s, &err), "common: session_id mismatch rejected");

    // run_nonce mismatch
    Json rn = good;
    rn.object[3].second = iqpctbrx::str("other-nonce");
    check(!validate_common(rn, "HELLO", s, &err), "common: run_nonce mismatch rejected");

    // manifest_sha256 mismatch
    Json ms = good;
    ms.object[4].second = iqpctbrx::str(std::string(64, 'b'));
    check(!validate_common(ms, "HELLO", s, &err), "common: manifest mismatch rejected");
}

// ---- SHA-64 validator ----------------------------------------------------------

void test_valid_sha64() {
    check(valid_sha64(std::string(64, 'a')), "sha64: 64 lowercase hex ok");
    check(valid_sha64(std::string(64, '0')), "sha64: 64 zeros ok");
    check(!valid_sha64(std::string(63, 'a')), "sha64: 63 chars rejected");
    check(!valid_sha64(std::string(65, 'a')), "sha64: 65 chars rejected");
    check(!valid_sha64(std::string(64, 'A')), "sha64: uppercase rejected");
    check(!valid_sha64(std::string(64, 'g')), "sha64: non-hex rejected");
}

// ---- --tx-control URL parser ---------------------------------------------------

void test_parse_tx_control_url() {
    std::string host;
    std::uint16_t port = 0;
    std::string err;
    check(parse_tx_control_url("tcp://192.168.2.1:39010", host, port, &err) &&
          host == "192.168.2.1" && port == 39010,
          "url: tcp://host:port parses");
    check(parse_tx_control_url("127.0.0.1:12345", host, port, &err) &&
          host == "127.0.0.1" && port == 12345,
          "url: bare host:port parses");
    check(!parse_tx_control_url("", host, port, &err), "url: empty rejected");
    check(!parse_tx_control_url("nohost", host, port, &err), "url: no colon rejected");
    check(!parse_tx_control_url(":39010", host, port, &err), "url: empty host rejected");
    check(!parse_tx_control_url("host:", host, port, &err), "url: empty port rejected");
    check(!parse_tx_control_url("host:0", host, port, &err), "url: port 0 rejected");
    check(!parse_tx_control_url("host:65536", host, port, &err), "url: port >65535 rejected");
    check(!parse_tx_control_url("host:abc", host, port, &err), "url: non-numeric port rejected");
}

}  // namespace

int main() {
    std::printf("test_pc_tx_protocol_fix10\n");

    test_protocol_constants();
    test_cfo_range_constants();
    test_json_roundtrip();
    test_json_reject_malformed();
    test_json_escape_roundtrip();
    test_validate_exact_fields();
    test_validate_common();
    test_valid_sha64();
    test_parse_tx_control_url();

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
