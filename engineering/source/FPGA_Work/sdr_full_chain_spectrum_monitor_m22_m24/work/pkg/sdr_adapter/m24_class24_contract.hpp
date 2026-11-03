#pragma once

// m24_class24_contract.hpp -- frozen 24-class input/output contract.
//
// The 24-class model is NOT yet trained (24CLASS_MODEL_NOT_READY).  This header
// freezes only the SHAPE and LABEL ORDER of the authoritative 24-class contract,
// so the interface stub and UI mapping can be built and tested against
// deterministic fake logits -- never against a real or pilot checkpoint.

#include <array>
#include <cstddef>
#include <string>

namespace m24 {

// Input contract: [N, 2, 1024] complex IQ (I/Q interleaved as 2 channels).
inline constexpr std::size_t CLASS24_NUM_CLASSES = 24;
inline constexpr std::size_t CLASS24_INPUT_CHANNELS = 2;
inline constexpr std::size_t CLASS24_INPUT_LEN = 1024;
inline constexpr std::size_t CLASS24_INPUT_STRIDE =
    CLASS24_INPUT_CHANNELS * CLASS24_INPUT_LEN;  // 2048 floats per frame

// Authoritative RadioML2018.01A label order, frozen from
// sdr_amr_rml24_ood_v1/data/radioml2018/classes.txt (order preserved verbatim).
inline const std::array<std::string, CLASS24_NUM_CLASSES>& class24_labels() {
    static const std::array<std::string, CLASS24_NUM_CLASSES> labels = {
        "OOK",      "4ASK",      "8ASK",      "BPSK",     "QPSK",
        "8PSK",     "16PSK",     "32PSK",     "16APSK",   "32APSK",
        "64APSK",   "128APSK",   "16QAM",     "32QAM",    "64QAM",
        "128QAM",   "256QAM",    "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
        "AM-DSB-SC", "FM",        "GMSK",      "OQPSK"};
    return labels;
}

}  // namespace m24
