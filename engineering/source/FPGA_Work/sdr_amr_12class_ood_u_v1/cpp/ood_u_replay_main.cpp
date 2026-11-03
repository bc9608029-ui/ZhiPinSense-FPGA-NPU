// CLI replay of the CPU-side OOD-U detector on a logits file.
//
// Usage: ood_u_replay <manifest.json> <logits.tsv>
//
// logits.tsv is one 12-d raw logit vector per line (space-separated floats).
// Prints a JSON object { "n": N, "decisions": [ {known, valid, class_index,
// score, threshold, score_method, class_name}, ... ] } to stdout.
//
// This lets the host-side Python reference and the board-side C++ detector be
// compared on the *exact same* logits (Python-C++ consistency check).
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "ood_threshold_manifest.hpp"
#include "ood_u_contract.hpp"
#include "ood_u_detector.hpp"

namespace {

std::vector<double> parse_row(const std::string& line) {
    std::istringstream in(line);
    std::vector<double> values;
    double v;
    while (in >> v) values.push_back(v);
    return values;
}

std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '"' || c == '\\') {
            out.push_back('\\');
            out.push_back(c);
        } else if (c == '\n') {
            out += "\\n";
        } else {
            out.push_back(c);
        }
    }
    return out;
}

void print_decision(const OodDecision& d, bool last) {
    std::cout << "    {"
              << "\"known\":" << (d.known ? "true" : "false") << ","
              << "\"valid\":" << (d.valid ? "true" : "false") << ","
              << "\"class_index\":" << d.class_index << ","
              << "\"score\":" << d.score << ","
              << "\"threshold\":" << d.threshold << ","
              << "\"score_method\":\"" << json_escape(d.score_method) << "\","
              << "\"class_name\":\"" << json_escape(d.class_name) << "\""
              << "}" << (last ? "\n" : ",\n");
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: ood_u_replay <manifest.json> <logits.tsv>\n";
        return 2;
    }
    const std::string manifest_path = argv[1];
    const std::string logits_path = argv[2];

    OodThresholdManifest manifest = load_ood_u_manifest(manifest_path);
    OodUDetector detector(manifest);

    // Print every double with full round-trip precision so the Python reference
    // and the C++ detector can be compared at the 1e-6 tolerance.
    std::cout << std::setprecision(17);

    std::ifstream in(logits_path);
    if (!in) {
        std::cerr << "cannot open logits file: " << logits_path << "\n";
        return 1;
    }

    std::cout << "{\"n\":";
    std::vector<OodDecision> decisions;
    std::string line;
    int n = 0;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::vector<double> row = parse_row(line);
        if (row.size() != static_cast<std::size_t>(ood_u_contract::OUTPUT_DIM)) {
            std::cerr << "bad logits row (expected " << ood_u_contract::OUTPUT_DIM
                      << " values, got " << row.size() << ")\n";
            return 1;
        }
        decisions.push_back(detector.classify_or_reject(row.data(), static_cast<int>(row.size())));
        ++n;
    }

    std::cout << n << ",\"decisions\":[\n";
    for (int i = 0; i < n; ++i) {
        print_decision(decisions[static_cast<std::size_t>(i)], i == n - 1);
    }
    std::cout << "]}\n";
    return 0;
}
