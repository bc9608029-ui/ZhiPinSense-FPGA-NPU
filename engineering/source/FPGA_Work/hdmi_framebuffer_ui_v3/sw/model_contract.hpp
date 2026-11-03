// model_contract.hpp — the single source of truth for the class NAME/ORDER.
//
// The UI renderer is fully generic over 8..16 classes: it takes `class_names`,
// `probabilities` and `class_count` at runtime and NEVER hard-codes a class list.
// The class order comes from THIS file (the "runtime model contract"), not from
// any UI code.  Changing the active model contract changes what the board shows
// with no renderer change.
//
//   * Active board-test contract (V1.1, 10 classes) is the currently-loaded model:
//       AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM
//   * Target 12-class contract is RESERVED for the future model — it must NOT be
//     presented as real model output until that model is actually loaded.  It is
//     listed here only so the renderer's 8..16 range is exercised in host tests.
//
// Validation: class_count must be in [8,16]; class_names.size() must equal
// class_count; names must be non-empty and contain only glyph-supported chars.

#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace model {

constexpr int kMinClasses = 8;
constexpr int kMaxClasses = 16;

// A resolved model contract: the ordered class list the model actually outputs.
struct Contract {
    std::vector<std::string> class_names;   // order = model output order (argmax index)
    int class_count = 0;

    bool empty() const { return class_names.empty(); }
    int size() const { return class_count; }
    const std::string& name(int idx) const { return class_names[static_cast<std::size_t>(idx)]; }
};

// Validates a contract: count in [8,16], name list matches count, every name
// non-empty and composed only of chars the bitmap font can render.  Writes a
// reason to `why` (when non-null) on failure.
bool is_valid_contract(const std::vector<std::string>& names, std::string* why = nullptr);

// The active V1.1 board-test contract (10 classes, currently-loaded model).
Contract contract_v1_1();

// The reserved target 12-class contract (future model).  NOT the current model.
Contract contract_target_12();

} // namespace model
