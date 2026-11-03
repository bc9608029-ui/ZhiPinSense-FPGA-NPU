#pragma once

#if defined(__has_include)
#  if __has_include(<fmsh_common_lock.h>)
#    define ICRAFT_OSAL_HAS_FMSH_COMMON_LOCK 1
#  endif
#endif

#ifndef ICRAFT_OSAL_HAS_FMSH_COMMON_LOCK
#  define ICRAFT_OSAL_HAS_FMSH_COMMON_LOCK 0
#endif

#if ICRAFT_OSAL_HAS_FMSH_COMMON_LOCK
#  include <fmsh_common_lock.h>
#else
#  include <atomic>
#endif

namespace icraft::osal::sync::detail {

#if ICRAFT_OSAL_HAS_FMSH_COMMON_LOCK

using Mutex = Spinlock;

#else

class Spinlock {
  public:
    Spinlock() noexcept = default;
    ~Spinlock() = default;
    Spinlock(const Spinlock&) = delete;
    Spinlock& operator=(const Spinlock&) = delete;

    void lock() noexcept {
        while (flag_.test_and_set(std::memory_order_acquire)) {
        }
    }

    bool try_lock() noexcept {
        return !flag_.test_and_set(std::memory_order_acquire);
    }

    void unlock() noexcept {
        flag_.clear(std::memory_order_release);
    }

  private:
    std::atomic_flag flag_ = ATOMIC_FLAG_INIT;
};

using Mutex = Spinlock;

#endif

}  // namespace icraft::osal::sync::detail