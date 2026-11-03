#pragma once

// iq_clean_baseline.hpp -- fix10-prep Path B/C: the 6-column CLEAN baseline loader,
// split out of iq_clean_iq_23class_fix10.hpp so the host test can exercise it
// WITHOUT pulling in the NPU backend (npu_classifier24.hpp -> icraft-backends).
//
//   source_index  file_name  sha256  deployed_class  split_role  frozen_baseline_pred
//
// This DIFFERS from the fix9r2g1 baseline (that one carries original_sha256 +
// modulation in place of file_name + sha256).  The frozen prediction is the model's
// OWN argmax through the 24->23 merge, never back-filled from deployed_class.
//
// Fail-closed: a short row, a non-64-hex sha, an out-of-range deployed_class, a
// non-holdout split_role, an out-of-range frozen_baseline_pred, an unsafe file_name,
// a duplicate source_index, or an empty file all throw.

#include <cstdint>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqclean23fix10 {

struct CleanBaselineRow {
    std::uint64_t source_index = 0;
    std::string file_name;
    std::string sha256;
    int deployed_class = -1;
    std::string split_role;
    int frozen_baseline_pred = -1;
};

inline bool is_hex64(const std::string& s) {
    if (s.size() != 64) return false;
    for (char c : s)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

inline std::map<std::uint64_t, CleanBaselineRow> load_clean_baseline(
        const std::string& path, int class_count) {
    std::map<std::uint64_t, CleanBaselineRow> m;
    std::ifstream f(path);
    if (!f)
        throw std::runtime_error("fix10-clean: cannot open baseline " + path);
    std::string line;
    std::getline(f, line);   // header: source_index file_name sha256 ... frozen_baseline_pred
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
            throw std::runtime_error("fix10-clean: bad baseline row (want 6 cols): " +
                                     line);
        CleanBaselineRow r;
        r.source_index = static_cast<std::uint64_t>(std::stoull(p[0]));
        r.file_name = p[1];
        r.sha256 = p[2];
        r.deployed_class = std::stoi(p[3]);
        r.split_role = p[4];
        r.frozen_baseline_pred = std::stoi(p[5]);
        if (r.file_name.empty() || r.file_name.find('/') != std::string::npos ||
            r.file_name.find('\\') != std::string::npos ||
            r.file_name.find("..") != std::string::npos)
            throw std::runtime_error("fix10-clean: unsafe baseline file_name for "
                                     "source_index " + std::to_string(r.source_index));
        if (!is_hex64(r.sha256))
            throw std::runtime_error("fix10-clean: baseline sha not 64-hex for "
                                     "source_index " + std::to_string(r.source_index));
        if (r.deployed_class < 0 || r.deployed_class >= class_count)
            throw std::runtime_error("fix10-clean: baseline deployed_class out of range");
        if (r.frozen_baseline_pred < 0 || r.frozen_baseline_pred >= class_count)
            throw std::runtime_error("fix10-clean: baseline frozen_baseline_pred out of "
                                     "range");
        if (r.split_role != "holdout")
            throw std::runtime_error("fix10-clean: baseline split_role != holdout");
        if (!m.emplace(r.source_index, r).second)
            throw std::runtime_error("fix10-clean: duplicate baseline source_index " +
                                     std::to_string(r.source_index));
    }
    if (m.empty())
        throw std::runtime_error("fix10-clean: baseline is empty: " + path);
    return m;
}

}  // namespace iqclean23fix10
