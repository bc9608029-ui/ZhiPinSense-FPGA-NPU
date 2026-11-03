#pragma once

// Reference (software) re-implementation of the *frozen* deployment physical
// frontend, for the offline File-IQ end-to-end chain only.
//
// On the board this transform is computed in the FPGA Mandatory Core (and its
// int8 quantizer is inside the frozen Core -- this layer does NOT reproduce the
// quantizer).  Here we provide a float reference of the SAME formula so the
// offline chain (FileIqSource -> preprocess -> classify -> ResultFrame) can be
// exercised without hardware:
//
//   power[n]      = I[n]·I[n] + Q[n]·Q[n]
//   lag1_real[n]  = I[n]·I[n-1] + Q[n]·Q[n-1]
//   lag1_imag[n]  = Q[n]·I[n-1] - I[n]·Q[n-1]
//   first sample (n=0): lag1_real = lag1_imag = 0  (deterministic zero)
//
// See contracts/sampling_and_iq_contract.md section 4 (normative).  The hardware
// carries power as unsigned 32-bit and lag terms as signed 33-bit; this software
// reference widens to 64-bit during accumulation then stores float32 for the
// model-side input shape [1,3,1024].
//
// iCraft-free and header-only; unit-tested against hand-computed values.

#include <cstddef>
#include <cstdint>
#include <vector>

namespace preproc {

struct PhysicalPlane {
    std::vector<float> power;      // length == samples
    std::vector<float> lag1_real;  // length == samples
    std::vector<float> lag1_imag;  // length == samples
};

// `iq` points to interleaved [I0,Q0,I1,Q1,...] signed int16 (2*samples entries).
inline PhysicalPlane physical_frontend(const std::int16_t* iq,
                                       std::size_t samples) {
    PhysicalPlane p;
    p.power.resize(samples);
    p.lag1_real.resize(samples);
    p.lag1_imag.resize(samples);

    std::int32_t prev_i = 0, prev_q = 0;
    for (std::size_t n = 0; n < samples; ++n) {
        const std::int32_t i = iq[2 * n];
        const std::int32_t q = iq[2 * n + 1];

        // 64-bit accumulate: I·I + Q·Q fits int32 for int16 inputs but the
        // hardware word is wider, so widen defensively before storing float.
        p.power[n] = static_cast<float>(static_cast<std::int64_t>(i) * i +
                                        static_cast<std::int64_t>(q) * q);

        if (n == 0) {
            p.lag1_real[n] = 0.0f;
            p.lag1_imag[n] = 0.0f;
        } else {
            p.lag1_real[n] = static_cast<float>(static_cast<std::int64_t>(i) * prev_i +
                                                static_cast<std::int64_t>(q) * prev_q);
            p.lag1_imag[n] = static_cast<float>(static_cast<std::int64_t>(q) * prev_i -
                                                static_cast<std::int64_t>(i) * prev_q);
        }
        prev_i = i;
        prev_q = q;
    }
    return p;
}

}  // namespace preproc
