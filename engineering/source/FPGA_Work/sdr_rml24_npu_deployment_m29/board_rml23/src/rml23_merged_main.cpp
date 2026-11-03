// M29 Phase F4 — board integration example for the RML23-AMSSB-MERGED chain.
//
// Shows EXACTLY where the 23-class merge slots into the existing NPU chain:
//
//     NPU -> float logits[24] (raw)  -> save raw  -> rml23::merge_predict
//          -> result log (raw_24_top1 + merged_23_top1 + deployment_mode)
//
// The NPU model is loaded ONCE by the existing driver (no per-frame reopen);
// the input preprocessing and the 24-dim index are UNCHANGED.  The only new
// logic is the single merge_predict call below.
//
// For host testing this example reads 24-dim float32 logits from a binary file
// (one frame = 24 little-endian float32) and writes one JSON result line per
// frame.  On the board, replace the file-read with the NPU's per-frame logits
// buffer; the merge + logging are identical.
#include "rml23_merged.hpp"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

int main(int argc, char** argv) {
    if (argc < 3) {
        std::fprintf(stderr, "usage: %s <logits.f32> <n_frames>\n", argv[0]);
        return 2;
    }
    const char* path = argv[1];
    const long long n_frames = std::atoll(argv[2]);
    if (n_frames <= 0) return 2;

    std::ifstream f(path, std::ios::binary);
    if (!f) { std::fprintf(stderr, "cannot open %s\n", path); return 2; }

    for (long long frame = 0; frame < n_frames; ++frame) {
        float logits[24];
        f.read(reinterpret_cast<char*>(logits), sizeof(logits));
        if (f.gcount() != static_cast<std::streamsize>(sizeof(logits))) break;

        rml23::RML23Result r;
        if (!rml23::merge_predict(logits, &r)) {
            // fail-closed: a non-finite frame is reported, never silently dropped
            std::printf("{\"frame\":%lld,\"raw_24_top1\":-1,\"merged_23_top1\":-1,"
                        "\"merged_23_label\":\"INVALID\",\"deployment_mode\":\"%s\","
                        "\"expert_enabled\":false,\"expert_result\":\"%s\"}\n",
                        frame, rml23::kDeploymentMode, rml23::kExpertResult);
            continue;
        }
        std::printf("{\"frame\":%lld,\"raw_24_top1\":%d,\"merged_23_top1\":%d,"
                    "\"merged_23_label\":\"%s\",\"deployment_mode\":\"%s\","
                    "\"expert_enabled\":false,\"expert_result\":\"%s\"}\n",
                    frame, r.raw_24_top1, r.merged_23_top1, r.merged_23_label,
                    rml23::kDeploymentMode, rml23::kExpertResult);
    }
    return 0;
}
