// test_fix10class24_noretrain_dump.cpp -- host tests for the Phase B diagnostic
// export header (iq_fix10class24_noretrain_dump.hpp).  Exercises the gated-logits
// dump and the gate-refused marker WITHOUT the NPU / libiio / board device.  The
// header is iCraft-free and libiio-free by construction.

#include "../board_package/iq_fix10class24_noretrain_dump.hpp"
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
const std::string kBase = "/tmp/fix10class24_noretrain_dump_test";

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

std::vector<float> read_f32(const std::string& path) {
    const std::string raw = read_text(path);
    std::vector<float> out(raw.size() / 4);
    for (std::size_t i = 0; i < out.size(); ++i) {
        std::uint32_t u = 0;
        for (int b = 0; b < 4; ++b)
            u |= static_cast<std::uint32_t>(
                     static_cast<unsigned char>(raw[i * 4 + b])) << (8 * b);
        float f;
        std::memcpy(&f, &u, 4);
        out[i] = f;
    }
    return out;
}

bool contains(const std::string& s, const std::string& sub) {
    return s.find(sub) != std::string::npos;
}

void test_gated_logits() {
    const std::string out = kBase + "/gated";
    iqfix10dump::mkdir_p(out);

    std::vector<float> logits(24, -10.0f);
    logits[5] = 3.5f;   // argmax = 5 (8PSK)
    logits[7] = 2.0f;   // top2
    std::vector<float> model(2048, 0.25f);
    model[0] = 1.5f;

    iqfix10dump::dump_gated_logits(out, 2500, 5, "8PSK", "RF_PRESERVES_IQ",
                                   logits, model, 5, true);

    const std::string dir = out + "/dump_rx/2500/";
    check(file_exists(dir + "raw24_logits_f32le.bin"), "gated: raw24_logits_f32le.bin present");
    check(file_exists(dir + "model_input_f32le.bin"), "gated: model_input_f32le.bin present");
    check(file_exists(dir + "classification_dump.json"), "gated: classification_dump.json present");
    check(file_exists(dir + "SHA256SUMS.txt"), "gated: SHA256SUMS.txt present");

    const std::vector<float> rd = read_f32(dir + "raw24_logits_f32le.bin");
    check(rd.size() == 24, "gated: logits length == 24");
    check(rd.size() == 24 && rd[5] == 3.5f && rd[0] == -10.0f, "gated: logits LE roundtrip");
    const std::vector<float> mi = read_f32(dir + "model_input_f32le.bin");
    check(mi.size() == 2048, "gated: model input length == 2048");
    check(mi.size() == 2048 && mi[0] == 1.5f && mi[1] == 0.25f, "gated: model input LE roundtrip");

    const std::string js = read_text(dir + "classification_dump.json");
    check(contains(js, "\"source_index\":2500"), "gated: source_index");
    check(contains(js, "\"source_class\":5"), "gated: source_class");
    check(contains(js, "\"rf_verdict\":\"RF_PRESERVES_IQ\""), "gated: rf_verdict");
    check(contains(js, "\"diagnostic_gate_bypass\":0"), "gated: diagnostic_gate_bypass=0");
    check(contains(js, "\"production_gate_modified\":0"), "gated: production_gate_modified=0");
    check(contains(js, "\"wide_linear_enabled\":1"), "gated: wide_linear_enabled=1");
    check(contains(js, "\"raw24_pred\":5"), "gated: raw24_pred=5");
    check(contains(js, "\"raw24_label\":\"8PSK\""), "gated: raw24_label=8PSK");
    check(contains(js, "\"logit_finite\":1"), "gated: logit_finite=1");

    const std::string sums = read_text(dir + "SHA256SUMS.txt");
    check(contains(sums, "raw24_logits_f32le.bin"), "gated: SHA256SUMS lists logits");
    check(contains(sums, "model_input_f32le.bin"), "gated: SHA256SUMS lists model input");
}

void test_refused_marker() {
    const std::string out = kBase + "/refused";
    iqfix10dump::mkdir_p(out);

    iqfix10dump::dump_refused_logits_marker(out, 500, 1, "4ASK", "RF_DISTORTS_IQ");

    const std::string js =
        read_text(out + "/dump_rx/500/classification_dump.json");
    check(contains(js, "\"source_index\":500"), "refused: source_index");
    check(contains(js, "\"source_class\":1"), "refused: source_class");
    check(contains(js, "\"rf_verdict\":\"RF_DISTORTS_IQ\""), "refused: rf_verdict");
    check(contains(js, "\"diagnostic_gate_bypass\":1"), "refused: diagnostic_gate_bypass=1");
    check(contains(js, "\"production_gate_modified\":0"), "refused: production_gate_modified=0");
    check(contains(js, "\"raw24_pred\":-1"), "refused: raw24_pred=-1");
    check(contains(js, "\"raw24_logits_present\":0"), "refused: raw24_logits_present=0");
    check(contains(js, "\"model_input_present\":0"), "refused: model_input_present=0");
}

}  // namespace

int main() {
    test_gated_logits();
    test_refused_marker();
    std::printf("test_fix10class24_noretrain_dump: %d pass / %d fail\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
