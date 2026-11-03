// pilot1_e2e_sim.cpp -- M29-RML24-REALRF-FINETUNE-PILOT1 / line B: 24-frame
// end-to-end save-before-gate simulation (HOST, iCraft-free / libiio-free / SDR-free).
//
// This is the review-gating "24 帧端到端模拟": it loads the REAL per-session
// tx_manifest.tsv through the REAL board loader (pilot1::load_tx_manifest), takes one
// source per class (24 classes -> 24 frames, instance 0 of each), and runs the REAL
// 32-field save path (sdr::Sha256 of real on-disk bytes + pilot1::emit_result_row) for
// each frame.  It does NOT open a Pluto / NPU / TCP control channel -- those are
// board-only; it exercises the exact manifest->save->row contract the board runs and
// the offline judge consumes.
//
// Outcome mix (deterministic, exercises every save-before-gate branch):
//   class 0..19   : valid recovery  (gate_pass=1, correct pred, tensor+logits saved)
//   class 20..22  : gate-reject      (gate_pass=0, failure_token set, tensor STILL saved)
//   class 23      : hard-invalid     (no_sync, no tensor, empty model_input/logits SHA)
//
// Writes to --out-dir: capture_sim_<session>.tsv (32-field header + 24 rows),
// per-frame raw_rx/model_input/logits binaries (where present), and
// capture_sim_summary.json (manifest_sha256 + per-branch counts).
//
// Exit 0 iff every invariant holds (24 rows, 32 fields/row, save-before-gate, SHA
// non-empty exactly where a binary was written).  A wrong manifest / bad field count /
// clipped payload fails closed via the loader before any output.

#include "../board_package/pilot1_capture_schema.hpp"
#include "../board_package/pilot1_tx_manifest.hpp"
#include "../sdr_adapter/sha256.hpp"

#include <cstdint>
#include <cstdio>
#include <exception>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr std::size_t kTensorFloats = 2048;   // [2,1024] f32
constexpr std::size_t kLogitsFloats = 24;     // 24-class logits

std::string get_arg(int argc, char** argv, const char* name, const std::string& dflt) {
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        const std::string prefix = std::string(name) + "=";
        if (a.rfind(prefix, 0) == 0) return a.substr(prefix.size());
        if (a == name && i + 1 < argc) return argv[i + 1];
    }
    return dflt;
}

std::string join_path(const std::string& dir, const std::string& name) {
    if (dir.empty()) return name;
    if (dir.back() == '/' || dir.back() == '\\') return dir + name;
    return dir + "/" + name;
}

// Deterministic synthetic raw RX (int16 interleaved I/Q) that is railed-free for the
// valid/gate-reject frames (so rx_clipped=0) but present for ALL frames (raw_rx is
// always saved, before any gate).  Multipliers chosen so no intermediate overflows int.
std::vector<std::int16_t> synth_raw_rx(int seed) {
    std::vector<std::int16_t> v;
    v.reserve(8192);
    for (int i = 0; i < 8192; ++i) {
        const int x = (i * 1103 + seed * 123) % 2001 - 1000;  // |x|<=1000, no overflow
        v.push_back(static_cast<std::int16_t>(x));
    }
    return v;
}

std::vector<float> synth_tensor(int seed) {
    std::vector<float> v(kTensorFloats);
    for (std::size_t i = 0; i < kTensorFloats; ++i)
        v[i] = static_cast<float>((static_cast<int>(i + static_cast<std::size_t>(seed)) % 1000) - 500) / 500.0f;
    return v;
}

std::vector<float> synth_logits(int seed) {
    std::vector<float> v(kLogitsFloats, -10.0f);
    v[static_cast<std::size_t>(seed) % kLogitsFloats] = 5.0f;
    return v;
}

std::string write_and_sha(const std::string& path, const void* data, std::size_t bytes) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("e2e_sim: cannot open " + path);
    f.write(static_cast<const char*>(data), static_cast<std::streamsize>(bytes));
    f.flush();
    if (!f) throw std::runtime_error("e2e_sim: write failed " + path);
    return sdr::Sha256::hex(data, bytes);
}

int run(int argc, char** argv) {
    const std::string manifest_path = get_arg(argc, argv, "--tx-manifest", "");
    const std::string out_dir = get_arg(argc, argv, "--out-dir", "");
    if (manifest_path.empty() || out_dir.empty()) {
        std::fprintf(stderr, "usage: pilot1_e2e_sim --tx-manifest=<tsv> --out-dir=<dir>\n");
        return 2;
    }
    std::filesystem::create_directories(out_dir);

    // REAL loader: fails closed on a malformed / clipped / wrong-count manifest.
    const std::vector<pilot1::TxManifestRow> rows = pilot1::load_tx_manifest(manifest_path);
    if (rows.size() != pilot1::kSamplesPerSession) {
        std::fprintf(stderr, "e2e_sim: manifest has %zu rows (want %zu)\n",
                     rows.size(), pilot1::kSamplesPerSession);
        return 1;
    }
    const std::string session = rows.front().session_id;

    std::string manifest_sha;
    {
        bool ok = false;
        manifest_sha = sdr::sha256_hex_file(manifest_path, &ok);
        if (!ok || manifest_sha.size() != 64) {
            std::fprintf(stderr, "e2e_sim: cannot hash manifest %s\n", manifest_path.c_str());
            return 1;
        }
    }

    const std::string tsv_path = join_path(out_dir, "capture_sim_" + session + ".tsv");
    std::ofstream tsv(tsv_path, std::ios::binary);
    if (!tsv) throw std::runtime_error("e2e_sim: cannot open " + tsv_path);
    tsv << pilot1::result_tsv_header() << "\n";

    std::size_t valid = 0, gate_reject = 0, hard_invalid = 0;
    for (int ci = 0; ci < static_cast<int>(pilot1::kClassCount); ++ci) {
        // one source per class: instance 0 of each class (manifest is source_id-sorted).
        const pilot1::TxManifestRow& row = rows[static_cast<std::size_t>(ci) * 10];
        {
            // 3-col manifest has no class_index; derive the class from the source_id
            // (s1_c{ci:02d}_i00) to keep the per-class outcome mix deterministic.
            int sn = 0, rci = 0, inst = 0;
            if (!pilot1::valid_source_id_format(row.source_id, &sn, &rci, &inst) ||
                rci != ci || inst != 0) {
                std::fprintf(stderr, "e2e_sim: class order drift at ci=%d (row=%s)\n",
                             ci, row.source_id.c_str());
                return 1;
            }
        }

        // Deterministic outcome per class: 0..19 valid, 20..22 gate-reject, 23 hard-invalid.
        const bool is_hard = (ci == 23);
        const bool is_gate_reject = (ci >= 20 && ci < 23);
        const bool is_valid = (!is_hard && !is_gate_reject);

        // save-before-gate: raw_rx is ALWAYS written (unconditional first save).
        const std::vector<std::int16_t> rx = synth_raw_rx(ci);
        const std::string raw_rx_sha = write_and_sha(
            join_path(out_dir, row.source_id + ".raw_rx.i16"), rx.data(), rx.size() * 2);

        std::string model_input_sha, logits_sha, pred1, pred2;
        if (!is_hard) {
            const std::vector<float> tensor = synth_tensor(ci);
            const std::vector<float> logits = synth_logits(ci);
            model_input_sha = write_and_sha(
                join_path(out_dir, row.source_id + ".model_input.bin"),
                tensor.data(), tensor.size() * sizeof(float));
            logits_sha = write_and_sha(
                join_path(out_dir, row.source_id + ".logits.bin"),
                logits.data(), logits.size() * sizeof(float));
            pred1 = std::to_string(ci);
            pred2 = std::to_string(ci);
        }

        pilot1::CaptureRow r;
        r.session_id = row.session_id;
        r.source_id = row.source_id;
        r.tx_payload_sha256 = row.tx_payload_sha256;
        // 真值列板端置空（评审 39e5 Blocker 2）：class_index/class_name/dataset_index/
        // split/source_iq_sha256/label 离线按 source_id 回填。
        r.raw_rx_sha256 = raw_rx_sha;
        r.model_input_sha256 = model_input_sha;
        r.logits_sha256 = logits_sha;
        r.digital_pred = "";               // Host-side offline backfill
        r.digital_label_correct = "";
        r.board_pred1 = pred1;
        r.board_pred2 = pred2;
        r.capture_ok = is_hard ? "0" : "1";
        r.no_sync = is_hard ? "1" : "0";
        r.rx_clipped = "0";
        r.hard_invalid = is_hard ? "1" : "0";
        r.gate_pass = is_valid ? "1" : "0";
        r.failure_token = is_hard ? "TRAINING_NOT_FOUND"
                                  : (is_gate_reject ? "PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH" : "");
        r.coarse_cfo_hz = is_hard ? "" : "0";
        r.fractional_timing = is_hard ? "" : "0.000000";
        r.timing_offset = is_hard ? "" : "8192";
        r.corr = is_hard ? "" : "0.990000";
        r.training_residual = is_hard ? "" : "0.050000";
        r.training_residual_rel = is_hard ? "" : (is_gate_reject ? "0.120000" : "0.050000");
        r.a_real = is_hard ? "" : "1.000000";
        r.a_imag = is_hard ? "" : "0.000000";
        r.b_real = is_hard ? "" : "0.000000";
        r.b_imag = is_hard ? "" : "0.000000";

        // REAL 32-field emit.
        pilot1::emit_result_row(tsv, r);

        if (is_hard) ++hard_invalid;
        else if (is_gate_reject) ++gate_reject;
        else ++valid;

        // save-before-gate invariant: a non-hard frame must have tensor + pred saved
        // even when gate-rejected.
        if (!is_hard && (model_input_sha.size() != 64 || logits_sha.size() != 64 ||
                         pred1.empty() || pred2.empty())) {
            std::fprintf(stderr, "e2e_sim: save-before-gate violated at ci=%d\n", ci);
            return 1;
        }
        if (is_hard && (!model_input_sha.empty() || !logits_sha.empty())) {
            std::fprintf(stderr, "e2e_sim: hard-invalid leaked tensor SHA at ci=%d\n", ci);
            return 1;
        }
        if (raw_rx_sha.size() != 64) {
            std::fprintf(stderr, "e2e_sim: raw_rx SHA missing at ci=%d\n", ci);
            return 1;
        }
    }
    tsv.close();

    const std::string summary_path = join_path(out_dir, "capture_sim_summary.json");
    {
        std::ofstream f(summary_path, std::ios::binary);
        f << "{\n"
          << "  \"token\":\"M29_RML24_REALRF_FINETUNE_PILOT1_E2E_SIM\",\n"
          << "  \"session\":\"" << session << "\",\n"
          << "  \"manifest_sha256\":\"" << manifest_sha << "\",\n"
          << "  \"frames\":24,\n"
          << "  \"valid\":" << valid << ",\n"
          << "  \"gate_reject\":" << gate_reject << ",\n"
          << "  \"hard_invalid\":" << hard_invalid << ",\n"
          << "  \"result_tsv\":\"capture_sim_" << session << ".tsv\"\n"
          << "}\n";
    }

    std::printf("PILOT1_E2E_SIM session=%s frames=24 valid=%zu gate_reject=%zu "
                "hard_invalid=%zu manifest_sha256=%s\n",
                session.c_str(), valid, gate_reject, hard_invalid, manifest_sha.c_str());
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        return run(argc, argv);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "PILOT1_E2E_SIM FAIL: %s\n", e.what());
        return 1;
    }
}
