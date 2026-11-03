#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "icraft-utils/dllexport.h"
#include "icraft-utils/osal/capabilities.hpp"

#if defined(_BAREME)
#include "icraft-utils/osal/baremetal/filesystem.hpp"
#elif defined(_FREERTOS)
#include "icraft-utils/osal/freertos/filesystem.hpp"
#elif !defined(_ACOREOS)
#include <filesystem>
#endif

namespace icraft::osal::fs {

enum class EntryType {
    missing,
    regular,
    directory,
    other,
};

#if defined(_BAREME) || defined(_FREERTOS)
using NativeFileSystem = ::FileSystem;
#endif

UTILS_DLL bool exists(std::string_view path);
UTILS_DLL EntryType entry_type(std::string_view path);
UTILS_DLL bool is_directory(std::string_view path);
UTILS_DLL bool create_directories(std::string_view path);
UTILS_DLL bool ensure_directory(std::string_view path);
UTILS_DLL bool remove_file(std::string_view path);
UTILS_DLL bool rename(std::string_view from, std::string_view to);
UTILS_DLL std::uint64_t file_size(std::string_view path);
UTILS_DLL std::vector<std::string> list_directory(std::string_view path);
UTILS_DLL std::string current_path();

}  // namespace icraft::osal::fs
