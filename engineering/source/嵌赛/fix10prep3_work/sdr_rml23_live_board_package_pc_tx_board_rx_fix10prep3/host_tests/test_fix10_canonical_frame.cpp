// test_fix10_canonical_frame.cpp -- fix10prep3 Batch 2 canonical training-frame
// host test.  Proves that fix10canonical::buildTxBurstFromFrozen assembles the full
// burst from the aarch64-FROZEN training components, so the canonical full burst SHA
// equals the ARM-authoritative full burst SHA for the two fixed dual-SDR samples
// (BPSK source_index=405512 -> 2e965828…, 4ASK source_index=192513 -> 7e8126fb…),
// while payload_sha_pre / payload_sha_post / tx_scale are unchanged from fix10prep2.
//
// iCraft-free and libiio-free.

#include "../board_package/iq_fix10_canonical_frame.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
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

std::string read_binary(const std::string& path, std::vector<std::int16_t>* out) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    f.seekg(0, std::ios::end);
    const std::streamsize n = f.tellg();
    f.seekg(0, std::ios::beg);
    out->resize(static_cast<std::size_t>(n) / sizeof(std::int16_t));
    f.read(reinterpret_cast<char*>(out->data()), n);
    f.close();
    return sdr::Sha256::hex(out->data(), out->size() * sizeof(std::int16_t));
}

void write_binary(const std::string& path, const std::vector<std::int16_t>& iq) {
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
}

// Deterministic non-zero synthetic payload (exactly kPayloadComplex complex).
std::vector<std::int16_t> make_payload() {
    std::vector<std::int16_t> iq(iqrftrain::kPayloadComplex * 2);
    for (std::size_t k = 0; k < iq.size(); ++k) {
        const std::uint32_t v = static_cast<std::uint32_t>(k) * 2654435761u;
        iq[k] = static_cast<std::int16_t>((v >> 16) & 0xFFFFu);
    }
    return iq;
}

bool all_zero(const std::vector<std::int16_t>& v, std::size_t begin, std::size_t end) {
    for (std::size_t i = begin; i < end; ++i)
        if (v[i] != 0) return false;
    return true;
}

bool segment_eq(const std::vector<std::int16_t>& v, std::size_t begin,
                const std::array<std::int16_t, 2048>& ref) {
    if (begin + 2048 > v.size()) return false;
    for (std::size_t i = 0; i < 2048; ++i)
        if (v[begin + i] != ref[i]) return false;
    return true;
}

void test_metadata_and_embedded_sha() {
    const fix10canonical::CanonicalMetadata m = fix10canonical::metadata();
    check(m.contract_version == 1, "metadata: contract_version == 1");
    check(m.preamble_sha == "d4b4bb3af9ad57836f4de7dfd9046898983c66f949d33aad35ed8dc434ccc97f",
          "metadata: preamble_sha");
    check(m.payload_training_sha == "f06e9b3de0f51594d8db0501a03918350072d4bc0e5a56f955053bafa35663ca",
          "metadata: payload_training_sha");
    check(m.tail_sha == "ccddabe154b62a4cbae7d628f410d89ef9bfd54ebbaf79d83139417a36666a8e",
          "metadata: tail_sha");
    check(m.contract_sha == "9907b7bed97c5cdc19b147f347f81d7ff8c5d026dc70c6f2c94495894750f8c5",
          "metadata: contract_sha");

    // Recompute each embedded array SHA and compare to the frozen constant.
    const std::string p = sdr::Sha256::hex(
        fix10canonical::kCanonicalPreamble.data(),
        fix10canonical::kCanonicalPreamble.size() * sizeof(std::int16_t));
    const std::string t = sdr::Sha256::hex(
        fix10canonical::kCanonicalPayloadTraining.data(),
        fix10canonical::kCanonicalPayloadTraining.size() * sizeof(std::int16_t));
    const std::string l = sdr::Sha256::hex(
        fix10canonical::kCanonicalTail.data(),
        fix10canonical::kCanonicalTail.size() * sizeof(std::int16_t));
    check(fix10canonical::kCanonicalPreamble.size() == 2048,
          "embedded: preamble array length 2048");
    check(fix10canonical::kCanonicalPayloadTraining.size() == 2048,
          "embedded: payload_training array length 2048");
    check(fix10canonical::kCanonicalTail.size() == 2048,
          "embedded: tail array length 2048");
    check(p == fix10canonical::kCanonicalPreambleSha, "embedded: preamble SHA matches constant");
    check(t == fix10canonical::kCanonicalPayloadTrainingSha,
          "embedded: payload_training SHA matches constant");
    check(l == fix10canonical::kCanonicalTailSha, "embedded: tail SHA matches constant");

    bool threw = false;
    try { fix10canonical::verifyEmbeddedContract(); }
    catch (const std::exception&) { threw = true; }
    check(!threw, "embedded: verifyEmbeddedContract() does not throw");
}

void test_burst_layout() {
    const std::vector<std::int16_t> payload = make_payload();
    const std::vector<std::int16_t> b = fix10canonical::buildBurst(payload);

    check(b.size() == iqrftrain::kTotalBurstComplex * 2,
          "layout: burst size == kTotalBurstComplex*2");
    check(segment_eq(b, 0, fix10canonical::kCanonicalPreamble),
          "layout: preamble segment == embedded preamble");
    check(all_zero(b, 2048, 4096), "layout: settling-zero zone all zero");
    check(segment_eq(b, 4096, fix10canonical::kCanonicalPayloadTraining),
          "layout: payload_training segment == embedded payload_training");
    check(all_zero(b, 113664, 117760), "layout: guard-zero zone all zero");
    check(segment_eq(b, 117760, fix10canonical::kCanonicalTail),
          "layout: tail segment == embedded tail");
    // payload sits in [6144, 113664) and equals the input scaled payload.
    bool payload_ok = true;
    for (std::size_t i = 0; i < payload.size(); ++i)
        if (b[6144 + i] != payload[i]) { payload_ok = false; break; }
    check(payload_ok, "layout: payload segment == input scaled payload");

    const std::vector<std::int16_t> b2 = fix10canonical::buildBurst(payload);
    check(b == b2, "layout: buildBurst deterministic");

    bool threw = false;
    try { fix10canonical::buildBurst(std::vector<std::int16_t>(100)); }
    catch (const std::exception&) { threw = true; }
    check(threw, "layout: wrong payload length throws fail-closed");
}

void test_build_from_synthetic() {
    const std::vector<std::int16_t> payload = make_payload();
    const std::uint64_t cc = iqrftrain::kPayloadComplex;
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = "/tmp/fix10_canonical_" + std::to_string(::getpid());
    ::mkdir(dir.c_str(), 0700);
#else
    const std::string dir = ".";
#endif
    const std::string path = dir + "/payload.ci16";
    write_binary(path, payload);
    const std::string sha = sdr::Sha256::hex(payload.data(),
                                             payload.size() * sizeof(std::int16_t));

    const iqpctbrx::TxBurstBuild a =
        fix10canonical::buildTxBurstFromFrozen(path, cc, sha, 2048.0);
    const iqpctbrx::TxBurstBuild b =
        fix10canonical::buildTxBurstFromFrozen(path, cc, sha, 2048.0);
    check(a.payload_sha_pre == sha, "synthetic: payload_sha_pre == frozen SHA");
    check(iqpctbrx::valid_sha64(a.payload_sha_post), "synthetic: payload_sha_post 64-hex");
    check(iqpctbrx::valid_sha64(a.burst_sha), "synthetic: burst_sha 64-hex");
    check(a.burst.size() == iqrftrain::kTotalBurstComplex * 2,
          "synthetic: burst size == kTotalBurstComplex*2");
    check(a.tx_scale > 0.0, "synthetic: tx_scale > 0");
    check(a.payload_sha_pre == b.payload_sha_pre, "synthetic: pre SHA deterministic");
    check(a.payload_sha_post == b.payload_sha_post, "synthetic: post SHA deterministic");
    check(a.burst_sha == b.burst_sha, "synthetic: burst SHA deterministic");
    check(a.burst == b.burst, "synthetic: burst bytes deterministic");

    bool threw = false;
    try { fix10canonical::buildTxBurstFromFrozen(path, cc, std::string(64, '0'), 2048.0); }
    catch (const std::exception&) { threw = true; }
    check(threw, "synthetic: wrong expect_sha throws fail-closed");

    threw = false;
    try { fix10canonical::buildTxBurstFromFrozen(path, cc + 1, sha, 2048.0); }
    catch (const std::exception&) { threw = true; }
    check(threw, "synthetic: wrong complex_count throws fail-closed");

    threw = false;
    try { fix10canonical::buildTxBurstFromFrozen(dir + "/missing.ci16", cc, sha, 2048.0); }
    catch (const std::exception&) { threw = true; }
    check(threw, "synthetic: missing file throws fail-closed");

    const iqpctbrx::TxBurstBuild clip =
        fix10canonical::buildTxBurstFromFrozen(path, cc, sha, 3.0e9);
    check(clip.clip_post, "synthetic: absurd target_rms clips post-scale (preserved)");

#if defined(__unix__) || defined(__APPLE__)
    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#endif
}

struct AuthoritativeSample {
    std::string file_name;
    std::string payload_sha_pre;
    std::string payload_sha_post;
    std::string full_burst_sha;
    double tx_scale;
};

void test_authoritative(const std::string& fixtures_dir) {
    const std::uint64_t cc = iqrftrain::kPayloadComplex;
    const AuthoritativeSample samples[] = {
        {"quantized_d2_2p56m_000006.ci16",
         "b0c4ff066ee0f635152c0e1baa477887c8c05b6119d93ac397c9e2a564d318de",
         "efbfad0a4d2104c96a013667ead267ff4ac62bb4f6424a57c5fdb73c7d6f62ab",
         "2e965828737350ba5ece97fa3896cfe62f5d7b806532bafa237bc0a25339342e",
         2.2915091544498973},
        {"quantized_d2_2p56m_000002.ci16",
         "abfe3f0e45b837e04298b42aeac251611828d75e8d29d888ed1600fc3bcc7b7d",
         "67d2cb6680c7746d03f30c8922b1225ede626d863b7ef00e89a994fb42fc64b7",
         "7e8126fb37c300e05ed1c22e11c162cbfd919c9ab16e6030644fb48c41195754",
         2.2918134810704101},
    };
    for (const auto& s : samples) {
        const std::string path = fixtures_dir + "/" + s.file_name;
        std::vector<std::int16_t> frozen;
        const std::string got_pre = read_binary(path, &frozen);
        if (got_pre.empty()) {
            ++g_fail;
            std::printf("  FAIL: authoritative: cannot read %s\n", path.c_str());
            continue;
        }
        check(got_pre == s.payload_sha_pre, "authoritative: frozen ci16 SHA (" + s.file_name + ")");

        const iqpctbrx::TxBurstBuild r =
            fix10canonical::buildTxBurstFromFrozen(path, cc, s.payload_sha_pre, 2048.0);
        check(r.payload_sha_pre == s.payload_sha_pre,
              "authoritative: payload_sha_pre unchanged (" + s.file_name + ")");
        check(r.payload_sha_post == s.payload_sha_post,
              "authoritative: payload_sha_post unchanged (" + s.file_name + ")");
        check(std::fabs(r.tx_scale - s.tx_scale) < 1e-9,
              "authoritative: tx_scale unchanged (" + s.file_name + ")");
        check(r.burst_sha == s.full_burst_sha,
              "authoritative: canonical burst_sha == ARM full_burst_sha (" + s.file_name + ")");
    }
}

}  // namespace

int main(int argc, char** argv) {
    std::printf("test_fix10_canonical_frame\n");

    std::string fixtures_dir = "fixtures_fix10_canonical";
    for (int i = 1; i + 1 < argc; ++i)
        if (std::strcmp(argv[i], "--fixtures-dir") == 0) fixtures_dir = argv[i + 1];

    test_metadata_and_embedded_sha();
    test_burst_layout();
    test_build_from_synthetic();
    test_authoritative(fixtures_dir);

    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
