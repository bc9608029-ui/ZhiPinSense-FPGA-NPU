// Frozen M20 12-class OOD-U contract (C++ mirror of ood_u/contract.py).
//
// These constants must match ood_u/contract.py byte-for-byte.  They are the
// single source of truth for the CPU-side rejection module and are asserted
// fail-closed when loading the threshold manifest.
#ifndef OOD_U_CONTRACT_HPP
#define OOD_U_CONTRACT_HPP

#include <array>
#include <string>
#include <vector>

namespace ood_u_contract {

// Authoritative NPU int8-compiled weights (== model_12class.raw SHA-256).
inline constexpr const char* MODEL_SHA256 =
    "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c";
inline constexpr const char* MODEL_NAME = "12CLASS_CHAIN_VALIDATION_MODEL";

// Frozen 12-class label order (must match contract.LABEL_ORDER_12).
inline const std::array<std::string, 12> LABEL_ORDER_12 = {
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
};

inline constexpr int OUTPUT_DIM = 12;
inline constexpr const char* DIRECTION = "higher_is_ood";

// The five frozen OOD-U score methods (match contract.SCORE_METHODS).
inline const std::vector<std::string> SCORE_METHODS = {
    "msp", "entropy", "max_logit", "logit_margin", "energy",
};

// Decision sentinels.  UNKNOWN is the OOD-U rejection label and must be kept
// distinct from NO_SIGNAL (no input) and ERROR (no valid logits).
inline constexpr const char* UNKNOWN = "UNKNOWN";
inline constexpr const char* NO_SIGNAL = "NO_SIGNAL";
inline constexpr const char* ERROR = "ERROR";
inline constexpr const char* EMPTY = "";

}  // namespace ood_u_contract

#endif  // OOD_U_CONTRACT_HPP
