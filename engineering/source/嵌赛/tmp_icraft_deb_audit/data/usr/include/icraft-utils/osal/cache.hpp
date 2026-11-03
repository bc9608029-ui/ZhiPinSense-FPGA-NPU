#pragma once

#include <cstddef>
#include <cstdint>

#if defined(_BAREME) || defined(_FREERTOS)
#include <fmsh_cache.h>
#elif defined(_REWORKS)
#include <reworks/cache.h>
#elif defined(_ACOREOS)
#include <cache.h>
#elif defined(_SYLIXOS)
#include <SylixOS.h>
#endif

namespace icraft::osal::cache {

inline bool requires_explicit_sync() noexcept {
#if defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS) || defined(_SYLIXOS)
    return true;
#else
    return false;
#endif
}

inline bool should_flush_range(const void* address, std::size_t bytes) noexcept {
    return requires_explicit_sync() && address != nullptr && bytes != 0U;
}

inline bool should_invalidate_range(const void* address, std::size_t bytes) noexcept {
    return requires_explicit_sync() && address != nullptr && bytes != 0U;
}

inline void flush_range(void* address, std::size_t bytes) noexcept {
    if (!should_flush_range(address, bytes)) {
        return;
    }

#if defined(_BAREME) || defined(_FREERTOS)
    Fmsh_DCacheFlushRange(reinterpret_cast<std::intptr_t>(address), bytes);
#elif defined(_REWORKS)
    REWORKS_CACHE_FLUSH(address, bytes);
#elif defined(_ACOREOS)
    constexpr std::uintptr_t kCacheLineSize = 64U;
    const auto begin = reinterpret_cast<std::uintptr_t>(address);
    const auto aligned_begin = begin & ~(kCacheLineSize - 1U);
    const auto aligned_bytes = (bytes + (begin - aligned_begin) + kCacheLineSize - 1U) & ~(kCacheLineSize - 1U);
    (void)ACoreOs_cache_flush(ACOREOS_CACHE_DAT, reinterpret_cast<void*>(aligned_begin), static_cast<UINT32>(aligned_bytes));
#elif defined(_SYLIXOS)
    API_CacheDmaFlush(address, bytes);
#else
    (void)address;
    (void)bytes;
#endif
}

inline void invalidate_range(void* address, std::size_t bytes) noexcept {
    if (!should_invalidate_range(address, bytes)) {
        return;
    }

#if defined(_BAREME) || defined(_FREERTOS)
    Fmsh_DCacheInvalidateRange(reinterpret_cast<std::intptr_t>(address), bytes);
#elif defined(_REWORKS)
    REWORKS_CACHE_INVALIDATE(address, bytes);
#elif defined(_ACOREOS)
    constexpr std::uintptr_t kCacheLineSize = 64U;
    const auto begin = reinterpret_cast<std::uintptr_t>(address);
    const auto aligned_begin = begin & ~(kCacheLineSize - 1U);
    const auto aligned_bytes = (bytes + (begin - aligned_begin) + kCacheLineSize - 1U) & ~(kCacheLineSize - 1U);
    (void)ACoreOs_cache_invalidate(ACOREOS_CACHE_DAT, reinterpret_cast<void*>(aligned_begin), static_cast<UINT32>(aligned_bytes));
#elif defined(_SYLIXOS)
    API_CacheDmaInvalidate(address, bytes);
#else
    (void)address;
    (void)bytes;
#endif
}

}  // namespace icraft::osal::cache
