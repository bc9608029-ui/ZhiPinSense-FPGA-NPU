#pragma once

#include "icraft-utils/osal/capabilities.hpp"

#ifdef _WIN32
#include "icraft-utils/osal/windows.hpp"
#endif

namespace icraft::osal::console {

struct ConsoleCaps {
    bool stdout_supports_ansi = false;
    bool stderr_supports_ansi = false;
    bool supports_utf8_output = false;
    bool has_stderr = true;
    int columns = 0;
};

struct ConsoleCallResult {
    bool success = false;
    unsigned long error_code = 0;
    const char* failed_call = nullptr;
};

inline ConsoleCaps query() noexcept {
#if defined(_BAREME) || defined(_FREERTOS)
    return {false, false, false, false, 0};
#elif defined(_REWORKS) || defined(_ACOREOS) || defined(_SYLIXOS)
    return {false, false, false, true, 80};
#elif defined(_WIN32)
    return {true, true, true, true, 0};
#else
    return {true, true, true, true, 0};
#endif
}

namespace detail {

#ifdef _WIN32
inline ConsoleCallResult enable_ansi_for_handle(DWORD handle_id) noexcept {
    DWORD mode = 0;
    auto handle = GetStdHandle(handle_id);
    if (handle == INVALID_HANDLE_VALUE || handle == nullptr) {
        return {false, static_cast<unsigned long>(GetLastError()), "GetStdHandle"};
    }

    if (!GetConsoleMode(handle, &mode)) {
        return {false, static_cast<unsigned long>(GetLastError()), "GetConsoleMode"};
    }

    mode |= ENABLE_VIRTUAL_TERMINAL_PROCESSING;
    if (!SetConsoleMode(handle, mode)) {
        return {false, static_cast<unsigned long>(GetLastError()), "SetConsoleMode"};
    }

    return {true, 0, nullptr};
}
#endif

}  // namespace detail

inline ConsoleCallResult enable_stdout_ansi() noexcept {
#ifdef _WIN32
    return detail::enable_ansi_for_handle(STD_OUTPUT_HANDLE);
#else
    return {query().stdout_supports_ansi, 0, nullptr};
#endif
}

inline ConsoleCallResult enable_stderr_ansi() noexcept {
#ifdef _WIN32
    return detail::enable_ansi_for_handle(STD_ERROR_HANDLE);
#else
    return {query().stderr_supports_ansi, 0, nullptr};
#endif
}

inline ConsoleCallResult enable_utf8_output() noexcept {
#ifdef _WIN32
    if (!SetConsoleOutputCP(65001)) {
        return {false, static_cast<unsigned long>(GetLastError()), "SetConsoleOutputCP"};
    }
    return {true, 0, nullptr};
#else
    return {query().supports_utf8_output, 0, nullptr};
#endif
}

}  // namespace icraft::osal::console
