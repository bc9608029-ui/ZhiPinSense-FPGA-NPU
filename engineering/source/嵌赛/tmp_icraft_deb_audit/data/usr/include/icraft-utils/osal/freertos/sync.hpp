#pragma once

#include <FreeRTOS.h>
#include <semphr.h>

namespace icraft::osal::sync::detail {

class FreeRtosMutex {
public:
    FreeRtosMutex() {
        handle_ = xSemaphoreCreateMutex();
    }

    ~FreeRtosMutex() {
        if (handle_ != nullptr) {
            vSemaphoreDelete(handle_);
            handle_ = nullptr;
        }
    }

    FreeRtosMutex(const FreeRtosMutex&) = delete;
    FreeRtosMutex& operator=(const FreeRtosMutex&) = delete;

    FreeRtosMutex(FreeRtosMutex&& other) noexcept : handle_(other.handle_) {
        other.handle_ = nullptr;
    }

    FreeRtosMutex& operator=(FreeRtosMutex&& other) noexcept {
        if (this != &other) {
            if (handle_ != nullptr) {
                vSemaphoreDelete(handle_);
            }
            handle_ = other.handle_;
            other.handle_ = nullptr;
        }
        return *this;
    }

    void lock() noexcept {
        if (handle_ != nullptr) {
            (void)xSemaphoreTake(handle_, portMAX_DELAY);
        }
    }

    void unlock() noexcept {
        if (handle_ != nullptr) {
            (void)xSemaphoreGive(handle_);
        }
    }

    bool try_lock() noexcept {
        if (handle_ == nullptr) {
            return false;
        }
        return xSemaphoreTake(handle_, 0) == pdTRUE;
    }

private:
    SemaphoreHandle_t handle_ = nullptr;
};

using Mutex = FreeRtosMutex;

}  // namespace icraft::osal::sync::detail