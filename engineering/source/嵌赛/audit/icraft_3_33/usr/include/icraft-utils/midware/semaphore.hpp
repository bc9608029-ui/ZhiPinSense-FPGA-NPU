#pragma once

#ifdef _BAREME
#include <cstddef>
#include <chrono>
#include <atomic>

namespace icraft::midware
{
    class Semaphore
    {
    public:
        explicit Semaphore(std::ptrdiff_t desired);
        Semaphore(const Semaphore &) = delete;
        void release(std::ptrdiff_t update = 1);
        void acquire();
        bool try_acquire() noexcept;
        template <class Rep, class Period>
        bool try_acquire_for(const std::chrono::duration<Rep, Period> &rel_time)
        {
            auto begin = std::chrono::high_resolution_clock::now();
            while (!try_acquire())
            {
                auto now = std::chrono::high_resolution_clock::now();
                if (now - begin > rel_time)
                {
                    return false;
                }
            }
            return true;
        }
        template <class Clock, class Duration>
        bool try_acquire_until(const std::chrono::time_point<Clock, Duration> &abs_time)
        {
            while (!try_acquire())
            {
                auto now = std::chrono::high_resolution_clock::now();
                if (now > abs_time)
                {
                    return false;
                }
            }
            return true;
        }

    private:
        std::atomic_uint32_t count;
    };
}
#endif