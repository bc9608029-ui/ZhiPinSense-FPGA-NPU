// test_pc_tx_provenance_fix10.cpp -- fix10prep2 provenance host test: the board's
// INDEPENDENT TX-burst rebuild (build_tx_burst_from_frozen) is byte-identical across
// runs, and check_readiness_provenance accepts an exact PC match and fail-closes on
// any field mismatch or clip.  This is the proof that the PC (via build_burst_cli,
// the same iq_rf_training_frame.hpp) and the board derive the same payload_sha_pre /
// payload_sha_post / burst_sha / tx_scale from the same frozen ci16 + --rf-tx-target-rms.
//
// iCraft-free and libiio-free.

#include "../board_package/iq_pc_tx_board_rx_transfer_fix10.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

using iqpctbrx::TxBurstBuild;
using iqpctbrx::build_tx_burst_from_frozen;
using iqpctbrx::check_readiness_provenance;
using iqpctbrx::PreparedInfo;
using iqpctbrx::ReadyInfo;

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

// The full frozen payload is kPayloadComplex (53760) complex samples.
void test_build_deterministic(const std::string& path, const std::string& sha,
                              std::uint64_t cc) {
    const double target_rms = 2048.0;
    const TxBurstBuild a = build_tx_burst_from_frozen(path, cc, sha, target_rms);
    const TxBurstBuild b = build_tx_burst_from_frozen(path, cc, sha, target_rms);

    check(a.payload_sha_pre == sha, "build: payload_sha_pre == frozen ci16 SHA");
    check(iqpctbrx::valid_sha64(a.payload_sha_pre), "build: payload_sha_pre is 64-hex");
    check(iqpctbrx::valid_sha64(a.payload_sha_post), "build: payload_sha_post is 64-hex");
    check(iqpctbrx::valid_sha64(a.burst_sha), "build: burst_sha is 64-hex");
    check(!a.payload.empty(), "build: payload non-empty");
    check(!a.burst.empty(), "build: burst non-empty");
    check(a.burst.size() == iqrftrain::kTotalBurstComplex * 2,
          "build: burst size == kTotalBurstComplex*2 int16");
    check(a.tx_scale > 0.0, "build: tx_scale > 0");
    check(!a.clip_pre, "build: no pre-scale clip at amp 2048");
    check(!a.clip_post, "build: no post-scale clip at target_rms 2048");

    check(a.payload_sha_pre == b.payload_sha_pre, "build: pre SHA deterministic");
    check(a.payload_sha_post == b.payload_sha_post, "build: post SHA deterministic");
    check(a.burst_sha == b.burst_sha, "build: burst SHA deterministic");
    check(a.tx_scale == b.tx_scale, "build: tx_scale deterministic");
    check(a.payload == b.payload, "build: payload bytes deterministic");
    check(a.burst == b.burst, "build: burst bytes deterministic");
}

void test_build_fail_closed(const std::string& path, const std::string& sha,
                            std::uint64_t cc) {
    // Wrong SHA must throw.
    bool threw = false;
    try { build_tx_burst_from_frozen(path, cc, std::string(64, '0'), 2048.0); }
    catch (const std::exception&) { threw = true; }
    check(threw, "build: wrong expect_sha throws fail-closed");

    // Wrong complex count must throw.
    threw = false;
    try { build_tx_burst_from_frozen(path, cc + 1, sha, 2048.0); }
    catch (const std::exception&) { threw = true; }
    check(threw, "build: wrong complex_count throws fail-closed");
}

void test_provenance_match(const std::string& path, const std::string& sha,
                           std::uint64_t cc) {
    const TxBurstBuild expected = build_tx_burst_from_frozen(path, cc, sha, 2048.0);
    PreparedInfo prepared;
    prepared.payload_sha_pre = expected.payload_sha_pre;
    prepared.payload_sha_post = expected.payload_sha_post;
    prepared.burst_sha = expected.burst_sha;
    prepared.tx_scale = expected.tx_scale;
    ReadyInfo ready;
    ready.payload_sha_pre = expected.payload_sha_pre;
    ready.payload_sha_post = expected.payload_sha_post;
    ready.burst_sha = expected.burst_sha;
    ready.tx_scale = expected.tx_scale;
    ready.sample_rate_readback = 2560000;
    ready.tx_lo_readback = 2400000000;
    ready.tx_bw_readback = 18000000;
    ready.tx_atten_readback = -40.0;
    ready.tx_running = true;

    const auto ok = check_readiness_provenance(expected, prepared, ready, 1e-6);
    check(ok.ok, "provenance: exact match ok (" + ok.report + ")");
}

void test_provenance_mismatch(const std::string& path, const std::string& sha,
                              std::uint64_t cc) {
    const TxBurstBuild expected = build_tx_burst_from_frozen(path, cc, sha, 2048.0);

    auto mk = [&](PreparedInfo* p, ReadyInfo* r) {
        p->payload_sha_pre = expected.payload_sha_pre;
        p->payload_sha_post = expected.payload_sha_post;
        p->burst_sha = expected.burst_sha;
        p->tx_scale = expected.tx_scale;
        r->payload_sha_pre = expected.payload_sha_pre;
        r->payload_sha_post = expected.payload_sha_post;
        r->burst_sha = expected.burst_sha;
        r->tx_scale = expected.tx_scale;
        r->tx_running = true;
    };

    PreparedInfo p; ReadyInfo r;
    mk(&p, &r);
    r.payload_sha_post = std::string(64, '1');
    check(!check_readiness_provenance(expected, p, r, 1e-6).ok,
          "provenance: READY payload_sha_post mismatch rejected");

    mk(&p, &r);
    r.burst_sha = std::string(64, '2');
    check(!check_readiness_provenance(expected, p, r, 1e-6).ok,
          "provenance: READY burst_sha mismatch rejected");

    mk(&p, &r);
    r.tx_scale = expected.tx_scale + 0.01;
    check(!check_readiness_provenance(expected, p, r, 1e-6).ok,
          "provenance: READY tx_scale mismatch rejected");

    mk(&p, &r);
    p.burst_sha = std::string(64, '3');
    check(!check_readiness_provenance(expected, p, r, 1e-6).ok,
          "provenance: PREPARED burst_sha mismatch rejected");
}

// A target_rms that forces post-scale clipping makes the provenance check fail-closed.
void test_provenance_clip(const std::string& path, const std::string& sha,
                          std::uint64_t cc) {
    const TxBurstBuild expected =
        build_tx_burst_from_frozen(path, cc, sha, 3.0e9);   // absurd target_rms -> clip
    check(expected.clip_post, "provenance: absurd target_rms clips post-scale");
    PreparedInfo p; ReadyInfo r;
    p.payload_sha_pre = expected.payload_sha_pre;
    p.payload_sha_post = expected.payload_sha_post;
    p.burst_sha = expected.burst_sha;
    p.tx_scale = expected.tx_scale;
    r.payload_sha_pre = expected.payload_sha_pre;
    r.payload_sha_post = expected.payload_sha_post;
    r.burst_sha = expected.burst_sha;
    r.tx_scale = expected.tx_scale;
    r.tx_running = true;
    const auto res = check_readiness_provenance(expected, p, r, 1e-6);
    check(!res.ok, "provenance: clip_post fail-closes (" + res.report + ")");
}

}  // namespace

int main() {
    std::printf("test_pc_tx_provenance_fix10\n");

#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = "/tmp/fix10_pctrx_prov_" + std::to_string(::getpid());
    ::mkdir(dir.c_str(), 0700);
#else
    const std::string dir = ".";
#endif
    const std::uint64_t cc = iqrftrain::kPayloadComplex;
    const std::vector<std::int16_t> payload = make_payload(cc, 0x9E3779B9u);
    const std::string path = dir + "/payload.ci16";
    write_binary(path, payload);
    const std::string sha = sdr::Sha256::hex(payload.data(),
                                             payload.size() * sizeof(std::int16_t));

    test_build_deterministic(path, sha, cc);
    test_build_fail_closed(path, sha, cc);
    test_provenance_match(path, sha, cc);
    test_provenance_mismatch(path, sha, cc);
    test_provenance_clip(path, sha, cc);

#if defined(__unix__) || defined(__APPLE__)
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#endif

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
