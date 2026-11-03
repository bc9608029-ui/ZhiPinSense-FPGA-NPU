#include "iq_source.hpp"

#include <stdexcept>

// SdrIqSource is a contract placeholder.  The local materials do not specify a
// concrete SDR model, electrical interface, or target sample rate (audited:
// "No final SDR is selected by this analysis").  No vendor API, USB VID:PID,
// Ethernet protocol, or sample format (float32 / int12 / int16) may be assumed
// before the device arrives.  Constructing this source is therefore a hard
// error rather than a silent wrong-device guess.

SdrIqSource::SdrIqSource() {
    throw std::runtime_error(
        "SdrIqSource is a placeholder: SDR model/interface/sample rate not yet specified");
}

bool SdrIqSource::next(iq::Frame& /*out*/) {
    throw std::runtime_error("SdrIqSource::next not implemented (SDR unspecified)");
}

void SdrIqSource::rewind() {
    throw std::runtime_error("SdrIqSource::rewind not implemented (SDR unspecified)");
}

std::uint64_t SdrIqSource::frame_count() const {
    return 0;  // unknown
}
