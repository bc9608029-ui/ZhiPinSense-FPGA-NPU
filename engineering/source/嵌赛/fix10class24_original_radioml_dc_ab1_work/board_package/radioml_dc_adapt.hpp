#pragma once

// radioml_dc_adapt.hpp -- task fix10class24-original-radioml-dc-ab1: the SINGLE shared
// DC-adaptation implementation for BOTH the dual-SDR and single-SDR board runners.
//
// The DC layer is implemented ONCE here (constants + the model-window reconstruction);
// radioml_dualsdr_ab_{loader,runner}.hpp and radioml_singlesdr_ab_{loader,runner}.hpp
// both #include this header and call the SAME functions -- there is NO second copy of
// the DC math anywhere.  The direct adaptation (cyclic tile -> CI16 -> * unscale) is
// untouched: it keeps its existing byte-identical behavior, and this header only ADDS
// a second frozen adaptation tag + the three-stage undo (see the offline contract
// contract/dc_transport_adaptation_contract.md, the single authority for the math).
//
//   adaptation tag  direct        = "cyclic_tile_1024_to_53760_rms2048_ci16"
//   adaptation tag  dc-transport  = "dc_transport_cyclic_tile_1024_to_53760_rms2048_ci16"
//
//   dc-transport model window (three stages, strictly separated, no double scale-undo):
//     stage 1  RF gain recovery = recover_payload_with_coarse_cfo (unchanged, shared
//              with direct; expected.tx_scale ~ 1.0 because the .i16 is pre-scaled to
//              RMS 2048).
//     stage 2  TX scale undo    = counts[:1024] * inverse_scale   (ac_rms / 2048).
//     stage 3  DC add-back      = + (dc_i + j*dc_q).
//
// The DC parameters (dc_i / dc_q / ac_rms / inverse_scale) are bound to the input SHA
// and read from the per-frame manifest, NEVER derived from class or recognition result.

#include <complex>
#include <string>

namespace rml24dc {

// The two frozen adaptation tags (must match scripts/radioml_dc_adapt.py byte-for-byte).
inline const char* kAdaptationDirect() {
    return "cyclic_tile_1024_to_53760_rms2048_ci16";
}
inline const char* kAdaptationDcTransport() {
    return "dc_transport_cyclic_tile_1024_to_53760_rms2048_ci16";
}

inline bool is_direct(const std::string& a) {
    return a == kAdaptationDirect();
}
inline bool is_dc_transport(const std::string& a) {
    return a == kAdaptationDcTransport();
}
inline bool valid_adaptation(const std::string& a) {
    return is_direct(a) || is_dc_transport(a);
}

// The 4-column suffix appended to the 18-column direct manifest header to form the
// 22-column dc-transport manifest header (dc_i, dc_q, ac_rms, inverse_scale).  It must
// match scripts/radioml_dc_adapt.py::DC_EXTRA_HEADER + scripts/export_radioml_dc_tx_payload.py.
inline const char* dc_extra_header() {
    return "\tdc_i\tdc_q\tac_rms\tinverse_scale";
}

// The per-frame DC parameters (bound to the input SHA; never to class / prediction).
struct DcParams {
    double dc_i = 0.0;          // mean(iq).real
    double dc_q = 0.0;          // mean(iq).imag
    double ac_rms = 0.0;        // native_rms(iq - dc)  (complex RMS)
    double inverse_scale = 0.0; // ac_rms / 2048  (counts -> AC f32 domain)
};

// Reconstruct the dc-transport model window (stages 2 + 3) into the planar [2, n]
// f32 tensor (the SAME layout as the direct path: real at [0..n), imag at [n..2n)).
// `payload` is the recovered payload's first n complex counts (ccr.payload[:1024]).
inline void reconstruct_dc_window(const std::complex<double>* payload, std::size_t n,
                                  const DcParams& p, float* tensor) {
    for (std::size_t k = 0; k < n; ++k) {
        const double ac_r = payload[k].real() * p.inverse_scale;   // stage 2
        const double ac_i = payload[k].imag() * p.inverse_scale;   // stage 2
        tensor[k] = static_cast<float>(ac_r + p.dc_i);             // stage 3
        tensor[n + k] = static_cast<float>(ac_i + p.dc_q);         // stage 3
    }
}

}  // namespace rml24dc
