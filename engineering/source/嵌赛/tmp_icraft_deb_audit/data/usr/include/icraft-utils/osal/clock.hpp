#pragma once

#include <chrono>
#include <cstdint>

#include "icraft-utils/osal/capabilities.hpp"

#if defined(_ACOREOS)
#include <os/acClock.h>
#include <os/pos/apex/apexLib.h>
#endif

namespace icraft::osal::time {

namespace detail {

#if defined(_BAREME) || defined(_FREERTOS) || defined(_ACOREOS)
using steady_now_clock = std::chrono::system_clock;
#else
using steady_now_clock = std::chrono::steady_clock;
#endif

template <typename Clock>
inline std::uint64_t now_ns() noexcept {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now().time_since_epoch()).count());
}

}  // namespace detail

inline std::uint64_t steady_now_ns() noexcept {
#if defined(_ACOREOS)
    SYSTEM_TIME_TYPE now = 0;
    RETURN_CODE_TYPE ret = NO_ERROR;
#if defined(ACORE_OS653MP)
    GET_TIME(&now, &ret);
#else
    ret = ACoreOs_clock_get_systime(&now);
#endif
    return ret == NO_ERROR ? static_cast<std::uint64_t>(now) : 0U;
#else
    return detail::now_ns<detail::steady_now_clock>();
#endif
}

inline std::uint64_t system_now_ns() noexcept {
#if defined(_ACOREOS)
    return steady_now_ns();
#else
    return detail::now_ns<std::chrono::system_clock>();
#endif
}

}  // namespace icraft::osal::time
