#pragma once

// iq_fix10_canonical_frame.hpp -- fix10prep3: cross-architecture DETERMINISTIC
// training-frame assembly.
//
// The root cause fixed here: iq_rf_training_frame.hpp generates the Zadoff-Chu
// preamble/tail and the payload-domain 16QAM training block with std::sin/std::cos/
// std::lround, whose rounding differs between x86 (PC/WSL) and aarch64 (board).  The
// SAME source therefore produced DIFFERENT full-burst bytes on the two ends, and the
// dual-SDR readiness provenance (burst_sha) rejected a good run.
//
// Fix: the three non-zero training components (preamble / payload_training / tail)
// are frozen from the aarch64-board-authoritative output (contracts/
// fix10_canonical_frame_v1) into compile-time arrays in
// iq_fix10_canonical_frame_data.hpp.  Both the PC and the board assemble the burst
// from those SAME bytes, so the full burst SHA is byte-identical across architectures.
//
// This header is ADDITIVE: it does NOT modify any red-line header
// (iq_rf_training_frame.hpp / iq_rf_sync_recovery.hpp / iq_digital_loopback.hpp /
// iq_pc_tx_board_rx_transfer_fix10.hpp).  It REUSES
// iqpctbrx::build_tx_burst_from_frozen for the payload load / verify / RMS scale /
// clip / payload_sha_pre / payload_sha_post / tx_scale (unchanged), and replaces ONLY
// the runtime-generated training components with the embedded canonical ones, then
// recomputes burst_sha.
//
// iCraft-free and libiio-free; compiles identically on host and board.

#include "iq_pc_tx_board_rx_transfer_fix10.hpp"  // TxBurstBuild, build_tx_burst_from_frozen
#include "iq_fix10_canonical_frame_data.hpp"

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

namespace fix10canonical {

// ---------------------------------------------------------------------------
// Canonical contract identity.
// ---------------------------------------------------------------------------
struct CanonicalMetadata {
    int contract_version = 0;
    std::string preamble_sha;
    std::string payload_training_sha;
    std::string tail_sha;
    std::string contract_sha;
};

inline CanonicalMetadata metadata() {
    CanonicalMetadata m;
    m.contract_version = kCanonicalContractVersion;
    m.preamble_sha = kCanonicalPreambleSha;
    m.payload_training_sha = kCanonicalPayloadTrainingSha;
    m.tail_sha = kCanonicalTailSha;
    m.contract_sha = kCanonicalContractSha;
    return m;
}

// One log line printed identically by the PC and the board at first build.
inline std::string contractLine() {
    return std::string("FIX10_CANONICAL_FRAME contract_version=") +
           std::to_string(kCanonicalContractVersion) +
           " preamble_sha=" + kCanonicalPreambleSha +
           " payload_training_sha=" + kCanonicalPayloadTrainingSha +
           " tail_sha=" + kCanonicalTailSha +
           " contract_sha=" + kCanonicalContractSha;
}

// ---------------------------------------------------------------------------
// Fail-closed contract verification: recompute the SHA of each embedded component
// and compare against the frozen constant.  Runs once per process (first use);
// throws on any mismatch (protects against build-time tampering).  Also emits the
// canonical contract line so PC and board logs carry the SAME identity.
// ---------------------------------------------------------------------------
inline void verifyEmbeddedContract() {
    static const bool ok = []() -> bool {
        const std::string p = sdr::Sha256::hex(
            kCanonicalPreamble.data(),
            kCanonicalPreamble.size() * sizeof(std::int16_t));
        const std::string t = sdr::Sha256::hex(
            kCanonicalPayloadTraining.data(),
            kCanonicalPayloadTraining.size() * sizeof(std::int16_t));
        const std::string l = sdr::Sha256::hex(
            kCanonicalTail.data(),
            kCanonicalTail.size() * sizeof(std::int16_t));
        if (p != kCanonicalPreambleSha)
            throw std::runtime_error("fix10canonical: embedded preamble SHA mismatch");
        if (t != kCanonicalPayloadTrainingSha)
            throw std::runtime_error(
                "fix10canonical: embedded payload_training SHA mismatch");
        if (l != kCanonicalTailSha)
            throw std::runtime_error("fix10canonical: embedded tail SHA mismatch");
        std::printf("%s\n", contractLine().c_str());
        std::fflush(stdout);
        return true;
    }();
    (void)ok;
}

// ---------------------------------------------------------------------------
// Assemble the full 59904-complex burst from the embedded canonical components +
// the already-scaled payload.  Layout (== iqrftrain::build_burst):
//   [preamble 1024][settling-zero 1024][payload_training 1024][payload 53760]
//   [guard-zero 2048][tail 1024]
// ---------------------------------------------------------------------------
inline std::vector<std::int16_t> buildBurst(
        const std::vector<std::int16_t>& scaledPayload) {
    if (scaledPayload.size() != iqrftrain::kPayloadComplex * 2)
        throw std::runtime_error(
            "fix10canonical: scaled payload must be exactly " +
            std::to_string(iqrftrain::kPayloadComplex) + " complex samples");

    std::vector<std::int16_t> b;
    b.reserve(iqrftrain::kTotalBurstComplex * 2);

    // preamble (canonical)
    b.insert(b.end(), kCanonicalPreamble.begin(), kCanonicalPreamble.end());
    // settling-zero: 1024 complex of silence (2048 int16 zeros)
    b.insert(b.end(),
             (iqrftrain::kPayloadTrainingOffset - iqrftrain::kPreambleComplex) * 2,
             std::int16_t{0});
    // payload-domain gain training (canonical)
    b.insert(b.end(), kCanonicalPayloadTraining.begin(),
             kCanonicalPayloadTraining.end());
    // scaled payload
    b.insert(b.end(), scaledPayload.begin(), scaledPayload.end());
    // guard-zero: 2048 complex of silence (4096 int16 zeros)
    b.insert(b.end(), iqrftrain::kGuardComplex * 2, std::int16_t{0});
    // tail (canonical)
    b.insert(b.end(), kCanonicalTail.begin(), kCanonicalTail.end());

    if (b.size() != iqrftrain::kTotalBurstComplex * 2)
        throw std::runtime_error("fix10canonical: built burst length mismatch");
    return b;
}

// ---------------------------------------------------------------------------
// Canonical TX-burst build.  REUSES iqpctbrx::build_tx_burst_from_frozen for the
// payload load / verify / RMS scale / clip / payload_sha_pre / payload_sha_post /
// tx_scale (all unchanged), then replaces the runtime-generated training frame with
// the embedded canonical components and recomputes burst_sha.  Throws fail-closed on
// a SHA mismatch / empty waveform / wrong length / embedded-contract tamper.
// ---------------------------------------------------------------------------
inline iqpctbrx::TxBurstBuild buildTxBurstFromFrozen(const std::string& path,
                                                     std::uint64_t complex_count,
                                                     const std::string& expect_sha,
                                                     double target_rms) {
    verifyEmbeddedContract();
    iqpctbrx::TxBurstBuild r =
        iqpctbrx::build_tx_burst_from_frozen(path, complex_count, expect_sha, target_rms);
    r.burst = buildBurst(r.payload);
    r.burst_sha = sdr::Sha256::hex(r.burst.data(),
                                   r.burst.size() * sizeof(std::int16_t));
    return r;
}

}  // namespace fix10canonical
