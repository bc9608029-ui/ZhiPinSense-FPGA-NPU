// test_pilot1_capture.cpp -- host tests for the M29-RML24-REALRF-FINETUNE-PILOT1
// board capture headers (line B).  iCraft-free / libiio-free / SDR-free: it exercises
// the EXACT code the board runs for the 32-field save-before-gate TSV schema and the
// 3-col per-session TX manifest loader, plus the phase surface -- not Python dict
// fixtures.  The full runner (pilot1_capture_runner.hpp) needs pluto devices + the TCP
// TX-control channel + the NPU, so it is NOT compiled here; its pure contracts
// (schema + manifest fail-closed) are, and the full runner IS compiled separately by
// syntax_check.sh (pilot1_capture_runner_syntax.cpp) against the iCraft headers.

#include "../board_package/pilot1_capture_schema.hpp"
#include "../board_package/pilot1_tx_manifest.hpp"
#include "../board_package/gate9_phase.hpp"

#include <cstdio>
#include <fstream>
#include <string>

namespace {

int g_pass = 0;
int g_fail = 0;

void check(bool ok, const std::string& what) {
    if (ok) ++g_pass;
    else { ++g_fail; std::printf("  FAIL: %s\n", what.c_str()); }
}

template <typename F>
bool throws(F f) {
    try { f(); } catch (const std::exception&) { return true; }
    return false;
}

std::string sha64(char c) { return std::string(64, c); }

std::string manifest_header() {
    std::string h;
    const char* const* f = pilot1::tx_manifest_fields();
    for (std::size_t i = 0; i < pilot1::kTxManifestFieldCount; ++i) {
        if (i) h += '\t';
        h += f[i];
    }
    return h;
}

std::string manifest_row(int ci, int inst) {
    char sid[16];
    std::snprintf(sid, sizeof(sid), "s1_c%02d_i%02d", ci, inst);
    // 3-col board-public identity manifest: session_id / source_id / tx_payload_sha256.
    return "S1\t" + std::string(sid) + "\t" + sha64('b');
}

std::string valid_manifest_text() {
    std::string out = manifest_header() + "\n";
    for (int ci = 0; ci < 24; ++ci)
        for (int inst = 0; inst < 10; ++inst) {
            out += manifest_row(ci, inst);
            out += '\n';
        }
    return out;
}

std::string write_tmp(const std::string& name, const std::string& content) {
    const std::string path = std::string("bin/") + name;
    std::ofstream f(path, std::ios::binary);
    f << content;
    f.close();
    return path;
}

// --- 32-field schema ---

void test_schema() {
    check(pilot1::kResultFieldCount == 32,
          "schema: kResultFieldCount == 32 (got " +
          std::to_string(pilot1::kResultFieldCount) + ")");

    const std::string hdr = pilot1::result_tsv_header();
    check(pilot1::count_tab_fields(hdr) == 32,
          "schema: header has 32 fields (got " +
          std::to_string(pilot1::count_tab_fields(hdr)) + ")");

    // Header text must carry the exact 32 canonical names.
    check(hdr.find("session_id") != std::string::npos, "schema: header has session_id");
    check(hdr.find("source_iq_sha256") != std::string::npos,
          "schema: header has source_iq_sha256");
    check(hdr.find("digital_pred") != std::string::npos, "schema: header has digital_pred");
    check(hdr.find("b_imag") != std::string::npos, "schema: header has b_imag (last)");

    // A row rendered from an all-empty CaptureRow still emits exactly 32 fields
    // (save-before-gate must never drop columns for a hard-invalid / gate-reject frame).
    pilot1::CaptureRow r;
    const std::string line = pilot1::render_result_row(r);
    check(pilot1::count_tab_fields(line) == 32,
          "schema: empty row still 32 fields (got " +
          std::to_string(pilot1::count_tab_fields(line)) + ")");
}

// --- source_id format ---

void test_source_id_format() {
    int sn = 0, ci = 0, inst = 0;
    check(pilot1::valid_source_id_format("s1_c00_i00", &sn, &ci, &inst) &&
          sn == 1 && ci == 0 && inst == 0,
          "source_id: s1_c00_i00 -> sn=1 ci=0 inst=0");
    check(pilot1::valid_source_id_format("s4_c23_i09", &sn, &ci, &inst) &&
          sn == 4 && ci == 23 && inst == 9,
          "source_id: s4_c23_i09 -> sn=4 ci=23 inst=9");
    check(!pilot1::valid_source_id_format("s0_c00_i00", nullptr, nullptr, nullptr),
          "source_id: reject sn=0");
    check(!pilot1::valid_source_id_format("s5_c00_i00", nullptr, nullptr, nullptr),
          "source_id: reject sn=5");
    check(!pilot1::valid_source_id_format("s1_c24_i00", nullptr, nullptr, nullptr),
          "source_id: reject ci=24");
    check(!pilot1::valid_source_id_format("s1_c00_i10", nullptr, nullptr, nullptr),
          "source_id: reject inst=10");
    check(!pilot1::valid_source_id_format("s1_c00_i0", nullptr, nullptr, nullptr),
          "source_id: reject wrong length (9)");
    check(!pilot1::valid_source_id_format("S1_c00_i00", nullptr, nullptr, nullptr),
          "source_id: reject uppercase S");
}

// --- TX manifest load (valid) ---

void test_load_ok() {
    const std::string path = write_tmp("_pilot1_ok.tsv", valid_manifest_text());
    const std::vector<pilot1::TxManifestRow> rows = pilot1::load_tx_manifest(path);
    check(rows.size() == 240, "manifest: 240 rows (got " +
          std::to_string(rows.size()) + ")");
    check(rows.front().source_id == "s1_c00_i00", "manifest: first source_id");
    check(rows.back().source_id == "s1_c23_i09", "manifest: last source_id");
    check(rows.front().session_id == "S1", "manifest: session S1");
    check(rows.front().tx_payload_sha256 == sha64('b'),
          "manifest: tx_payload_sha256 == 64-hex identity");
    std::remove(path.c_str());
}

// --- TX manifest load (fail-closed) ---

void test_load_fail_closed() {
    // Header mismatch.
    {
        std::string bad = valid_manifest_text();
        const std::string hdr = manifest_header();
        const std::size_t pos = bad.find("session_id");
        bad.replace(pos, 10, "session_idx");
        const std::string p = write_tmp("_pilot1_bad_hdr.tsv", bad);
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: header mismatch throws");
        std::remove(p.c_str());
    }

    // Wrong field count (2 fields: drop last column from header only).
    {
        std::string hdr2 = manifest_header();
        const std::size_t pos = hdr2.rfind('\t');
        hdr2 = hdr2.substr(0, pos);
        std::string bad = hdr2 + "\n" + manifest_row(0, 0) + "\n";
        const std::string p = write_tmp("_pilot1_bad_2col.tsv", bad);
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: 2-col header throws");
        std::remove(p.c_str());
    }

    // Wrong row count (239 rows).
    {
        std::string bad = valid_manifest_text();
        // Drop the last line.
        const std::size_t pos = bad.rfind('\n');
        bad = bad.substr(0, pos);   // remove trailing newline
        const std::size_t pos2 = bad.rfind('\n');
        bad = bad.substr(0, pos2) + "\n";
        const std::string p = write_tmp("_pilot1_bad_239.tsv", bad);
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: 239 rows throws");
        std::remove(p.c_str());
    }

    // Duplicate source_id (duplicate the first row).
    {
        std::string bad = valid_manifest_text();
        const std::string first = manifest_row(0, 0) + "\n";
        bad = manifest_header() + "\n" + first + first;
        const std::string p = write_tmp("_pilot1_dup_sid.tsv", bad);
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: duplicate source_id throws");
        std::remove(p.c_str());
    }

    // Bad session_id (S5).
    {
        std::string line = manifest_row(0, 0);
        line.replace(0, 2, "S5");
        const std::string bad = manifest_header() + "\n" + line + "\n" +
                                manifest_row(0, 1) + "\n";
        const std::string p = write_tmp("_pilot1_bad_sess.tsv", bad);
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: session S5 throws");
        std::remove(p.c_str());
    }

    // Bad tx_payload_sha256 (63 chars).
    {
        std::string line = manifest_row(0, 0);
        const std::size_t pos = line.rfind(sha64('b'));
        line.replace(pos, 64, std::string(63, 'b'));
        const std::string bad = manifest_header() + "\n" + line + "\n" +
                                manifest_row(0, 1) + "\n";
        const std::string p = write_tmp("_pilot1_bad_sha.tsv", bad);
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: 63-char tx_payload_sha256 throws");
        std::remove(p.c_str());
    }

    // Bad source_id (ci=24 -> out of 0..23 range).
    {
        std::string bad = manifest_header() + "\n" +
                          "S1\ts1_c24_i00\t" + sha64('b') + "\n" +
                          manifest_row(0, 1) + "\n";
        const std::string p = write_tmp("_pilot1_bad_sid24.tsv", bad);
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: source_id ci=24 throws");
        std::remove(p.c_str());
    }

    // Empty file.
    {
        const std::string p = write_tmp("_pilot1_empty.tsv", "");
        check(throws([&] { pilot1::load_tx_manifest(p); }),
              "manifest: empty file throws");
        std::remove(p.c_str());
    }
}

// --- phase surface ---

void test_phase_surface() {
    check(gate9::valid_phase("iq-pc-tx-board-rx-24class-finetune-pilot1"),
          "phase: accepts iq-pc-tx-board-rx-24class-finetune-pilot1");
    check(!gate9::valid_phase("iq-pc-tx-board-rx-24class-finetune-pilot1x"),
          "phase: rejects trailing-x near-miss");
    check(!gate9::valid_phase("iq-pc-tx-board-rx-24class-finetune-pilot"),
          "phase: rejects truncated near-miss");
    check(!gate9::valid_phase(""),
          "phase: rejects empty");
    check(gate9::valid_phase("iq-pc-tx-board-rx-24class-bf16-fix10"),
          "phase: still accepts the 24-class dual-SDR phase");
    check(gate9::valid_phase("iq-rf-loopback-24class-bf16-scalarwl"),
          "phase: still accepts the scalarwl phase");
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
    std::printf("test_pilot1_capture\n");
    run_test("schema", test_schema);
    run_test("source_id_format", test_source_id_format);
    run_test("load_ok", test_load_ok);
    run_test("load_fail_closed", test_load_fail_closed);
    run_test("phase_surface", test_phase_surface);
    std::printf("  pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
