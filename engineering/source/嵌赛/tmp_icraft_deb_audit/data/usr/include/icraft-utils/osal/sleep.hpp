#pragma once

#include <chrono>
#include <cstdint>

#if defined(_FREERTOS)
#include <FreeRTOS.h>
#include <task.h>
#elif defined(_BAREME)
#include <stdint.h>
extern "C" void delay_us(uint32_t time_us);
#elif defined(_ACOREOS)
#include <os/pos/apex/apexLib.h>
#else
#include <thread>
#endif

namespace icraft::osal::thread {

inline void yield() noexcept {
#if defined(_FREERTOS)
    taskYIELD();
#elif defined(_BAREME)
    (void)0;
#elif defined(_ACOREOS)
    RETURN_CODE_TYPE ret = NO_ERROR;
    TIMED_WAIT(0, &ret);
#else
    std::this_thread::yield();
#endif
}

inline void sleep_for_ns(std::uint64_t ns) {
#if defined(_FREERTOS)
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::nanoseconds(ns));
    if (ms.count() <= 0) {
        taskYIELD();
        return;
    }
    TickType_t ticks = pdMS_TO_TICKS(static_cast<uint32_t>(ms.count()));
    if (ticks == 0) {
        ticks = 1;
    }
    vTaskDelay(ticks);
#elif defined(_BAREME)
    auto us = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::nanoseconds(ns));
    if (us.count() > 0) {
        delay_us(us.count());
    }
#elif defined(_ACOREOS)
    RETURN_CODE_TYPE ret = NO_ERROR;
    TIMED_WAIT(static_cast<SYSTEM_TIME_TYPE>(ns), &ret);
#else
    if (ns == 0) {
        std::this_thread::yield();
        return;
    }
    std::this_thread::sleep_for(std::chrono::nanoseconds(ns));
#endif
}

}  // namespace icraft::osal::thread
