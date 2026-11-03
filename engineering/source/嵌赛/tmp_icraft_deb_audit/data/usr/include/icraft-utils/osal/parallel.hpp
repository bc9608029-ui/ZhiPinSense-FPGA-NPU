#pragma once

#include <cstddef>

#if !defined(_BAREME) && !defined(_FREERTOS) && !defined(_REWORKS) && !defined(_ACOREOS) && !defined(_SYLIXOS)
#include <omp.h>
#endif

namespace icraft::osal::parallel {

inline void set_num_threads(int n) noexcept {
#if defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS) || defined(_SYLIXOS)
    (void)n;
#else
    if (n > 0) {
        omp_set_num_threads(n);
    }
#endif
}

template <class Fn>
inline void parallel_for(std::size_t begin, std::size_t end, Fn&& fn) {
#if defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS) || defined(_SYLIXOS)
    for (std::size_t i = begin; i < end; ++i) {
        fn(i);
    }
#else
    #pragma omp parallel for
    for (long long i = static_cast<long long>(begin); i < static_cast<long long>(end); ++i) {
        fn(static_cast<std::size_t>(i));
    }
#endif
}

}  // namespace icraft::osal::parallel
