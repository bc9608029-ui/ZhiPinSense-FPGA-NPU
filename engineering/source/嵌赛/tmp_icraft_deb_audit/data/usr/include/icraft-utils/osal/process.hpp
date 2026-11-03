#pragma once

#include <cstdint>
#include <string>

#ifdef _WIN32
#include "icraft-utils/osal/windows.hpp"
#elif !defined(_BAREME) && !defined(_FREERTOS) && !defined(_ACOREOS)
#include <unistd.h>
#endif

#if !defined(_BAREME) && !defined(_FREERTOS) && !defined(_ACOREOS)
#include <filesystem>
#endif

namespace icraft::osal::process {

inline std::uint64_t current_pid() noexcept {
#ifdef _WIN32
    return static_cast<std::uint64_t>(GetCurrentProcessId());
#elif defined(_BAREME) || defined(_FREERTOS) || defined(_ACOREOS)
    return 0;
#else
    return static_cast<std::uint64_t>(getpid());
#endif
}

inline std::string temp_directory() {
#if defined(_BAREME) || defined(_FREERTOS)
    return "/";
#elif defined(_ACOREOS)
    return "A:/";
#else
    return std::filesystem::temp_directory_path().string();
#endif
}

}  // namespace icraft::osal::process
