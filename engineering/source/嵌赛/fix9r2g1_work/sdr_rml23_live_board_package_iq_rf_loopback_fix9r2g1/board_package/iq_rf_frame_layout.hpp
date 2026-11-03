#pragma once

// iq_rf_frame_layout.hpp -- Route F fix9r2 Task R4/R5: the explicit CYCLIC frame
// layout + capture sizing + math sign conventions, shared between the TX-side
// burst builder (iq_rf_training_frame.hpp) and the RX-side recovery core
// (iq_rf_sync_recovery.hpp).
//
// Why this file exists: fix9r1's bug was that the receiver searched only the first
// 4096 samples of the capture for the preamble, even though the TX is a CYCLIC
// buffer whose period is 59904 samples -- so the RX capture start is ARBITRARY and
// the preamble is only inside the first 4096 samples ~6.8% of the time.  This file
// makes the cyclic frame explicit and defines the capture size that guarantees a
// complete [preamble .. tail] burst fits for ANY cyclic start (>= 2 periods), so
// the receiver can search the whole capture and never assume the burst starts at
// sample 0 (Task R4 "不得假定 RX 捕获从循环帧起点开始").
//
// iCraft-free and libiio-free.

#include <cstddef>
#include <cstdint>

#include "iq_rf_training_frame.hpp"   // the ZC sequences + build_burst (TX reference)

namespace iqrflayout {

// Re-export the single source of truth (iqrftrain) so every consumer reads the
// layout from ONE place.
using iqrftrain::kFs;
using iqrftrain::kPreambleComplex;
using iqrftrain::kGuardComplex;
using iqrftrain::kPayloadComplex;
using iqrftrain::kTailComplex;
using iqrftrain::kPayloadStart;
using iqrftrain::kTailStart;
using iqrftrain::kTotalBurstComplex;

// ---- cyclic frame layout (Task R4), all in complex samples, relative to the ----
// ---- burst head (preamble sample 0). -----------------------------------------
//
//   [preamble 1024][guard 2048][payload 53760][guard 2048][tail 1024]
//
constexpr std::size_t kFramePeriodComplex = kTotalBurstComplex;   // 59904
constexpr std::size_t kTrainingOffset     = 0;                    // preamble head
constexpr std::size_t kTrainingLength     = kPreambleComplex;     // 1024
constexpr std::size_t kPayloadOffset      = kPayloadStart;        // 3072
constexpr std::size_t kPayloadLength      = kPayloadComplex;      // 53760
constexpr std::size_t kGuardBeforePayload = kGuardComplex;        // 2048
constexpr std::size_t kGuardAfterPayload  = kGuardComplex;        // 2048
constexpr std::size_t kTailOffset         = kTailStart;           // 58880
constexpr std::size_t kTailLength         = kTailComplex;         // 1024

// ---- capture sizing (Task R4) ------------------------------------------------
// The TX buffer is cyclic, so the RX capture is a WINDOW into an infinite periodic
// stream: the preamble sits at an arbitrary offset p in [0, kFramePeriodComplex).
// Capturing >= 2 full periods guarantees p + kFramePeriodComplex <= capture for
// every p, i.e. a complete [preamble .. tail] burst always fits inside the capture.
constexpr std::size_t kMinCapturePeriods = 2;

// Total capture length in complex samples for a given post-burst delay margin.
inline std::size_t capture_complex(std::size_t delay_margin_complex) {
    return kMinCapturePeriods * kFramePeriodComplex + delay_margin_complex;
}

// ---- math sign conventions (Task R5) -----------------------------------------
//   * A CFO of +f Hz means the received sample equals the transmitted sample times
//     exp(+j 2*pi*f*k/fs).  The recovery therefore DE-rotates by exp(-j 2*pi*f*k/fs)
//     anchored at the burst head (sample 0 == the preamble peak).
//   * The ZC preamble u[k] = exp(-j*pi*r*k^2/N) has differential d[k] =
//     u[k]*conj(u[k-1]) = exp(-j*pi*r*(2k-1)/N), a PURE TONE of frequency -r/N
//     cycles/sample.  Correlating the received differential against d[k] peaks at
//     the preamble start with phase 2*pi*f/fs, so f = arg(corr_peak)*fs/(2*pi)
//     (unambiguous over +/- fs/2 == +/-1.28 MHz -- this is the coarse-CFO mechanism
//     reserved for double-SDR fix10).  fix9r2 (same-Pluto, CFO ~ 0) instead applies
//     the preamble-vs-tail fine CFO (iq_rf_sync_recovery.hpp), which is sub-Hz but
//     unambiguous only over +/- fs/(2*kTailOffset) ~ +/-21.7 Hz.
//   * SRO s = (f_rx - f_tx)/f_tx: a TX sample m lands at RX index m*(1+s).  To
//     recover TX sample m the receiver reads RX index m*(1+s) -- MULTIPLY by
//     (1+s), never divide.
//   * A complex channel gain a is undone by multiplying by a^-1 = conj(a)/|a|^2.

}  // namespace iqrflayout
