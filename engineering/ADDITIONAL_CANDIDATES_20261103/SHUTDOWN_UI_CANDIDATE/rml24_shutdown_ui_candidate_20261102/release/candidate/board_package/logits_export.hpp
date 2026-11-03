#pragma once

// logits_export.hpp -- atomic raw-24 logits export (errata 39e5 Stage E, #7).
//
// The three-backend comparison (Host / board NPU / FP32) needs each backend to
// export its RAW 24-dim logits for the SAME input, keyed by the input's SHA-256,
// so an offline tool can only ever compare results that come from identical
// bytes.  This hook is the board-NPU side of that contract: for every classified
// frame it writes one JSON record to <dir>/logits_<frame_id>.json with
//
//   { "backend": "board_npu", "frame_id": N,
//     "input_sha256": "<64 hex>", "model_sha": "<64 hex>",
//     "raw24": [24 float logits, pre-merge, pre-softmax] }
//
// Written atomically (sibling .tmp then rename()), exactly like capture_hook.hpp,
// so a crash mid-write never leaves a truncated record that a later compare would
// silently treat as a valid board export.  The FP32 exporter
// (scripts/export_fp32_onnx.py) emits the same schema with backend "fp32_onnx",
// and the Host reference lives in deployment_golden/expected_logits_or_argmax.json
// (per-sample "raw_24_logits"): scripts/compare_three_backends.py matches them by
// input_sha256 and refuses any record whose model identity differs.
//
// iCraft-free / libiio-free: only <cstdio> + <cstdint> + <string>.  No file I/O
// on the hot path unless a non-empty dir is passed.

#include <cstdint>
#include <cstdio>
#include <string>

namespace board {

class LogitsExport {
public:
    // dir: destination directory (must already exist).  Empty dir disables the
    // export: export_frame() returns "" without touching the filesystem.
    explicit LogitsExport(std::string dir) : dir_(std::move(dir)) {}

    bool enabled() const { return !dir_.empty(); }

    // Atomically write one JSON record for a classified frame.  `raw24` holds
    // kDeployedOutputDim==24 pre-merge logits (fp32).  Returns the input SHA-256
    // (== the record's key) on success, "" on any failure (caller fails closed).
    std::string export_frame(std::uint64_t frame_id, const std::string& input_sha256,
                             const std::string& model_sha, const float* raw24,
                             std::size_t n_raw24) const {
        if (dir_.empty()) return "";

        char path[1024];
        std::snprintf(path, sizeof path, "%s/logits_%llu.json",
                      dir_.c_str(), static_cast<unsigned long long>(frame_id));
        const std::string final(path);
        const std::string tmp = final + ".tmp";

        std::FILE* f = std::fopen(tmp.c_str(), "wb");
        if (!f) return "";

        std::fprintf(f,
                     "{\"backend\":\"board_npu\",\"frame_id\":%llu,"
                     "\"input_sha256\":\"%s\",\"model_sha\":\"%s\","
                     "\"raw24\":[",
                     static_cast<unsigned long long>(frame_id),
                     input_sha256.c_str(), model_sha.c_str());
        for (std::size_t k = 0; k < n_raw24; ++k) {
            if (k) std::fputc(',', f);
            std::fprintf(f, "%.9g", static_cast<double>(raw24[k]));
        }
        std::fputs("]}\n", f);

        const bool flushed = (std::fflush(f) == 0);
        const bool closed = (std::fclose(f) == 0);
        if (!flushed || !closed) {
            std::remove(tmp.c_str());
            return "";
        }
        if (std::rename(tmp.c_str(), final.c_str()) != 0) {
            std::remove(tmp.c_str());
            return "";
        }
        return input_sha256;
    }

private:
    std::string dir_;
};

}  // namespace board
