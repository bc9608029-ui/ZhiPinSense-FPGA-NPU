// test_iq_rf_loopback_23class.cpp -- host tests for Stage H-F / Route F fix9
// Task G/H (the 23-class physical-RF closed loop), the pieces that are pure logic
// and iCraft-free.  The NPU inference itself is board-only; everything the host can
// exercise -- the D2 sidecar loader, the D2 RF restore, the --rf-tx-target-rms
// scaling, the classification-window selection, and the 24->23 merge -- is covered
// here so the board runner's failure modes are pinned BEFORE a board run.
//
// Covered (no NPU, no libiio):
//   * load_d2_sidecar: parses route_d2_rf_manifest.tsv + verifies the ci16 SHA/size
//     and the [2,1024] recovered-tensor SHA/size, fail-closed on split_role /
//     deployed-class-mapping / SHA / sample-rate / path-safety / missing tensor;
//   * the 24->23 kSourceToDeployed mapping is a surjection onto 0..22 with exactly
//     the AM-SSB slot (17) double-covered (sources 17 and 18);
//   * apply_d2_restore_to_stream: x d2_rec_scale + add DC LAST (the DC was removed
//     before TX so it is not rotated by the RF gain);
//   * transfer_one_file_rf with --rf-tx-target-rms (Task D): no-op when target==0,
//     scales up when native RMS < target, refuses to scale into a clip (tx_clip_post,
//     tx_scale stays 1.0, bytes unchanged -- no silent saturation);
//   * select_classification_window finds the reference-aligned window;
//   * merge_logits_23 / merge_predict (AM-SSB fold + fail-closed on non-finite);
//   * the D2 restore end-to-end: unit-RMS AC -> RF gain -> ONE global inverse gain
//     -> d2 restore -> select_classification_window -> corr ~ 1 against the original.

#include "../board_package/iq_digital_loopback.hpp"
#include "../board_package/iq_rf_loopback.hpp"
#include "../board_package/iq_rf_loopback_transfer.hpp"
#include "../board_package/rml23_merged.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

constexpr double kPi = 3.141592653589793238462643383279502884;

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

// ---- deterministic waveforms (LCG, same as test_iq_rf_loopback.cpp) ------------

std::vector<std::int16_t> make_prbs(std::size_t P, int A, std::uint32_t seed) {
    std::vector<std::int16_t> iq(P * 2);
    std::uint32_t s = seed ? seed : 0x9e3779b9u;
    auto bit = [&s]() -> int {
        s = s * 1664525u + 1013904223u;
        return static_cast<int>((s >> 24) & 1u);
    };
    for (std::size_t k = 0; k < P; ++k) {
        iq[k * 2 + 0] = static_cast<std::int16_t>(bit() ? A : -A);
        iq[k * 2 + 1] = static_cast<std::int16_t>(bit() ? A : -A);
    }
    return iq;
}

#if defined(__unix__) || defined(__APPLE__)
std::string make_tmp_dir(const char* stem) {
    const std::string base = "/tmp/" + std::string(stem) + "_" + std::to_string(::getpid());
    ::mkdir(base.c_str(), 0700);
    return base;
}

std::string write_ci16(const std::string& dir, const std::string& name,
                       const std::vector<std::int16_t>& iq) {
    const std::string path = dir + "/" + name;
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(iq.data()),
            static_cast<std::streamsize>(iq.size() * sizeof(std::int16_t)));
    f.close();
    return sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
}

std::string write_tensor(const std::string& dir, const std::string& name,
                         const std::vector<float>& t) {
    const std::string path = dir + "/" + name;
    std::ofstream f(path, std::ios::binary);
    f.write(reinterpret_cast<const char*>(t.data()),
            static_cast<std::streamsize>(t.size() * sizeof(float)));
    f.close();
    return sdr::Sha256::hex(t.data(), t.size() * sizeof(float));
}

void write_manifest(const std::string& dir, const std::vector<std::string>& rows) {
    const std::string path = dir + "/route_d2_rf_manifest.tsv";
    std::ofstream f(path);
    f << "sample_index\tsource_index\traw24_class\tdeployed23_class\tmodulation"
         "\tsnr_db\tsplit_role\tglobal_K\toriginal_dc_i\toriginal_dc_q\tac_rms"
         "\trec_scale\tcomplex_count\tsample_rate\ttx_rms\ttx_peak\tclip_count"
         "\tedge_policy\tguard\toriginal_sha256\tquantized_sha256"
         "\trecovered_tensor_sha256\tquantized_file\trecovered_tensor_file\n";
    for (const auto& r : rows) f << r << "\n";
}

// Write the D2 fixture files (one ci16 of 128 complex, one [2,1024] fp32 tensor)
// under fixed names and return their SHAs.  The manifest rows reference these by
// name; a test that mutates the row's quantized_file/recovered_tensor_file column
// still has the files on disk under the fixed names so cleanup works.
struct D2Shas { std::string ci16; std::string tensor; };

D2Shas write_d2_files(const std::string& dir) {
    D2Shas s;
    const std::vector<std::int16_t> iq = make_prbs(128, 2048, 1);
    s.ci16 = write_ci16(dir, "q.ci16", iq);
    std::vector<float> t(chain::kTensorFloats);
    for (std::size_t k = 0; k < t.size(); ++k)
        t[k] = static_cast<float>(std::sin(static_cast<double>(k) * 0.01));
    s.tensor = write_tensor(dir, "t.bin", t);
    return s;
}

std::vector<std::string> default_d2_fields(const std::string& ci16_sha,
                                           const std::string& tensor_sha) {
    const std::string original_sha(64, 'a');
    return {
        "0", "7", "18", "17", "AM-SSB-SC", "20.0", "calibration", "2048",
        "0.125", "-0.0625", "0.5", "0.5", "128", "2560000", "2048", "3200",
        "0", "zero_guard", "832", original_sha, ci16_sha, tensor_sha,
        "q.ci16", "t.bin",
    };
}

std::string join_tab(const std::vector<std::string>& f) {
    std::string s;
    for (std::size_t i = 0; i < f.size(); ++i) {
        if (i) s += '\t';
        s += f[i];
    }
    return s;
}

void rm_fixture(const std::string& dir) {
    ::unlink((dir + "/q.ci16").c_str());
    ::unlink((dir + "/t.bin").c_str());
    ::unlink((dir + "/route_d2_rf_manifest.tsv").c_str());
    ::rmdir(dir.c_str());
}

pluto::DataFormatInfo identity_tx_fmt() {
    pluto::DataFormatInfo f;
    f.length_bits = 16;
    f.bits = 16;
    f.shift = 0;
    f.is_signed = true;
    f.is_fully_defined = true;
    return f;
}
#endif

// ---- 1. load_d2_sidecar: valid manifest parses (calibration + holdout) --------

void test_d2_sidecar_parses_valid() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_d2_valid");
    const D2Shas s = write_d2_files(dir);
    std::vector<std::string> r0 = default_d2_fields(s.ci16, s.tensor);
    // r0: source 18 -> deployed 17 (AM-SSB fold), calibration.
    std::vector<std::string> r1 = r0;
    r1[0] = "1"; r1[1] = "8"; r1[2] = "3"; r1[3] = "3"; r1[4] = "BPSK";
    r1[6] = "holdout";
    r1[8] = "0.25"; r1[9] = "0.125"; r1[11] = "0.75";
    write_manifest(dir, { join_tab(r0), join_tab(r1) });

    const auto v = iqdloop::load_d2_sidecar(dir);
    check(v.size() == 2, "d2-valid: two rows loaded");
    check(v[0].is_calibration && v[0].split_role == "calibration",
          "d2-valid: row0 calibration");
    check(v[0].source_class == 18 && v[0].deployed_class == 17,
          "d2-valid: row0 source 18 -> deployed 17 (AM-SSB fold)");
    check(v[0].modulation == "AM-SSB-SC", "d2-valid: row0 modulation");
    check(std::fabs(v[0].original_dc_i - 0.125) < 1e-9 &&
          std::fabs(v[0].original_dc_q - (-0.0625)) < 1e-9,
          "d2-valid: row0 dc_i/dc_q extracted");
    check(std::fabs(v[0].d2_rec_scale - 0.5) < 1e-9, "d2-valid: row0 rec_scale");
    check(v[0].complex_count == 128 && v[0].sample_rate == iqdloop::kFrozenFsIn,
          "d2-valid: row0 complex_count + sample_rate");
    check(v[0].file_name == "q.ci16", "d2-valid: row0 quantized_file");
    check(v[0].original_sha256 == std::string(64, 'a') &&
              v[0].sha256 == s.ci16 && v[0].original_sha256 != v[0].sha256,
          "d2-valid: original and quantized SHA identities remain distinct");
    check(v[0].recovered_tensor_file == "t.bin",
          "d2-valid: row0 recovered_tensor_file");
    check(v[0].has_d2_restore && v[0].has_recovered_ref,
          "d2-valid: row0 has_d2_restore + has_recovered_ref");
    check(!v[1].is_calibration && v[1].split_role == "holdout",
          "d2-valid: row1 holdout");
    check(v[1].source_class == 3 && v[1].deployed_class == 3,
          "d2-valid: row1 source 3 -> deployed 3");
    check(std::fabs(v[1].d2_rec_scale - 0.75) < 1e-9, "d2-valid: row1 rec_scale");
    rm_fixture(dir);
#else
    (void)0;
#endif
}

// ---- 2. the 24->23 mapping is a surjection with exactly one double-covered slot ----

void test_d2_sidecar_mapping_bijection() {
    int hit[rml23::kDeployedClassCount] = {0};
    for (int s = 0; s < rml23::kSourceClassCount; ++s) {
        const int d = rml23::kSourceToDeployed[s];
        check(d >= 0 && d < rml23::kDeployedClassCount,
              "mapping: every source maps into [0,22]");
        ++hit[d];
    }
    bool all_reached = true;
    int doubled = 0;
    for (int d = 0; d < rml23::kDeployedClassCount; ++d) {
        if (hit[d] < 1) all_reached = false;
        if (hit[d] == 2) ++doubled;
    }
    check(all_reached, "mapping: every deployed slot 0..22 is reached");
    check(doubled == 1 && hit[rml23::kAmSsbDeployed] == 2,
          "mapping: exactly the AM-SSB slot (17) is double-covered");
}

// ---- 3-8. load_d2_sidecar fail-closed rejections -----------------------------

void test_d2_sidecar_rejects_bad_split_role() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_d2_badrole");
    const D2Shas s = write_d2_files(dir);
    auto f = default_d2_fields(s.ci16, s.tensor);
    f[6] = "validation";
    write_manifest(dir, { join_tab(f) });
    bool threw = false;
    try { iqdloop::load_d2_sidecar(dir); } catch (const std::exception&) { threw = true; }
    check(threw, "d2-reject: unexpected split_role throws");
    rm_fixture(dir);
#else
    (void)0;
#endif
}

void test_d2_sidecar_rejects_mapping_mismatch() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_d2_badmap");
    const D2Shas s = write_d2_files(dir);
    auto f = default_d2_fields(s.ci16, s.tensor);
    f[3] = "16";   // source 18 -> deployed 16 contradicts kSourceToDeployed
    write_manifest(dir, { join_tab(f) });
    bool threw = false;
    try { iqdloop::load_d2_sidecar(dir); } catch (const std::exception&) { threw = true; }
    check(threw, "d2-reject: deployed23 != mapping throws");
    rm_fixture(dir);
#else
    (void)0;
#endif
}

void test_d2_sidecar_rejects_sha_mismatch() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_d2_badsha");
    const D2Shas s = write_d2_files(dir);
    auto f = default_d2_fields(s.ci16, s.tensor);
    f[20] = std::string(64, 'a');   // well-formed 64-hex, wrong content
    write_manifest(dir, { join_tab(f) });
    bool threw = false;
    try { iqdloop::load_d2_sidecar(dir); } catch (const std::exception&) { threw = true; }
    check(threw, "d2-reject: quantized_sha256 mismatch throws");
    rm_fixture(dir);
#else
    (void)0;
#endif
}

void test_d2_sidecar_rejects_bad_sample_rate() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_d2_badrate");
    const D2Shas s = write_d2_files(dir);
    auto f = default_d2_fields(s.ci16, s.tensor);
    f[13] = "2500000";
    write_manifest(dir, { join_tab(f) });
    bool threw = false;
    try { iqdloop::load_d2_sidecar(dir); } catch (const std::exception&) { threw = true; }
    check(threw, "d2-reject: sample_rate != 2.56M throws");
    rm_fixture(dir);
#else
    (void)0;
#endif
}

void test_d2_sidecar_rejects_unsafe_path() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_d2_unsafe");
    const D2Shas s = write_d2_files(dir);
    auto f = default_d2_fields(s.ci16, s.tensor);
    f[22] = "../evil.ci16";   // path traversal in quantized_file
    write_manifest(dir, { join_tab(f) });
    bool threw = false;
    try { iqdloop::load_d2_sidecar(dir); } catch (const std::exception&) { threw = true; }
    check(threw, "d2-reject: unsafe quantized_file throws");
    rm_fixture(dir);
#else
    (void)0;
#endif
}

void test_d2_sidecar_rejects_missing_tensor() {
#if defined(__unix__) || defined(__APPLE__)
    const std::string dir = make_tmp_dir("rml23_d2_notensor");
    const D2Shas s = write_d2_files(dir);
    auto f = default_d2_fields(s.ci16, s.tensor);
    f[23] = "missing.bin";   // safe name but no such file
    write_manifest(dir, { join_tab(f) });
    bool threw = false;
    try { iqdloop::load_d2_sidecar(dir); } catch (const std::exception&) { threw = true; }
    check(threw, "d2-reject: missing recovered tensor throws");
    rm_fixture(dir);
#else
    (void)0;
#endif
}

// ---- 9. apply_d2_restore_to_stream: x rec_scale then + DC ---------------------

void test_apply_d2_restore() {
    // frame_complex=2 -> each frame is [I0,I1,Q0,Q1]; two frames = 8 floats.
    std::vector<float> s = {1, 2, 3, 4, 5, 6, 7, 8};
    iqdloop::apply_d2_restore_to_stream(s, 2, /*dc_i=*/10.0, /*dc_q=*/100.0,
                                        /*rec_scale=*/2.0);
    const float want[8] = {12, 14, 106, 108, 20, 22, 114, 116};
    bool ok = true;
    for (std::size_t k = 0; k < s.size(); ++k)
        if (std::fabs(s[k] - want[k]) > 1e-4f) ok = false;
    check(ok, "d2-restore: I*2+10 and Q*2+100 across both frames");
}

// ---- 10. apply_d2_restore_to_stream: identity + partial trailing frame ---------

void test_apply_d2_restore_identity_and_partial() {
    std::vector<float> s = {1, 2, 3, 4};
    iqdloop::apply_d2_restore_to_stream(s, 2, 0.0, 0.0, 1.0);
    check(s[0] == 1.0f && s[3] == 4.0f, "d2-restore: identity (scale 1, dc 0) no-op");

    // 6 floats, frame_complex=2 -> only the first full frame (4 floats) is touched;
    // the trailing partial frame is left alone (fail-safe, no out-of-range write).
    std::vector<float> p = {1, 2, 3, 4, 5, 6};
    iqdloop::apply_d2_restore_to_stream(p, 2, 10.0, 100.0, 2.0);
    check(p[4] == 5.0f && p[5] == 6.0f,
          "d2-restore: trailing partial frame untouched");
    check(std::fabs(p[0] - 12.0f) < 1e-4f && std::fabs(p[3] - 108.0f) < 1e-4f,
          "d2-restore: full frame restored");
}

// ---- 11-13. transfer_one_file_rf --rf-tx-target-rms (Task D) ------------------

void run_transfer_target_rms_noop() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_23c_noop");
    const auto iq = make_prbs(N, 900, 101);
    const std::string sha = write_ci16(dir, "rf.ci16", iq);
    const std::string path = dir + "/rf.ci16";
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 1.0; dev.rf_phase_deg = 0.0; dev.rf_delay = 0;
    dev.rf_noise_rms = 0.0;
    dev.tx_fmt_ = idfmt;

    const auto tr = iqrfloop_run::transfer_one_file_rf(
        dev, path, N, sha, 2400000000ULL, 10.0, -40.0, 16384, 0, 4096, nullptr,
        idfmt, idfmt, /*target_rms=*/0.0);
    check(tr.tx_target_rms == 0.0, "rms-noop: tx_target_rms == 0");
    check(tr.tx_native_rms > 0.0, "rms-noop: native rms recorded");
    check(tr.tx_scale == 1.0, "rms-noop: tx_scale == 1.0");
    check(!tr.tx_clip_pre && !tr.tx_clip_post, "rms-noop: no clip");
    check(tr.tx_sha_pre == sha, "rms-noop: tx_sha_pre == frozen sha");
    check(tr.tx_sha_post == sha, "rms-noop: tx_sha_post == frozen sha");
    check(tr.tx_sha_post == tr.tx_sha_pre, "rms-noop: post == pre");
    check(tr.tx_dma_payload_ok, "rms-noop: tx_dma_payload_ok");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void run_transfer_target_rms_scale_up() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_23c_scaleup");
    const auto iq = make_prbs(N, 1000, 102);   // native RMS == 1000
    const std::string sha = write_ci16(dir, "rf.ci16", iq);
    const std::string path = dir + "/rf.ci16";
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 1.0; dev.rf_phase_deg = 0.0; dev.rf_delay = 0;
    dev.rf_noise_rms = 0.0;
    dev.tx_fmt_ = idfmt;

    const auto tr = iqrfloop_run::transfer_one_file_rf(
        dev, path, N, sha, 2400000000ULL, 10.0, -40.0, 16384, 0, 4096, nullptr,
        idfmt, idfmt, /*target_rms=*/2000.0);
    check(tr.tx_target_rms == 2000.0, "rms-up: tx_target_rms recorded");
    check(std::fabs(tr.tx_native_rms - 1000.0) < 1.0, "rms-up: native rms ~ 1000");
    check(std::fabs(tr.tx_scale - 2.0) < 1e-6, "rms-up: tx_scale ~ 2.0");
    check(!tr.tx_clip_pre && !tr.tx_clip_post, "rms-up: no clip (peak 2000 << 32767)");
    check(tr.tx_peak_post > tr.tx_peak_pre, "rms-up: post peak > pre peak");
    check(tr.tx_sha_post != sha, "rms-up: post SHA differs from frozen SHA");
    check(tr.tx_dma_payload_ok, "rms-up: payload matches the scaled bytes");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

void run_transfer_target_rms_refuse_clip() {
#if defined(__unix__) || defined(__APPLE__)
    const std::size_t N = 2048;
    const std::string dir = make_tmp_dir("rml23_23c_clip");
    const auto iq = make_prbs(N, 20000, 103);   // native RMS/peak == 20000
    const std::string sha = write_ci16(dir, "rf.ci16", iq);
    const std::string path = dir + "/rf.ci16";
    const pluto::DataFormatInfo idfmt = identity_tx_fmt();

    pluto::FakePlutoDevice dev;
    dev.open();
    dev.rf_echo_mode = true;
    dev.rf_gain = 1.0; dev.rf_phase_deg = 0.0; dev.rf_delay = 0;
    dev.rf_noise_rms = 0.0;
    dev.tx_fmt_ = idfmt;

    const auto tr = iqrfloop_run::transfer_one_file_rf(
        dev, path, N, sha, 2400000000ULL, 10.0, -40.0, 16384, 0, 4096, nullptr,
        idfmt, idfmt, /*target_rms=*/40000.0);   // 2x -> peak 40000 >= 32767
    check(tr.tx_clip_post, "rms-clip: predicted clip -> tx_clip_post == true");
    check(!tr.tx_clip_pre, "rms-clip: source bytes were not pre-clipped");
    check(tr.tx_scale == 1.0, "rms-clip: tx_scale stays 1.0 (refused)");
    check(tr.tx_sha_post == sha, "rms-clip: bytes unchanged (post == pre == frozen)");
    check(tr.tx_peak_post > 32767.0, "rms-clip: predicted post peak exceeds the rail");

    ::unlink(path.c_str());
    ::rmdir(dir.c_str());
#else
    (void)0;
#endif
}

// ---- 14. select_classification_window finds the restored frame ----------------

void test_select_window_restored_d2() {
    const std::size_t N = chain::kFrameComplex, F = chain::kTensorFloats;
    std::vector<float> ref(F);
    for (std::size_t k = 0; k < N; ++k) {
        ref[k] = static_cast<float>(std::sin(static_cast<double>(k) * 0.03));
        ref[N + k] = static_cast<float>(std::cos(static_cast<double>(k) * 0.05));
    }
    // frame 0 = zero guard, frame 1 = the reference (the model window the restore
    // must land on), exactly mirroring the D2 zero-guard / valid-region geometry.
    std::vector<float> stream(F * 2, 0.0f);
    std::copy(ref.begin(), ref.end(), stream.begin() + F);

    const auto w = iqdloop::select_classification_window(stream, ref);
    check(w.valid, "window: valid");
    check(w.delay_offset == static_cast<int>(N), "window: delay == 1024 (frame 1)");
    check(w.tensor_corr > 0.999, "window: corr ~ 1 at the restored frame");
    check(w.sha_equal, "window: byte-exact ref selected (sha_equal)");
}

// ---- 15. merge_logits_23: AM-SSB fold + fail-closed ---------------------------

void test_merge_logits_23() {
    float l[rml23::kNpuOutputDim];
    for (int i = 0; i < rml23::kNpuOutputDim; ++i) l[i] = -10.0f;
    l[rml23::kAmSsbSourceWc] = 3.0f;
    l[rml23::kAmSsbSourceSc] = 5.0f;
    float m[rml23::kDeployedClassCount];
    check(rml23::merge_logits_23(l, m), "merge: returns true on finite input");
    check(std::fabs(m[rml23::kAmSsbDeployed] -
                    rml23::logaddexp(3.0f, 5.0f)) < 1e-4f,
          "merge: AM-SSB slot folds WC+SC via logaddexp");
    bool copy_ok = true;
    for (int i = 0; i < rml23::kDeployedClassCount; ++i) {
        if (i == rml23::kAmSsbDeployed) continue;
        if (m[i] != -10.0f) copy_ok = false;
    }
    check(copy_ok, "merge: non-AM-SSB dims copy through unchanged");

    float bad[rml23::kNpuOutputDim];
    for (int i = 0; i < rml23::kNpuOutputDim; ++i) bad[i] = 0.0f;
    bad[3] = std::numeric_limits<float>::quiet_NaN();
    check(!rml23::merge_logits_23(bad, m), "merge: NaN -> false (fail-closed)");
}

// ---- 16. merge_predict: raw24 top1 preserved + merged argmax + fail-closed -----

void test_merge_predict_23() {
    float l[rml23::kNpuOutputDim];
    for (int i = 0; i < rml23::kNpuOutputDim; ++i) l[i] = -10.0f;
    l[rml23::kAmSsbSourceSc] = 5.0f;   // source 18 (max in 24-dim)
    l[rml23::kAmSsbSourceWc] = 3.0f;   // source 17
    l[5] = 4.0f;                       // 8PSK
    rml23::RML23Result r;
    check(rml23::merge_predict(l, &r), "predict: succeeds");
    check(r.valid, "predict: valid");
    check(r.raw_24_top1 == rml23::kAmSsbSourceSc,
          "predict: raw24 top1 preserved (source 18)");
    check(r.merged_23_top1 == rml23::kAmSsbDeployed,
          "predict: merged top1 == 17 (AM-SSB fold wins)");
    check(std::string(r.merged_23_label) == "AM-SSB", "predict: label AM-SSB");
    check(!r.expert_enabled, "predict: no SC/WC expert in this task");

    l[2] = std::numeric_limits<float>::infinity();
    check(!rml23::merge_predict(l, &r), "predict: inf -> false");
    check(!r.valid, "predict: inf -> valid == false");
}

// ---- 17. D2 restore end-to-end (RF gain -> global inverse -> restore -> corr) --

void run_d2_restore_end_to_end() {
    const std::size_t N = chain::kFrameComplex, F = chain::kTensorFloats;

    // Original model-domain reference tensor (deterministic, nonzero DC).
    std::vector<float> ref(F);
    for (std::size_t k = 0; k < N; ++k) {
        const double th = 2.0 * kPi * static_cast<double>(k) / static_cast<double>(N);
        ref[k] = static_cast<float>(
            0.35 + 0.9 * std::sin(7.0 * th) + 0.4 * std::sin(13.0 * th));
        ref[N + k] = static_cast<float>(
            -0.25 + 0.8 * std::cos(5.0 * th) + 0.3 * std::cos(11.0 * th));
    }
    // Build-time DC + unit-RMS AC (the chain(rec_scale=1.0) output decimate(iq/2048)).
    double dc_i = 0.0, dc_q = 0.0;
    for (std::size_t k = 0; k < N; ++k) { dc_i += ref[k]; dc_q += ref[N + k]; }
    dc_i /= N; dc_q /= N;
    double ac_e = 0.0;
    std::vector<float> unit_ac(F);
    for (std::size_t k = 0; k < N; ++k) {
        const double ai = static_cast<double>(ref[k]) - dc_i;
        const double aq = static_cast<double>(ref[N + k]) - dc_q;
        ac_e += ai * ai + aq * aq;
        unit_ac[k] = static_cast<float>(ai);
        unit_ac[N + k] = static_cast<float>(aq);
    }
    const double ac_rms = std::sqrt(ac_e / N);   // d2_rec_scale == ac_rms (K=2048)
    for (std::size_t k = 0; k < F; ++k) unit_ac[k] =
        static_cast<float>(static_cast<double>(unit_ac[k]) / ac_rms);

    // The physical RF path applied an unknown gain A (magnitude + phase).
    const double A_mag = 0.8, A_phase = 30.0;
    const std::complex<double> A = std::polar(A_mag, A_phase * kPi / 180.0);
    std::vector<float> rf_stream = unit_ac;
    for (std::size_t k = 0; k < N; ++k) {
        const std::complex<double> y =
            A * std::complex<double>(unit_ac[k], unit_ac[N + k]);
        rf_stream[k] = static_cast<float>(y.real());
        rf_stream[N + k] = static_cast<float>(y.imag());
    }

    // Calibration subset estimates the ONE global gain (inverse of A).
    const auto g = iqrfloop::estimate_global_gain({A});
    check(g.valid, "d2-e2e: global gain valid");
    check(std::fabs(g.mag - A_mag) < 1e-9, "d2-e2e: median magnitude recovered");
    check(std::fabs(g.phase_deg - A_phase) < 0.5, "d2-e2e: circular-mean phase recovered");
    check(std::fabs(g.k_mag - 1.0 / A_mag) < 1e-9, "d2-e2e: k_mag == 1/A_mag");

    // Undo the RF gain, then D2-restore (x rec_scale + add DC LAST, unrotated).
    iqrfloop::apply_global_gain_to_stream(rf_stream, N, g);
    iqdloop::apply_d2_restore_to_stream(rf_stream, N, dc_i, dc_q, ac_rms);

    const auto w = iqdloop::select_classification_window(rf_stream, ref);
    check(w.valid, "d2-e2e: window valid");
    check(w.delay_offset == 0, "d2-e2e: single frame -> delay 0");
    check(w.tensor_corr > 0.9999, "d2-e2e: restored tensor corr ~ 1 vs original");
    check(w.max_abs_diff < 1e-3, "d2-e2e: restored tensor matches ref to < 1e-3");
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
    std::printf("test_iq_rf_loopback_23class\n");
    run_test("parses_valid", test_d2_sidecar_parses_valid);
    run_test("mapping_bijection", test_d2_sidecar_mapping_bijection);
    run_test("rejects_bad_split_role", test_d2_sidecar_rejects_bad_split_role);
    run_test("rejects_mapping_mismatch", test_d2_sidecar_rejects_mapping_mismatch);
    run_test("rejects_sha_mismatch", test_d2_sidecar_rejects_sha_mismatch);
    run_test("rejects_bad_sample_rate", test_d2_sidecar_rejects_bad_sample_rate);
    run_test("rejects_unsafe_path", test_d2_sidecar_rejects_unsafe_path);
    run_test("rejects_missing_tensor", test_d2_sidecar_rejects_missing_tensor);
    run_test("apply_d2_restore", test_apply_d2_restore);
    run_test("apply_d2_restore_identity_and_partial", test_apply_d2_restore_identity_and_partial);
    run_test("transfer_target_rms_noop", run_transfer_target_rms_noop);
    run_test("transfer_target_rms_scale_up", run_transfer_target_rms_scale_up);
    run_test("transfer_target_rms_refuse_clip", run_transfer_target_rms_refuse_clip);
    run_test("select_window_restored_d2", test_select_window_restored_d2);
    run_test("merge_logits_23", test_merge_logits_23);
    run_test("merge_predict_23", test_merge_predict_23);
    run_test("d2_restore_end_to_end", run_d2_restore_end_to_end);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
