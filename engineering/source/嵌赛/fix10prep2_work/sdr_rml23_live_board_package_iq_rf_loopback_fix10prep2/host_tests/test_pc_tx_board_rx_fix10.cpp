// test_pc_tx_board_rx_fix10.cpp -- fix10prep2 board-side state machine host test: the
// strict per-sample control-channel protocol (HELLO -> HELLO_ACK -> PREPARE ->
// PREPARED -> START -> READY -> CAPTURED -> STOPPED) driven over a REAL 127.0.0.1 TCP
// loopback, plus the CFO capture-range boundaries (task book §7 / §8).
//
// A forked child plays the PC-side server (mirroring host_tools/fix10_tx_protocol.py)
// while the parent plays the board-side client (the transfer header's send_* / recv_*).
// Every rejection is fail-closed; the board NEVER transmits and the PC NEVER receives.
//
// iCraft-free and libiio-free.

#include "../board_package/iq_pc_tx_board_rx_transfer_fix10.hpp"
#include "../board_package/iq_dual_sdr_coarse_cfo_recovery.hpp"
#include "../board_package/iq_dual_sdr_transfer_fix10.hpp"
#include "../sdr_adapter/pluto_dual_air_link.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

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
using iqpctbrx::TcpControlClient;
using iqpctbrx::SessionIdentity;
using iqpctbrx::SampleIdentity;
using iqpctbrx::HelloAckInfo;
using iqpctbrx::PreparedInfo;
using iqpctbrx::ReadyInfo;
using iqpctbrx::StoppedInfo;
using iqpctbrx::TxBurstBuild;
using iqpctbrx::build_tx_burst_from_frozen;
using iqpctbrx::check_readiness_provenance;
using iqpctbrx::send_hello;
using iqpctbrx::recv_hello_ack;
using iqpctbrx::send_prepare;
using iqpctbrx::recv_prepared;
using iqpctbrx::send_start;
using iqpctbrx::recv_ready;
using iqpctbrx::send_captured;
using iqpctbrx::recv_stopped;
using iqpctbrx::send_abort;
using iqpctbrx::common_fields;

// ---- raw frame helpers (mirror TcpControlClient wire format, PC server side) ----

#if defined(__unix__) || defined(__APPLE__)
bool raw_write_all(int fd, const char* p, std::size_t n) {
    std::size_t off = 0;
    while (off < n) {
#ifdef MSG_NOSIGNAL
        const int fl = MSG_NOSIGNAL;
#else
        const int fl = 0;
#endif
        const ssize_t w = ::send(fd, p + off, n - off, fl);
        if (w > 0) { off += static_cast<std::size_t>(w); continue; }
        if (w < 0 && errno == EINTR) continue;
        return false;
    }
    return true;
}

bool raw_wait_readable(int fd, int timeout_ms) {
    struct pollfd p;
    p.fd = fd; p.events = POLLIN; p.revents = 0;
    int rc;
    do { rc = ::poll(&p, 1, timeout_ms); } while (rc < 0 && errno == EINTR);
    return rc > 0 && (p.revents & POLLIN) != 0;
}

bool raw_read_exact(int fd, char* p, std::size_t n, int timeout_ms) {
    std::size_t off = 0;
    while (off < n) {
        if (!raw_wait_readable(fd, timeout_ms)) return false;
        const ssize_t r = ::recv(fd, p + off, n - off, 0);
        if (r > 0) { off += static_cast<std::size_t>(r); continue; }
        if (r < 0 && errno == EINTR) continue;
        return false;
    }
    return true;
}

std::string frame(const std::string& json) {
    const std::uint32_t len = static_cast<std::uint32_t>(json.size());
    std::string f;
    f.reserve(4 + json.size());
    f.push_back(static_cast<char>((len >> 24) & 0xFF));
    f.push_back(static_cast<char>((len >> 16) & 0xFF));
    f.push_back(static_cast<char>((len >> 8) & 0xFF));
    f.push_back(static_cast<char>(len & 0xFF));
    f += json;
    return f;
}

bool raw_send(int fd, const std::string& json) {
    const std::string f = frame(json);
    return raw_write_all(fd, f.data(), f.size());
}

bool raw_send_fragmented(int fd, const std::string& json, std::size_t chunk) {
    const std::string f = frame(json);
    std::size_t off = 0;
    while (off < f.size()) {
        const std::size_t n = std::min(chunk, f.size() - off);
        if (!raw_write_all(fd, f.data() + off, n)) return false;
        off += n;
    }
    return true;
}

bool raw_send_two(int fd, const std::string& a, const std::string& b) {
    const std::string fa = frame(a);
    const std::string fb = frame(b);
    std::string both = fa;
    both += fb;
    return raw_write_all(fd, both.data(), both.size());
}

bool raw_recv(int fd, std::string& json, int timeout_ms = 5000) {
    char hdr[4];
    if (!raw_read_exact(fd, hdr, 4, timeout_ms)) return false;
    const std::uint32_t len =
        (static_cast<std::uint32_t>(static_cast<unsigned char>(hdr[0])) << 24) |
        (static_cast<std::uint32_t>(static_cast<unsigned char>(hdr[1])) << 16) |
        (static_cast<std::uint32_t>(static_cast<unsigned char>(hdr[2])) << 8) |
        (static_cast<std::uint32_t>(static_cast<unsigned char>(hdr[3])));
    if (len > iqpctbrx::kMaxMessageBytes) return false;
    std::string buf(static_cast<std::size_t>(len), '\0');
    if (len != 0 && !raw_read_exact(fd, &buf[0], static_cast<std::size_t>(len), timeout_ms))
        return false;
    json = std::move(buf);
    return true;
}

struct ForkedServer {
    pid_t pid = -1;
    std::uint16_t port = 0;
};

using Handler = std::function<void(int)>;

ForkedServer fork_server(Handler handler) {
    ForkedServer s;
    const int ls = ::socket(AF_INET, SOCK_STREAM, 0);
    if (ls < 0) return s;
    int one = 1;
    ::setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    struct sockaddr_in addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = 0;
    if (::bind(ls, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) < 0) {
        ::close(ls); return s;
    }
    if (::listen(ls, 1) < 0) { ::close(ls); return s; }
    struct sockaddr_in got;
    socklen_t glen = sizeof(got);
    ::getsockname(ls, reinterpret_cast<struct sockaddr*>(&got), &glen);
    s.port = ntohs(got.sin_port);
    const pid_t pid = ::fork();
    if (pid == 0) {
        const int cfd = ::accept(ls, nullptr, nullptr);
        if (cfd >= 0) { handler(cfd); ::close(cfd); }
        ::close(ls);
        ::_exit(0);
    }
    ::close(ls);
    s.pid = pid;
    return s;
}
#endif  // __unix__

// ---- PC-side response builders (mirror host_tools/fix10_tx_protocol.py) -------

std::string hello_ack_json(const SessionIdentity& s, const HelloAckInfo& a) {
    Json m = common_fields("HELLO_ACK", s);
    m.object.emplace_back("tx_serial", iqpctbrx::str(a.tx_serial));
    m.object.emplace_back("tx_uri", iqpctbrx::str(a.tx_uri));
    m.object.emplace_back("tx_atten_db", iqpctbrx::num(a.tx_atten_db));
    m.object.emplace_back("configuration_verified", iqpctbrx::boolean(a.configuration_verified));
    return json_dump(m);
}

std::string prepared_json(const SessionIdentity& s, const SampleIdentity& smp,
                          const PreparedInfo& p, bool cfg) {
    Json m = common_fields("PREPARED", s);
    m.object.emplace_back("source_index", iqpctbrx::num(static_cast<double>(smp.source_index)));
    m.object.emplace_back("file_name", iqpctbrx::str(smp.file_name));
    m.object.emplace_back("payload_sha_pre", iqpctbrx::str(p.payload_sha_pre));
    m.object.emplace_back("payload_sha_post", iqpctbrx::str(p.payload_sha_post));
    m.object.emplace_back("burst_sha", iqpctbrx::str(p.burst_sha));
    m.object.emplace_back("tx_scale", iqpctbrx::num(p.tx_scale));
    m.object.emplace_back("configuration_verified", iqpctbrx::boolean(cfg));
    return json_dump(m);
}

std::string ready_json(const SessionIdentity& s, const SampleIdentity& smp,
                       const ReadyInfo& r) {
    Json m = common_fields("READY", s);
    m.object.emplace_back("source_index", iqpctbrx::num(static_cast<double>(smp.source_index)));
    m.object.emplace_back("file_name", iqpctbrx::str(smp.file_name));
    m.object.emplace_back("payload_sha_pre", iqpctbrx::str(r.payload_sha_pre));
    m.object.emplace_back("payload_sha_post", iqpctbrx::str(r.payload_sha_post));
    m.object.emplace_back("burst_sha", iqpctbrx::str(r.burst_sha));
    m.object.emplace_back("tx_scale", iqpctbrx::num(r.tx_scale));
    m.object.emplace_back("sample_rate_readback", iqpctbrx::num(static_cast<double>(r.sample_rate_readback)));
    m.object.emplace_back("tx_lo_readback", iqpctbrx::num(static_cast<double>(r.tx_lo_readback)));
    m.object.emplace_back("tx_bw_readback", iqpctbrx::num(static_cast<double>(r.tx_bw_readback)));
    m.object.emplace_back("tx_atten_readback", iqpctbrx::num(r.tx_atten_readback));
    m.object.emplace_back("tx_running", iqpctbrx::boolean(r.tx_running));
    return json_dump(m);
}

std::string stopped_json(const SessionIdentity& s, bool tx_restore_ok) {
    Json m = common_fields("STOPPED", s);
    m.object.emplace_back("tx_restore_ok", iqpctbrx::boolean(tx_restore_ok));
    return json_dump(m);
}

// ---- shared fixtures ----------------------------------------------------------

SessionIdentity make_session() {
    SessionIdentity s;
    s.session_id = "sid-fix10prep2";
    s.run_nonce = "nonce-0001";
    s.manifest_sha256 = std::string(64, 'e');
    s.input_kind = "radioml-d2-2p56m";
    s.sample_rate = 2560000ULL;
    s.center_hz = 2400000000ULL;
    s.target_rms = 2048.0;
    return s;
}

HelloAckInfo make_ack() {
    HelloAckInfo a;
    a.tx_serial = "1044734a9a920006000f00ff27c215f9";   // arbitrary placeholder serial
    a.tx_uri = "ip:192.168.2.1";
    a.tx_atten_db = -40.0;
    a.configuration_verified = true;
    return a;
}

void fill_prepared(const TxBurstBuild& e, PreparedInfo* p) {
    p->payload_sha_pre = e.payload_sha_pre;
    p->payload_sha_post = e.payload_sha_post;
    p->burst_sha = e.burst_sha;
    p->tx_scale = e.tx_scale;
}

void fill_ready(const TxBurstBuild& e, ReadyInfo* r) {
    r->payload_sha_pre = e.payload_sha_pre;
    r->payload_sha_post = e.payload_sha_post;
    r->burst_sha = e.burst_sha;
    r->tx_scale = e.tx_scale;
    r->sample_rate_readback = 2560000;
    r->tx_lo_readback = 2400000000;
    r->tx_bw_readback = 18000000;
    r->tx_atten_readback = -40.0;
    r->tx_running = true;
}

// ---- the board-side client helper (connects, returns a fresh TcpControlClient) ---

#if defined(__unix__) || defined(__APPLE__)
bool connect_client(TcpControlClient& c, std::uint16_t port, std::string* err) {
    c.host = "127.0.0.1";
    c.port = port;
    return c.connect(err);
}
#endif

// ---- HELLO/ACK handshake ------------------------------------------------------

#if defined(__unix__) || defined(__APPLE__)
void test_handshake_happy() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j;
        raw_recv(cfd, j);
        raw_send(cfd, hello_ack_json(sess, ack_want));
    });

    TcpControlClient c;
    std::string err;
    check(connect_client(c, srv.port, &err), "sm: connect (" + err + ")");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "sm: send HELLO (" + err + ")");
    check(recv_hello_ack(c, sess, ack, &err), "sm: recv HELLO_ACK (" + err + ")");
    check(ack.configuration_verified, "sm: HELLO_ACK configuration_verified");
    check(ack.tx_serial == ack_want.tx_serial, "sm: HELLO_ACK tx_serial");
    check(ack.tx_uri == ack_want.tx_uri, "sm: HELLO_ACK tx_uri");
    check(std::fabs(ack.tx_atten_db - ack_want.tx_atten_db) < 1e-9, "sm: HELLO_ACK tx_atten_db");
    c.close();
    int st = 0;
    ::waitpid(srv.pid, &st, 0);
}

// Each rejection case: the PC sends a message with ONE wrong field; the board's
// recv_* must fail closed.

void test_reject_protocol_version() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        Json m = json_parse(hello_ack_json(sess, ack_want)).value;
        m.object[1].second = iqpctbrx::num(999);   // protocol
        raw_send(cfd, json_dump(m));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "reject: send HELLO");
    check(!recv_hello_ack(c, sess, ack, &err), "reject: protocol version mismatch rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

void test_reject_session_id() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        Json m = json_parse(hello_ack_json(sess, ack_want)).value;
        m.object[2].second = iqpctbrx::str("evil-sid");   // session_id
        raw_send(cfd, json_dump(m));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "reject: send HELLO");
    check(!recv_hello_ack(c, sess, ack, &err), "reject: session_id mismatch rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

void test_reject_run_nonce() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        Json m = json_parse(hello_ack_json(sess, ack_want)).value;
        m.object[3].second = iqpctbrx::str("evil-nonce");   // run_nonce
        raw_send(cfd, json_dump(m));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "reject: send HELLO");
    check(!recv_hello_ack(c, sess, ack, &err), "reject: run_nonce mismatch rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

void test_reject_manifest() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        Json m = json_parse(hello_ack_json(sess, ack_want)).value;
        m.object[4].second = iqpctbrx::str(std::string(64, 'f'));   // manifest_sha256
        raw_send(cfd, json_dump(m));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "reject: send HELLO");
    check(!recv_hello_ack(c, sess, ack, &err), "reject: manifest mismatch rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

void test_reject_unknown_field() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        Json m = json_parse(hello_ack_json(sess, ack_want)).value;
        m.object.emplace_back("extra_field", iqpctbrx::num(1.0));   // unknown field
        raw_send(cfd, json_dump(m));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "reject: send HELLO");
    check(!recv_hello_ack(c, sess, ack, &err), "reject: unknown field rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

void test_reject_configuration_unverified() {
    const SessionIdentity sess = make_session();
    HelloAckInfo ack_want = make_ack();
    ack_want.configuration_verified = false;
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        raw_send(cfd, hello_ack_json(sess, ack_want));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "reject: send HELLO");
    check(!recv_hello_ack(c, sess, ack, &err), "reject: unverified configuration rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

// Full happy-path state machine + provenance over the wire.
void test_state_machine_happy(const std::string& path, std::uint64_t cc,
                              const std::string& sha) {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    const TxBurstBuild expected = build_tx_burst_from_frozen(path, cc, sha, 2048.0);
    SampleIdentity smp;
    smp.source_index = 3;
    smp.file_name = "payload.ci16";
    smp.payload_sha_pre = expected.payload_sha_pre;
    PreparedInfo prep_want; fill_prepared(expected, &prep_want);
    ReadyInfo ready_want; fill_ready(expected, &ready_want);

    ForkedServer srv = fork_server([&](int cfd) {
        std::string j;
        raw_recv(cfd, j);                                  // HELLO
        raw_send(cfd, hello_ack_json(sess, ack_want));     // HELLO_ACK
        raw_recv(cfd, j);                                  // PREPARE
        raw_send(cfd, prepared_json(sess, smp, prep_want, true));  // PREPARED
        raw_recv(cfd, j);                                  // START
        raw_send(cfd, ready_json(sess, smp, ready_want));  // READY
        raw_recv(cfd, j);                                  // CAPTURED
        raw_send(cfd, stopped_json(sess, true));           // STOPPED
    });

    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "sm: connect (" + err + ")");

    HelloAckInfo ack;
    check(send_hello(c, sess, &err) && recv_hello_ack(c, sess, ack, &err),
          "sm: HELLO/ACK (" + err + ")");

    PreparedInfo prep;
    check(send_prepare(c, sess, smp, &err), "sm: send PREPARE (" + err + ")");
    check(recv_prepared(c, sess, smp, prep, &err), "sm: recv PREPARED (" + err + ")");
    check(prep.payload_sha_post == expected.payload_sha_post, "sm: PREPARED payload_sha_post");
    check(prep.burst_sha == expected.burst_sha, "sm: PREPARED burst_sha");

    ReadyInfo ready;
    check(send_start(c, sess, smp, &err), "sm: send START (" + err + ")");
    check(recv_ready(c, sess, smp, ready, &err), "sm: recv READY (" + err + ")");
    check(ready.tx_running, "sm: READY tx_running");
    check(ready.sample_rate_readback == 2560000, "sm: READY sample_rate_readback");
    check(ready.tx_lo_readback == 2400000000, "sm: READY tx_lo_readback");
    check(ready.tx_bw_readback == 18000000, "sm: READY tx_bw_readback");

    const auto prov = check_readiness_provenance(expected, prep, ready, 1e-6);
    check(prov.ok, "sm: provenance ok (" + prov.report + ")");

    StoppedInfo stopped;
    check(send_captured(c, sess, smp, &err), "sm: send CAPTURED (" + err + ")");
    check(recv_stopped(c, sess, stopped, &err), "sm: recv STOPPED (" + err + ")");
    check(stopped.tx_restore_ok, "sm: STOPPED tx_restore_ok");

    c.close();
    int st = 0; ::waitpid(srv.pid, &st, 0);
}

// PREPARED carrying a payload_sha_pre that does not match the sample identity.
void test_reject_prepared_sha(const std::string& path, std::uint64_t cc,
                              const std::string& sha) {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    const TxBurstBuild expected = build_tx_burst_from_frozen(path, cc, sha, 2048.0);
    SampleIdentity smp;
    smp.source_index = 3;
    smp.file_name = "payload.ci16";
    smp.payload_sha_pre = expected.payload_sha_pre;
    PreparedInfo prep_bad; fill_prepared(expected, &prep_bad);
    prep_bad.payload_sha_pre = std::string(64, '7');   // wrong identity

    ForkedServer srv = fork_server([&](int cfd) {
        std::string j;
        raw_recv(cfd, j);
        raw_send(cfd, hello_ack_json(sess, ack_want));
        raw_recv(cfd, j);
        raw_send(cfd, prepared_json(sess, smp, prep_bad, true));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    PreparedInfo prep;
    check(send_hello(c, sess, &err) && recv_hello_ack(c, sess, ack, &err), "reject: hello");
    check(send_prepare(c, sess, smp, &err), "reject: send PREPARE");
    check(!recv_prepared(c, sess, smp, prep, &err), "reject: PREPARED payload_sha_pre mismatch rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

// PREPARED carrying configuration_verified == false must be rejected fail-closed: the PC
// declares its TX configuration is NOT verified, so the board must not proceed to send START.
void test_reject_prepared_unverified(const std::string& path, std::uint64_t cc,
                                     const std::string& sha) {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    const TxBurstBuild expected = build_tx_burst_from_frozen(path, cc, sha, 2048.0);
    SampleIdentity smp;
    smp.source_index = 3;
    smp.file_name = "payload.ci16";
    smp.payload_sha_pre = expected.payload_sha_pre;
    PreparedInfo prep_want; fill_prepared(expected, &prep_want);

    ForkedServer srv = fork_server([&](int cfd) {
        std::string j;
        raw_recv(cfd, j);
        raw_send(cfd, hello_ack_json(sess, ack_want));
        raw_recv(cfd, j);
        raw_send(cfd, prepared_json(sess, smp, prep_want, /*cfg=*/false));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack;
    PreparedInfo prep;
    check(send_hello(c, sess, &err) && recv_hello_ack(c, sess, ack, &err), "reject: hello");
    check(send_prepare(c, sess, smp, &err), "reject: send PREPARE");
    check(!recv_prepared(c, sess, smp, prep, &err),
          "reject: PREPARED configuration_verified=false rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

// READY with tx_running == false must be rejected (PC is not actually transmitting).
void test_reject_ready_not_running(const std::string& path, std::uint64_t cc,
                                   const std::string& sha) {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    const TxBurstBuild expected = build_tx_burst_from_frozen(path, cc, sha, 2048.0);
    SampleIdentity smp;
    smp.source_index = 3;
    smp.file_name = "payload.ci16";
    smp.payload_sha_pre = expected.payload_sha_pre;
    PreparedInfo prep_want; fill_prepared(expected, &prep_want);
    ReadyInfo ready_bad; fill_ready(expected, &ready_bad);
    ready_bad.tx_running = false;

    ForkedServer srv = fork_server([&](int cfd) {
        std::string j;
        raw_recv(cfd, j); raw_send(cfd, hello_ack_json(sess, ack_want));
        raw_recv(cfd, j); raw_send(cfd, prepared_json(sess, smp, prep_want, true));
        raw_recv(cfd, j); raw_send(cfd, ready_json(sess, smp, ready_bad));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "reject: connect");
    HelloAckInfo ack; PreparedInfo prep; ReadyInfo ready;
    check(send_hello(c, sess, &err) && recv_hello_ack(c, sess, ack, &err), "reject: hello");
    check(send_prepare(c, sess, smp, &err) && recv_prepared(c, sess, smp, prep, &err), "reject: prepared");
    check(send_start(c, sess, smp, &err), "reject: send START");
    check(!recv_ready(c, sess, smp, ready, &err), "reject: READY tx_running=false rejected");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

// Oversize outgoing message fails closed before hitting the wire.
void test_oversize_send() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        raw_send(cfd, hello_ack_json(sess, ack_want));
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "oversize: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err) && recv_hello_ack(c, sess, ack, &err), "oversize: hello");
    // Force the limit low and send a message that would exceed it.
    c.max_message_bytes = 32;
    check(!send_prepare(c, sess, SampleIdentity{1, "f", std::string(64, 'a')}, &err),
          "oversize: outgoing message over limit fail-closed");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

// A frame split across many tiny writes is reassembled by TcpControlClient.
void test_fragmented_frame() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        raw_send_fragmented(cfd, hello_ack_json(sess, ack_want), 3);   // 3-byte chunks
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "frag: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "frag: send HELLO");
    check(recv_hello_ack(c, sess, ack, &err), "frag: reassembled fragmented HELLO_ACK (" + err + ")");
    check(ack.tx_serial == ack_want.tx_serial, "frag: tx_serial intact");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}

// Two frames coalesced into one write are read one at a time.
void test_coalesced_frames() {
    const SessionIdentity sess = make_session();
    const HelloAckInfo ack_want = make_ack();
    ForkedServer srv = fork_server([&](int cfd) {
        std::string j; raw_recv(cfd, j);
        raw_send_two(cfd, hello_ack_json(sess, ack_want),
                     stopped_json(sess, true));   // one write, two frames
    });
    TcpControlClient c; std::string err;
    check(connect_client(c, srv.port, &err), "coalesce: connect");
    HelloAckInfo ack;
    check(send_hello(c, sess, &err), "coalesce: send HELLO");
    check(recv_hello_ack(c, sess, ack, &err), "coalesce: first frame (HELLO_ACK) (" + err + ")");
    StoppedInfo stopped;
    check(recv_stopped(c, sess, stopped, &err), "coalesce: second frame (STOPPED) (" + err + ")");
    check(stopped.tx_restore_ok, "coalesce: STOPPED intact");
    c.close(); int st = 0; ::waitpid(srv.pid, &st, 0);
}
#endif  // __unix__

// ---- CFO capture-range boundaries (task book §8) ------------------------------

struct Fixture {
    std::shared_ptr<pluto::FakeRfLink> link;
    pluto::FakeTxDevice tx;
    pluto::FakeRxDevice rx;
    Fixture() : link(std::make_shared<pluto::FakeRfLink>()), tx(link), rx(link) {
        const pluto::DataFormatInfo ident{16, 16, 0, true, true, false, 1};
        tx.tx_fmt_ = ident;
        rx.rx_fmt_ = ident;
        tx.open();
        rx.open();
        tx.set_sample_rate(2560000);
        rx.set_sample_rate(2560000);
    }
};

std::vector<std::int16_t> make_payload(std::size_t n_complex, std::uint32_t seed) {
    const std::size_t sps = 32;
    const double amp = 2048.0;
    std::vector<std::int16_t> iq(n_complex * 2);
    std::uint32_t s = seed;
    for (std::size_t m = 0; m < n_complex; m += sps) {
        s = s * 1664525u + 1013904223u;
        const int bi = ((s >> 16) & 1u) ? 1 : -1;
        s = s * 1664525u + 1013904223u;
        const int bq = ((s >> 16) & 1u) ? 1 : -1;
        const std::int16_t I = static_cast<std::int16_t>(std::lround(amp * bi));
        const std::int16_t Q = static_cast<std::int16_t>(std::lround(amp * bq));
        for (std::size_t j = 0; j < sps && m + j < n_complex; ++j) {
            iq[(m + j) * 2 + 0] = I;
            iq[(m + j) * 2 + 1] = Q;
        }
    }
    return iq;
}

void write_binary(const std::string& path, const std::vector<std::int16_t>& iq) {
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
}

double complex_corr(const std::vector<std::complex<double>>& rec,
                    const std::vector<std::int16_t>& orig) {
    std::complex<double> num(0.0, 0.0);
    double den_r = 0.0, den_o = 0.0;
    const std::size_t n = rec.size();
    for (std::size_t k = 0; k < n; ++k) {
        const std::complex<double> o(static_cast<double>(orig[2 * k]),
                                     static_cast<double>(orig[2 * k + 1]));
        num += rec[k] * std::conj(o);
        den_r += rec[k].real() * rec[k].real() + rec[k].imag() * rec[k].imag();
        den_o += o.real() * o.real() + o.imag() * o.imag();
    }
    return den_r > 0.0 && den_o > 0.0 ? std::abs(num) / std::sqrt(den_r * den_o) : 0.0;
}

iqrfrec::EstimateConfig runner_cfg() {
    iqrfrec::EstimateConfig c;
    c.min_corr = 0.9;
    c.max_residual = iqrfrec::kPayloadTrainingResidualMax;   // 0.10
    c.max_cfo_hz = 30.0;
    c.max_sro_ppm = 30.0;
    c.search_limit = 0;
    return c;
}

struct RunOutcome {
    bool threw = false;
    std::string err;
    iqdual_run_fix10::DualSdrTransferResult r;
};

RunOutcome run_transfer(pluto::FakeTxDevice& tx, pluto::FakeRxDevice& rx,
                        const std::string& path, std::uint64_t complex_count,
                        const std::string& expect_sha, double cfo_hz) {
    RunOutcome o;
    try {
        o.r = iqdual_run_fix10::transfer_one_file_dual_sdr_fix10(
            tx, rx, path, complex_count, expect_sha, 2400000000ULL, 10.0, -40.0,
            iqdual_run_fix10::kFix10DelayMarginDefault,
            iqrfloop_run::kRfNoiseComplexDefault, nullptr, 0.0);
    } catch (const std::exception& e) {
        o.threw = true;
        o.err = e.what();
    }
    (void)cfo_hz;
    return o;
}

// In-range: 200 Hz is inside the +/-625 Hz unambiguous coarse range.
void test_cfo_in_range(const std::string& path, std::uint64_t cc,
                       const std::string& sha, const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->cfo_hz = 200.0;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, 200.0);
    check(!o.threw, "cfo-in: transfer succeeds (" + o.err + ")");
    if (o.threw) return;
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(o.r.rx);
    const iqdual23fix10::CoarseCfoRecovery cfo =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, runner_cfg(), o.r.tx_scale);
    check(cfo.rec.valid, "cfo-in: recovery valid");
    // The coarse CFO estimator (LS-gain phase diff over the two 1024-sample blocks)
    // carries a ~2.85% systematic underestimate: a 200 Hz offset measures ~194.3 Hz.
    // That residual is well inside the fine-CFO gate (max_cfo_hz=30), so recovery is
    // still valid; assert the in-range case loosely, and the +/-625 Hz unambiguous
    // bound separately below.
    check(std::fabs(cfo.coarse_cfo_hz - 200.0) <= 15.0,
          "cfo-in: coarse_cfo_hz ~200 Hz (got " + std::to_string(cfo.coarse_cfo_hz) + ")");
    check(std::fabs(cfo.coarse_cfo_hz) <= iqpctbrx::coarse_cfo_unambiguous_range_hz(),
          "cfo-in: coarse_cfo_hz within unambiguous range");
    check(complex_corr(cfo.payload, payload) >= 0.99,
          "cfo-in: recovered payload corr >= 0.99");
}

// Out-of-range: 700 Hz exceeds +/-625 Hz, so the coarse CFO ALIASES (measures ~-550)
// and the fine residual (1250 Hz) is unrecoverable -> fail-closed (rec.valid == false).
void test_cfo_out_of_range(const std::string& path, std::uint64_t cc,
                           const std::string& sha, const std::vector<std::int16_t>& payload) {
    Fixture fx;
    fx.link->cfo_hz = 700.0;
    RunOutcome o = run_transfer(fx.tx, fx.rx, path, cc, sha, 700.0);
    check(!o.threw, "cfo-out: transfer succeeds (" + o.err + ")");
    if (o.threw) return;
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(o.r.rx);
    const iqdual23fix10::CoarseCfoRecovery cfo =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, runner_cfg(), o.r.tx_scale);
    check(std::fabs(cfo.coarse_cfo_hz - 700.0) > 100.0,
          "cfo-out: 700 Hz aliases in coarse estimate (got " +
              std::to_string(cfo.coarse_cfo_hz) + ")");
    bool failed_closed = !cfo.rec.valid;
    if (cfo.rec.valid && !cfo.payload.empty())
        failed_closed = failed_closed || (complex_corr(cfo.payload, payload) < 0.90);
    check(failed_closed, "cfo-out: 700 Hz (>625 unambiguous) fails closed "
                         "(valid=" + std::string(cfo.rec.valid ? "true" : "false") + ")");
}

}  // namespace

int main() {
    std::printf("test_pc_tx_board_rx_fix10\n");

#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = "/tmp/fix10_pctrx_" + std::to_string(::getpid());
    ::mkdir(dir.c_str(), 0700);
    const std::uint64_t cc = iqrftrain::kPayloadComplex;
    const std::vector<std::int16_t> payload = make_payload(cc, 0x9E3779B9u);
    const std::string path = dir + "/payload.ci16";
    write_binary(path, payload);
    const std::string sha = sdr::Sha256::hex(payload.data(),
                                             payload.size() * sizeof(std::int16_t));

    test_handshake_happy();
    test_reject_protocol_version();
    test_reject_session_id();
    test_reject_run_nonce();
    test_reject_manifest();
    test_reject_unknown_field();
    test_reject_configuration_unverified();
    test_state_machine_happy(path, cc, sha);
    test_reject_prepared_sha(path, cc, sha);
    test_reject_prepared_unverified(path, cc, sha);
    test_reject_ready_not_running(path, cc, sha);
    test_oversize_send();
    test_fragmented_frame();
    test_coalesced_frames();

    test_cfo_in_range(path, cc, sha, payload);
    test_cfo_out_of_range(path, cc, sha, payload);

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    std::printf("  (TCP loopback + CFO tests are POSIX-only; skipped on this platform)\n");
#endif

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
