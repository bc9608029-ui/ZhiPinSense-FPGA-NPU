#pragma once

// iq_digital_loopback_sweep.hpp — Stage H-E / Route E: the digital-loopback
// AMPLITUDE sweep + root-cause classification for the RX amplitude loss seen on
// board.
//
// fix4 corrects the fix3 discriminator, which misjudged the ~ -24 dB raw-container
// loss as "ambiguous" because it (a) never propagated kind/target_rms into the
// levels, (b) applied an unconditional 12-bit mask in format_convert_raw_to_host
// that turned a fully-defined right-justified negative (-32 = 0xFFE0) into a false
// +4064 RMS/clip, and (c) compared TX/RX counts directly without accounting for the
// TX-16-bit vs RX-12-bit signed full scale.  fix4 introduces the COUNT-domain vs
// NORMALIZED-domain pair:
//
//   count_gain_db      = 20 log10(rx_count_rms / tx_count_rms)   (raw container)
//   normalized_gain_db = 20 log10((rx_count/2^(rx_bits-1)) / (tx_count/2^(tx_bits-1)))
//
// A -24.08 dB count gain with a ~0 dB normalized gain is DIGITAL_LOOPBACK_COUNT_
// DOMAIN_SCALE (the bit-width full-scale difference), NOT a real loopback
// attenuation.  Only a board run may confirm it (normalized ~0 dB AND corr >=
// threshold AND no clip AND multi-level linear AND libiio == host mirror); the
// encoding stage never pre-bakes that conclusion.
//
// Pure logic over pluto::Device (fake on host, libiio on board) + pluto::PlutoTx
// (the RF-safety state machine).  It never opens the NPU and never touches libiio
// directly.  Fix3 requirements and where each lives here:
//   req 1  audit the TX/RX data format            -> SweepReport.{rx_fmt,tx_fmt} +
//             the round-trip identity self-check (printed by the board wrapper)
//   req 2  sweep tone/ramp/PRBS at RMS 8..512     -> make_sweep_waveform()
//   req 3  per level: TX logical, convert_inverse raw, RX raw, convert'd logical,
//             gain dB, corr, clip rate            -> sweep_one_level() + SweepLevel
//   req 4  classify: libiio convert / 12-bit shift / HDL alignment / fixed gain /
//             count-domain scale -> classify_root_cause()
//   req 5  if a FORMAT error, fix the FORMAT (never an empirical multiplier)
//             -> find_correct_rx_shift() searches the bit position
//   req 6/7 if count-domain scale or a fixed loopback gain, auto-select a TX scale
//             (test fixture only) -> auto_select_scale()
//
// iCraft-free, libiio-free.

#include "iq_digital_loopback.hpp"
#include "../sdr_adapter/pluto_device.hpp"
#include "../sdr_adapter/pluto_tx.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace iqdloop_sweep {

// Sweep grid (logical RMS counts).  Highest is 512: with a ~24 dB loss the RX RMS
// is ~32, still inside the auto-select window [16,128], so the grid resolves the
// loss without the TX itself ever nearing the 2048 full scale.
const double kSweepLevels[] = {8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0};
const char* const kSweepKinds[] = {"tone", "ramp", "prbs"};

// Discard-refill length for the stale flush before each sweep capture (matches
// iqdloop_run::kDiscardComplex in spirit; kept local so this header stays
// independent of the transfer header).
constexpr std::size_t kSweepDiscardComplex = 4096;

// Raw/logical gain within +/- this many dB counts as "preserved" in the
// discriminator.
constexpr double kGainPreservedDb = 3.0;

// Correlation threshold for "the waveform is actually preserved": a correct
// normalized gain WITHOUT this correlation is still NOT_PROVEN.  Same value the
// shift search / scale selection used (now a named constant).
constexpr double kFidelityCorrThreshold = 0.9;

// RX count RMS at or below this is indistinguishable from quantization noise; such
// a level is quantization-boundary evidence, not a gain measurement.
constexpr double kQuantFloorCounts = 2.0;

// ---- small numeric helpers --------------------------------------------------

inline std::uint32_t norm_bits(std::uint32_t bits) {
    return (bits == 0 || bits > 16) ? 16u : bits;
}

// Signed full scale for a `bits`-wide two's-complement value: 2^(bits-1).  The
// count-domain -> normalized-domain mapping divides by this (NOT a hardcoded
// 16/12): the board's TX reports 16 bits (fs 32768), RX 12 bits (fs 2048).
inline double signed_full_scale(std::uint32_t bits) {
    return std::ldexp(1.0, static_cast<int>(norm_bits(bits)) - 1);
}

inline double rms_magnitude(const std::vector<std::int16_t>& iq) {
    double e = 0.0;
    const std::size_t n = iq.size() / 2;
    for (std::size_t k = 0; k < n; ++k) {
        const double i = iq[k * 2 + 0];
        const double q = iq[k * 2 + 1];
        e += i * i + q * q;
    }
    return n ? std::sqrt(e / static_cast<double>(n)) : 0.0;
}

inline std::int16_t max_abs_sample(const std::vector<std::int16_t>& iq) {
    std::int16_t m = 0;
    for (std::int16_t v : iq)
        m = std::max(m, static_cast<std::int16_t>(
                            std::abs(static_cast<int>(v))));
    return m;
}

inline std::uint64_t count_clip(const std::vector<std::int16_t>& iq,
                                std::int16_t threshold) {
    std::uint64_t n = 0;
    for (std::int16_t v : iq)
        if (std::abs(static_cast<int>(v)) >= threshold) ++n;
    return n;
}

inline double median(std::vector<double> v) {
    if (v.empty()) return 0.0;
    std::sort(v.begin(), v.end());
    const std::size_t n = v.size();
    return (n % 2) ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

// Scale an interleaved int16 waveform so its measured complex-magnitude RMS equals
// `target_rms` (the same definition align_and_measure_int16 uses for rms_tx/rms_rx).
inline void scale_to_rms(std::vector<std::int16_t>& iq, double target_rms) {
    const double rms = rms_magnitude(iq);
    if (rms <= 0.0) return;
    const double s = target_rms / rms;
    for (auto& v : iq) {
        const double sv = std::llround(static_cast<double>(v) * s);
        v = static_cast<std::int16_t>(
            std::max(-32768.0, std::min(32767.0, sv)));
    }
}

// ---- deterministic sweep waveforms (tone / ramp / prbs) ---------------------

inline std::vector<std::int16_t> make_sweep_waveform(const std::string& kind,
                                                     double target_rms,
                                                     std::size_t n_complex) {
    std::vector<std::int16_t> iq(n_complex * 2, 0);
    const double kPi = 3.14159265358979323846;
    if (kind == "tone") {
        // Complex tone at fs/16 (16 samples/cycle): |x| constant so measured RMS
        // == amplitude, and integer cycles keep the cyclic buffer periodic.
        const double ph = 2.0 * kPi / 16.0;
        for (std::size_t k = 0; k < n_complex; ++k) {
            iq[k * 2 + 0] = static_cast<std::int16_t>(
                std::llround(1000.0 * std::cos(ph * static_cast<double>(k))));
            iq[k * 2 + 1] = static_cast<std::int16_t>(
                std::llround(1000.0 * std::sin(ph * static_cast<double>(k))));
        }
    } else if (kind == "ramp") {
        // Real sawtooth -A..+A on I (Q = 0): covers every amplitude level
        // deterministically, exercising the full quantizer transfer curve.
        for (std::size_t k = 0; k < n_complex; ++k) {
            const double t = (static_cast<double>(k) /
                              static_cast<double>(n_complex)) * 2.0 - 1.0;
            iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(1000.0 * t));
            iq[k * 2 + 1] = 0;
        }
    } else {  // "prbs"
        // 16-bit Galois LFSR PRBS on I and Q independently: pseudo-random +/-A,
        // spectrally flat and deterministic (seed fixed).
        std::uint32_t st = 0xACE1u;
        const auto bit = [&st]() {
            const std::uint32_t b =
                ((st >> 0) ^ (st >> 2) ^ (st >> 3) ^ (st >> 5)) & 1u;
            st = (st >> 1) | (b << 15);
            return b;
        };
        for (std::size_t k = 0; k < n_complex; ++k) {
            iq[k * 2 + 0] = bit() ? 1000 : -1000;
            iq[k * 2 + 1] = bit() ? 1000 : -1000;
        }
    }
    scale_to_rms(iq, target_rms);
    return iq;
}

// ---- sign-extension self-check (fix4) ----------------------------------------

// Proves the corrected convert mirror matches libiio semantics across the three
// layout families.  Returned struct is printed by the board wrapper as SIGNCHECK.
struct SignCheck {
    bool fully_defined_ok = false;
    bool sign_extend_ok = false;
    bool shift4_ok = false;
    bool ok = false;
};

inline SignCheck verify_sign_extension() {
    SignCheck sc;
    const auto mk = [](std::uint32_t length_bits, std::uint32_t bits,
                       std::uint32_t shift, bool fully_defined) {
        pluto::DataFormatInfo f;
        f.length_bits = length_bits; f.bits = bits; f.shift = shift;
        f.is_signed = true; f.is_fully_defined = fully_defined;
        f.is_be = false; f.repeat = 1;
        return f;
    };
    const pluto::DataFormatInfo fd0 = mk(16, 12, 0, true);    // fully-defined signed
    const pluto::DataFormatInfo nfd0 = mk(16, 12, 0, false);  // not-fully-defined signed
    const pluto::DataFormatInfo nfd4 = mk(16, 12, 4, false);

    const std::int16_t NEG_FFFF = static_cast<std::int16_t>(0xFFFF);
    const std::int16_t NEG_FFE0 = static_cast<std::int16_t>(0xFFE0);
    const std::int16_t NEG_F800 = static_cast<std::int16_t>(0xF800);
    const std::int16_t POS_07FF = static_cast<std::int16_t>(0x07FF);
    const std::int16_t POS_0FFF = static_cast<std::int16_t>(0x0FFF);
    const std::int16_t POS_0800 = static_cast<std::int16_t>(0x0800);
    const std::int16_t POS_7FF0 = static_cast<std::int16_t>(0x7FF0);
    const std::int16_t POS_8000 = static_cast<std::int16_t>(0x8000);

    sc.fully_defined_ok =
        pluto::format_convert_raw_to_host(fd0, NEG_FFFF) == -1 &&
        pluto::format_convert_raw_to_host(fd0, NEG_FFE0) == -32 &&
        pluto::format_convert_raw_to_host(fd0, NEG_F800) == -2048 &&
        pluto::format_convert_raw_to_host(fd0, POS_07FF) == 2047;
    sc.sign_extend_ok =
        pluto::format_convert_raw_to_host(nfd0, POS_0FFF) == -1 &&
        pluto::format_convert_raw_to_host(nfd0, POS_0800) == -2048 &&
        pluto::format_convert_raw_to_host(nfd0, POS_07FF) == 2047;
    sc.shift4_ok =
        pluto::format_convert_raw_to_host(nfd4, POS_7FF0) == 2047 &&
        pluto::format_convert_raw_to_host(nfd4, POS_8000) == -2048;
    sc.ok = sc.fully_defined_ok && sc.sign_extend_ok && sc.shift4_ok;
    return sc;
}

// ---- per-level measurement --------------------------------------------------

// One captured sample position: the raw container word plus every convert
// reference, kept so the board wrapper can print the exact bit-level evidence and
// the analyzer can independently re-derive the divergence.
struct SweepSample {
    std::int16_t tx_logical = 0;      // TX host value (what was loaded)
    std::int16_t tx_raw = 0;          // convert_inverse container word
    std::int16_t rx_raw = 0;          // RX raw container word (before convert)
    std::int16_t rx_libiio = 0;       // actual libiio RX convert of rx_raw
    std::int16_t rx_host_mirror = 0;  // host mirror of the REPORTED RX format
    std::int16_t rx_force_signed = 0; // force-signed diagnostic view
};

// One candidate RX convert bit position (shift 0..4) evaluated against a level.
struct ShiftScanEntry {
    int shift = 0;
    double count_gain_db = 0.0;       // raw-container gain (shift-INDEPENDENT)
    double normalized_gain_db = 0.0;  // raw-container gain, bit-width-normalized
    double logical_gain_db = 0.0;     // decoded-logical gain AT THIS shift
    double corr = 0.0;
    double clip_rate = 0.0;
};

struct SweepLevel {
    std::string kind;              // "tone" | "ramp" | "prbs"
    double target_rms = 0.0;       // logical RMS target (counts)
    double tx_logical_rms = 0.0;   // measured TX logical RMS (complex magnitude)
    double rx_logical_rms = 0.0;   // measured RX logical RMS (reported-format convert)
    double gain_db = 0.0;          // LS complex gain, logical domain
    double corr = 0.0;             // |correlation|, logical domain
    double tx_raw_rms = 0.0;       // TX raw container RMS (convert_inverse output)
    double rx_raw_rms = 0.0;       // RX raw container RMS (before convert)
    double raw_gain_db = 0.0;      // 20 log10(rx_raw_rms / tx_raw_rms)
    std::int16_t tx_logical_peak = 0;   // max |.| TX logical sample
    std::int16_t tx_raw_peak = 0;       // max |.| convert_inverse container sample
    std::int16_t rx_raw_peak = 0;       // max |.| RX raw container sample
    std::uint64_t tx_clip = 0;     // TX logical samples at |v| >= 2047 (DAC rail)
    std::uint64_t rx_clip = 0;     // RX logical samples at |v| >= 2047 (ADC rail)
    std::uint64_t rx_raw_clip = 0; // RX raw samples at |v| >= 32767 (16-bit rail)
    double clip_rate = 0.0;        // rx_clip / (2 * rx_complex)
    std::uint64_t rx_nonzero = 0;
    bool capture_ok = false;
    bool convert_diverged = false; // tx_raw_after_inverse != host mirror of tx format
    // fix4 count-domain vs normalized-domain split.  Count domain = raw 16-bit
    // container RMS; normalized = count / 2^(bits-1) (signed full scale from the
    // DATA FORMAT, never hardcoded).
    double tx_count_rms = 0.0;        // == tx_raw_rms (count domain)
    double rx_count_rms = 0.0;        // == rx_raw_rms (count domain)
    double count_gain_db = 0.0;       // 20 log10(rx_count_rms / tx_count_rms)
    double tx_normalized_rms = 0.0;   // tx_count_rms / 2^(tx_bits-1)
    double rx_normalized_rms = 0.0;   // rx_count_rms / 2^(rx_bits-1)
    double normalized_gain_db = 0.0;  // 20 log10(rx_normalized / tx_normalized)
    bool rx_libiio_diverged = false;  // any sample: libiio RX convert != host mirror
    std::vector<ShiftScanEntry> shift_scan;  // shift 0..4 decode evidence
    std::vector<SweepSample> samples;        // >= 8 captured raw+convert positions
    // Full containers, kept so the board wrapper can print raw bytes and so
    // find_correct_rx_shift can re-derive the logical value at any bit position.
    std::vector<std::int16_t> tx_host;   // the logical waveform that was TX'd
    std::vector<std::int16_t> tx_raw;    // dry-run convert_inverse output
    std::vector<std::int16_t> rx_raw;    // the raw capture container
};

// One candidate RX convert bit position (shift 0..4) evaluated against a level.
// Re-decode rx_raw at the candidate shift with the corrected mirror, then measure
// the correlation and clip rate.  count/normalized gain are raw-container
// quantities and therefore shift-INDEPENDENT (the raw container is what travelled
// the loopback); only corr + clip_rate depend on the decode shift.
inline ShiftScanEntry measure_shift(const std::vector<std::int16_t>& tx_host,
                                    const std::vector<std::int16_t>& tx_raw,
                                    const std::vector<std::int16_t>& rx_raw,
                                    const pluto::DataFormatInfo& tx_fmt,
                                    const pluto::DataFormatInfo& rx_fmt,
                                    int shift, std::uint64_t fs,
                                    std::size_t delay_margin) {
    ShiftScanEntry e;
    e.shift = shift;
    pluto::DataFormatInfo cand = rx_fmt;
    cand.shift = static_cast<std::uint32_t>(shift);
    std::vector<std::int16_t> logical(rx_raw.size());
    for (std::size_t k = 0; k < rx_raw.size(); ++k)
        logical[k] = pluto::format_convert_raw_to_host(cand, rx_raw[k]);

    const iqdloop::FidelityMetrics m =
        iqdloop::align_and_measure_int16(tx_host, logical, fs, delay_margin);
    e.corr = m.corr;
    e.logical_gain_db = m.gain_db;   // 20 log10(rms(rx_logical)/rms(tx_host))

    const double tx_count = rms_magnitude(tx_raw);
    const double rx_count = rms_magnitude(rx_raw);
    e.count_gain_db = (tx_count > 0.0 && rx_count > 0.0)
                          ? 20.0 * std::log10(rx_count / tx_count)
                          : -200.0;
    const double tx_fs = signed_full_scale(tx_fmt.bits);
    const double rx_fs = signed_full_scale(rx_fmt.bits);
    e.normalized_gain_db =
        (tx_count > 0.0 && rx_count > 0.0 && tx_fs > 0.0 && rx_fs > 0.0)
            ? 20.0 * std::log10((rx_count / rx_fs) / (tx_count / tx_fs))
            : -200.0;

    e.clip_rate = static_cast<double>(count_clip(logical, 2047)) /
                  static_cast<double>(logical.size());
    return e;
}

// Run one sweep level: dry-run the TX convert, TX it cyclically (PlutoTx safety
// machine, -40 dB ceiling enforced), flush the stale RX buffer, then capture the
// RAW container in one contiguous refill and convert it back to logical with the
// REPORTED RX format (exactly what read_rx does on the board).  Every measurement
// the classifier needs is recorded; nothing is inferred from a heuristic
// multiplier.
inline SweepLevel sweep_one_level(pluto::Device& dev, std::uint64_t center_hz,
                                  double rx_gain_db, double tx_atten_db,
                                  const std::string& kind, double target_rms,
                                  const pluto::DataFormatInfo& tx_fmt,
                                  const pluto::DataFormatInfo& rx_fmt,
                                  const std::vector<std::int16_t>& tx_iq,
                                  std::uint64_t fs, std::size_t delay_margin,
                                  std::size_t capture_complex) {
    SweepLevel L;
    L.capture_ok = false;
    L.kind = kind;
    L.target_rms = target_rms;
    L.tx_host = tx_iq;

    // TX raw container = exactly what tx_start_cyclic writes.
    dev.tx_raw_after_inverse(tx_iq, L.tx_raw);

    // Cross-check libiio convert_inverse against the host mirror of the REPORTED
    // TX format.  During the sweep no override is set, so a divergence is the
    // "libiio convert semantics" bucket (req 4).
    if (!dev.has_tx_format_override()) {
        for (std::size_t k = 0; k < tx_iq.size() && !L.convert_diverged; ++k)
            if (pluto::format_convert_host_to_raw(tx_fmt, tx_iq[k]) != L.tx_raw[k])
                L.convert_diverged = true;
    }

    {
        pluto::TxConfig txc;
        txc.center_freq_hz = center_hz;
        txc.rx_gain_db = rx_gain_db;
        txc.tx_atten_db = tx_atten_db;
        txc.loopback = 1;                  // digital
        txc.confirm_safe_rf_path = false;  // no antenna / no coax
        txc.waveform = tx_iq;
        pluto::PlutoTx tx(dev, txc);
        tx.prepare();                      // enforce -40 dB ceiling (req 9)
        tx.start_cyclic();

        dev.recreate_rx_buffer();
        dev.read_rx_raw(kSweepDiscardComplex, 1000);   // stale-flush discard
        const iio::RawChunk c = dev.read_rx_raw(capture_complex, 1000);
        if (!c.broken && c.samples_available > 0)
            L.rx_raw.assign(c.samples, c.samples + c.samples_available * 2);
    }

    if (L.rx_raw.empty()) return L;

    // Convert the RAW container back to logical using the REPORTED RX format --
    // the same convert read_rx performs on the board (so a wrong reported shift
    // shows up here as a logical loss while the raw container stays intact).
    std::vector<std::int16_t> rx_logical(L.rx_raw.size());
    for (std::size_t k = 0; k < L.rx_raw.size(); ++k)
        rx_logical[k] = pluto::format_convert_raw_to_host(rx_fmt, L.rx_raw[k]);

    // Logical-domain fidelity via the shared circular-alignment measure.
    const iqdloop::FidelityMetrics m =
        iqdloop::align_and_measure_int16(tx_iq, rx_logical, fs, delay_margin);
    L.gain_db = m.gain_db;
    L.corr = m.corr;
    L.tx_logical_rms = m.rms_tx;
    L.rx_logical_rms = m.rms_rx;
    L.rx_nonzero = m.rx_nonzero;

    // Raw-domain (container) stats.
    L.tx_raw_rms = rms_magnitude(L.tx_raw);
    L.rx_raw_rms = rms_magnitude(L.rx_raw);
    L.raw_gain_db = (L.tx_raw_rms > 0.0 && L.rx_raw_rms > 0.0)
                        ? 20.0 * std::log10(L.rx_raw_rms / L.tx_raw_rms)
                        : -200.0;

    // fix4 count-domain vs normalized-domain split (TX16/RX12 full scale).
    L.tx_count_rms = L.tx_raw_rms;
    L.rx_count_rms = L.rx_raw_rms;
    L.count_gain_db = L.raw_gain_db;
    const double tx_fs = signed_full_scale(tx_fmt.bits);
    const double rx_fs = signed_full_scale(rx_fmt.bits);
    L.tx_normalized_rms = tx_fs > 0.0 ? L.tx_count_rms / tx_fs : 0.0;
    L.rx_normalized_rms = rx_fs > 0.0 ? L.rx_count_rms / rx_fs : 0.0;
    L.normalized_gain_db =
        (L.tx_normalized_rms > 0.0 && L.rx_normalized_rms > 0.0)
            ? 20.0 * std::log10(L.rx_normalized_rms / L.tx_normalized_rms)
            : -200.0;

    L.tx_logical_peak = max_abs_sample(tx_iq);
    L.tx_raw_peak = max_abs_sample(L.tx_raw);
    L.rx_raw_peak = max_abs_sample(L.rx_raw);
    L.tx_clip = count_clip(tx_iq, 2047);
    L.rx_clip = count_clip(rx_logical, 2047);
    L.rx_raw_clip = count_clip(L.rx_raw, 32767);
    L.clip_rate = static_cast<double>(L.rx_clip) /
                  static_cast<double>(2 * (rx_logical.size() / 2));

    // fix4: libiio RX convert divergence (per-sample, over ALL samples) plus the
    // per-sample evidence table (>= 8 positions, spread across the capture).
    const std::size_t n_complex = L.rx_raw.size() / 2;
    const std::size_t n_samples = std::min<std::size_t>(8, n_complex);
    const std::size_t stride =
        n_complex > 0 && n_samples > 0 ? std::max<std::size_t>(1, n_complex / n_samples) : 1;
    for (std::size_t c = 0; c < n_complex; ++c) {
        const std::int16_t rr = L.rx_raw[c * 2 + 0];
        const std::int16_t lib = dev.rx_convert_raw_libiio(rr);
        const std::int16_t mirror = pluto::format_convert_raw_to_host(rx_fmt, rr);
        if (lib != mirror) L.rx_libiio_diverged = true;
        if (c % stride == 0 && L.samples.size() < n_samples) {
            SweepSample sp;
            sp.tx_logical = (c * 2 < tx_iq.size()) ? tx_iq[c * 2 + 0] : 0;
            sp.tx_raw = (c * 2 < L.tx_raw.size()) ? L.tx_raw[c * 2 + 0] : 0;
            sp.rx_raw = rr;
            sp.rx_libiio = lib;
            sp.rx_host_mirror = mirror;
            sp.rx_force_signed =
                pluto::format_convert_raw_to_host_force_signed(rx_fmt, rr);
            L.samples.push_back(sp);
        }
    }

    // fix4: shift scan (0..4) evidence with the corrected mirror.
    for (int sh = 0; sh <= 4; ++sh)
        L.shift_scan.push_back(measure_shift(tx_iq, L.tx_raw, L.rx_raw,
                                             tx_fmt, rx_fmt, sh, fs, delay_margin));

    L.capture_ok = true;
    return L;
}

// ---- root-cause classification (req 4) --------------------------------------

struct RootCause {
    std::string token;   // see the *_ROOT_CAUSE tokens below
    std::string reason;  // human-readable evidence
    std::vector<std::string> components;   // which evidence drove the call

    std::string components_str() const {
        std::string s;
        for (std::size_t i = 0; i < components.size(); ++i) {
            if (i) s += ",";
            s += components[i];
        }
        return s;
    }
};

inline const char* kRootCauseFixedAttenuation = "DIGITAL_LOOPBACK_FIXED_ATTENUATION";
inline const char* kRootCauseFormatMisalignment = "DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT";
inline const char* kRootCauseLibiioConvert = "DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS";
inline const char* kRootCauseUnity = "DIGITAL_LOOPBACK_UNITY";
inline const char* kRootCauseCountDomainScale = "DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE";
inline const char* kRootCauseNotProven = "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN";

// A -> G priority, strictly ordered:
//   A  any captured level rx_libiio_diverged            -> LIBIIO_CONVERT_SEMANTICS
//   B  capture failed / RX all-zero / no usable level   -> NOT_PROVEN
//   C  a non-reported shift improves corr+normalized+clip -> FORMAT_MISALIGNMENT
//   D  reported-format corr still below threshold        -> NOT_PROVEN
//   E  normalized ~0 dB: count gain matches the bit width -> COUNT_DOMAIN_SCALE
//                                                           (or UNITY if same width)
//   F  normalized << 0 dB with corr ok and no clip        -> FIXED_ATTENUATION
//   G  otherwise                                          -> NOT_PROVEN
inline RootCause classify_root_cause(const std::vector<SweepLevel>& levels,
                                     const pluto::DataFormatInfo& tx_fmt,
                                     const pluto::DataFormatInfo& rx_fmt) {
    RootCause rc;
    rc.token = kRootCauseNotProven;
    rc.reason = "no sweep level captured a usable signal";
    char buf[256];

    // A: libiio RX convert divergence (any captured level).
    for (const SweepLevel& L : levels) {
        if (L.capture_ok && L.rx_libiio_diverged) {
            rc.token = kRootCauseLibiioConvert;
            rc.reason = "libiio RX convert output diverges from the host mirror "
                        "of the reported RX data format";
            rc.components = {"rx_libiio"};
            return rc;
        }
    }

    // B: capture failed / RX all-zero / no usable level.
    bool any_raw = false, any_signal = false;
    for (const SweepLevel& L : levels) {
        if (L.capture_ok && !L.rx_raw.empty()) any_raw = true;
        if (L.rx_count_rms >= kQuantFloorCounts) any_signal = true;
    }
    if (!any_raw || !any_signal) {
        rc.reason = "capture failed / RX all-zero / insufficient valid levels";
        rc.components = {"capture"};
        return rc;
    }

    // C: format misalignment — the reported decode is INCONSISTENT with the raw
    //    container (logical gain diverges from count gain, or the reported corr is
    //    already destroyed), but a NON-reported shift recovers BOTH the shape
    //    (corr >= threshold) and the scale (logical gain matches the count gain)
    //    with no added clip.  Correlation is scale-invariant, so a pure bit-position
    //    error that only rescales the waveform does NOT lower corr; the scale match
    //    (logical gain == count gain) is the discriminator in that case.
    const int reported_shift = static_cast<int>(rx_fmt.shift >= 16 ? 15 : rx_fmt.shift);
    for (const SweepLevel& L : levels) {
        if (!L.capture_ok || L.shift_scan.empty()) continue;
        const double rep_clip = L.clip_rate;
        const bool reported_inconsistent =
            std::fabs(L.gain_db - L.count_gain_db) > kGainPreservedDb ||
            L.corr < kFidelityCorrThreshold;
        if (!reported_inconsistent) continue;
        for (const ShiftScanEntry& e : L.shift_scan) {
            if (e.shift == reported_shift) continue;
            const bool recovers_shape = e.corr >= kFidelityCorrThreshold;
            const bool recovers_scale =
                std::fabs(e.logical_gain_db - L.count_gain_db) <= kGainPreservedDb;
            const bool no_clip = e.clip_rate <= rep_clip + 1e-6;
            if (recovers_shape && recovers_scale && no_clip) {
                rc.token = kRootCauseFormatMisalignment;
                std::snprintf(buf, sizeof(buf),
                              "shift %d recovers both shape (corr %.3f) and scale "
                              "(logical gain %.2f dB == count gain %.2f dB) while the "
                              "reported shift %d decodes a logical gain %.2f dB",
                              e.shift, e.corr, e.logical_gain_db, L.count_gain_db,
                              reported_shift, L.gain_db);
                rc.reason = buf;
                rc.components = {"shift_scan"};
                return rc;
            }
        }
    }

    // Valid-level selection: high-amplitude band only (target_rms >= 64), no clip,
    // RX above the quantization floor.  8/16 are quantization-boundary evidence and
    // do not drive the call.
    std::vector<double> norm_gain_db, count_gain_db, logical_gain_db, corr;
    for (const SweepLevel& L : levels) {
        if (!L.capture_ok || L.target_rms < 64.0) continue;
        if (L.rx_clip != 0 || L.tx_clip != 0 || L.rx_raw_clip != 0) continue;
        if (L.rx_count_rms < kQuantFloorCounts) continue;
        norm_gain_db.push_back(L.normalized_gain_db);
        count_gain_db.push_back(L.count_gain_db);
        logical_gain_db.push_back(L.gain_db);
        corr.push_back(L.corr);
    }

    // D: too few clip-free valid high-amplitude levels, or reported-format corr
    //    still below the fidelity threshold.
    if (norm_gain_db.size() < 2) {
        rc.reason = "too few clip-free valid high-amplitude levels";
        rc.components = {"valid_levels"};
        return rc;
    }
    const double ng = median(norm_gain_db);
    const double cg = median(count_gain_db);
    const double lg = median(logical_gain_db);
    const double mc = median(corr);
    if (mc < kFidelityCorrThreshold) {
        std::snprintf(buf, sizeof(buf),
                      "median corr %.3f < %.2f: gain alone is not fidelity (count "
                      "%.2f dB, normalized %.2f dB)", mc, kFidelityCorrThreshold,
                      cg, ng);
        rc.reason = buf;
        rc.components = {"corr"};
        return rc;
    }

    const int tx_bits = static_cast<int>(norm_bits(tx_fmt.bits));
    const int rx_bits = static_cast<int>(norm_bits(rx_fmt.bits));

    // The reported decode must be CONSISTENT with the raw container: for a correct
    // decode the logical gain equals the count gain (the decode is just the raw
    // container re-expressed).  A divergence means the reported bit position is
    // wrong; the C-step above should have caught it via the shift scan.  If it did
    // not (no shift recovered consistency), it is unexplained, not a gain verdict.
    if (std::fabs(lg - cg) > kGainPreservedDb) {
        std::snprintf(buf, sizeof(buf),
                      "reported decode inconsistent with the raw container: logical "
                      "gain %.2f dB vs count gain %.2f dB, and no shift recovered "
                      "consistency", lg, cg);
        rc.reason = buf;
        rc.components = {"decode_inconsistent"};
        return rc;
    }

    // E: normalized ~0 dB — the count-domain loss is fully explained by the bit
    //    width (or there is no loss at all).
    if (std::fabs(ng) <= kGainPreservedDb) {
        if (tx_bits != rx_bits) {
            const double expected_cg =
                -20.0 * std::log10(std::ldexp(1.0, tx_bits - rx_bits));
            if (std::fabs(cg - expected_cg) <= kGainPreservedDb) {
                rc.token = kRootCauseCountDomainScale;
                std::snprintf(buf, sizeof(buf),
                              "count gain %.2f dB matches the TX%d/RX%d full-scale "
                              "difference (%.2f dB); normalized gain %.2f dB ~ 0",
                              cg, tx_bits, rx_bits, expected_cg, ng);
                rc.reason = buf;
                rc.components = {"count_domain", "normalized"};
                return rc;
            }
        } else {
            if (std::fabs(cg) <= kGainPreservedDb) {
                rc.token = kRootCauseUnity;
                std::snprintf(buf, sizeof(buf),
                              "count gain %.2f dB and normalized gain %.2f dB ~ 0: "
                              "loopback is unity at these levels", cg, ng);
                rc.reason = buf;
                rc.components = {"count_domain", "normalized"};
                return rc;
            }
        }
    }

    // F: normalized significantly < 0 dB (a real attenuation remains after the
    //    bit-width normalization), with corr ok and no clip.
    if (ng < -kGainPreservedDb) {
        rc.token = kRootCauseFixedAttenuation;
        std::snprintf(buf, sizeof(buf),
                      "normalized gain %.2f dB remains below 0 after the TX%d/RX%d "
                      "full-scale normalization; corr %.3f, no clip: a real "
                      "level-independent attenuation", ng, tx_bits, rx_bits, mc);
        rc.reason = buf;
        rc.components = {"fixed_attenuation"};
        return rc;
    }

    // G: everything else (e.g. normalized gain > +3 dB is unexpected).
    std::snprintf(buf, sizeof(buf),
                  "unexplained: count gain %.2f dB, normalized gain %.2f dB, corr %.3f",
                  cg, ng, mc);
    rc.reason = buf;
    rc.components = {"unexplained"};
    return rc;
}

// ---- format correction search (req 5) ---------------------------------------

struct ShiftSearch {
    int shift = -1;           // the RX convert shift that recovers the TX value
    double gain_db = 0.0;     // residual logical gain at that shift
    double corr = 0.0;        // |correlation| at that shift
    bool ok = false;
};

// The raw container is preserved (rx_raw ≈ tx_raw), so the correct RX convert
// shift is the one that maps the raw container back to the KNOWN TX host values.
// Search shift 0..15 and keep the one with the highest correlation at the fixed
// loopback delay.  This is a FORMAT search (bit position), not an empirical
// multiplier.  Only used after classify_root_cause has already confirmed the
// normalized gain is ~0 (FORMAT_MISALIGNMENT), so a recovered corr >= threshold is
// the only additional requirement here.
inline ShiftSearch find_correct_rx_shift(const std::vector<std::int16_t>& tx_host,
                                         const std::vector<std::int16_t>& rx_raw,
                                         const pluto::DataFormatInfo& rx_fmt,
                                         std::uint64_t fs,
                                         std::size_t delay_margin) {
    ShiftSearch s;
    if (tx_host.size() < 2 || rx_raw.size() < 4) return s;

    // Reference delay: found once with the reported-shift convert; the delay is a
    // time alignment and does not depend on the bit position.
    std::vector<std::int16_t> ref_logical(rx_raw.size());
    for (std::size_t k = 0; k < rx_raw.size(); ++k)
        ref_logical[k] = pluto::format_convert_raw_to_host(rx_fmt, rx_raw[k]);
    const iqdloop::FidelityMetrics refm =
        iqdloop::align_and_measure_int16(tx_host, ref_logical, fs, delay_margin);
    const std::size_t d = static_cast<std::size_t>(refm.delay);
    const std::size_t N = tx_host.size() / 2;
    const std::size_t R = rx_raw.size() / 2;

    pluto::DataFormatInfo cand = rx_fmt;
    double best_corr = -1.0;
    for (int sh = 0; sh <= 15; ++sh) {
        cand.shift = static_cast<std::uint32_t>(sh);
        std::complex<double> num(0.0, 0.0), den(0.0, 0.0);
        double ex = 0.0, ey = 0.0;
        for (std::size_t k = 0; k < R; ++k) {
            const std::size_t ridx = (static_cast<std::size_t>(k) -
                                      static_cast<std::size_t>(d) + N) % N;
            const std::complex<double> x = iqdloop::iq_sample(tx_host, ridx);
            const double yi = pluto::format_convert_raw_to_host(cand, rx_raw[k * 2 + 0]);
            const double yq = pluto::format_convert_raw_to_host(cand, rx_raw[k * 2 + 1]);
            const std::complex<double> y(yi, yq);
            num += y * std::conj(x);
            den += x * std::conj(x);
            ex += std::norm(x);
            ey += std::norm(y);
        }
        const double corr = std::sqrt(ex * ey) > 0.0
                                ? std::abs(num) / std::sqrt(ex * ey)
                                : 0.0;
        if (corr > best_corr) {
            best_corr = corr;
            s.shift = sh;
            const std::complex<double> g = std::abs(den) > 1e-30
                ? num / den : std::complex<double>(1.0, 0.0);
            s.gain_db = 20.0 * std::log10(std::abs(g) + 1e-300);
            s.corr = corr;
        }
    }
    s.ok = (s.shift >= 0 && s.corr >= kFidelityCorrThreshold);
    return s;
}

// ---- auto-select the compensating TX scale (req 6/7) ------------------------

struct ScaleSelection {
    bool ok = false;
    double scale = 1.0;          // multiplier for the frozen TX waveform
    double expected_rx_rms = 0.0;
    std::string reason;
};

// Given the measured normalized-domain loopback gain and the TX/RX data formats,
// choose the TX scale that maps RX-domain frozen counts back to TX-domain logical
// counts: S = 2^(tx_bits-rx_bits) / normalized_gain_linear.  For COUNT_DOMAIN_SCALE
// (normalized gain ~1) this is 2^(tx_bits-rx_bits) (=16 for TX16/RX12); for a real
// FIXED_ATTENUATION (normalized gain < 1) it additionally compensates that loss.
// The scale is a TEST FIXTURE mapping (frozen SHA check first, then llround(v*S)),
// never a change to the production preprocessing semantics.
inline ScaleSelection auto_select_scale(const std::vector<SweepLevel>& levels,
                                        const pluto::DataFormatInfo& tx_fmt,
                                        const pluto::DataFormatInfo& rx_fmt,
                                        double frozen_rms, double frozen_peak) {
    ScaleSelection s;
    s.reason = "no usable sweep level";

    std::vector<double> norm_linear;
    for (const SweepLevel& L : levels) {
        if (!L.capture_ok || L.rx_count_rms < kQuantFloorCounts ||
            L.corr < kFidelityCorrThreshold)
            continue;
        norm_linear.push_back(std::pow(10.0, L.normalized_gain_db / 20.0));
    }
    if (norm_linear.empty()) return s;
    const double G_norm = median(norm_linear);   // normalized-domain loopback gain
    if (G_norm <= 0.0) { s.reason = "normalized loopback gain is zero"; return s; }

    const int tx_bits = static_cast<int>(norm_bits(tx_fmt.bits));
    const int rx_bits = static_cast<int>(norm_bits(rx_fmt.bits));
    const double bit_scale = std::ldexp(1.0, tx_bits - rx_bits);  // 2^(tx_bits-rx_bits)

    const double kFullScale = 2048.0 * 0.9;   // 10% clip margin (12-bit ADC/DAC)
    double scale = bit_scale / G_norm;
    scale = std::max(1.0, std::min(4096.0, scale));
    if (frozen_peak > 0.0) {
        scale = std::min(scale, kFullScale / frozen_peak);   // TX logical rail
        scale = std::max(1.0, scale);
    }

    // Expected RX RMS in counts: RX_count = G_norm * scale * frozen_rms * rx_fs/tx_fs.
    const double rx_fs = signed_full_scale(rx_fmt.bits);
    const double tx_fs = signed_full_scale(tx_fmt.bits);
    const double expected_rx_rms = G_norm * scale * frozen_rms * rx_fs / tx_fs;

    s.ok = true;
    s.scale = scale;
    s.expected_rx_rms = expected_rx_rms;
    s.reason = "normalized gain " + std::to_string(G_norm) + ", bit_scale 2^(" +
               std::to_string(tx_bits) + "-" + std::to_string(rx_bits) + ")=" +
               std::to_string(bit_scale) + " -> scale " + std::to_string(scale) +
               " -> RX RMS ~" + std::to_string(expected_rx_rms) + " counts";
    return s;
}

// RMS (complex magnitude) and peak (max |I|,|Q|) of a waveform.
inline void waveform_stats(const std::vector<std::int16_t>& iq, double& rms,
                           double& peak) {
    rms = rms_magnitude(iq);
    peak = static_cast<double>(max_abs_sample(iq));
}

// ---- orchestration (pure over an already-open Device; no board:: deps) ------

struct SweepConfig {
    std::uint64_t center_hz = 2400000000;
    double rx_gain_db = 10.0;
    double tx_atten_db = pluto::kSafeTxAttenDb;   // -89.75; PlutoTx re-reads/ceil
    std::uint64_t fs = 2560000;
    std::size_t delay_margin = 1024;
    std::size_t capture_complex = 4096;
    std::vector<std::string> kinds;
    std::vector<double> levels;
};

struct SweepReport {
    pluto::DataFormatInfo rx_fmt;
    pluto::DataFormatInfo tx_fmt;
    bool rx_roundtrip_identity = false;
    bool tx_roundtrip_identity = false;
    std::vector<SweepLevel> levels;
    RootCause cause;
    ShiftSearch rx_shift;        // only meaningful for FORMAT_MISALIGNMENT
    ScaleSelection scale_sel;    // meaningful for COUNT_DOMAIN_SCALE / FIXED_ATTENUATION
    bool ran = false;
    std::string error;           // non-empty => fail-closed
};

// Run the full amplitude sweep against an already-open device.  Does not print and
// does not touch the NPU or board:: plumbing, so it is host-testable against
// FakePlutoDevice.  `frozen_rms`/`frozen_peak` (optional) enable the req 6/7
// auto-selected scale.
inline SweepReport sweep_all_levels(pluto::Device& dev, const SweepConfig& cfg,
                                    double frozen_rms, double frozen_peak,
                                    bool have_frozen) {
    SweepReport rep;
    rep.ran = true;
    rep.rx_fmt = dev.rx_data_format();
    rep.tx_fmt = dev.tx_data_format();
    rep.rx_roundtrip_identity = pluto::format_roundtrip_identity(rep.rx_fmt);
    rep.tx_roundtrip_identity = pluto::format_roundtrip_identity(rep.tx_fmt);

    std::vector<std::string> kinds = cfg.kinds.empty()
        ? std::vector<std::string>(kSweepKinds, kSweepKinds + 3)
        : cfg.kinds;
    std::vector<double> levels = cfg.levels.empty()
        ? std::vector<double>(kSweepLevels, kSweepLevels + 7)
        : cfg.levels;

    for (const std::string& kind : kinds)
        for (double lvl : levels) {
            const std::vector<std::int16_t> w =
                make_sweep_waveform(kind, lvl, cfg.capture_complex);
            rep.levels.push_back(sweep_one_level(
                dev, cfg.center_hz, cfg.rx_gain_db, cfg.tx_atten_db, kind, lvl,
                rep.tx_fmt, rep.rx_fmt, w, cfg.fs, cfg.delay_margin,
                cfg.capture_complex));
        }

    rep.cause = classify_root_cause(rep.levels, rep.tx_fmt, rep.rx_fmt);

    // Format correction (req 5): find the bit position that recovers the TX value.
    if (rep.cause.token == kRootCauseFormatMisalignment) {
        // Use the highest-level usable level for the best SNR.
        const SweepLevel* best = nullptr;
        for (const SweepLevel& L : rep.levels)
            if (L.capture_ok && !L.rx_raw.empty() &&
                (!best || L.target_rms > best->target_rms))
                best = &L;
        if (best)
            rep.rx_shift = find_correct_rx_shift(best->tx_host, best->rx_raw,
                                                 rep.rx_fmt, cfg.fs,
                                                 cfg.delay_margin);
    }

    // Count-domain scale / fixed-attenuation scale (req 6/7): only with a frozen
    // waveform in hand.
    if ((rep.cause.token == kRootCauseFixedAttenuation ||
         rep.cause.token == kRootCauseCountDomainScale) && have_frozen)
        rep.scale_sel = auto_select_scale(rep.levels, rep.tx_fmt, rep.rx_fmt,
                                          frozen_rms, frozen_peak);

    return rep;
}

}  // namespace iqdloop_sweep
