// board_calibrate_rec_scale.cpp -- §九 receiver_scale calibration (NOT hardcoded).
//
// The model input domain is "clean-signal RMS == amplitude == 1.0".  The chain
// maps 12-bit int16 ADC counts (full scale 2048, after iio_channel_convert) onto
// that domain with ONE global fixed scalar receiver_scale:
//
//     model_input = (adc_count / 2048) * receiver_scale
//
// so receiver_scale = target_rms * 2048 / adc_rms_counts  (see chain_common.hpp
// `calibrate_rec_scale`).  This program MEASURES adc_rms_counts against a known
// reference -- the digital-loopback CW tone of fixed DAC amplitude -- and prints
// the resulting receiver_scale.  It is the repeatable, non-blind calibration the
// board user runs before Gate 9; the value is then passed as --rec-scale (never
// baked into the chain).
//
// Procedure (digital loopback, fully deterministic -- no RF, no cable loss):
//   1. digital loopback a 10 kHz CW tone at DAC amplitude --tx-amp (default 1500);
//   2. collect --samples complex int16 samples of the received tone;
//   3. measure adc_rms_counts (magnitude RMS in counts) and, as a cross-check,
//      the Goertzel tone amplitude in counts (they must agree for a clean tone);
//   4. receiver_scale = target_rms * 2048 / adc_rms_counts;
//   5. FAIL if the tone is absent (loopback broken), the ADC clips, or the two
//      amplitude estimates disagree (non-tone / pathological input).
//
// Output: a machine-parseable `REC_SCALE rec_scale=... adc_rms_counts=...` line,
// a GATE_RESULT line, and (with --out) a single-line `rec_scale=<value>` file the
// run scripts can source.  Exit 0/1/2 = pass / fail / device-not-found.
//
// Build (on board): see build_on_board.sh.  libiio only; no iCraft.

#include "board_common.hpp"
#include "chain_common.hpp"

#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

namespace {

bool write_rec_scale(const std::string& path, double rec_scale) {
    if (path.empty()) return true;
    FILE* f = std::fopen(path.c_str(), "w");
    if (!f) return false;
    std::fprintf(f, "rec_scale=%.9g\n", rec_scale);
    std::fclose(f);
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();
    const std::string uri = board::get_opt(argc, argv, "--uri", "");

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("calibrate_rec_scale", false,
                    std::string("device_not_found: ") + e.what());
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

            const std::uint64_t samples = board::opt_u64(argc, argv, "--samples", 100000);
            const double tone_hz = board::opt_d(argc, argv, "--tone", 10000.0);
            const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
            const double tx_amp = board::opt_d(argc, argv, "--tx-amp", 1500.0);
            const double target_rms = board::opt_d(argc, argv, "--target-rms",
                                                   chain::kTargetModelRms);
            const std::string out = board::get_opt(argc, argv, "--out", "rec_scale.txt");

            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(gain_db);
            dev->set_loopback(1);   // digital loopback (deterministic, no RF)

            pluto::TxConfig txc;
            txc.center_freq_hz = board::opt_u64(argc, argv, "--center", 2450000000ULL);
            txc.rx_gain_db = gain_db;
            txc.tx_atten_db = board::opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
            txc.loopback = 1;
            txc.confirm_safe_rf_path = false;
            txc.waveform = board::make_periodic_tone(
                tone_hz, static_cast<double>(neg.actual_hz), 8, tx_amp);
            pluto::PlutoTx tx(*dev, txc);
            tx.prepare();
            tx.start_cyclic();   // RX is read by capture_contiguous below.

            std::vector<std::int16_t> iq;
            board::RxStats st;
            board::Continuity cont;
            // ONE contiguous RX refill (no multi-refill RMS averaging of
            // phase-discontinuous blocks -- same continuity rule as Gate 6/9).
            const bool got = board::capture_contiguous(
                *dev, static_cast<std::size_t>(samples), iq, st, cont);
            if (!got) {
                detail += " stream_broken";
                detail += cont.report();
            } else {
                const std::size_t n = iq.size() / 2;
                const auto x = sdr::to_complex(iq, chain::kAdcFullScale);

                // Magnitude RMS in int16 counts (phase-break independent).
                const double rms_norm = sdr::rms(x);             // in [0,1]
                const double adc_rms = rms_norm * chain::kAdcFullScale;

                // Goertzel tone amplitude in counts (cross-check, needs a frame).
                const int peak = sdr::max_abs_iq(iq);
                double tone_amp = 0.0, ratio = 0.0;
                if (n >= chain::kFrameComplex) {
                    std::vector<std::complex<float>> frame(
                        x.begin(), x.begin() + static_cast<long>(chain::kFrameComplex));
                    ratio = std::max(sdr::goertzel_ratio(frame, tone_hz,
                                                         static_cast<double>(neg.actual_hz)),
                                     sdr::goertzel_ratio(frame, -tone_hz,
                                                         static_cast<double>(neg.actual_hz)));
                    tone_amp = sdr::goertzel_amp(frame, tone_hz,
                                                 static_cast<double>(neg.actual_hz)) *
                               chain::kAdcFullScale;
                }

                // Clipping: fraction of samples at the 12-bit rail.
                std::uint64_t clip = 0;
                for (const std::int16_t v : iq) {
                    const int a = v < 0 ? -v : v;
                    if (a >= 2047) ++clip;
                }
                const double clip_ratio =
                    iq.empty() ? 0.0
                               : static_cast<double>(clip) / static_cast<double>(iq.size());

                const double rec_scale =
                    chain::calibrate_rec_scale(adc_rms, target_rms);

                const bool tone_ok = ratio > 0.3;
                const bool no_clip = peak < static_cast<int>(chain::kAdcFullScale);
                // Tone amplitude and RMS must agree (clean tone: |A| == RMS).
                const double rel = (tone_amp > 0.0)
                                       ? std::fabs(adc_rms - tone_amp) / tone_amp
                                       : 1.0;
                const bool amp_consistent = (tone_amp > 0.0) && (rel < 0.20);
                const bool sane = adc_rms > 0.0 && adc_rms < chain::kAdcFullScale &&
                                  rec_scale > 0.0 && rec_scale < 1e3;
                // Reject multi-refill: a single refill into a large enough buffer is
                // required, exactly as Gate 6/9 (no multi-refill RMS).
                pass = tone_ok && no_clip && amp_consistent && sane && cont.ok();

                detail += " samples=" + std::to_string(n);
                detail += " rec_scale=" + std::to_string(rec_scale);
                detail += " adc_rms_counts=" + std::to_string(adc_rms);
                detail += " tone_amp_counts=" + std::to_string(tone_amp);
                detail += " amp_rel_err=" + std::to_string(rel);
                detail += " adc_peak=" + std::to_string(peak);
                detail += " clip_ratio=" + std::to_string(clip_ratio);
                detail += " tone_ratio=" + std::to_string(ratio);
                detail += " target_rms=" + std::to_string(target_rms);
                detail += " overflow=" + std::to_string(st.overflow);
                detail += " drop=" + std::to_string(st.dropped);
                detail += " disc=" + std::to_string(st.discontinuity);
                detail += cont.report();
                if (!tone_ok) detail += " (tone_missing)";
                if (!no_clip) detail += " (adc_clipped)";
                if (!amp_consistent) detail += " (amp_inconsistent)";
                if (!sane) detail += " (out_of_range)";
                if (!cont.ok()) detail += " (multi_refill)";

                // The single authoritative number, printed separately for easy
                // capture and written to --out when requested.
                std::printf("REC_SCALE rec_scale=%.9g adc_rms_counts=%.9g "
                            "tone_amp_counts=%.9g target_rms=%.9g\n",
                            rec_scale, adc_rms, tone_amp, target_rms);
                std::fflush(stdout);
                if (!write_rec_scale(out, rec_scale)) detail += " (out_write_failed)";
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
        // Fail-closed: a functional PASS is only real if the restore also
        // succeeded (closes the fail-open on restore_result=FAIL).
        pass = board::final_gate_pass(pass, guard->restore_ok(), detail);
    } else {
        pass = false;
        detail += " (no_state_guard)";
    }

    board::emit("calibrate_rec_scale", pass, detail);
    return pass ? 0 : 1;
}
