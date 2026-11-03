// IqFrameLoader.hpp — offline file-backed IQ frame loading (fail-closed).
//
// Reads a JSON metadata sidecar + its paired binary IQ file, validates every
// contract point (schema / dtype / layout / length / SHA / NaN-Inf / stage
// semantics), and fills an IqFrame. No binary parsing happens in QML.
#pragma once

#include "IqFrame.hpp"

#include <string>
#include <vector>

namespace cst {

// Load one frame from a JSON sidecar (the binary `iq_file` is resolved next to
// the sidecar). Returns false and fills `err` on any validation failure.
bool load_sidecar_frame(const std::string& sidecar_json_path, IqFrame& frame,
                        std::string& err);

// List *.json sidecar files in `dir`, sorted by (frame_id, file name). A file
// whose JSON cannot be parsed is SKIPPED here (so listing is not a hard stop),
// but loading any listed frame still fail-closes. Duplicate frame_ids are left
// in place (sorted adjacent) so the caller can warn on them.
std::vector<std::string> list_sidecars(const std::string& dir, std::string& err);

// FileIqFrameSource — the only IqFrameSource implemented this phase. Wraps a
// single sidecar; nextFrame() returns the frame once, then false (EOF). A load
// failure returns false with a non-empty error (the caller must STOP, never
// auto-skip a corrupted frame).
class FileIqFrameSource : public IqFrameSource {
public:
    explicit FileIqFrameSource(std::string sidecar_json_path)
        : path_(std::move(sidecar_json_path)), done_(false) {}

    bool nextFrame(IqFrame& frame, std::string& error) override;

    const std::string& sidecarPath() const { return path_; }

private:
    std::string path_;
    bool done_;
};

}  // namespace cst
