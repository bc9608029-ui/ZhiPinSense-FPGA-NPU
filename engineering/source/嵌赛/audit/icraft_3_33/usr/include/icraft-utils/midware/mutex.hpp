#pragma once

#ifndef _BAREME
#include <mutex>
#else
#include <fmsh_common_lock.h>
#endif

namespace icraft::midware
{
    namespace impl
    {
        /*
         * @brief 无效mutex，用于裸机单线程环境
         */
        class DummyMutex
        {
        public:
            void lock() noexcept
            {
            }
            void unlock() noexcept
            {
            }
            void try_lock() noexcept
            {
            }
        };

        template <class _Mutex>
        class lock_guard { // class with destructor that unlocks a mutex
        public:
            using mutex_type = _Mutex;

            explicit lock_guard(_Mutex& _Mtx) : _MyMutex(_Mtx) { // construct and lock
                _MyMutex.lock();
            }
            
            ~lock_guard() noexcept {
                _MyMutex.unlock();
            }

            lock_guard(const lock_guard&)            = delete;
            lock_guard& operator=(const lock_guard&) = delete;

        private:
            _Mutex& _MyMutex;
        };
    }
#ifndef _BAREME
    using Mutex = std::mutex;
    template<class _Mutex>
    using LockGuard=std::lock_guard<_Mutex>;
#else

    // using Mutex = impl::DummyMutex;
    using Mutex = Spinlock;
    template<class _Mutex>
    using LockGuard=impl::lock_guard<_Mutex>;
#endif
}