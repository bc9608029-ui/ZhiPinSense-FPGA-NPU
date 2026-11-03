#pragma once

// Category (class-name) contract for the non-model system layer.
//
// The classification output width is NOT hardcoded anywhere in this layer: it is
// carried by cat::Contract and validated against [kMinClasses, kMaxClasses].
// Three contracts are provided, each with a provenance tag so nothing is ever
// mistaken for the wrong model:
//
//   frozen_8    -- the *deployment Mandatory Core* output order (tied to the
//                  frozen model.raw + reference_argmax.txt; MUST NOT change).
//   current_10  -- the V1.1 AMR model (model_ad_amr_v1_1) output order.
//   target_12   -- the reserved future-model order (RESERVED, not a real output
//                  today; do NOT treat as inference).
//
// The authoritative 12-class order is fixed as (2026-10-05):
//   OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM.
// The 10-class order follows model_ad_amr_v1_1 (V1.1 AMR).  The historical
// F:/FPGA_Work/hdmi_framebuffer_ui_v3/sw/model_contract.cpp is DEPRECATED and
// its old 12-class list is OBSOLETE -- do NOT source the order from it.  The
// frozen 8 order is
//   board_package/continuous_joint_stress.cpp (kClasses) and
//   contracts/sampling_and_iq_contract.md section 2.
//
// iCraft-free and header-only; unit-tested (orders, counts, validity range).

#include <cstddef>
#include <string>
#include <vector>

namespace cat {

// Contract validity range.  The frozen Mandatory Core model has 8 classes; the
// V1.1 AMR model 10; the target twelve-class chain 12; the RML2018 24-class model
// 24 (and its deployed 23-class AM-SSB merge).  Widen only when a real model is
// added -- never narrower than the widest shipped contract.
constexpr int kMinClasses = 8;
constexpr int kMaxClasses = 24;

struct Contract {
    std::vector<std::string> class_names;  // index order == logits order
    int class_count = 0;                   // == class_names.size() when valid
    const char* provenance = "unspecified";  // "frozen" / "current" / "target"
};

// Deployment Mandatory Core output order (frozen; do NOT change).
inline Contract frozen_8() {
    return Contract{{"BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK",
                     "OFDM"},
                    8,
                    "frozen"};
}

// V1.1 AMR model output order (current, 10 classes).
inline Contract current_10() {
    return Contract{{"AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK", "QPSK", "8PSK",
                     "16QAM", "64QAM", "OFDM"},
                    10,
                    "current"};
}

// Reserved future model order (target, 12 classes).  RESERVED: not a real model
// output today -- do NOT feed this list to any real inference path.
inline Contract target_12() {
    return Contract{{"OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
                     "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"},
                    12,
                    "target"};
}

// RML2018 24-class source order (M29).  FROZEN: the NPU emits exactly these 24
// raw logits, index 17 = AM-SSB-WC, index 18 = AM-SSB-SC.  This order is the
// authoritative 24-dim contract; the 23-class deployment order below is derived
// from it by the AM-SSB logaddexp merge (see board_package/rml23_merged.hpp).
inline Contract target_24() {
    return Contract{{"OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK",
                     "32PSK", "16APSK", "32APSK", "64APSK", "128APSK",
                     "16QAM", "32QAM", "64QAM", "128QAM", "256QAM",
                     "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
                     "FM", "GMSK", "OQPSK"},
                    24,
                    "rml24"};
}

// RML2018 23-class deployed order (M29 Phase F).  AM-SSB-WC/SC (source 17/18)
// merge into a single "AM-SSB" at slot 17; source 19..23 shift down by one.  This
// is the label order the 23-class result protocol and UI use.  FROZEN label order
// SHA256 == 15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88.
inline Contract target_23() {
    return Contract{{"OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK",
                     "32PSK", "16APSK", "32APSK", "64APSK", "128APSK",
                     "16QAM", "32QAM", "64QAM", "128QAM", "256QAM",
                     "AM-SSB", "AM-DSB-WC", "AM-DSB-SC", "FM", "GMSK",
                     "OQPSK"},
                    23,
                    "rml23"};
}

// Validate a contract: class_count in [kMinClasses, kMaxClasses], names vector
// non-empty and length == class_count, every name non-empty.  On failure fills
// `why` (when non-null) and returns false.
inline bool is_valid(const Contract& c, std::string* why = nullptr) {
    auto fail = [&](const char* m) {
        if (why) *why = m;
        return false;
    };
    if (c.class_count < kMinClasses || c.class_count > kMaxClasses)
        return fail("class_count out of range");
    if (static_cast<int>(c.class_names.size()) != c.class_count)
        return fail("class_names size != class_count");
    for (const std::string& n : c.class_names)
        if (n.empty()) return fail("empty class name");
    return true;
}

// Human-readable class label for a logits index; "<i>" when out of range.
inline std::string label(const Contract& c, int idx) {
    if (idx < 0 || idx >= static_cast<int>(c.class_names.size()))
        return "<" + std::to_string(idx) + ">";
    return c.class_names[static_cast<std::size_t>(idx)];
}

}  // namespace cat
