#pragma once

// rml24_bf16_baseline.hpp -- fix10class24-dualsdr1 Phase 2: the 24-sample BF16
// raw-24 baseline loader (clean24_smoke_raw24_bf16_baseline.tsv, produced by
// scripts/predict_rml24_bf16_baseline.py on the iCraft Host backend).
//
//   source_index  original_sha256  raw24_class  modulation  split_role
//   frozen_bf16_raw24_pred  model_sha256
//
// The runner compares every scored holdout file against this baseline
// (source_index + original_sha256 + raw24_class + split_role) so the acceptance
// gate can prove the 24 scored samples are EXACTLY the 24 baseline samples, and
// compares the board's BF16 raw24 argmax against ``frozen_bf16_raw24_pred``.
//
// Unlike iq_rf_fix9r_baseline.hpp / iq_clean_baseline.hpp, the label column is a
// RAW 24-class index (0..23), AM-SSB-WC(17)/AM-SSB-SC(18) kept separate, and
// there is a trailing model_sha256 provenance column (7 cols total).
//
// iCraft-free and libiio-free: it compiles identically on the host and the board,
// so the host test exercises the exact parser the runner uses.

#include <cstdint>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace rml24bf16 {

struct BaselineRow {
    std::uint64_t source_index = 0;
    std::string original_sha256;
    int raw24_class = -1;                  // 0..23, AM-SSB WC/SC kept separate
    std::string modulation;
    std::string split_role;
    int frozen_bf16_raw24_pred = -1;       // 0..23 (BF16 Host raw24 argmax)
    std::string model_sha256;
};

inline bool is_hex64(const std::string& s) {
    if (s.size() != 64) return false;
    for (char c : s)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

// Parse the 7-column BF16 baseline TSV -> map<source_index, BaselineRow>.
// Fail-closed: a short row, a non-64-hex sha, a non-64-hex model_sha256, an
// out-of-range raw24_class, a non-holdout split_role, an out-of-range
// frozen_bf16_raw24_pred, or a duplicate source_index all throw.
inline std::map<std::uint64_t, BaselineRow> load_baseline(const std::string& path,
                                                          int class_count) {
    std::map<std::uint64_t, BaselineRow> m;
    std::ifstream f(path);
    if (!f) throw std::runtime_error("rml24bf16: cannot open baseline " + path);
    std::string line;
    std::getline(f, line);   // header
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();  // CRLF tolerance
        if (line.empty()) continue;
        std::vector<std::string> p;
        std::size_t pos = 0;
        while (true) {
            const std::size_t tab = line.find('\t', pos);
            if (tab == std::string::npos) { p.push_back(line.substr(pos)); break; }
            p.push_back(line.substr(pos, tab - pos));
            pos = tab + 1;
        }
        if (p.size() < 7)
            throw std::runtime_error("rml24bf16: bad baseline row (want 7 cols): " + line);
        BaselineRow r;
        r.source_index = static_cast<std::uint64_t>(std::stoull(p[0]));
        r.original_sha256 = p[1];
        r.raw24_class = std::stoi(p[2]);
        r.modulation = p[3];
        r.split_role = p[4];
        r.frozen_bf16_raw24_pred = std::stoi(p[5]);
        r.model_sha256 = p[6];
        if (!is_hex64(r.original_sha256))
            throw std::runtime_error("rml24bf16: baseline original_sha256 not 64-hex "
                                     "for source_index " + std::to_string(r.source_index));
        if (!is_hex64(r.model_sha256))
            throw std::runtime_error("rml24bf16: baseline model_sha256 not 64-hex for "
                                     "source_index " + std::to_string(r.source_index));
        if (r.raw24_class < 0 || r.raw24_class >= class_count)
            throw std::runtime_error("rml24bf16: baseline raw24_class out of range");
        if (r.frozen_bf16_raw24_pred < 0 || r.frozen_bf16_raw24_pred >= class_count)
            throw std::runtime_error("rml24bf16: baseline frozen_bf16_raw24_pred out of range");
        if (r.split_role != "holdout")
            throw std::runtime_error("rml24bf16: baseline split_role != holdout");
        if (!m.emplace(r.source_index, r).second)
            throw std::runtime_error("rml24bf16: duplicate baseline source_index " +
                                     std::to_string(r.source_index));
    }
    if (m.empty()) throw std::runtime_error("rml24bf16: baseline is empty: " + path);
    return m;
}

}  // namespace rml24bf16
