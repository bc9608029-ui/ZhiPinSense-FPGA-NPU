#pragma once

// iq_rf_tx_provenance.hpp -- Route F fix9r2 Task R1/R2: byte-level TX provenance +
// an INDEPENDENT TX-frame verifier.
//
// R1 (provenance): every burst passes through five byte stages on its way to the
//     DMA, and each stage is fingerprinted (SHA-256 / RMS / peak / clip + the fixed
//     container semantics I/Q order, bit-width, signedness, endianness).  The five
//     stages are assembled by the transfer (which owns the device + the payload):
//         payload_source          -- the frozen payload ci16 (post target-RMS scale)
//         training_reference      -- the KNOWN preamble+tail (kTrainAmp)
//         framed_logical_iq       -- the full burst
//                                    [pre][settling-zero][training][payload][guard][tail]
//         formatted_tx_container  -- the burst after iio_channel_convert_inverse
//         submitted_iio_buffer    -- the bytes actually handed to iio_buffer_push
//
// R2 (verifier): re-parse the framed burst sample-by-sample and compare the training
//     frame and the payload against the KNOWN references; also assert the guards are
//     zero and the length is exact.  Any mismatch (training_exact_match /
//     payload_exact_match / frame_layout_match) is a hard fail that forbids the push.
//
// iCraft-free and libiio-free: it compiles identically on the host and the board.

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "iq_rf_training_frame.hpp"
#include "../sdr_adapter/sha256.hpp"

namespace iqrftxprov {

// ---- one stage's byte fingerprint -------------------------------------------
struct ByteFingerprint {
    std::string sha256;                // SHA-256 of the interleaved int16 bytes
    std::size_t complex = 0;           // complex sample count
    double rms = 0.0;                  // RMS over all int16
    int peak = 0;                      // max |int16|
    bool clip = false;                 // any sample == +/-32767
    // fixed container semantics (identical for every logical stage; the container
    // stages reuse the SAME 16-bit LE interleaved container, so these stay constant
    // and the meaningful per-stage descriptor is `format_desc`).
    std::string iq_order = "interleaved(I0,Q0,I1,Q1,...)";
    int bits = 16;
    bool is_signed = true;
    std::string endianness = "little";
    // human-readable data-format descriptor (empty for logical stages; the transfer
    // fills it with describe_data_format(tx_data_format()) for the container stages).
    std::string format_desc;
};

inline ByteFingerprint fingerprint(const std::vector<std::int16_t>& iq) {
    ByteFingerprint f;
    f.sha256 = sdr::Sha256::hex(iq.data(), iq.size() * sizeof(std::int16_t));
    f.complex = iq.size() / 2;
    if (iq.empty()) return f;   // rms/peak/clip stay at their zero defaults
    double sum2 = 0.0;
    int peak = 0;
    for (std::int16_t v : iq) {
        const double d = static_cast<double>(v);
        sum2 += d * d;
        const int a = (v < 0) ? (-static_cast<int>(v)) : static_cast<int>(v);
        if (a > peak) peak = a;
    }
    f.rms = std::sqrt(sum2 / static_cast<double>(iq.size()));
    f.peak = peak;
    f.clip = (peak >= 32767);
    return f;
}

// ---- the five-stage provenance (assembled by the transfer) --------------------
struct TxByteProvenance {
    ByteFingerprint payload_source;
    ByteFingerprint training_reference;
    ByteFingerprint framed_logical_iq;
    ByteFingerprint formatted_tx_container;
    ByteFingerprint submitted_iio_buffer;
};

// The known training reference (preamble concatenated with the tail) as interleaved
// int16, exactly as it sits inside the burst at offsets 0 and kTailStart.  This keeps
// its original semantics (preamble + tail) for the existing consumers; the payload-
// domain gain training block is accessed separately below (it is NOT contiguous with
// the preamble or tail in the burst, so it must NOT be concatenated here).
inline std::vector<std::int16_t> training_reference_iq() {
    const std::vector<std::int16_t> pre = iqrftrain::preamble();
    const std::vector<std::int16_t> t = iqrftrain::tail();
    std::vector<std::int16_t> ref;
    ref.reserve(pre.size() + t.size());
    ref.insert(ref.end(), pre.begin(), pre.end());
    ref.insert(ref.end(), t.begin(), t.end());
    return ref;
}

// The payload-domain gain training block as interleaved int16 (the independent
// reference for the block at absolute offset kPayloadTrainingOffset).
inline std::vector<std::int16_t> payload_gain_training_reference() {
    return iqrftrain::payload_gain_training();
}

// ---- R2: independent TX-frame verifier ---------------------------------------
struct TxFrameVerify {
    bool training_exact_match = false;        // preamble@0 + tail@kTailStart bytes match
    bool settling_guard_exact_zero = false;   // settling-zero zone @kPreambleComplex all zero
    bool payload_training_exact_match = false;// training block @kPayloadTrainingOffset matches
    bool payload_exact_match = false;         // payload bytes == the framed payload
    bool frame_layout_match = false;          // guard-after zero + exact total length
    bool ok = false;                          // all five true
};

// Re-parse the framed burst and compare the training frame + payload against the
// known references sample-by-sample.  This is an INDEPENDENT check (it reads the
// burst bytes directly, not the builder), so any framing/packing/order bug that the
// builder and the verifier would otherwise share is caught here.
inline TxFrameVerify verify_frame(const std::vector<std::int16_t>& burst,
                                  const std::vector<std::int16_t>& payload_iq) {
    TxFrameVerify v;
    if (burst.size() != iqrftrain::kTotalBurstComplex * 2)
        return v;   // wrong length -> layout mismatch (everything else stays false)
    const std::vector<std::int16_t> pre = iqrftrain::preamble();
    const std::vector<std::int16_t> t = iqrftrain::tail();
    const std::vector<std::int16_t> pt = iqrftrain::payload_gain_training();
    const std::ptrdiff_t payload_off =
        static_cast<std::ptrdiff_t>(iqrftrain::kPayloadStart * 2);
    const std::ptrdiff_t tail_off =
        static_cast<std::ptrdiff_t>(iqrftrain::kTailStart * 2);
    const std::ptrdiff_t training_off =
        static_cast<std::ptrdiff_t>(iqrftrain::kPayloadTrainingOffset * 2);

    v.training_exact_match =
        std::equal(pre.begin(), pre.end(), burst.begin()) &&
        std::equal(t.begin(), t.end(), burst.begin() + tail_off);
    v.payload_training_exact_match =
        std::equal(pt.begin(), pt.end(), burst.begin() + training_off);
    v.payload_exact_match =
        std::equal(payload_iq.begin(), payload_iq.end(), burst.begin() + payload_off);

    // settling-zero zone between the ZC preamble and the payload training block:
    // @kPreambleComplex, length kPayloadTrainingOffset - kPreambleComplex (1024).
    const std::size_t settle_off = iqrftrain::kPreambleComplex * 2;
    const std::size_t settle_len =
        (iqrftrain::kPayloadTrainingOffset - iqrftrain::kPreambleComplex) * 2;
    bool settling_zero = true;
    for (std::size_t k = 0; k < settle_len; ++k) {
        if (burst[settle_off + k] != 0) {
            settling_zero = false;
            break;
        }
    }
    v.settling_guard_exact_zero = settling_zero;

    // guard-after-payload silence block (kGuardComplex) immediately before the tail.
    const std::size_t guard1 =
        (iqrftrain::kPayloadStart + iqrftrain::kPayloadComplex) * 2;
    bool guard_after_zero = true;
    for (std::size_t k = 0; k < iqrftrain::kGuardComplex * 2; ++k) {
        if (burst[guard1 + k] != 0) {
            guard_after_zero = false;
            break;
        }
    }
    v.frame_layout_match = guard_after_zero;
    v.ok = v.training_exact_match && v.settling_guard_exact_zero &&
           v.payload_training_exact_match && v.payload_exact_match &&
           v.frame_layout_match;
    return v;
}

}  // namespace iqrftxprov
