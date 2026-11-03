#pragma once

// iq_rf_fix9r_baseline.hpp -- Route F fix9r Task B: the 46-sample EXACT baseline
// loader (route_f_fix9r_exact_baseline.tsv).  The runner compares every scored
// holdout file against this baseline (source_index + original_sha256 +
// deployed_class + split_role) so the acceptance gate can prove the 46 scored
// samples are EXACTLY the 46 baseline samples (wrong files / wrong order / extra
// or missing samples fail closed).
//
// iCraft-free and libiio-free: it compiles identically on the host and the board,
// so the host test exercises the exact parser the runner uses.

#include <cstdint>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqrffix9r {

struct BaselineRow {
    std::uint64_t source_index = 0;
    std::string sha256;
    int deployed_class = -1;
    std::string modulation;
    std::string split_role;
    int frozen_baseline_pred = -1;   // fix9r2g: the FROZEN offline model prediction
};

inline bool is_hex64(const std::string& s) {
    if (s.size() != 64) return false;
    for (char c : s)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

// Parse the 6-column baseline TSV -> map<source_index, BaselineRow>.
// Fail-closed: a short row, a non-64-hex sha, an out-of-range deployed class, a
// non-holdout split_role, an out-of-range frozen_baseline_pred, or a duplicate
// source_index all throw.
inline std::map<std::uint64_t, BaselineRow> load_baseline(const std::string& path,
                                                          int class_count) {
    std::map<std::uint64_t, BaselineRow> m;
    std::ifstream f(path);
    if (!f) throw std::runtime_error("fix9r: cannot open baseline " + path);
    std::string line;
    std::getline(f, line);   // header
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        std::vector<std::string> p;
        std::size_t pos = 0;
        while (true) {
            const std::size_t tab = line.find('\t', pos);
            if (tab == std::string::npos) { p.push_back(line.substr(pos)); break; }
            p.push_back(line.substr(pos, tab - pos));
            pos = tab + 1;
        }
        if (p.size() < 6)
            throw std::runtime_error("fix9r: bad baseline row (want 6 cols): " + line);
        BaselineRow r;
        r.source_index = static_cast<std::uint64_t>(std::stoull(p[0]));
        r.sha256 = p[1];
        r.deployed_class = std::stoi(p[2]);
        r.modulation = p[3];
        r.split_role = p[4];
        r.frozen_baseline_pred = std::stoi(p[5]);
        if (!is_hex64(r.sha256))
            throw std::runtime_error("fix9r: baseline sha not 64-hex for source_index " +
                                     std::to_string(r.source_index));
        if (r.deployed_class < 0 || r.deployed_class >= class_count)
            throw std::runtime_error("fix9r: baseline deployed_class out of range");
        if (r.frozen_baseline_pred < 0 || r.frozen_baseline_pred >= class_count)
            throw std::runtime_error("fix9r: baseline frozen_baseline_pred out of range");
        if (r.split_role != "holdout")
            throw std::runtime_error("fix9r: baseline split_role != holdout");
        if (!m.emplace(r.source_index, r).second)
            throw std::runtime_error("fix9r: duplicate baseline source_index " +
                                     std::to_string(r.source_index));
    }
    if (m.empty()) throw std::runtime_error("fix9r: baseline is empty: " + path);
    return m;
}

}  // namespace iqrffix9r
