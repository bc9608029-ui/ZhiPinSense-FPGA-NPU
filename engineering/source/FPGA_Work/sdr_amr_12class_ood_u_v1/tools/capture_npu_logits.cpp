// Board-side NPU logits capture tool (Section 十一).
//
// Feeds the fixed parity IQ bundle (parity_iq.bin) through the NPU and writes
// the raw fp32 logits in the canonical schema consumed by
// scripts/run_m20_logits_parity.sh:
//
//   { "n": N, "output_dim": 12, "logits": [[12 floats], ...] }
//
// The actual NPU forward is board-specific (iCraft / ZG330).  On the board,
// ``npu_forward`` is implemented with the deployed NpuClassifier12.  On the host
// this tool builds and runs in ``--mode=replay`` against a pre-dumped logits
// file so the I/O contract is verified without the NPU.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "../cpp/minijson.hpp"
#include "../cpp/ood_u_contract.hpp"

namespace {

constexpr int SAMPLES_PER_IQ = 2 * 1024;  // planar I/Q, 1024 samples x 2 channels

// ---------------------------------------------------------------------------
// NPU forward integration point.
//
// Board implementation (ZG330 / iCraft): run one [1,2,1024] fp32 planar I/Q
// frame through the deployed 12-class NPU and return its 12-d raw fp32 logits
// (no softmax).  Returns 0 on success, non-zero on failure.
// ---------------------------------------------------------------------------
int npu_forward(const float* /*iq*/, float* /*logits*/, const char* /*model_path*/) {
    std::fprintf(stderr, "capture_npu_logits: board NPU forward not available on host "
                         "(use --mode=replay with --replay-logits)\n");
    return -1;
}

bool read_binary(const std::string& path, std::vector<float>& out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        std::fprintf(stderr, "cannot open %s\n", path.c_str());
        return false;
    }
    in.seekg(0, std::ios::end);
    std::streampos size = in.tellg();
    in.seekg(0, std::ios::beg);
    out.resize(static_cast<std::size_t>(size) / sizeof(float));
    in.read(reinterpret_cast<char*>(out.data()), static_cast<std::streamsize>(size));
    return static_cast<std::size_t>(in.gcount()) == out.size() * sizeof(float);
}

std::string read_text(const std::string& path) {
    std::ifstream in(path);
    std::ostringstream buf;
    buf << in.rdbuf();
    return buf.str();
}

}  // namespace

int main(int argc, char** argv) {
    std::string iq_bin, iq_meta, out_path, mode = "replay", replay_logits, model_path;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) { std::fprintf(stderr, "missing value for %s\n", a.c_str()); std::exit(2); }
            return argv[++i];
        };
        if (a == "--iq-bin") iq_bin = next();
        else if (a == "--iq-meta") iq_meta = next();
        else if (a == "--out") out_path = next();
        else if (a == "--mode") mode = next();
        else if (a == "--replay-logits") replay_logits = next();
        else if (a == "--model") model_path = next();
        else { std::fprintf(stderr, "unknown arg %s\n", a.c_str()); return 2; }
    }

    if (iq_bin.empty() || iq_meta.empty() || out_path.empty()) {
        std::fprintf(stderr, "usage: capture_npu_logits --iq-bin F --iq-meta M --out O "
                             "[--mode board|replay] [--replay-logits L] [--model P]\n");
        return 2;
    }

    // Validate the IQ meta (N, shape, SHA) so we know how many frames to run.
    minijson::Value meta;
    try {
        meta = minijson::parse(read_text(iq_meta));
    } catch (const std::exception& e) {
        std::fprintf(stderr, "bad iq-meta: %s\n", e.what());
        return 1;
    }
    int n = static_cast<int>(meta.at("n").as_double());
    if (n <= 0) {
        std::fprintf(stderr, "iq-meta has non-positive n\n");
        return 1;
    }

    std::vector<float> iq;
    if (!read_binary(iq_bin, iq)) {
        std::fprintf(stderr, "failed to read %s\n", iq_bin.c_str());
        return 1;
    }
    if (iq.size() != static_cast<std::size_t>(n) * SAMPLES_PER_IQ) {
        std::fprintf(stderr, "iq-bin size mismatch: expected %d frames x %d floats, got %zu\n",
                     n, SAMPLES_PER_IQ, iq.size());
        return 1;
    }

    std::vector<std::vector<float>> logits(static_cast<std::size_t>(n));
    if (mode == "board") {
        for (int i = 0; i < n; ++i) {
            logits[static_cast<std::size_t>(i)].assign(ood_u_contract::OUTPUT_DIM, 0.0f);
            if (npu_forward(&iq[static_cast<std::size_t>(i) * SAMPLES_PER_IQ],
                            logits[static_cast<std::size_t>(i)].data(), model_path.c_str()) != 0) {
                return 1;
            }
        }
    } else if (mode == "replay") {
        if (replay_logits.empty()) {
            std::fprintf(stderr, "--mode=replay requires --replay-logits <file>\n");
            return 2;
        }
        minijson::Value src;
        try {
            src = minijson::parse(read_text(replay_logits));
        } catch (const std::exception& e) {
            std::fprintf(stderr, "bad replay-logits: %s\n", e.what());
            return 1;
        }
        const auto& arr = src.at("logits").as_array();
        if (static_cast<int>(arr.size()) != n) {
            std::fprintf(stderr, "replay-logits has %zu rows, expected %d\n", arr.size(), n);
            return 1;
        }
        for (int i = 0; i < n; ++i) {
            const auto& row = arr[static_cast<std::size_t>(i)].as_array();
            if (row.size() != ood_u_contract::OUTPUT_DIM) {
                std::fprintf(stderr, "replay-logits row %d has %zu values, expected %d\n",
                             i, row.size(), ood_u_contract::OUTPUT_DIM);
                return 1;
            }
            for (std::size_t j = 0; j < row.size(); ++j) {
                logits[static_cast<std::size_t>(i)].push_back(static_cast<float>(row[j].as_double()));
            }
        }
    } else {
        std::fprintf(stderr, "unknown --mode %s\n", mode.c_str());
        return 2;
    }

    // Emit the canonical npu_logits.json.
    std::ofstream out(out_path);
    out << "{\"n\":" << n << ",\"output_dim\":" << ood_u_contract::OUTPUT_DIM << ",\"logits\":[\n";
    for (int i = 0; i < n; ++i) {
        out << "  [";
        const auto& row = logits[static_cast<std::size_t>(i)];
        for (std::size_t j = 0; j < row.size(); ++j) {
            out << row[j];
            if (j + 1 < row.size()) out << ", ";
        }
        out << "]";
        if (i + 1 < n) out << ",";
        out << "\n";
    }
    out << "]}\n";
    if (!out) {
        std::fprintf(stderr, "failed to write %s\n", out_path.c_str());
        return 1;
    }
    std::printf("capture_npu_logits: wrote %d x %d logits to %s\n", n, ood_u_contract::OUTPUT_DIM, out_path.c_str());
    return 0;
}
