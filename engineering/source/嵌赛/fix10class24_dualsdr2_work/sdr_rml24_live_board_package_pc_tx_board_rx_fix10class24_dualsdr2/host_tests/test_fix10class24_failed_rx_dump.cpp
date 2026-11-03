// test_fix10class24_failed_rx_dump.cpp -- host tests for the Phase B failed-RX dump
// header (iq_fix10class24_failed_rx_dump.hpp).  Exercises the three little-endian
// writers and the 7-file dump_failed_rx_sample() with a synthetic recovery, asserting
// byte order, file presence, SHA256SUMS format, and the recovery_diagnostics.json
// contents -- WITHOUT the NPU / libiio / board device.  The dump header is iCraft-free
// and libiio-free by construction, so it compiles and runs host-side identically.

#include "../board_package/iq_fix10class24_failed_rx_dump.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

int g_pass = 0;
int g_fail = 0;
const std::string kBase = "/tmp/fix10class24_dump_test";

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

std::string read_text(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

bool file_exists(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    return static_cast<bool>(f);
}

// LE reader mirroring the dump writer's byte order.
std::vector<std::int16_t> read_ci16(const std::string& path) {
    const std::string raw = read_text(path);
    std::vector<std::int16_t> out(raw.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i) {
        const std::uint16_t u = static_cast<std::uint16_t>(
            static_cast<unsigned char>(raw[i * 2])) |
            (static_cast<std::uint16_t>(static_cast<unsigned char>(raw[i * 2 + 1])) << 8);
        out[i] = static_cast<std::int16_t>(u);
    }
    return out;
}

void test_writers(const std::string& dir) {
    iqfix10dump::mkdir_p(dir);
    // ci16: 0, 1, -1, 32767, -32768  -> little-endian roundtrip.
    const std::vector<std::int16_t> ci = {0, 1, -1, 32767, -32768};
    iqfix10dump::write_ci16_le(dir + "/w.ci16", ci);
    const std::vector<std::int16_t> ci2 = read_ci16(dir + "/w.ci16");
    check(ci2 == ci, "write_ci16_le / read roundtrip (incl. -32768, 32767)");

    // cf64: known complex<double> values roundtrip at full double precision.
    const std::vector<std::complex<double>> cf = {
        std::complex<double>(1.5, -2.25), std::complex<double>(0.0, 3.141592653589793)};
    iqfix10dump::write_cf64_le(dir + "/w.cf64", cf);
    {
        const std::string raw = read_text(dir + "/w.cf64");
        check(raw.size() == 2 * 16, "cf64 byte count == 2*16");
        std::complex<double> z[2];
        for (int k = 0; k < 2; ++k) {
            std::uint64_t re_bits = 0, im_bits = 0;
            for (int b = 0; b < 8; ++b) {
                re_bits |= static_cast<std::uint64_t>(
                    static_cast<unsigned char>(raw[k * 16 + b])) << (8 * b);
                im_bits |= static_cast<std::uint64_t>(
                    static_cast<unsigned char>(raw[k * 16 + 8 + b])) << (8 * b);
            }
            double re = 0.0, im = 0.0;
            std::memcpy(&re, &re_bits, 8);
            std::memcpy(&im, &im_bits, 8);
            z[k] = std::complex<double>(re, im);
        }
        check(z[0] == cf[0] && z[1] == cf[1], "write_cf64_le / read double-precision roundtrip");
    }

    // f32: float precision roundtrip (truncation to float is expected/defined).
    iqfix10dump::write_f32_le(dir + "/w.f32", cf);
    {
        const std::string raw = read_text(dir + "/w.f32");
        check(raw.size() == 2 * 8, "f32 byte count == 2*8");
        float re = 0.0f, im = 0.0f;
        std::uint32_t re_bits = 0, im_bits = 0;
        for (int b = 0; b < 4; ++b) {
            re_bits |= static_cast<std::uint32_t>(static_cast<unsigned char>(raw[b])) << (8 * b);
            im_bits |= static_cast<std::uint32_t>(static_cast<unsigned char>(raw[4 + b])) << (8 * b);
        }
        std::memcpy(&re, &re_bits, 4);
        std::memcpy(&im, &im_bits, 4);
        check(re == static_cast<float>(cf[0].real()) && im == static_cast<float>(cf[0].imag()),
              "write_f32_le / read float-precision roundtrip");
    }
}

void test_dump(const std::string& base) {
    // A real, valid recovery from a clean single-burst capture gives the dump
    // non-trivial content (non-empty payload + finite diagnostics).
    std::vector<std::int16_t> payload(iqrftrain::kPayloadComplex * 2, 0);
    for (std::size_t k = 0; k < iqrftrain::kPayloadComplex; ++k) {
        const double ph = 2.0 * iqrftrain::kPi * static_cast<double>(k % 41) / 41.0;
        payload[k * 2 + 0] = static_cast<std::int16_t>(std::lround(1100.0 * std::cos(ph)));
        payload[k * 2 + 1] = static_cast<std::int16_t>(std::lround(1100.0 * std::sin(ph)));
    }
    const std::vector<std::int16_t> burst = iqrftrain::build_burst(payload);
    const std::vector<std::complex<double>> rx = iqrftrain::deinterleave(burst);

    iqrfrec::EstimateConfig cfg;
    cfg.min_corr = 0.9;
    cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;
    cfg.max_cfo_hz = static_cast<double>(iqrftrain::kFs) /
                     (2.0 * static_cast<double>(iqrftrain::kTailStart));
    cfg.max_sro_ppm = 30.0;
    cfg.search_limit = 0;
    cfg.payload_tx_target_rms = 2048.0;

    const iqdual23fix10::CoarseCfoRecovery ccr =
        iqdual23fix10::recover_payload_with_coarse_cfo(rx, cfg, 1.0);
    check(ccr.rec.valid, "synthetic clean recovery is valid (dump test precondition)");

    iqdloop::FrozenIq fz;
    fz.source_index = 1500;
    fz.file_name = "synth_1500.ci16";
    fz.modulation = "BPSK";
    fz.source_class = 0;
    fz.snr_db = 20.0;
    fz.split_role = "holdout";

    iqpctbrx::TxBurstBuild expected;
    expected.payload = payload;
    expected.burst = burst;
    expected.tx_scale = 1.0;
    expected.payload_sha_pre = "pre";
    expected.payload_sha_post = "post";
    expected.burst_sha = "burstsha";

    iqfix10dump::dump_failed_rx_sample(
        fz, expected, burst, rx, ccr,
        ccr.coarse_cfo_hz, ccr.rec.cfo_hz, ccr.coarse_cfo_hz + ccr.rec.cfo_hz,
        true, true, "RF_PRESERVES_IQ", base, 2048.0, cfg, 625.0, 21.74, -625.0, 625.0);

    const std::string dir = base + "/failed_rx/1500";
    check(file_exists(dir + "/raw_rx_ci16le.bin"), "raw_rx_ci16le.bin exists");
    check(file_exists(dir + "/expected_scaled_payload_ci16le.bin"),
          "expected_scaled_payload_ci16le.bin exists");
    check(file_exists(dir + "/expected_full_burst_ci16le.bin"),
          "expected_full_burst_ci16le.bin exists");
    check(file_exists(dir + "/coarse_corrected_rx_cf64le.bin"),
          "coarse_corrected_rx_cf64le.bin exists");
    check(file_exists(dir + "/recovered_payload_f32le.bin"), "recovered_payload_f32le.bin exists");
    check(file_exists(dir + "/recovery_diagnostics.json"), "recovery_diagnostics.json exists");
    check(file_exists(dir + "/SHA256SUMS.txt"), "SHA256SUMS.txt exists");

    // raw_rx bytes == the exact interleaved int16 burst (LE).
    const std::vector<std::int16_t> raw_back = read_ci16(dir + "/raw_rx_ci16le.bin");
    check(raw_back == burst, "raw_rx_ci16le.bin roundtrip == source int16 burst");

    // expected_scaled_payload / expected_full_burst roundtrip.
    check(read_ci16(dir + "/expected_scaled_payload_ci16le.bin") == payload,
          "expected_scaled_payload roundtrip");
    check(read_ci16(dir + "/expected_full_burst_ci16le.bin") == burst,
          "expected_full_burst roundtrip");

    // recovered_payload is kPayloadComplex complex samples = *8 bytes.
    check(read_text(dir + "/recovered_payload_f32le.bin").size() ==
              iqrftrain::kPayloadComplex * 8,
          "recovered_payload_f32le.bin has kPayloadComplex*8 bytes");

    // SHA256SUMS: 5 lines, each "<64-hex>  <name>", first hash == raw_rx hash.
    const std::string sums = read_text(dir + "/SHA256SUMS.txt");
    std::size_t lines = 0;
    std::size_t pos = 0;
    bool first_matches = false;
    while (pos < sums.size()) {
        const std::size_t nl = sums.find('\n', pos);
        const std::string line = sums.substr(pos, (nl == std::string::npos) ? std::string::npos
                                                                            : nl - pos);
        if (!line.empty()) {
            ++lines;
            const std::size_t sp = line.find("  ");
            check(sp == 64, "SHA256SUMS line has '<64-hex>  name' separator at col 64");
            if (lines == 1) {
                bool ok = false;
                const std::string h = sdr::sha256_hex_file(dir + "/raw_rx_ci16le.bin", &ok);
                first_matches = ok && (line.substr(0, 64) == h) && (line.substr(66) == "raw_rx_ci16le.bin");
            }
        }
        if (nl == std::string::npos) break;
        pos = nl + 1;
    }
    check(lines == 5, "SHA256SUMS has 5 lines (got " + std::to_string(lines) + ")");
    check(first_matches, "SHA256SUMS first line == sha256(raw_rx_ci16le.bin)  raw_rx_ci16le.bin");

    // JSON: spot-check the diagnostic fields + the dump's recorded recovery values.
    const std::string json = read_text(dir + "/recovery_diagnostics.json");
    const auto has = [&](const std::string& s) { return json.find(s) != std::string::npos; };
    check(has("\"source_index\":1500"), "json: source_index");
    check(has("\"modulation\":\"BPSK\""), "json: modulation");
    check(has("\"rf_verdict\":\"RF_PRESERVES_IQ\""), "json: rf_verdict");
    check(has("\"failure\":\"NONE\""), "json: failure NONE");
    check(has("\"failure_enum\":0"), "json: failure_enum 0");
    check(has("\"target_rms\":2048"), "json: target_rms");
    check(has("\"tx_scale\":1"), "json: tx_scale");
    check(has("\"raw_rx_complex_count\":59904"), "json: raw_rx_complex_count");
    check(has("\"recovered_payload_complex_count\":53760"), "json: recovered payload count");
    check(has("\"estimate_config\""), "json: estimate_config nested object");
    check(has("\"max_residual\":0.1"), "json: estimate_config.max_residual == 0.1");
    check(has("\"payload_tx_target_rms\":2048"), "json: estimate_config.payload_tx_target_rms");
}

}  // namespace

void run_test(const char* name, void (*fn)()) {
    try {
        fn();
    } catch (const std::exception& e) {
        std::printf("  EXCEPTION in %s: %s\n", name, e.what());
        ++g_fail;
    }
}

int main() {
    std::printf("test_fix10class24_failed_rx_dump\n");
    run_test("writers", [] { test_writers(kBase); });
    run_test("dump", [] { test_dump(kBase); });
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
