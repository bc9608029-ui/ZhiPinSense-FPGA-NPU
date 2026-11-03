// board_gate8_ui.cpp -- Gate 8: results -> UI JSONL (task 39e5 §七/§八).
//
// Proves the twelve-class ResultFrame -> UI JSON-lines link WITHOUT the SDR or
// the NPU: it reads a logits table (default deployment_golden/expected_logits.tsv,
// one `index` + 12 logits per line), builds a rf::ResultFrame for each via
// chain::fill_result(), and emits the §八 record through ui::result_frame_v2_line()
// to a ui::Sink (stdout, and optionally a Unix socket via --sock).
//
// The gate then VALIDATES every emitted line:
//   1. well-formed JSON object (balanced braces, starts/ends with { } ),
//   2. `"type":"result"` present,
//   3. argmax_idx / argmax_class match the logits (self-consistency),
//   4. probabilities sum to ~1, class_count==12, version tag present,
//   5. model_sha (provenance) present when --model-sha given.
//
// This is the formatting/labeling proof the HDMI/UI consumer depends on; the live
// SDR->NPU->UI flow is Gate 9.  iCraft-free, libiio-free (host-testable on WSL).
//
// Exit 0/1 = pass/fail.  Build via build_on_board.sh (no backend link needed).

#include "board_common.hpp"
#include "chain_common.hpp"
#include "unix_socket_sink.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::vector<std::string> split_tsv(const std::string& line) {
    std::vector<std::string> f;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = line.find('\t', start);
        if (pos == std::string::npos) { f.push_back(line.substr(start)); break; }
        f.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    return f;
}

// Minimal structural JSON-object check (the v2 record is hand-built, flat, and
// value-safe, so balanced-braces + required-field presence is a strong check).
bool well_formed_object(const std::string& line) {
    if (line.size() < 2 || line.front() != '{' || line.back() != '}')
        return false;
    int depth = 0;
    bool in_str = false, esc = false;
    for (char c : line) {
        if (esc) { esc = false; continue; }
        if (in_str) {
            if (c == '\\') esc = true;
            else if (c == '"') in_str = false;
            continue;
        }
        if (c == '"') in_str = true;
        else if (c == '{' || c == '[') ++depth;
        else if (c == '}' || c == ']') --depth;
        if (depth < 0) return false;
    }
    return !in_str && depth == 0;
}

bool validate_line(const std::string& line, const rf::ResultFrame& r,
                   const std::string& model_sha, std::string* why) {
    if (!well_formed_object(line)) { if (why) *why = "malformed_json"; return false; }
    if (line.find("\"type\":\"result\"") == std::string::npos) {
        if (why) *why = "missing_type";
        return false;
    }
    if (line.find("\"argmax_idx\":" + std::to_string(r.argmax_idx)) == std::string::npos) {
        if (why) *why = "argmax_idx_mismatch";
        return false;
    }
    if (line.find("\"argmax_class\":\"" + r.argmax_class + "\"") == std::string::npos) {
        if (why) *why = "argmax_class_mismatch";
        return false;
    }
    if (r.class_count != 12) { if (why) *why = "class_count"; return false; }
    if (r.version != "12class-chain-v1") { if (why) *why = "version_tag"; return false; }
    if (r.probabilities.size() != static_cast<std::size_t>(r.class_count)) {
        if (why) *why = "probabilities_width";
        return false;
    }
    double psum = 0.0;
    for (float p : r.probabilities) psum += static_cast<double>(p);
    if (std::fabs(psum - 1.0) > 1e-3) { if (why) *why = "probabilities_sum"; return false; }
    if (!model_sha.empty() && r.model_sha != model_sha) {
        if (why) *why = "model_sha";
        return false;
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();

    const std::string logits_tsv = board::get_opt(argc, argv, "--logits-tsv",
                                                  "deployment_golden/expected_logits.tsv");
    const std::string model_sha = board::get_opt(argc, argv, "--model-sha", "");
    const std::string sock_path = board::get_opt(argc, argv, "--sock", "");
    const std::size_t count = static_cast<std::size_t>(board::opt_u64(argc, argv, "--count", 240));

    // Read the logits table.
    std::ifstream in(logits_tsv.c_str());
    if (!in)
        return (board::emit("gate8_ui", false, "error=cannot_open_logits_tsv:" + logits_tsv), 1);
    std::vector<std::vector<float>> all_logits;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        const std::vector<std::string> f = split_tsv(line);
        if (f.size() < 13) continue;   // index + 12 logits
        std::vector<float> lg(12);
        for (int c = 0; c < 12; ++c) lg[static_cast<std::size_t>(c)] = std::strtof(f[1 + c].c_str(), nullptr);
        all_logits.push_back(lg);
    }
    in.close();
    if (all_logits.empty())
        return (board::emit("gate8_ui", false, "error=empty_logits_tsv:" + logits_tsv), 1);

    const cat::Contract contract = chain::contract_12();
    ui::StdoutSink out;
    ui::UnixSocketSink sock(sock_path);

    const std::size_t n = count < all_logits.size() ? count : all_logits.size();
    std::size_t emitted = 0, valid = 0;
    std::string detail;

    for (std::size_t i = 0; i < n; ++i) {
        if (board::g_stop_requested) break;
        rf::ResultFrame r;
        r.frame_id = static_cast<std::uint64_t>(i + 1);
        r.timestamp_us = static_cast<std::uint64_t>(i + 1) * 8000ULL;   // 128 kHz frame period
        r.source = "fpga_npu";
        r.mock = false;
        chain::fill_result(r, all_logits[i], contract, model_sha,
                           std::numeric_limits<double>::quiet_NaN());

        const std::string rec = ui::result_frame_v2_line(r);
        out.write(rec);
        if (sock.enabled()) sock.write(rec);

        std::string why;
        ++emitted;
        if (validate_line(rec, r, model_sha, &why)) ++valid;
        else detail += " frame_" + std::to_string(i + 1) + ":" + why;
    }

    const bool pass = (emitted == n) && (valid == emitted);
    detail = " samples=" + std::to_string(emitted) + "/" + std::to_string(n) +
             " valid=" + std::to_string(valid) +
             " class_count=" + std::to_string(contract.class_count) +
             " version=12class-chain-v1" +
             " model_sha=" + (model_sha.empty() ? std::string("<none>") : model_sha) +
             " sock=" + (sock.enabled() ? sock_path : std::string("<stdout-only>")) +
             " sock_errors=" + std::to_string(sock.error_count()) + detail;
    if (emitted != n) detail += " (count_short)";
    if (valid != emitted) detail += " (invalid_frames)";

    board::emit("gate8_ui", pass, detail);
    return pass ? 0 : 1;
}
