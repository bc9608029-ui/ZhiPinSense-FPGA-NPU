#pragma once

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <limits>

#if defined(_WIN32)
#include <malloc.h>
#elif defined(_ACOREOS)
#include <malloc.h>
#endif

#if defined(_SYLIXOS)
extern "C" {
extern void* API_VmmDmaAllocAlign(unsigned long stSize, unsigned long stAlign);
extern void API_VmmDmaFree(void* pvDmaMem);
}
#endif

namespace icraft::osal::memory {
namespace detail {

inline bool is_power_of_two(std::size_t value) noexcept {
    return value != 0U && (value & (value - 1U)) == 0U;
}

inline std::size_t normalize_alignment(std::size_t alignment) noexcept {
    if (alignment == 0U) {
        return 0U;
    }
    if (alignment < sizeof(void*)) {
        alignment = sizeof(void*);
    }
    if (!is_power_of_two(alignment)) {
        return 0U;
    }
    return alignment;
}

inline std::size_t round_up_to_alignment(std::size_t byte_size, std::size_t alignment) noexcept {
    const auto align_mask = alignment - 1U;
    if (byte_size > std::numeric_limits<std::size_t>::max() - align_mask) {
        return 0U;
    }
    return (byte_size + align_mask) & ~align_mask;
}

#if defined(_REWORKS)
inline void* reworks_aligned_malloc(std::size_t byte_size, std::size_t alignment) noexcept {
    alignment = normalize_alignment(alignment);
    if (alignment == 0U) {
        return nullptr;
    }

    if (byte_size > std::numeric_limits<std::size_t>::max() - (alignment - 1U) - sizeof(void*)) {
        return nullptr;
    }

    const auto total_size = byte_size + alignment - 1U + sizeof(void*);
    auto* raw = static_cast<unsigned char*>(std::malloc(total_size));
    if (raw == nullptr) {
        return nullptr;
    }

    auto raw_addr = reinterpret_cast<std::uintptr_t>(raw + sizeof(void*));
    const auto align_mask = static_cast<std::uintptr_t>(alignment - 1U);
    if (raw_addr > std::numeric_limits<std::uintptr_t>::max() - align_mask) {
        std::free(raw);
        return nullptr;
    }

    auto aligned_addr = (raw_addr + align_mask) & ~align_mask;
    auto* aligned_ptr = reinterpret_cast<void*>(aligned_addr);
    reinterpret_cast<void**>(aligned_ptr)[-1] = raw;
    return aligned_ptr;
}

inline void reworks_aligned_free(void* ptr) noexcept {
    if (ptr == nullptr) {
        return;
    }
    auto* raw = reinterpret_cast<void**>(ptr)[-1];
    std::free(raw);
}
#endif

}  // namespace detail

inline void* aligned_malloc(std::size_t byte_size, std::size_t alignment) noexcept {
    alignment = detail::normalize_alignment(alignment);
    if (alignment == 0U) {
        return nullptr;
    }

#if defined(_WIN32)
    return _aligned_malloc(byte_size, alignment);
#elif defined(_ACOREOS)
    const auto requested_size = byte_size == 0U ? alignment : byte_size;
    const auto padded_size = detail::round_up_to_alignment(requested_size, alignment);
    if (padded_size == 0U) {
        return nullptr;
    }
    return memalign(alignment, padded_size);
#elif defined(_REWORKS)
    return detail::reworks_aligned_malloc(byte_size, alignment);
#elif defined(_SYLIXOS)
    const auto requested_size = byte_size == 0U ? alignment : byte_size;
    const auto padded_size = detail::round_up_to_alignment(requested_size, alignment);
    if (padded_size == 0U) {
        return nullptr;
    }
    void* ptr = nullptr;
    if (posix_memalign(&ptr, alignment, padded_size) != 0) {
        return nullptr;
    }
    return ptr;
#else
    const auto requested_size = byte_size == 0U ? alignment : byte_size;
    const auto padded_size = detail::round_up_to_alignment(requested_size, alignment);
    if (padded_size == 0U) {
        return nullptr;
    }
    return aligned_alloc(alignment, padded_size);
#endif
}

inline void aligned_free(void* ptr) noexcept {
#if defined(_WIN32)
    _aligned_free(ptr);
#elif defined(_ACOREOS)
    std::free(ptr);
#elif defined(_REWORKS)
    detail::reworks_aligned_free(ptr);
#elif defined(_SYLIXOS)
    std::free(ptr);
#else
    std::free(ptr);
#endif
}

inline void* dma_aligned_malloc(std::size_t byte_size, std::size_t alignment) noexcept {
#if defined(_SYLIXOS)
    if (alignment < 64U) {
        alignment = 64U;
    }
    alignment = detail::normalize_alignment(alignment);
    if (alignment == 0U) {
        return nullptr;
    }

    const auto requested_size = byte_size == 0U ? alignment : byte_size;
    const auto padded_size = detail::round_up_to_alignment(requested_size, alignment);
    if (padded_size == 0U) {
        return nullptr;
    }

    return API_VmmDmaAllocAlign(
        static_cast<unsigned long>(padded_size),
        static_cast<unsigned long>(alignment));
#else
    return aligned_malloc(byte_size, alignment);
#endif
}

inline void dma_aligned_free(void* ptr) noexcept {
    if (ptr == nullptr) {
        return;
    }
#if defined(_SYLIXOS)
    API_VmmDmaFree(ptr);
#else
    aligned_free(ptr);
#endif
}

inline bool host_pointer_has_device_address() noexcept {
#if defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS) || defined(_SYLIXOS)
    return true;
#else
    return false;
#endif
}

inline std::uint64_t host_pointer_device_address(const void* ptr) noexcept {
    return static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(ptr));
}

}  // namespace icraft::osal::memory
