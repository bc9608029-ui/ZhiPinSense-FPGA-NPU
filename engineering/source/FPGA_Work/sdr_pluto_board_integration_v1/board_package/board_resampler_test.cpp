// board_resampler_test.cpp -- Gate 5: loopback IQ -> NCO downconvert -> streaming
// resample -> 128 kHz / 1024-complex frames -> receiver_scale / Q1.15.
//
// Verifies on real board data, with STRICTLY SEPARATED metrics (task 39e5 section 四):
//   * tone spectral ratio  -- Goertzel concentration at DC (unitless, ~1.0), NOT
//                             compared to an amplitude;
//   * tone amplitude       -- |mean(y)| after NCO-downconvert, vs a_in/2048*rscale
//                             (12-bit count / 2048 = normalised float, FIR DC gain 1);
//   * alias suppression    -- 20*log10(alias_amp / (a_out/2048*rscale)), alias at
//                             +/-38 kHz (100 kHz probe - 10 kHz NCO = 90 kHz, which
//                             decimates to -38 kHz; measured at BOTH signs);
//   * frequency error      -- dominant-freq estimate of the DC tone (expect ~0 Hz);
//   * buffer continuity    -- chunked vs single-shot resample: length equality +
//                             max |difference| (NOT exact vector==);
//   * receiver_scale stats -- input RMS (counts), output RMS, recommended scale,
//                             Q1.15 peak + saturation count.
//
// Uses digital loopback (loopback=1): no external RF is emitted.  TX amplitudes
// are 12-bit (a_in + a_out < 2048) because the AD9364 DAC is 12-bit and
// iio_channel_convert_inverse keeps only the low 12 bits.
//
// Build (on board): see build_on_board.sh.

#include "board_common.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <memory>
#include <string>

namespace {

std::uint64_t opt_u64(int argc, char** argv, const char* name, std::uint64_t def) {
    const std::string s = board::get_opt(argc, argv, name, std::to_string(def));
    return std::strtoull(s.c_str(), nullptr, 10);
}
double opt_d(int argc, char** argv, const char* name, double def) {
    const std::string s = board::get_opt(argc, argv, name, std::to_string(def));
    return std::strtod(s.c_str(), nullptr);
}

const sdr::FirSpec* find_spec(std::uint64_t fs_in) {
    for (std::size_t i = 0; i < sdr::kFirSpecCount; ++i)
        if (sdr::kFirSpecs[i].fs_in_hz == fs_in) return &sdr::kFirSpecs[i];
    return nullptr;
}

std::vector<double> coeff_vec(const sdr::FirSpec& s) {
    return std::vector<double>(s.coeffs, s.coeffs + s.n);
}

// Interleaved int16 multi-tone: in-band (f_in) + out-of-band alias probe (f_out).
// Amplitudes are 12-bit DAC counts; a_in + a_out MUST stay below 2048 so the
// combined peak never clips/masks through iio_channel_convert_inverse.
std::vector<std::int16_t> make_multitone(double fs, std::size_t n, double f_in,
                                         double f_out, double a_in, double a_out) {
    std::vector<std::int16_t> iq(n * 2);
    for (std::size_t k = 0; k < n; ++k) {
        const double t = static_cast<double>(k);
        const double re = a_in * std::cos(2.0 * board::kPi * f_in / fs * t) +
                          a_out * std::cos(2.0 * board::kPi * f_out / fs * t);
        const double im = a_in * std::sin(2.0 * board::kPi * f_in / fs * t) +
                          a_out * std::sin(2.0 * board::kPi * f_out / fs * t);
        iq[k * 2 + 0] = static_cast<std::int16_t>(std::llround(re));
        iq[k * 2 + 1] = static_cast<std::int16_t>(std::llround(im));
    }
    return iq;
}

// Mean of a complex vector (the DC component after down-conversion).
std::complex<double> mean_c(const std::vector<std::complex<float>>& x) {
    if (x.empty()) return std::complex<double>(0.0, 0.0);
    std::complex<double> s(0.0, 0.0);
    for (const auto& v : x) s += std::complex<double>(v.real(), v.imag());
    return s / static_cast<double>(x.size());
}

// Save an interleaved complex<float> stream as little-endian float32 pairs.
void save_cfloat(const std::string& path, const std::vector<std::complex<float>>& x) {
    std::vector<float> flat(x.size() * 2);
    for (std::size_t k = 0; k < x.size(); ++k) {
        flat[k * 2 + 0] = x[k].real();
        flat[k * 2 + 1] = x[k].imag();
    }
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return;
    std::fwrite(flat.data(), sizeof(float), flat.size(), f);
    std::fclose(f);
}

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();
    const std::string uri = board::get_opt(argc, argv, "--uri", "");
    const double f_in = opt_d(argc, argv, "--tone", 10000.0);       // in-band
    const double f_out = opt_d(argc, argv, "--probe", 100000.0);    // out-of-band
    const double a_in = opt_d(argc, argv, "--tone-amp", 1200.0);    // 12-bit counts
    const double a_out = opt_d(argc, argv, "--probe-amp", 800.0);
    const double rscale = opt_d(argc, argv, "--receiver-scale", 1.0);
    // Output-sample target.  Default 1024 keeps the required INPUT samples inside
    // ONE Pluto RX DMA buffer so a single iio_buffer_refill can return the whole
    // stream CONTIGUOUSLY (the continuity requirement).  n_in grows with the
    // decimation factor: at 3.84M(×30, 903 taps) 1024 outputs need ~57.9k inputs,
    // still under the ~64k-complex DMA buffer; requesting more here will simply
    // fail-closed at buffer creation (see collect_raw_contiguous).
    const std::uint64_t n_out_target = opt_u64(argc, argv, "--samples", 1024);

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("resampler_test", false, std::string("device_not_found: ") + e.what());
        return 2;
    }

    bool pass = false;
    std::string detail;
    std::unique_ptr<pluto::DeviceStateGuard> guard;
    try {
        guard.reset(new pluto::DeviceStateGuard(*dev));

        const sdr::RateNegotiation neg =
            sdr::negotiate_sample_rate(*dev, sdr::default_rate_candidates(), 128000);
        if (!neg.ok) {
            detail = "negotiation_failed: " + neg.report();
        } else {
            detail = neg.report() + ";";

            const sdr::FirSpec* spec = find_spec(neg.actual_hz);
            if (spec == nullptr) {
                detail += " no_fir_spec";
            } else {
                const double fs_dev = static_cast<double>(neg.actual_hz);

                // TX the multi-tone via digital loopback.  768 = lcm(256, 384):
                // whole periods of BOTH 10 kHz and 100 kHz tones at 2.56 MHz and
                // 3.84 MHz, so the cyclic TX buffer wraps without a phase jump.
                const std::size_t n_wave = 768;
                pluto::TxConfig txc;
                txc.center_freq_hz = opt_u64(argc, argv, "--center", 2450000000ULL);
                txc.rx_gain_db = opt_d(argc, argv, "--rx-gain", 10.0);
                txc.loopback = 1;  // digital
                txc.waveform = make_multitone(fs_dev, n_wave, f_in, f_out, a_in, a_out);

                pluto::PlutoTx tx(*dev, txc);
                tx.prepare();
                tx.start_cyclic();

                // Acquire enough input for n_out_target VALID outputs + transient + slack,
                // as ONE contiguous RX refill.  A single iio_buffer_refill returns
                // contiguous DMA samples (no dropped-sample phase break), so the NCO /
                // resampler / receiver_scale below see a real continuous stream.  The
                // refill count and buffer capacity are recorded as the continuity proof.
                const std::size_t n_in =
                    (static_cast<std::size_t>(n_out_target) + spec->n) * spec->down + 64;
                std::vector<std::int16_t> raw;
                board::RxStats st;
                const std::uint64_t refill_before = dev->rx_refill_count();
                const bool contiguous = board::collect_raw_contiguous(*dev, n_in, raw, st);
                const std::uint64_t refill_after = dev->rx_refill_count();
                const std::uint64_t refills_used = refill_after - refill_before;
                const bool single_refill = contiguous && (refills_used == 1) &&
                                           dev->rx_buffer_capacity() >= n_in;
                if (!contiguous || !single_refill) {
                    detail += " contiguous_refill_failed(refills=" +
                              std::to_string(refills_used) +
                              ",capacity=" + std::to_string(dev->rx_buffer_capacity()) +
                              ",n_in=" + std::to_string(n_in) + ")";
                } else {
                    // -> float IQ (count/2048), apply fixed receiver_scale.
                    std::vector<std::complex<float>> x = board::to_complex(raw);
                    for (auto& v : x) v *= static_cast<float>(rscale);

                    // NCO downconvert the in-band tone to DC.
                    sdr::Nco nco(f_in, fs_dev);
                    nco.mix(x.data(), x.size());

                    // Streaming resample (single-shot) to 128 kHz.
                    const std::vector<double> h = coeff_vec(*spec);
                    sdr::StreamResampler rs(spec->up, spec->down, h);
                    rs.push(x.data(), x.size());
                    std::vector<std::complex<float>> y(rs.available());
                    const std::size_t got = rs.pull(y.data(), y.size());
                    y.resize(got);

                    // Buffer continuity: chunked (two halves, same resampler) vs
                    // single-shot.  Compare length + max |difference|, NOT vector==.
                    sdr::StreamResampler rs2(spec->up, spec->down, h);
                    const std::size_t half = x.size() / 2;
                    rs2.push(x.data(), half);
                    rs2.push(x.data() + half, x.size() - half);
                    std::vector<std::complex<float>> y2(rs2.available());
                    const std::size_t got2 = rs2.pull(y2.data(), y2.size());
                    y2.resize(got2);
                    const bool chunk_len_match = (y.size() == y2.size());
                    double chunk_max_err = 0.0;
                    const std::size_t cmn = std::min(y.size(), y2.size());
                    for (std::size_t k = 0; k < cmn; ++k) {
                        const double e = std::abs(y[k] - y2[k]);
                        if (e > chunk_max_err) chunk_max_err = e;
                    }
                    const bool chunk_equal = chunk_len_match && chunk_max_err < 1e-4;

                    // Frame to 1024-complex (drop partial tail; never zero-pad).
                    const std::size_t n_frames = y.size() / 1024;

                    // ---- strictly separated metrics --------------------------
                    // (1) tone spectral ratio: concentration at DC (unitless ~1.0).
                    const double dc_ratio = board::goertzel_ratio(y, 0.0, 128000.0);
                    // (2) tone amplitude: |mean(y)| = DC component = downconverted
                    //     in-band tone amplitude (FIR DC gain == 1).
                    const double tone_amp = std::abs(mean_c(y));
                    const double expect_amp = a_in / 2048.0 * rscale;
                    // (3) alias suppression: alias lands at +/-38 kHz (100k-10k=90k,
                    //     decimated -> 90k-128k = -38k); measure BOTH signs.
                    const double alias_amp = std::max(
                        board::goertzel_amp(y, -38000.0, 128000.0),
                        board::goertzel_amp(y, 38000.0, 128000.0));
                    const double alias_db =
                        (alias_amp > 0.0 && a_out > 0.0)
                            ? 20.0 * std::log10(alias_amp / (a_out / 2048.0 * rscale))
                            : -999.0;
                    // (4) frequency error: dominant frequency of the DC tone.
                    const double freq_err = board::dominant_freq_hz(y, 128000.0);

                    // ---- receiver_scale stats (count domain) ----------------
                    double input_rms_counts = 0.0;
                    {
                        double s = 0.0;
                        for (const std::int16_t v : raw) {
                            const double d = v;
                            s += d * d;
                        }
                        input_rms_counts = std::sqrt(s / static_cast<double>(raw.size()));
                    }
                    const double target_q115_rms = 8192.0;   // ~ -12 dBFS
                    const double rec_scale =
                        sdr::ReceiverScale::calibrate_scale(input_rms_counts,
                                                            target_q115_rms);
                    const double output_rms = board::rms(y);
                    std::uint64_t q115_sat = 0;
                    int q115_peak = 0;
                    {
                        sdr::ReceiverScale rs(static_cast<float>(rec_scale));
                        const std::size_t qn = std::min<std::size_t>(raw.size(), 2048);
                        for (std::size_t k = 0; k < qn; ++k) {
                            const std::int16_t qv = rs.to_q115(raw[k]);
                            const int a = qv < 0 ? -qv : qv;
                            if (a > q115_peak) q115_peak = a;
                            if (qv == 32767 || qv == -32768) ++q115_sat;
                        }
                    }

                    // ---- verdicts -------------------------------------------
                    const double rel_err =
                        (expect_amp > 0.0) ? std::fabs(tone_amp - expect_amp) / expect_amp : 1.0;
                    const bool spectral_ok = dc_ratio > 0.9;         // tone dominates DC
                    const bool amp_ok = rel_err < 0.2;               // 20% (absorbs ~0.9999 passband)
                    const bool alias_ok = alias_db < -50.0;          // >= 50 dB suppression
                    const bool freq_ok = std::fabs(freq_err) < 10.0;
                    const bool sat_ok = (q115_sat == 0);
                    const bool clean = !st.short_block && !st.interrupted &&
                                       st.overflow == 0 && st.dropped == 0 &&
                                       st.discontinuity == 0;

                    pass = spectral_ok && amp_ok && alias_ok && freq_ok &&
                           chunk_equal && sat_ok && clean && n_frames >= 1;

                    detail += " n_frames=" + std::to_string(n_frames);
                    detail += " dc_ratio=" + std::to_string(dc_ratio);
                    detail += " tone_amp=" + std::to_string(tone_amp);
                    detail += " expect_amp=" + std::to_string(expect_amp);
                    detail += " alias_db=" + std::to_string(alias_db);
                    detail += " freq_err_hz=" + std::to_string(freq_err);
                    detail += " chunk_len_match=" + std::to_string(chunk_len_match ? 1 : 0);
                    detail += " chunk_max_err=" + std::to_string(chunk_max_err);
                    detail += " input_rms=" + std::to_string(input_rms_counts);
                    detail += " output_rms=" + std::to_string(output_rms);
                    detail += " rec_scale=" + std::to_string(rec_scale);
                    detail += " q115_peak=" + std::to_string(q115_peak);
                    detail += " q115_sat=" + std::to_string(q115_sat);
                    detail += " short=" + std::to_string(st.short_block ? 1 : 0);
                    detail += " interrupted=" + std::to_string(st.interrupted ? 1 : 0);
                    detail += " overflow=" + std::to_string(st.overflow);
                    detail += " drop=" + std::to_string(st.dropped);
                    detail += " disc=" + std::to_string(st.discontinuity);
                    detail += " timeouts=" + std::to_string(st.timeouts);
                    detail += " rx_buffer_capacity=" + std::to_string(dev->rx_buffer_capacity());
                    detail += " rx_refill_count=" + std::to_string(dev->rx_refill_count());
                    detail += " single_refill=" + std::to_string(single_refill ? 1 : 0);
                    if (!spectral_ok) detail += " (spectral_error)";
                    if (!amp_ok) detail += " (amplitude_error)";
                    if (!alias_ok) detail += " (alias_leak)";
                    if (!freq_ok) detail += " (frequency_error)";
                    if (!chunk_equal) detail += " (phase_jump)";
                    if (!sat_ok) detail += " (q115_saturated)";
                    if (!clean) detail += " (stream_anomaly)";

                    // Save raw / NCO-after / resample frame / stats on failure.
                    if (!pass) {
                        board::save_raw_iq("resampler_raw.bin", raw);
                        save_cfloat("resampler_nco.bin", x);
                        save_cfloat("resampler_out.bin", y);
                        detail += " dump=resampler_raw.bin";
                    }
                }
            }
        }

        guard->restore();
    } catch (const std::exception& e) {
        pass = false;
        detail += std::string(" error=") + e.what();
    }

    if (guard) {
        guard->restore();
        detail += board::restore_report(*dev, *guard);
    }

    board::emit("resampler_test", pass, detail);
    return pass ? 0 : 1;
}
