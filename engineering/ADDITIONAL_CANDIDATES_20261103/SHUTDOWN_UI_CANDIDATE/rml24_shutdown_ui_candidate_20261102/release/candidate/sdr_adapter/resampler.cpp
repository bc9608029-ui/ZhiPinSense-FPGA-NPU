// resampler.cpp -- streaming rational polyphase resampler implementation.
//
// Polyphase identity: for the upsample-by-up -> filter h[n] -> decimate-by-down
// chain, output sample m satisfies
//     y[m] = sum_k  h[r + k*up] * x[i - k]
// where i = floor(m*down/up) and r = (m*down) mod up.

#include "resampler.hpp"

#include <stdexcept>

namespace sdr {

StreamResampler::StreamResampler(std::uint32_t up, std::uint32_t down,
                                 const std::vector<double>& fir)
    : up_(up ? up : 1), down_(down ? down : 1), h_(fir) {
    if (h_.size() % up_ != 0) {
        throw std::invalid_argument(
            "resampler: FIR length must be a multiple of up");
    }
    if (h_.empty()) {
        throw std::invalid_argument("resampler: FIR must be non-empty");
    }
    p_ = static_cast<std::uint32_t>(h_.size() / up_);
    reset();
}

void StreamResampler::reset() {
    x_.clear();
    in_base_ = 0;
    in_count_ = 0;
    out_idx_ = 0;
    out_count_ = 0;
    discarded_ = 0;
}

void StreamResampler::push(const std::complex<float>* in, std::size_t n) {
    for (std::size_t k = 0; k < n; ++k) x_.push_back(in[k]);
    in_count_ += n;
}

std::size_t StreamResampler::available() const {
    if (x_.empty()) return 0;
    const std::uint64_t transient = h_.size() - 1;
    const std::uint64_t newest_avail = in_base_ + x_.size() - 1;
    // Max m with floor(m*down/up) <= newest_avail.
    const std::uint64_t max_m =
        ((newest_avail + 1) * up_ - 1) / down_;
    std::uint64_t start = out_idx_;
    if (start < transient) start = transient;
    if (max_m < start) return 0;
    return static_cast<std::size_t>(max_m - start + 1);
}

std::size_t StreamResampler::pull(std::complex<float>* out, std::size_t max) {
    const std::uint64_t transient = h_.size() - 1;
    std::size_t produced = 0;
    while (produced < max) {
        if (!can_produce(out_idx_)) break;
        std::complex<float> y = compute_output(out_idx_);
        if (out_idx_ < transient) {
            ++discarded_;
        } else {
            out[produced] = y;
            ++produced;
            ++out_count_;
        }
        ++out_idx_;
    }
    discard_old();
    return produced;
}

bool StreamResampler::can_produce(std::uint64_t m) const {
    if (x_.empty()) return false;
    const std::uint64_t i = (m * down_) / up_;  // newest input index needed
    const std::uint64_t newest_avail = in_base_ + x_.size() - 1;
    return newest_avail >= i;
}

std::complex<float> StreamResampler::compute_output(std::uint64_t m) const {
    const std::uint64_t i = (m * down_) / up_;
    const std::uint32_t r = static_cast<std::uint32_t>((m * down_) % up_);
    std::complex<double> acc(0.0, 0.0);
    for (std::uint32_t k = 0; k < p_; ++k) {
        const double c = h_[r + k * up_];
        const std::int64_t idx = static_cast<std::int64_t>(i) - k;
        double xr = 0.0, xi = 0.0;
        if (idx >= static_cast<std::int64_t>(in_base_)) {
            const std::complex<float>& xv =
                x_[static_cast<std::size_t>(idx - static_cast<std::int64_t>(in_base_))];
            xr = xv.real();
            xi = xv.imag();
        }
        acc = std::complex<double>(acc.real() + c * xr, acc.imag() + c * xi);
    }
    return std::complex<float>(static_cast<float>(acc.real()),
                               static_cast<float>(acc.imag()));
}

void StreamResampler::discard_old() {
    if (x_.empty()) return;
    const std::int64_t oldest =
        static_cast<std::int64_t>((out_idx_ * down_) / up_) -
        static_cast<std::int64_t>(p_ - 1);
    const std::uint64_t target_base = (oldest > 0) ? static_cast<std::uint64_t>(oldest) : 0;
    while (in_base_ < target_base && !x_.empty()) {
        x_.pop_front();
        ++in_base_;
    }
}

}  // namespace sdr
