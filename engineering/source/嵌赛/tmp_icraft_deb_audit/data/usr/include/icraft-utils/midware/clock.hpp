#pragma once

#include <chrono>

#include "icraft-utils/osal/clock.hpp"

namespace icraft::midware {

namespace detail {

#if defined(_BAREME) || defined(_FREERTOS) || defined(_ACOREOS)
using steady_clock_impl = std::chrono::system_clock;
#else
using steady_clock_impl = std::chrono::steady_clock;
#endif

template <typename Clock>
inline typename Clock::time_point make_time_point_from_ns(std::uint64_t ns) noexcept {
    return typename Clock::time_point(
        std::chrono::duration_cast<typename Clock::duration>(std::chrono::nanoseconds(ns)));
}

}  // namespace detail

using steady_clock = detail::steady_clock_impl;
using system_clock = std::chrono::system_clock;

inline std::uint64_t steady_now_ns() noexcept {
    return icraft::osal::time::steady_now_ns();
}

inline std::uint64_t system_now_ns() noexcept {
    return icraft::osal::time::system_now_ns();
}

inline steady_clock::time_point steady_now() noexcept {
    return detail::make_time_point_from_ns<steady_clock>(steady_now_ns());
}

inline system_clock::time_point system_now() noexcept {
    return detail::make_time_point_from_ns<system_clock>(system_now_ns());
}

}  // namespace icraft::midware
