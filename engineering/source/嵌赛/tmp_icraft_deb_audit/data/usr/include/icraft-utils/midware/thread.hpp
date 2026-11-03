#pragma once
#include <cstddef>
#include <cstdint>
#include <chrono>
#include "icraft-utils/osal/parallel.hpp"
#include "icraft-utils/osal/sleep.hpp"

namespace icraft::midware {

    inline void set_num_threads(int n) noexcept {
        icraft::osal::parallel::set_num_threads(n);
    }

    template <class Fn>
    inline void parallel_for(std::size_t begin, std::size_t end, Fn&& fn) {
        icraft::osal::parallel::parallel_for(begin, end, std::forward<Fn>(fn));
    }

    template<class Rep, class Period>
    inline void sleep_for(const std::chrono::duration<Rep, Period>& duration) {
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(duration);
        if (ns.count() <= 0) {
            icraft::osal::thread::yield();
            return;
        }
        icraft::osal::thread::sleep_for_ns(static_cast<std::uint64_t>(ns.count()));
    }

    inline void yield() noexcept {
        icraft::osal::thread::yield();
    }

} // namespace icraft::midware
