#pragma once
#include <cstdint>
#include <optional>
#include <string>

#include "contracts/result_frame.hpp"

namespace hdmiui {

// Produces ResultFrame objects.  Implementations:
//   * MockDataSource       — deterministic live simulation (source == MOCK);
//   * JsonLinesDataSource  — reads a JSON-Lines file (source == FILE);
//   * UnixSocketDataSource — reserved stub for the future SDR adapter.
class DataSource {
public:
    virtual ~DataSource() = default;

    // Human-readable label shown in the UI, e.g. "MOCK", "FILE".
    virtual std::string name() const = 0;

    // Backend kind: "mock", "file", "unix_socket", "sdr".
    virtual std::string kind() const = 0;

    // Open/start the source.  Returns false with *error on failure.
    virtual bool open(std::string* error) = 0;

    // Pull the next frame, blocking up to timeout_ms.  Returns std::nullopt on
    // EOF / close / timeout.  A malformed line is counted as counters.error
    // (or skipped) — see each implementation.
    virtual std::optional<ResultFrame> next(int timeout_ms) = 0;

    // Stop/close the source.
    virtual void close() = 0;
};

}  // namespace hdmiui
