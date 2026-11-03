#pragma once

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>

#include "icraft-utils/osal/sleep.hpp"

#if defined(_FREERTOS)
#include "icraft-utils/osal/freertos/sync.hpp"
#elif defined(_BAREME)
#include "icraft-utils/osal/baremetal/sync.hpp"
#elif defined(_REWORKS)
#include "icraft-utils/osal/reworks/sync.hpp"
#elif defined(_ACOREOS)
#include "icraft-utils/osal/acoreos/sync.hpp"
#elif defined(_SYLIXOS)
#include "icraft-utils/osal/sylixos/sync.hpp"
#else
#include <mutex>

namespace icraft::osal::sync::detail {

using Mutex = std::mutex;

}  // namespace icraft::osal::sync::detail
#endif

namespace icraft::osal::sync {

namespace detail {

template <class MutexType>
class lock_guard {
public:
    using mutex_type = MutexType;

    explicit lock_guard(MutexType& mutex) : mutex_(mutex) {
        mutex_.lock();
    }

    ~lock_guard() noexcept {
        mutex_.unlock();
    }

    lock_guard(const lock_guard&) = delete;
    lock_guard& operator=(const lock_guard&) = delete;

private:
    MutexType& mutex_;
};

}  // namespace detail

class DummyMutex {
public:
    void lock() noexcept {}
    void unlock() noexcept {}
    bool try_lock() noexcept { return true; }
};

using Mutex = detail::Mutex;

template <class MutexType>
using LockGuard = detail::lock_guard<MutexType>;

class Semaphore {
public:
    explicit Semaphore(std::ptrdiff_t desired)
        : count_(desired > 0 ? static_cast<std::uint32_t>(desired) : 0u) {}

    Semaphore(const Semaphore&) = delete;
    Semaphore& operator=(const Semaphore&) = delete;

    void release(std::ptrdiff_t update = 1) {
        if (update <= 0) {
            return;
        }
        count_.fetch_add(static_cast<std::uint32_t>(update), std::memory_order_release);
    }

    void acquire() {
        while (!try_acquire()) {
            icraft::osal::thread::yield();
        }
    }

    bool try_acquire() noexcept {
        auto local_count = count_.load(std::memory_order_relaxed);
        while (local_count != 0u) {
            if (count_.compare_exchange_weak(
                    local_count,
                    local_count - 1,
                    std::memory_order_acquire,
                    std::memory_order_relaxed)) {
                return true;
            }
        }
        return false;
    }

    template <class Rep, class Period>
    bool try_acquire_for(const std::chrono::duration<Rep, Period>& rel_time) {
        auto begin = std::chrono::high_resolution_clock::now();
        while (!try_acquire()) {
            if (std::chrono::high_resolution_clock::now() - begin > rel_time) {
                return false;
            }
            icraft::osal::thread::yield();
        }
        return true;
    }

    template <class Clock, class Duration>
    bool try_acquire_until(const std::chrono::time_point<Clock, Duration>& abs_time) {
        while (!try_acquire()) {
            if (Clock::now() > abs_time) {
                return false;
            }
            icraft::osal::thread::yield();
        }
        return true;
    }

private:
    std::atomic_uint32_t count_;
};

}  // namespace icraft::osal::sync
