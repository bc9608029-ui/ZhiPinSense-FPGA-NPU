#pragma once

// iio_attr_routing.hpp -- frozen AD9361/Pluto IIO attribute -> (target, api) map.
//
// This is the executable form of contracts/pluto_config_contract.md §1-3: it
// records, per logical attribute, WHICH libiio object it lives on and WHICH libiio
// API family reads/writes it.  It is PURE (no <iio.h>, no device), so the host
// test test_attr_routing.cpp locks the mapping without libiio; the real backend
// (pluto_device_libiio.cpp) resolves these targets to its concrete iio_channel* /
// iio_device* handles.
//
// AD9361 topology (ADALM-Pluto Rev.C + AD9364, fw v0.39), the corrected mapping:
//
//   ad9361-phy CONTROL channels (the attribute plane -- NOT the DMA devices):
//     voltage0  output=false  -> RX control: sampling_frequency / rf_bandwidth /
//                                             gain_control_mode / hardwaregain
//     voltage0  output=true   -> TX control: sampling_frequency / rf_bandwidth /
//                                             hardwaregain
//     altvoltage0 output=true -> RX LO: frequency
//     altvoltage1 output=true -> TX LO: frequency
//   ad9361-phy DEVICE DEBUG attribute:
//     loopback                -> iio_device_debug_attr_*  (NOT a device attr)
//   stream devices (DMA only; they carry NO control attributes):
//     cf-ad9361-lpc          voltage0/voltage1 output=false (RX DMA I/Q)
//     cf-ad9361-dds-core-lpc voltage0/voltage1 output=true  (TX DMA I/Q)
//
// Rules this table enforces (and the unit test asserts):
//   * sampling_frequency / rf_bandwidth / gain_control_mode / hardwaregain are
//     CHANNEL attributes on the PHY control channels -- never iio_device_attr_*,
//     never the cf-ad9361-*-lpc stream channels.
//   * loopback is a DEBUG attribute (Pluto v0.39), read/written with
//     iio_device_debug_attr_*.
//   * RX and TX sample rate / bandwidth / gain are distinct rows (no assumption
//     that the RX and TX sides are equal).
//
// iCraft-free.

#include <cstring>

namespace sdr {

enum class AttrApi {
    kChannel,  // iio_channel_attr_*
    kDebug,    // iio_device_debug_attr_*
    kDevice,   // iio_device_attr_*  (kept for completeness; AD9361 uses none)
};

enum class AttrTarget {
    kPhyRxCh,   // ad9361-phy voltage0 output=false (RX control channel)
    kPhyTxCh,   // ad9361-phy voltage0 output=true  (TX control channel)
    kRxLo,      // ad9361-phy altvoltage0 output=true (RX LO)
    kTxLo,      // ad9361-phy altvoltage1 output=true (TX LO)
    kPhyDebug,  // ad9361-phy device debug attribute
};

enum class AttrDir {
    kRx,    // RX side of a shared attribute
    kTx,    // TX side of a shared attribute
    kNone,  // no RX/TX side (e.g. loopback)
};

struct AttrRoute {
    AttrTarget target;
    AttrApi api;
};

namespace detail {

struct Row {
    const char* name;
    AttrDir dir;
    AttrTarget target;
    AttrApi api;
};

// The frozen routing table (internal linkage; each TU gets its own copy).
constexpr Row kRows[] = {
    {"sampling_frequency", AttrDir::kRx,   AttrTarget::kPhyRxCh, AttrApi::kChannel},
    {"sampling_frequency", AttrDir::kTx,   AttrTarget::kPhyTxCh, AttrApi::kChannel},
    {"rf_bandwidth",       AttrDir::kRx,   AttrTarget::kPhyRxCh, AttrApi::kChannel},
    {"rf_bandwidth",       AttrDir::kTx,   AttrTarget::kPhyTxCh, AttrApi::kChannel},
    {"gain_control_mode",  AttrDir::kRx,   AttrTarget::kPhyRxCh, AttrApi::kChannel},
    {"hardwaregain",       AttrDir::kRx,   AttrTarget::kPhyRxCh, AttrApi::kChannel},
    {"hardwaregain",       AttrDir::kTx,   AttrTarget::kPhyTxCh, AttrApi::kChannel},
    {"frequency",          AttrDir::kRx,   AttrTarget::kRxLo,    AttrApi::kChannel},
    {"frequency",          AttrDir::kTx,   AttrTarget::kTxLo,    AttrApi::kChannel},
    {"loopback",           AttrDir::kNone, AttrTarget::kPhyDebug, AttrApi::kDebug},
};

constexpr std::size_t kRowCount = sizeof(kRows) / sizeof(kRows[0]);

}  // namespace detail

// Resolve a logical AD9361 attribute to its IIO home.  `dir` selects the RX/TX
// side for shared attributes.  Returns false for an unknown (name, dir) pair.
inline bool route_ad9361_attr(const char* name, AttrDir dir, AttrRoute* out) {
    for (std::size_t i = 0; i < detail::kRowCount; ++i) {
        const detail::Row& r = detail::kRows[i];
        if (r.dir == dir && std::strcmp(r.name, name) == 0) {
            out->target = r.target;
            out->api = r.api;
            return true;
        }
    }
    return false;
}

inline const char* api_name(AttrApi a) {
    switch (a) {
        case AttrApi::kChannel: return "channel";
        case AttrApi::kDebug:   return "debug";
        case AttrApi::kDevice:  return "device";
    }
    return "?";
}

inline const char* target_name(AttrTarget t) {
    switch (t) {
        case AttrTarget::kPhyRxCh:  return "phy_rx_ch";
        case AttrTarget::kPhyTxCh:  return "phy_tx_ch";
        case AttrTarget::kRxLo:     return "rx_lo";
        case AttrTarget::kTxLo:     return "tx_lo";
        case AttrTarget::kPhyDebug: return "phy_debug";
    }
    return "?";
}

}  // namespace sdr
