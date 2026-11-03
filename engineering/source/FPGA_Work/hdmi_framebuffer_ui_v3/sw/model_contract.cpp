// model_contract.cpp — the class name/order contracts.
//
// The 10-class V1.1 list is the currently-loaded model's output order and is what
// the board test uses.  The 12-class list is a future target and must never be
// presented as real model output before that model is loaded.

#include "model_contract.hpp"

#include "font.hpp"

namespace model {

bool is_valid_contract(const std::vector<std::string>& names, std::string* why) {
    auto fail = [&](const std::string& m) { if (why) *why = m; return false; };

    const int n = static_cast<int>(names.size());
    if (n < kMinClasses || n > kMaxClasses)
        return fail("class_count out of range [" + std::to_string(kMinClasses) + ".." +
                    std::to_string(kMaxClasses) + "]: " + std::to_string(n));
    for (const std::string& s : names) {
        if (s.empty()) return fail("empty class name");
        for (char c : s) {
            if (!font::is_supported(c))
                return fail("class name has unsupported glyph char: '" + s + "'");
        }
    }
    return true;
}

Contract contract_v1_1() {
    return Contract{
        {"AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
         "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"},
        /*class_count=*/10};
}

Contract contract_target_12() {
    return Contract{
        {"OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK/GMSK",
         "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"},
        /*class_count=*/12};
}

} // namespace model
