#pragma once

// capture_hook.hpp -- atomic NPU-input tensor capture (errata 39e5 Stage C, #6).
//
// The live-rx producer feeds the [2,1024] fp32 preprocess tensor straight into
// the NPU.  Evidence 2/3/4 (QPSK -> QAM classification jumping) cannot be
// diagnosed from the printed argmax alone: we need the EXACT bytes the NPU saw,
// so an offline tool can re-run the frozen model and separate "the model says
// QAM" from "the board perturbed the input".  This hook dumps that tensor.
//
// "Atomic" means a reader sees either the complete 8192-byte file or nothing:
// the bytes are written to a sibling <name>.tmp and rename()d into place, so a
// crash mid-write can never leave a truncated tensor that a later analysis would
// silently treat as valid.  The SHA-256 of the 8192 bytes is returned so the
// caller can log a provenance fingerprint that the offline tool re-checks.
//
// iCraft-free / libiio-free: only sdr::Sha256 (sha256.hpp) + <cstdio>.  The
// captured file is byte-identical to the deployment_golden input_N.bin layout
// (little-endian fp32, plane 0 = I[0..1023], plane 1 = Q[0..1023], 8192 B), so
// one reader serves both the golden inputs and the live captures.

#include "../sdr_adapter/sha256.hpp"

#include <cstdint>
#include <cstdio>
#include <string>

namespace board {

class TensorCapture {
public:
    // dir: destination directory (must already exist).  An empty dir disables
    // capture: capture() returns "" without touching the filesystem.
    explicit TensorCapture(std::string dir) : dir_(std::move(dir)) {}

    bool enabled() const { return !dir_.empty(); }

    // Atomically write the `n_floats` fp32 samples at `tensor` (little-endian,
    // plane 0 = I[0..n/2-1], plane 1 = Q[0..n/2-1]) to
    // <dir>/live_rx_tensor_<frame_id>.f32.  Returns the SHA-256 hex digest of the
    // exact bytes on success, "" on any failure (the caller fails closed).
    std::string capture(std::uint64_t frame_id, const float* tensor,
                        std::size_t n_floats) const {
        if (dir_.empty()) return "";
        const std::size_t bytes = n_floats * sizeof(float);
        const std::string digest = sdr::Sha256::hex(tensor, bytes);

        char path[1024];
        std::snprintf(path, sizeof path, "%s/live_rx_tensor_%llu.f32",
                      dir_.c_str(), static_cast<unsigned long long>(frame_id));
        const std::string final(path);
        const std::string tmp = final + ".tmp";

        std::FILE* f = std::fopen(tmp.c_str(), "wb");
        if (!f) return "";
        const std::size_t written = std::fwrite(tensor, 1, bytes, f);
        const bool flushed = (std::fflush(f) == 0);
        const bool closed = (std::fclose(f) == 0);
        if (written != bytes || !flushed || !closed) {
            std::remove(tmp.c_str());
            return "";
        }
        if (std::rename(tmp.c_str(), final.c_str()) != 0) {
            std::remove(tmp.c_str());
            return "";
        }
        return digest;
    }

private:
    std::string dir_;
};

}  // namespace board
