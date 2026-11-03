#pragma once
#include <cstddef>

#ifndef _BAREME
#include <omp.h>
#include <thread>
#else
#include <fmsh_common.h>
#endif

namespace icraft::midware {

    inline void set_num_threads(int n) noexcept {
    #ifdef _BAREME
        (void)n;
    #else
        if (n > 0) omp_set_num_threads(n);
    #endif
    }

    template <class Fn>
    inline void parallel_for(std::size_t begin, std::size_t end, Fn&& fn) {
    #ifdef _BAREME
        for (std::size_t i = begin; i < end; ++i) fn(i);
    #else
        #pragma omp parallel for
        for (long long i = static_cast<long long>(begin); i < static_cast<long long>(end); ++i) {
            fn(static_cast<std::size_t>(i));
        }
    #endif
    }

    #ifdef _BAREME
        template<class _Rep, class _Period>
        void sleep_for(const std::chrono::duration<_Rep, _Period>& duration){
            auto us=std::chrono::duration_cast<std::chrono::microseconds>(duration);
            delay_us(us.count());
        }
    #else
        using std::this_thread::sleep_for;
    #endif

} // namespace icraft::midware
