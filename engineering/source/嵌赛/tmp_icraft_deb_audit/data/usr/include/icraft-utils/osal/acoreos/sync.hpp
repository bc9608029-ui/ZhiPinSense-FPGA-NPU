#pragma once

#include <atomic>
#include <cstdio>

#include <os/pos/apex/apexLib.h>

namespace icraft::osal::sync::detail {

class ACoreOsMutex {
public:
    ACoreOsMutex() {
        SEMAPHORE_NAME_TYPE name = {};
        const auto id = next_id().fetch_add(1U, std::memory_order_relaxed);
        std::snprintf(name, sizeof(name), "icr_mtx_%lu", static_cast<unsigned long>(id));

        RETURN_CODE_TYPE ret = NO_ERROR;
        CREATE_SEMAPHORE(name, 1, 1, FIFO, &handle_, &ret);
        created_ = ret == NO_ERROR;
    }

    ~ACoreOsMutex() = default;

    ACoreOsMutex(const ACoreOsMutex&) = delete;
    ACoreOsMutex& operator=(const ACoreOsMutex&) = delete;

    void lock() noexcept {
        if (!created_) {
            return;
        }
        RETURN_CODE_TYPE ret = NO_ERROR;
        WAIT_SEMAPHORE(handle_, INFINITE_TIME_VALUE, &ret);
    }

    void unlock() noexcept {
        if (!created_) {
            return;
        }
        RETURN_CODE_TYPE ret = NO_ERROR;
        SIGNAL_SEMAPHORE(handle_, &ret);
    }

    bool try_lock() noexcept {
        if (!created_) {
            return false;
        }
        RETURN_CODE_TYPE ret = NO_ERROR;
        WAIT_SEMAPHORE(handle_, 0, &ret);
        return ret == NO_ERROR;
    }

private:
    static std::atomic_uint& next_id() noexcept {
        static std::atomic_uint value{0U};
        return value;
    }

    SEMAPHORE_ID_TYPE handle_ = 0;
    bool created_ = false;
};

using Mutex = ACoreOsMutex;

}  // namespace icraft::osal::sync::detail
