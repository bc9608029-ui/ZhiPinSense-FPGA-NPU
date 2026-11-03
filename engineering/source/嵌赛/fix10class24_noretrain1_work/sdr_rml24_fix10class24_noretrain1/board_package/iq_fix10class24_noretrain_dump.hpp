#pragma once

// iq_fix10class24_noretrain_dump.hpp -- fix10class24-noretrain (task 39e5) Phase B:
// the DIAGNOSTIC EXPORT layer for the dual-SDR 24-class BF16 runner.
//
// Two ADDITIVE, default-off switches:
//   --dump-raw24-logits   : for GATED samples only, persist the NPU's raw 24-dim
//                           logits + the exact model input that produced them.
//   --dump-all-rx         : for EVERY sample (gated and gate-refused), persist the
//                           full diagnostic bundle: raw RX, recovery diagnostics,
//                           the model input + 24-dim logits (gated only), the gate
//                           result, and a SHA256SUMS manifest.
//
// Red lines: these switches are strictly additive.  With neither switch passed the
// runner is byte/behavior identical to rxrecovery1 (baseline FULL 6fd93f78...).
// A gate-refused sample dumped by --dump-all-rx records `diagnostic_gate_bypass=1`
// and `production_gate_modified=0`; it never writes RF_PASS / SMOKE_PASS, and its
// host-side provisional logits are NEVER presented as board NPU results.
//
// Layout (per sample):
//   <out_dir>/dump_rx/<source_index>/
//     raw_rx_ci16le.bin              -- interleaved int16 RX capture (--dump-all-rx)
//     recovered_payload_f32le.bin    -- ccr.payload f32 (--dump-all-rx; empty if rec invalid)
//     recovery_diagnostics.json      -- recovery fields + estimate config (--dump-all-rx)
//     model_input_f32le.bin          -- [2,1024] fp32 aligned tensor (gated only)
//     raw24_logits_f32le.bin         -- 24 x fp32 NPU logits (gated only)
//     classification_dump.json       -- source_index / gate result / pred / flags
//     SHA256SUMS.txt                 -- "SHA256  name" for each .bin
//
// Depends only on the existing dump header's helpers + rml24_raw + sha256, so it
// compiles identically on the board and the host, and is unit-testable without the
// NPU / chain / board device.

#include "iq_fix10class24_failed_rx_dump.hpp"  // join_path / json_escape / mkdir_p / write_*
#include "rml24_raw.hpp"                       // rml24::kClassCount / kLabelOrder24

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace iqfix10dump {

// Plain little-endian float32 writer (host byte-order independent).
inline void write_float32_le(const std::string& path, const std::vector<float>& v) {
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    if (!f) throw std::runtime_error("dump: cannot create " + path);
    for (float sample : v) {
        std::uint32_t bits = 0;
        const float val = sample;
        std::memcpy(&bits, &val, 4);
        const char b[4] = {static_cast<char>(bits & 0xffu),
                           static_cast<char>((bits >> 8) & 0xffu),
                           static_cast<char>((bits >> 16) & 0xffu),
                           static_cast<char>((bits >> 24) & 0xffu)};
        f.write(b, sizeof b);
    }
    f.close();
    if (!f) throw std::runtime_error("dump: cannot finish " + path);
}

// Dump the NPU raw 24-dim logits + the exact model input for a GATED sample.
// ``diagnostic_gate_bypass`` is 0 here: this is a production-gated sample whose NPU
// output is recorded verbatim (not a forced/host classification).
inline void dump_gated_logits(
        const std::string& out_dir, std::int64_t source_index, int source_class,
        const std::string& modulation, const std::string& rf_verdict,
        const std::vector<float>& raw24,          // 24-dim NPU logits
        const std::vector<float>& model_input,    // [2,1024] fp32 aligned tensor
        int raw_top, bool wide_linear_enabled) {
    const std::string dir =
        join_path(out_dir, "dump_rx/" + std::to_string(source_index));
    mkdir_p(dir);

    const std::string logits_path = join_path(dir, "raw24_logits_f32le.bin");
    const std::string model_path = join_path(dir, "model_input_f32le.bin");
    const std::string json_path = join_path(dir, "classification_dump.json");
    const std::string sums_path = join_path(dir, "SHA256SUMS.txt");

    write_float32_le(logits_path, raw24);
    write_float32_le(model_path, model_input);

    std::vector<std::string> sums;
    const auto record_sha = [&](const std::string& name, const std::string& path) {
        bool ok = false;
        const std::string h = sdr::sha256_hex_file(path, &ok);
        if (!ok) throw std::runtime_error("dump: cannot hash " + path);
        sums.push_back(h + "  " + name);
        return h;
    };
    const std::string logits_sha = record_sha("raw24_logits_f32le.bin", logits_path);
    const std::string model_sha = record_sha("model_input_f32le.bin", model_path);

    bool finite = true;
    float top1 = 0.0f, top2 = -1e30f;
    for (int i = 0; i < rml24::kClassCount; ++i) {
        if (!std::isfinite(raw24[i])) { finite = false; break; }
        if (raw24[i] > top1) top1 = raw24[i];
    }
    if (finite) {
        for (int i = 0; i < rml24::kClassCount; ++i)
            if (i != raw_top && raw24[i] > top2) top2 = raw24[i];
    }

    std::ofstream meta(json_path, std::ios::binary | std::ios::trunc);
    if (!meta) throw std::runtime_error("dump: cannot create " + json_path);
    meta << "{\n"
         << "  \"format\":\"little_endian_f32\",\n"
         << "  \"source_index\":" << source_index << ",\n"
         << "  \"source_class\":" << source_class << ",\n"
         << "  \"modulation\":\"" << json_escape(modulation) << "\",\n"
         << "  \"rf_verdict\":\"" << json_escape(rf_verdict) << "\",\n"
         << "  \"gate_result\":\"" << json_escape(rf_verdict) << "\",\n"
         << "  \"diagnostic_gate_bypass\":0,\n"
         << "  \"production_gate_modified\":0,\n"
         << "  \"wide_linear_enabled\":" << (wide_linear_enabled ? 1 : 0) << ",\n"
         << "  \"raw24_pred\":" << raw_top << ",\n"
         << "  \"raw24_label\":\""
         << ((raw_top >= 0 && raw_top < rml24::kClassCount)
                 ? rml24::kLabelOrder24[raw_top] : "") << "\",\n"
         << "  \"logit_finite\":" << (finite ? 1 : 0) << ",\n"
         << "  \"top1_logit\":" << top1 << ",\n"
         << "  \"top2_logit\":" << top2 << ",\n"
         << "  \"margin\":" << (top1 - top2) << ",\n"
         << "  \"model_input_sha256\":\"" << model_sha << "\",\n"
         << "  \"raw24_logits_sha256\":\"" << logits_sha << "\"\n"
         << "}\n";
    meta.close();
    if (!meta) throw std::runtime_error("dump: cannot finish " + json_path);

    std::ofstream sums_f(sums_path, std::ios::binary | std::ios::trunc);
    if (!sums_f) throw std::runtime_error("dump: cannot create " + sums_path);
    for (const std::string& line : sums) sums_f << line << "\n";
    sums_f.close();
    if (!sums_f) throw std::runtime_error("dump: cannot finish " + sums_path);

    std::printf("FIX10CLASS24_BF16_DUMP_LOGITS file=%s source_index=%lld "
                "raw24_pred=%d finite=%d wide_linear=%d\n",
                modulation.c_str(), static_cast<long long>(source_index),
                raw_top, finite ? 1 : 0, wide_linear_enabled ? 1 : 0);
    std::fflush(stdout);
}

// Write the classification_dump.json marker for a GATE-REFUSED sample dumped by
// --dump-all-rx.  The board never runs the NPU on a refused sample, so the logits
// and model input are recorded as absent; `diagnostic_gate_bypass=1` marks that any
// host-side provisional inputs are diagnostic, not board NPU results.
inline void dump_refused_logits_marker(
        const std::string& out_dir, std::int64_t source_index, int source_class,
        const std::string& modulation, const std::string& rf_verdict) {
    const std::string dir =
        join_path(out_dir, "dump_rx/" + std::to_string(source_index));
    mkdir_p(dir);
    const std::string json_path = join_path(dir, "classification_dump.json");

    std::ofstream meta(json_path, std::ios::binary | std::ios::trunc);
    if (!meta) throw std::runtime_error("dump: cannot create " + json_path);
    meta << "{\n"
         << "  \"format\":\"little_endian_f32\",\n"
         << "  \"source_index\":" << source_index << ",\n"
         << "  \"source_class\":" << source_class << ",\n"
         << "  \"modulation\":\"" << json_escape(modulation) << "\",\n"
         << "  \"rf_verdict\":\"" << json_escape(rf_verdict) << "\",\n"
         << "  \"gate_result\":\"" << json_escape(rf_verdict) << "\",\n"
         << "  \"diagnostic_gate_bypass\":1,\n"
         << "  \"production_gate_modified\":0,\n"
         << "  \"raw24_pred\":-1,\n"
         << "  \"raw24_label\":\"\",\n"
         << "  \"logit_finite\":-1,\n"
         << "  \"raw24_logits_present\":0,\n"
         << "  \"model_input_present\":0\n"
         << "}\n";
    meta.close();
    if (!meta) throw std::runtime_error("dump: cannot finish " + json_path);

    std::printf("FIX10CLASS24_BF16_DUMP_REFUSED_MARKER file=%s source_index=%lld "
                "rf_verdict=%s\n",
                modulation.c_str(), static_cast<long long>(source_index),
                rf_verdict.c_str());
    std::fflush(stdout);
}

}  // namespace iqfix10dump
