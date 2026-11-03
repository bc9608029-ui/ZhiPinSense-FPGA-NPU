// board_gate6_sdr_preprocess.cpp -- Gate 6: Pluto RX -> fp32 [1,2,1024] tensor.
//
// Proves the SDR->tensor preprocess chain on the board (task 39e5 §六):
//   Pluto RX (12-bit int16, FS 2048) -> NCO downconvert (offset)
//     -> polyphase FIR decimation (2.56M/3.84M -> 128 kHz) -> receiver_scale
//     -> fp32 [2,1024] tensor (plane 0 = I, plane 1 = Q).
//
// Two source modes:
//   --loopback 0  (default) capture ambient RX, write tensors to disk, report
//                 shape/RMS/peak.  PASS = produced `frames` valid tensors with no
//                 stream anomaly (proves the chain mechanics, not signal content).
//   --loopback 1  digital loopback: TX a known CW tone, capture it, and VERIFY
//                 every tensor still contains the tone at 128 kHz (single-bin
//                 Goertzel ratio, scale-invariant) -- proves the full chain
//                 end-to-end against a known signal.
//
// receiver_scale (--rec-scale) is a GLOBAL fixed scalar; the Goertzel PASS
// criterion is scale-invariant so Gate 6 does NOT depend on the calibrated value.
// Calibration is a separate §九 flow (see RECEIVER_SCALE_CALIBRATION.md).
//
// Build (on board): see build_on_board.sh.  Exit 0/1/2 = pass/fail/device-not-found.

#include "board_common.hpp"
#include "chain_common.hpp"

#include <sys/stat.h>

#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

namespace {
bool save_tensor(const std::string& path, const float* t, std::size_t n) {
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    const std::size_t w = std::fwrite(t, sizeof(float), n, f);
    std::fclose(f);
    return w == n;
}

// Per-tensor checks: reconstruct complex I+jQ, measure tone ratio (scale-free),
// RMS, and the peak |component| of the fp32 tensor.
struct TensorStats {
    double ratio = 0.0;   // Goertzel concentration at tone_hz (128k), loopback only
    double rms = 0.0;     // complex RMS of the reconstructed frame
    float peak = 0.0f;    // max |component| of the fp32 tensor
};
TensorStats check_tensor(const float* t, double tone_hz, double fs) {
    std::vector<std::complex<float>> x(chain::kFrameComplex);
    TensorStats s;
    for (std::size_t k = 0; k < chain::kFrameComplex; ++k) {
        const float re = t[k];
        const float im = t[chain::kFrameComplex + k];
        x[k] = std::complex<float>(re, im);
        const float ar = re < 0 ? -re : re;
        const float ai = im < 0 ? -im : im;
        if (ar > s.peak) s.peak = ar;
        if (ai > s.peak) s.peak = ai;
    }
    // Digital-loopback tone may come back at +f or -f (TX/RX I-Q orientation);
    // take the max, matching board_common::analyze_frame's ratio_pos/ratio_neg.
    const double rp = sdr::goertzel_ratio(x, tone_hz, fs);
    const double rn = sdr::goertzel_ratio(x, -tone_hz, fs);
    s.ratio = (rp > rn) ? rp : rn;
    s.rms = sdr::rms(x);
    return s;
}
}  // namespace

int main(int argc, char** argv) {
    board::arm_signal_handlers();
    const std::string uri = board::get_opt(argc, argv, "--uri", "");

    std::unique_ptr<pluto::Device> dev;
    try {
        dev.reset(pluto::make_device(uri));
    } catch (const std::exception& e) {
        board::emit("gate6_sdr_preprocess", false,
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

            const std::uint64_t frames = board::opt_u64(argc, argv, "--frames", 16);
            const int loopback = static_cast<int>(board::opt_u64(argc, argv, "--loopback", 0));
            const double tone_hz = board::opt_d(argc, argv, "--tone", 10000.0);
            const double gain_db = board::opt_d(argc, argv, "--rx-gain", 10.0);
            const float rec_scale = static_cast<float>(board::opt_d(argc, argv, "--rec-scale", 1.0));
            const double nco_offset = board::opt_d(argc, argv, "--nco-offset", 0.0);
            const std::string outdir = board::get_opt(argc, argv, "--outdir", "gate6_out");
            const double ratio_threshold = board::opt_d(argc, argv, "--ratio-min", 0.3);

            // RX config: manual low gain + requested loopback mode.
            dev->set_rx_gain_mode("manual");
            dev->set_rx_gain(gain_db);
            dev->set_loopback(loopback);

            // Optional digital-loopback TX (safe startup order via PlutoTx).
            std::unique_ptr<pluto::PlutoTx> tx;
            if (loopback == 1) {
                pluto::TxConfig txc;
                txc.center_freq_hz = board::opt_u64(argc, argv, "--center", 2450000000ULL);
                txc.rx_gain_db = gain_db;
                txc.tx_atten_db = board::opt_d(argc, argv, "--tx-atten", pluto::kSafeTxAttenDb);
                txc.loopback = 1;
                txc.confirm_safe_rf_path = false;
                txc.waveform = board::make_periodic_tone(tone_hz,
                                                         static_cast<double>(neg.actual_hz), 8);
                tx.reset(new pluto::PlutoTx(*dev, txc));
                tx->prepare();
                tx->start_cyclic();   // RX is started by the caller (below), last.
            }

            ::mkdir(outdir.c_str(), 0755);

            chain::PreprocessChain chain(static_cast<std::uint32_t>(neg.actual_hz),
                                         nco_offset, rec_scale);
            std::vector<float> tensor(chain::kTensorFloats);

            // ONE contiguous RX refill sized for the whole capture.  A chunk loop
            // concatenating several independent refills into one stateful chain is
            // the multi-refill phase-jump bug (each refill starts at an arbitrary
            // phase, so the resampler sees phase steps at the seams).  required_input
            // includes the FIR startup transient, so one refill yields `frames`
            // complete tensors.
            const std::size_t requested = chain.required_input(frames);
            std::vector<std::int16_t> iq;
            board::RxStats st;
            board::Continuity cont;
            const bool captured = board::capture_contiguous(*dev, requested, iq, st, cont);

            std::size_t written = 0;
            double ratio_min = 1e9, ratio_sum = 0.0;
            double rms_sum = 0.0;
            float peak_max = 0.0f;

            if (captured && !st.interrupted && iq.size() / 2 > 0) {
                // Feed the contiguous block into the chain ONCE, then drain tensors.
                chain.push_int16(iq.data(), iq.size() / 2);
                while (chain.ready() > 0 && written < frames) {
                    if (!chain.pull_tensor(tensor.data())) break;
                    ++written;
                    const TensorStats ts = check_tensor(tensor.data(), tone_hz, 128000.0);
                    if (ts.ratio < ratio_min) ratio_min = ts.ratio;
                    ratio_sum += ts.ratio;
                    rms_sum += ts.rms;
                    if (ts.peak > peak_max) peak_max = ts.peak;

                    char name[256];
                    std::snprintf(name, sizeof(name), "%s/tensor_%04zu.bin",
                                  outdir.c_str(), written);
                    if (!save_tensor(name, tensor.data(), chain::kTensorFloats))
                        break;   // disk write failure is not a stream fault
                }
            }

            // `captured` already encodes "one refill delivered the whole amount with
            // no timeout/short/overflow/drop/discontinuity".  The separate
            // continuity gate PROVES the capture was a single refill into a large
            // enough buffer (so it is not a concatenation pretending to be
            // continuous), and every frame must still complete and hold the tone.
            const bool frames_ok = (written == frames);
            const bool tone_ok = (loopback != 1) ||
                                 (frames_ok && ratio_min > ratio_threshold);
            pass = captured && !st.interrupted && cont.ok() && frames_ok && tone_ok;

            detail += " frames=" + std::to_string(written) + "/" + std::to_string(frames);
            detail += " loopback=" + std::to_string(loopback);
            detail += " rec_scale=" + std::to_string(rec_scale);
            detail += " nco_offset=" + std::to_string(nco_offset);
            detail += " ratio_min=" + std::to_string(ratio_min);
            detail += " ratio_mean=" +
                      std::to_string(written ? ratio_sum / static_cast<double>(written) : 0.0);
            detail += " tensor_rms_mean=" +
                      std::to_string(written ? rms_sum / static_cast<double>(written) : 0.0);
            detail += " tensor_peak=" + std::to_string(peak_max);
            detail += " resampler_transient=" + std::to_string(chain.resampler_transient());
            detail += " in_complex=" + std::to_string(chain.in_complex());
            detail += " short=" + std::to_string(st.short_block ? 1 : 0);
            detail += " interrupted=" + std::to_string(st.interrupted ? 1 : 0);
            detail += " overflow=" + std::to_string(st.overflow);
            detail += " drop=" + std::to_string(st.dropped);
            detail += " disc=" + std::to_string(st.discontinuity);
            detail += cont.report();
            detail += " outdir=" + outdir;
            if (!captured) detail += " (stream_broken)";
            if (!cont.ok()) detail += " (continuity_fail)";
            if (!frames_ok) detail += " (frame_short)";
            if (!tone_ok) detail += " (tone_missing)";
            if (st.interrupted) detail += " (interrupted)";
        }

        guard->restore();   // explicit, idempotent
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

    board::emit("gate6_sdr_preprocess", pass, detail);
    return pass ? 0 : 1;
}
