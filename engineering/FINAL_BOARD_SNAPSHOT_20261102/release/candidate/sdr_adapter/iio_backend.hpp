#pragma once

// IIO backend abstraction for the SDR source layer.
//
// PlutoIqSource (pluto.hpp) consumes this interface so it can be tested offline
// against iio::MockBackend (mock_iio.hpp) and, when compiled with
// SDR_ADAPTER_HAVE_LIBIIO, run against a real ADALM-Pluto via libiio.  The
// backend's only job is to hand out raw interleaved int16 IQ chunks and report
// device state; framing into 1024-sample frames is PlutoIqSource's job.
//
// iCraft-free and header-only.

#include <cstddef>
#include <cstdint>

namespace iio {

// One raw read from the device.
struct RawChunk {
    const std::int16_t* samples = nullptr;  // interleaved [I,Q,...]; valid only
                                            // while samples_available > 0
    std::size_t samples_available = 0;      // number of COMPLEX samples returned
    bool overflow = false;      // device FIFO overflow since last read
    bool discontinuity = false; // sample-rate / timestamp jump
    bool dropped = false;       // device dropped a block (backpressure)
    bool timed_out = false;     // read timed out, no data returned
    bool broken = false;        // stream is down; caller should reopen()
    bool eos = false;           // clean end of stream (no more data, ever)
};

class Backend {
public:
    virtual ~Backend() = default;

    // Read up to `max_complex` complex samples.  `timeout_ms` is the caller's
    // per-read timeout (0 = no timeout).  Returns a chunk; see RawChunk for how
    // each terminal/no-data condition is signalled.
    virtual RawChunk read(std::size_t max_complex, std::uint64_t timeout_ms) = 0;

    // Re-open the device stream after a break (stream-break recovery).
    virtual void reopen() = 0;

    virtual bool is_open() const = 0;
};

}  // namespace iio
