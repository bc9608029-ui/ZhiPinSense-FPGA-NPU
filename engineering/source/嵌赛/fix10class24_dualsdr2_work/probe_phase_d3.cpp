// probe_phase_d3.cpp -- TEMPORARY. Decisive test for Finding 1 (cross-arch RX
// recovery reference): compare the RUNTIME x86-generated training-frame components
// (iq_rf_training_frame.hpp) against the FROZEN CANONICAL components
// (iq_fix10_canonical_frame_data.hpp, frozen from the aarch64 board output).
//
// If any component MISMATCHES, that is exactly why the host replay (x86 runtime
// reference) cannot reproduce the board (aarch64 runtime reference == canonical),
// and why the RX recovery reference must be canonicalized like the TX already is.
#include "iq_rf_training_frame.hpp"
#include "iq_fix10_canonical_frame.hpp"
#include "sha256.hpp"

#include <cstdio>
#include <cstdint>
#include <string>
#include <vector>

static std::string sha_i16(const std::vector<std::int16_t>& v) {
    return sdr::Sha256::hex(v.data(), v.size() * sizeof(std::int16_t));
}

static void cmp(const char* name,
                const std::vector<std::int16_t>& runtime,
                const std::vector<std::int16_t>& canonical,
                const std::string& canonical_sha) {
    const std::string rs = sha_i16(runtime);
    const std::string cs = sha_i16(canonical);
    const bool sha_match = (rs == canonical_sha);
    const bool bytes_match = (runtime == canonical);
    std::printf("== %s ==\n", name);
    std::printf("  runtime   sha=%s\n", rs.c_str());
    std::printf("  canonical sha=%s\n", cs.c_str());
    std::printf("  frozen    sha=%s\n", canonical_sha.c_str());
    std::printf("  sha_match(frozen)=%d bytes_match=%d\n", sha_match ? 1 : 0, bytes_match ? 1 : 0);
    if (!bytes_match) {
        std::size_t n = runtime.size() < canonical.size() ? runtime.size() : canonical.size();
        std::size_t first = n;
        for (std::size_t i = 0; i < n; ++i)
            if (runtime[i] != canonical[i]) { first = i; break; }
        if (first < n)
            std::printf("  FIRST_DIFF int16_index=%zu runtime=%d canonical=%d delta=%d\n",
                        first, (int)runtime[first], (int)canonical[first],
                        (int)runtime[first] - (int)canonical[first]);
        else
            std::printf("  FIRST_DIFF none (length differs: runtime=%zu canonical=%zu)\n",
                        runtime.size(), canonical.size());
    }
}

int main() {
    const fix10canonical::CanonicalMetadata md = fix10canonical::metadata();

    const std::vector<std::int16_t> pre_rt = iqrftrain::preamble();
    const std::vector<std::int16_t> pt_rt  = iqrftrain::payload_gain_training();
    const std::vector<std::int16_t> tail_rt = iqrftrain::tail();

    const std::vector<std::int16_t> pre_c(
        fix10canonical::kCanonicalPreamble.begin(), fix10canonical::kCanonicalPreamble.end());
    const std::vector<std::int16_t> pt_c(
        fix10canonical::kCanonicalPayloadTraining.begin(),
        fix10canonical::kCanonicalPayloadTraining.end());
    const std::vector<std::int16_t> tail_c(
        fix10canonical::kCanonicalTail.begin(), fix10canonical::kCanonicalTail.end());

    std::printf("canonical contract_version=%d\n", md.contract_version);
    cmp("preamble", pre_rt, pre_c, md.preamble_sha);
    cmp("payload_training", pt_rt, pt_c, md.payload_training_sha);
    cmp("tail", tail_rt, tail_c, md.tail_sha);
    return 0;
}
