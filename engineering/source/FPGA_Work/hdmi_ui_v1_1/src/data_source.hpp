#pragma once
#include <cstdint>
#include <optional>
#include <string>

#include "contracts/result_frame.hpp"

namespace hdmiui {

// Produces ResultFrame objects.  Implementations:
//   * MockDataSource       — deterministic live simulation (source == MOCK);
//   * JsonLinesDataSource  — reads a JSON-Lines file (source == FILE);
//   * UnixSocketDataSource — live SDR adapter stream (source == SDR).
class DataSource {
public:
    virtual ~DataSource() = default;

    // Human-readable label shown in the UI, e.g. "MOCK", "FILE".
    virtual std::string name() const = 0;

    // Backend kind: "mock", "file", "unix_socket", "sdr".
    virtual std::string kind() const = 0;

    // A live source never truly "ends": a nullopt from next() means "no frame
    // right now" rather than "stream finished".  Mock and file sources are
    // finite (false); the Unix socket source is live (true).
    virtual bool is_live() const { return false; }

    // Open/start the source.  Returns false with *error on failure.
    virtual bool open(std::string* error) = 0;

    // Pull the next frame, blocking up to timeout_ms.  Returns std::nullopt on
    // EOF / close / timeout / transiently-no-data.  A malformed line is counted
    // as counters.error (or skipped) — see each implementation.
    virtual std::optional<ResultFrame> next(int timeout_ms) = 0;

    // Stop/close the source.
    virtual void close() = 0;
};

}  // namespace hdmiui
