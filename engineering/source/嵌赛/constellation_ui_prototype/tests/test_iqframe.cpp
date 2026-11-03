// test_iqframe.cpp — Qt-free unit tests for the M29 constellation UI core.
//
// Build (no Qt required):
//   g++ -std=c++17 -O2 -Wall -Wextra -I../src test_iqframe.cpp ../src/IqFrameLoader.cpp -o test_iqframe
// Run (fixtures ROOT dir is argv[1]; valid/ and negative/ are resolved below):
//   ./test_iqframe ../fixtures
//
// Covers the 14 required tests plus SHA-256 known-vector / fixture-hash checks,
// JSON parser checks, the SYMBOL_SAMPLED red line, and hotfix1 coverage
// (validity-field parsing + missing-field compat, valid/negative isolation,
// no-fake-RAW_RX, d2_rec_scale vs RF gain separation).
#include "../src/IqFrame.hpp"
#include "../src/IqFrameLoader.hpp"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace cst;

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        if (cond) {                                                     \
            ++g_pass;                                                   \
        } else {                                                        \
            ++g_fail;                                                   \
            std::printf("    FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        }                                                               \
    } while (0)

// ---------------------------------------------------------------------------
static bool write_bytes(const std::string& path, const std::string& bytes) {
    std::ofstream f(path, std::ios::binary);
    if (!f) return false;
    f.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    return f.good();
}

struct TempDir {
    std::string path;
    explicit TempDir(const std::string& tag) {
        static int counter = 0;
        path = (fs::temp_directory_path() /
                ("cst_iqframe_test_" + tag + "_" + std::to_string(++counter)))
                   .string();
        fs::create_directories(path);
    }
    ~TempDir() {
        std::error_code ec;
        fs::remove_all(path, ec);
    }
};

// Writes binary bytes + a flat sidecar and returns the sidecar path.
static std::string make_sidecar(TempDir& t, const std::string& name,
                                const std::string& bytes, const std::string& stage,
                                const std::string& dtype, const std::string& layout,
                                std::uint64_t cc, const std::string& sha_override,
                                const std::string& extra = "") {
    const std::string sha =
        sha_override.empty() ? sha256_hex(bytes.data(), bytes.size()) : sha_override;
    std::ostringstream js;
    js << "{\"schema_version\":1,\"frame_id\":1,\"stage\":\"" << stage
       << "\",\"dtype\":\"" << dtype << "\",\"layout\":\"" << layout
       << "\",\"complex_count\":" << cc << ",\"sample_rate_hz\":2560000"
       << ",\"payload_sha256\":\"" << sha << "\",\"iq_file\":\"" << name << "\""
       << extra << "}";
    write_bytes(t.path + "/" + name, bytes);
    const std::string jpath = t.path + "/" + name + ".json";
    write_bytes(jpath, js.str());
    return jpath;
}

static std::string i16_le(std::int16_t v) {
    std::string s(2, '\0');
    s[0] = static_cast<char>(v & 0xff);
    s[1] = static_cast<char>((v >> 8) & 0xff);
    return s;
}

static std::string f32_le(float v) {
    std::uint32_t u;
    std::memcpy(&u, &v, 4);
    std::string s(4, '\0');
    s[0] = static_cast<char>(u & 0xff);
    s[1] = static_cast<char>((u >> 8) & 0xff);
    s[2] = static_cast<char>((u >> 16) & 0xff);
    s[3] = static_cast<char>((u >> 24) & 0xff);
    return s;
}

// ---------------------------------------------------------------------------
// SHA-256 sanity + fixture hashes (the SHA checks everything else relies on).
static bool test_sha256() {
    CHECK(sha256_hex("", 0) ==
          "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    CHECK(sha256_hex("abc", 3) ==
          "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    CHECK(sha256_hex("The quick brown fox jumps over the lazy dog", 43) ==
          "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592");
    return true;
}

// ---------------------------------------------------------------------------
// 1. CI16 interleaved parse
static bool test_ci16_interleaved() {
    TempDir t("ci16");
    std::string bytes;
    for (std::int16_t v : {1, 2, 3, 4, 5, 6, 7, 8}) bytes += i16_le(v);  // I,Q pairs
    const std::string jp = make_sidecar(t, "c.bin", bytes, "RAW_RX", "<i2",
                                        "interleaved", 4, "");
    IqFrame f;
    std::string err;
    CHECK(load_sidecar_frame(jp, f, err));
    if (!err.empty()) std::printf("    err=%s\n", err.c_str());
    CHECK(f.dtype == DType::I16);
    CHECK(f.layout == Layout::Interleaved);
    CHECK(f.i.size() == 4 && f.q.size() == 4);
    CHECK(f.i[0] == 1.0f && f.q[0] == 2.0f && f.i[3] == 7.0f && f.q[3] == 8.0f);
    return true;
}

// ---------------------------------------------------------------------------
// 2. F32 planar parse
static bool test_f32_planar() {
    TempDir t("f32p");
    std::string bytes;
    for (float v : {1.0f, 2.0f, 3.0f, 4.0f}) bytes += f32_le(v);  // real[0:4]
    for (float v : {5.0f, 6.0f, 7.0f, 8.0f}) bytes += f32_le(v);  // imag[0:4]
    const std::string jp = make_sidecar(t, "p.bin", bytes, "MODEL_INPUT", "<f4",
                                        "planar", 4, "");
    IqFrame f;
    std::string err;
    CHECK(load_sidecar_frame(jp, f, err));
    CHECK(f.dtype == DType::F32);
    CHECK(f.layout == Layout::Planar);
    CHECK(f.i.size() == 4);
    CHECK(f.i[0] == 1.0f && f.i[3] == 4.0f && f.q[0] == 5.0f && f.q[3] == 8.0f);
    return true;
}

// ---------------------------------------------------------------------------
// 3. F32 interleaved parse
static bool test_f32_interleaved() {
    TempDir t("f32i");
    std::string bytes;
    const float vals[8] = {1.0f, 5.0f, 2.0f, 6.0f, 3.0f, 7.0f, 4.0f, 8.0f};
    for (float v : vals) bytes += f32_le(v);
    const std::string jp = make_sidecar(t, "i.bin", bytes, "RECOVERED_PAYLOAD", "<f4",
                                        "interleaved", 4, "");
    IqFrame f;
    std::string err;
    CHECK(load_sidecar_frame(jp, f, err));
    CHECK(f.i[0] == 1.0f && f.q[0] == 5.0f && f.i[3] == 4.0f && f.q[3] == 8.0f);
    return true;
}

// ---------------------------------------------------------------------------
// 4. Little-endian check
static bool test_little_endian() {
    const unsigned char c2[2] = {0x34, 0x12};
    CHECK(read_le_i16(c2) == 0x1234);
    const unsigned char neg[2] = {0x00, 0x80};
    CHECK(read_le_i16(neg) == -32768);
    const unsigned char f1[4] = {0x00, 0x00, 0x80, 0x3F};  // 1.0f LE
    CHECK(read_le_f32(f1) == 1.0f);
    const unsigned char fn[4] = {0x00, 0x00, 0x00, 0xC0};  // -2.0f LE
    CHECK(read_le_f32(fn) == -2.0f);
    return true;
}

// ---------------------------------------------------------------------------
// 5. Wrong length rejected
static bool test_wrong_length(const std::string& fixtures) {
    std::string err;
    IqFrame f;
    CHECK(!load_sidecar_frame(fixtures + "/negative/wrong_length.json", f, err));
    CHECK(err.find("length mismatch") != std::string::npos);
    return true;
}

// ---------------------------------------------------------------------------
// 6. Wrong SHA rejected
static bool test_wrong_sha(const std::string& fixtures) {
    std::string err;
    IqFrame f;
    CHECK(!load_sidecar_frame(fixtures + "/negative/wrong_sha.json", f, err));
    CHECK(err.find("SHA mismatch") != std::string::npos);
    return true;
}

// ---------------------------------------------------------------------------
// 7. NaN/Inf rejected
static bool test_nan_inf(const std::string& fixtures) {
    std::string err;
    IqFrame f;
    CHECK(!load_sidecar_frame(fixtures + "/negative/nan_inf.json", f, err));
    CHECK(err.find("NaN/Inf") != std::string::npos);
    return true;
}

// ---------------------------------------------------------------------------
// 8. Unknown schema rejected
static bool test_unknown_schema() {
    TempDir t("schema");
    const std::string bytes = f32_le(1.0f) + f32_le(2.0f);  // 1 complex planar
    const std::string sha = sha256_hex(bytes.data(), bytes.size());
    write_bytes(t.path + "/s.bin", bytes);
    const std::string js =
        "{\"schema_version\":2,\"stage\":\"MODEL_INPUT\",\"dtype\":\"<f4\","
        "\"layout\":\"planar\",\"complex_count\":1,\"payload_sha256\":\"" +
        sha + "\",\"iq_file\":\"s.bin\"}";
    write_bytes(t.path + "/s.json", js);
    std::string err;
    IqFrame f;
    CHECK(!load_sidecar_frame(t.path + "/s.json", f, err));
    CHECK(err.find("unknown schema_version") != std::string::npos);
    return true;
}

// ---------------------------------------------------------------------------
// 9. Unknown dtype / layout / stage rejected
static bool test_unknown_dtype_layout() {
    TempDir t("dl");
    const std::string bytes = f32_le(1.0f) + f32_le(2.0f);
    const std::string sha = sha256_hex(bytes.data(), bytes.size());
    write_bytes(t.path + "/d.bin", bytes);

    auto try_load = [&](const std::string& dtype, const std::string& layout,
                        const std::string& stage, std::string& err) {
        const std::string js =
            "{\"schema_version\":1,\"stage\":\"" + stage + "\",\"dtype\":\"" + dtype +
            "\",\"layout\":\"" + layout +
            "\",\"complex_count\":1,\"payload_sha256\":\"" + sha +
            "\",\"iq_file\":\"d.bin\"}";
        write_bytes(t.path + "/d.json", js);
        IqFrame f;
        return load_sidecar_frame(t.path + "/d.json", f, err);
    };

    std::string err;
    CHECK(!try_load("<f8", "planar", "MODEL_INPUT", err));
    CHECK(err.find("unknown dtype") != std::string::npos);
    CHECK(!try_load("<f4", "column-major", "MODEL_INPUT", err));
    CHECK(err.find("unknown layout") != std::string::npos);
    CHECK(!try_load("<f4", "planar", "FANCY_STAGE", err));
    CHECK(err.find("unknown stage") != std::string::npos);
    return true;
}

// ---------------------------------------------------------------------------
// 10. 1024-point coordinate transform
static bool test_transform_1024() {
    std::vector<float> i(1024), q(1024);
    for (int k = 0; k < 1024; ++k) {
        i[k] = static_cast<float>(k) / 1024.0f * 2.0f - 1.0f;   // [-1, 1)
        q[k] = -i[k];
    }
    std::vector<float> ux, uy;
    transform_to_unit(i, q, 1.0f, ux, uy);
    CHECK(ux.size() == 1024 && uy.size() == 1024);
    // center (0,0) -> (0.5, 0.5); (1,1)->(1,0); (-1,-1)->(0,1)
    transform_to_unit({0.0f}, {0.0f}, 1.0f, ux, uy);
    CHECK(std::fabs(ux[0] - 0.5f) < 1e-6f && std::fabs(uy[0] - 0.5f) < 1e-6f);
    transform_to_unit({1.0f}, {1.0f}, 1.0f, ux, uy);
    CHECK(std::fabs(ux[0] - 1.0f) < 1e-6f && std::fabs(uy[0] - 0.0f) < 1e-6f);
    transform_to_unit({-1.0f}, {-1.0f}, 1.0f, ux, uy);
    CHECK(std::fabs(ux[0] - 0.0f) < 1e-6f && std::fabs(uy[0] - 1.0f) < 1e-6f);
    return true;
}

// ---------------------------------------------------------------------------
// 11. Deterministic decimation
static bool test_decimation() {
    auto d1 = decimate_indices(16384, 4096);
    auto d2 = decimate_indices(16384, 4096);
    CHECK(d1.size() == 4096);
    CHECK(d1 == d2);                       // deterministic, no per-frame randomness
    CHECK(d1.front() == 0);
    CHECK(d1.back() < 16384);
    bool inc = true;
    for (std::size_t k = 1; k < d1.size(); ++k) inc = inc && (d1[k] > d1[k - 1]);
    CHECK(inc);                            // strictly increasing (no duplicates)

    auto all = decimate_indices(1024, 4096);
    CHECK(all.size() == 1024);             // below limit: keep everything
    CHECK(all.back() == 1023);

    auto raw = decimate_indices(53760, 4096);
    CHECK(raw.size() == 4096);
    return true;
}

// ---------------------------------------------------------------------------
// 12. Auto-scale (robust quantile)
static bool test_auto_scale() {
    std::vector<float> i(1000, 0.5f), q(1000, -0.5f);
    for (int k = 0; k < 1000; ++k) {
        i[k] = (k % 2 == 0) ? 0.5f : -0.5f;
        q[k] = (k % 3 == 0) ? 0.3f : -0.3f;
    }
    // a few wild outliers must not collapse the body
    i[0] = 100.0f; q[0] = -100.0f; i[1] = 50.0f;
    std::size_t oor = 0;
    const float r = auto_scale_range(i, q, oor);
    CHECK(r > 0.0f && r < 2.0f);   // body dominates; outliers ignored
    CHECK(oor > 0);                // outliers counted
    return true;
}

// ---------------------------------------------------------------------------
// 13. Empty frame rejected
static bool test_empty_frame() {
    TempDir t("empty");
    const std::string bytes;   // zero bytes
    const std::string sha = sha256_hex(bytes.data(), bytes.size());
    const std::string js =
        "{\"schema_version\":1,\"stage\":\"MODEL_INPUT\",\"dtype\":\"<f4\","
        "\"layout\":\"planar\",\"complex_count\":0,\"payload_sha256\":\"" +
        sha + "\",\"iq_file\":\"e.bin\"}";
    write_bytes(t.path + "/e.bin", bytes);
    write_bytes(t.path + "/e.json", js);
    std::string err;
    IqFrame f;
    CHECK(!load_sidecar_frame(t.path + "/e.json", f, err));
    CHECK(err.find("complex_count") != std::string::npos);
    return true;
}

// ---------------------------------------------------------------------------
// 14. Single-point / all-zero frame does not crash
static bool test_single_point_allzero() {
    TempDir t("zz");
    // single point
    const std::string one = f32_le(0.5f) + f32_le(-0.5f);
    const std::string jp1 = make_sidecar(t, "one.bin", one, "MODEL_INPUT", "<f4",
                                         "planar", 1, "");
    IqFrame f1;
    std::string err;
    CHECK(load_sidecar_frame(jp1, f1, err));
    CHECK(f1.i.size() == 1);
    std::size_t oor = 0;
    const float r1 = auto_scale_range(f1.i, f1.q, oor);
    CHECK(std::isfinite(r1) && r1 > 0.0f);

    // all-zero frame (1024 zeros)
    std::string zbytes;
    for (int k = 0; k < 2048; ++k) zbytes += f32_le(0.0f);
    const std::string jp2 = make_sidecar(t, "zero.bin", zbytes, "MODEL_INPUT", "<f4",
                                         "planar", 1024, "");
    IqFrame f2;
    CHECK(load_sidecar_frame(jp2, f2, err));
    const float r2 = auto_scale_range(f2.i, f2.q, oor);
    CHECK(std::isfinite(r2) && r2 > 0.0f);   // degenerate frame -> safe fallback
    std::vector<float> ux, uy;
    transform_to_unit(f2.i, f2.q, r2, ux, uy);
    CHECK(ux.size() == 1024 && std::isfinite(ux[0]));
    return true;
}

// ---------------------------------------------------------------------------
// Extras: real fixture loads + red lines + JSON parser
static bool test_real_fixtures(const std::string& fixtures) {
    std::string err;
    IqFrame bpsk;
    CHECK(load_sidecar_frame(fixtures + "/valid/bpsk_clean_model_input.json", bpsk, err));
    CHECK(bpsk.stage == Stage::ModelInput);
    CHECK(bpsk.complex_count == 1024 && bpsk.i.size() == 1024 && bpsk.q.size() == 1024);
    CHECK(bpsk.modulation == "BPSK");
    CHECK(bpsk.predicted_class == "BPSK" && bpsk.baseline_class == "BPSK");
    CHECK(bpsk.prediction_agreement());
    CHECK(!bpsk.symbol_timing_valid);

    IqFrame rec;
    CHECK(load_sidecar_frame(fixtures + "/valid/ask4_recovered_payload.json", rec, err));
    CHECK(rec.stage == Stage::RecoveredPayload);
    CHECK(rec.modulation == "4ASK");
    CHECK(std::fabs(rec.d2_rec_scale - 0.997743875) < 1e-9);
    return true;
}

static bool test_red_lines() {
    // SYMBOL_SAMPLED without symbol timing must be rejected.
    TempDir t("rl");
    const std::string bytes = f32_le(1.0f) + f32_le(1.0f);
    const std::string jp = make_sidecar(t, "s.bin", bytes, "SYMBOL_SAMPLED", "<f4",
                                        "planar", 1, "",
                                        ",\"symbol_timing_valid\":false");
    std::string err;
    IqFrame f;
    CHECK(!load_sidecar_frame(jp, f, err));
    CHECK(err.find("SYMBOL_SAMPLED") != std::string::npos);
    return true;
}

static bool test_json_parser() {
    JsonObject obj;
    std::string err;
    CHECK(parse_json_object("{\"a\":1,\"b\":\"x\",\"c\":true,\"d\":null}", obj, err));
    CHECK(obj.size() == 4);
    const JsonValue* a = find_field(obj, "a");
    CHECK(a && a->kind == JsonValue::Number && a->num == 1.0);
    const JsonValue* b = find_field(obj, "b");
    CHECK(b && b->kind == JsonValue::String && b->s == "x");

    CHECK(!parse_json_object("{", obj, err));                      // malformed
    CHECK(!parse_json_object("{\"a\":[1,2]}", obj, err));          // nested rejected
    CHECK(!parse_json_object("{\"a\":1} trailing", obj, err));     // trailing data
    CHECK(!parse_json_object("{\"a\":1e999}", obj, err));          // non-finite
    CHECK(parse_json_object("{\"a\":-12.5e-3}", obj, err));
    const JsonValue* n = find_field(obj, "a");
    CHECK(n && std::fabs(n->num + 0.0125) < 1e-12);
    return true;
}

// ---------------------------------------------------------------------------
// hotfix1: metric validity fields — present values parse, missing fields default
// to false (fail-closed toward "unavailable", so 0 never means "measured 0").
static bool test_validity_fields() {
    TempDir t("validity");
    {   // all present
        const std::string bytes = f32_le(1.0f) + f32_le(2.0f);
        const std::string sha = sha256_hex(bytes.data(), bytes.size());
        write_bytes(t.path + "/v.bin", bytes);
        const std::string js =
            "{\"schema_version\":1,\"stage\":\"RECOVERED_PAYLOAD\",\"dtype\":\"<f4\","
            "\"layout\":\"planar\",\"complex_count\":1,\"payload_sha256\":\"" + sha +
            "\",\"iq_file\":\"v.bin\","
            "\"confidence_valid\":true,\"cfo_valid\":true,\"sro_valid\":true,"
            "\"gain_valid\":true,\"recovery_metrics_valid\":true,"
            "\"d2_rec_scale\":0.5,\"metric_provenance\":\"real\"}";
        write_bytes(t.path + "/v.json", js);
        IqFrame f;
        std::string err;
        CHECK(load_sidecar_frame(t.path + "/v.json", f, err));
        CHECK(f.confidence_valid && f.cfo_valid && f.sro_valid && f.gain_valid);
        CHECK(f.recovery_metrics_valid);
        CHECK(std::fabs(f.d2_rec_scale - 0.5) < 1e-12);
        CHECK(f.metric_provenance == "real");
    }
    {   // all missing -> fail-closed false / empty
        const std::string bytes = f32_le(1.0f) + f32_le(2.0f);
        const std::string jp = make_sidecar(t, "m.bin", bytes, "MODEL_INPUT", "<f4",
                                            "planar", 1, "");
        IqFrame f;
        std::string err;
        CHECK(load_sidecar_frame(jp, f, err));
        CHECK(!f.confidence_valid && !f.cfo_valid && !f.sro_valid && !f.gain_valid);
        CHECK(!f.recovery_metrics_valid);
        CHECK(f.metric_provenance.empty());
        CHECK(f.d2_rec_scale == 0.0);
    }
    return true;
}

// ---------------------------------------------------------------------------
// hotfix1: valid/negative directory isolation — valid dir plays clean (no bad
// frame at index 5), negative dir fails closed on every entry.
static bool test_dir_isolation(const std::string& fixtures) {
    std::string err;
    const auto valid = list_sidecars(fixtures + "/valid", err);
    CHECK(valid.size() == 4);
    int ok = 0;
    for (const auto& p : valid) {
        IqFrame f;
        std::string e;
        if (load_sidecar_frame(p, f, e)) ++ok;
    }
    CHECK(ok == 4);

    const auto neg = list_sidecars(fixtures + "/negative", err);
    CHECK(neg.size() == 7);
    int fails = 0;
    for (const auto& p : neg) {
        IqFrame f;
        std::string e;
        if (!load_sidecar_frame(p, f, e)) ++fails;
    }
    CHECK(fails == 7);
    return true;
}

// ---------------------------------------------------------------------------
// hotfix1: no fake RAW_RX — the removed D2 TX file must not reappear as a RAW_RX
// fixture, and no valid fixture may claim the RAW_RX stage.
static bool test_no_fake_raw_rx(const std::string& fixtures) {
    std::string err;
    const auto valid = list_sidecars(fixtures + "/valid", err);
    for (const auto& p : valid) {
        CHECK(p.find("raw_rx") == std::string::npos);
        IqFrame f;
        std::string e;
        if (!load_sidecar_frame(p, f, e)) continue;
        CHECK(f.stage != Stage::RawRx);
    }
    return true;
}

// ---------------------------------------------------------------------------
// hotfix1: d2_rec_scale is a D2 recovery scalar, never mixed with a real RF
// gain_mag measurement (which stays invalid/unavailable in these fixtures).
static bool test_rec_scale_not_gain(const std::string& fixtures) {
    std::string err;
    IqFrame bpsk;
    CHECK(load_sidecar_frame(fixtures + "/valid/bpsk_recovered_payload.json", bpsk, err));
    CHECK(bpsk.recovery_metrics_valid);
    CHECK(std::fabs(bpsk.d2_rec_scale - 0.98077767) < 1e-9);
    CHECK(!bpsk.gain_valid);          // not an RF gain_mag measurement
    CHECK(bpsk.gain_mag == 0.0);
    CHECK(!bpsk.cfo_valid && !bpsk.sro_valid);
    CHECK(!bpsk.confidence_valid);    // placeholder confidence

    IqFrame mi;
    CHECK(load_sidecar_frame(fixtures + "/valid/bpsk_clean_model_input.json", mi, err));
    CHECK(!mi.gain_valid && !mi.recovery_metrics_valid);
    CHECK(mi.d2_rec_scale == 0.0);
    CHECK(!mi.confidence_valid);
    return true;
}

// ---------------------------------------------------------------------------
int main(int argc, char** argv) {
    const std::string fixtures = (argc > 1) ? argv[1] : "../fixtures";
    std::printf("constellation UI core tests (Qt-free)\n");
    std::printf("fixtures dir: %s\n\n", fixtures.c_str());

    // Run named tests with a small harness.
    int pass = 0, fail = 0;
    auto run = [&](const char* name, bool ok) {
        std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", name);
        ok ? ++pass : ++fail;
    };

    run("1. CI16 interleaved parse", test_ci16_interleaved());
    run("2. F32 planar parse", test_f32_planar());
    run("3. F32 interleaved parse", test_f32_interleaved());
    run("4. little-endian check", test_little_endian());
    run("5. wrong length rejected", test_wrong_length(fixtures));
    run("6. wrong SHA rejected", test_wrong_sha(fixtures));
    run("7. NaN/Inf rejected", test_nan_inf(fixtures));
    run("8. unknown schema rejected", test_unknown_schema());
    run("9. unknown dtype/layout/stage rejected", test_unknown_dtype_layout());
    run("10. 1024-point coordinate transform", test_transform_1024());
    run("11. deterministic decimation", test_decimation());
    run("12. robust auto-scale", test_auto_scale());
    run("13. empty frame rejected", test_empty_frame());
    run("14. single-point / all-zero no crash", test_single_point_allzero());
    run("extra. SHA-256 known vectors", test_sha256());
    run("extra. real fixture loads (SHA-verified)", test_real_fixtures(fixtures));
    run("extra. SYMBOL_SAMPLED red line", test_red_lines());
    run("extra. flat JSON parser", test_json_parser());
    run("hotfix1. metric validity fields + missing-field compat", test_validity_fields());
    run("hotfix1. valid/negative directory isolation", test_dir_isolation(fixtures));
    run("hotfix1. no fake RAW_RX fixture", test_no_fake_raw_rx(fixtures));
    run("hotfix1. d2_rec_scale not mixed with RF gain", test_rec_scale_not_gain(fixtures));

    std::printf("\nassertions: %d pass, %d fail\n", g_pass, g_fail);
    std::printf("tests: %d pass, %d fail\n", pass, fail);
    return (g_fail == 0 && fail == 0) ? 0 : 1;
}
