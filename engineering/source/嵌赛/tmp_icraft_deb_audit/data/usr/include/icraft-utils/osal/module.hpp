#pragma once

#include <string>
#include <string_view>

#ifdef _WIN32
#include "icraft-utils/osal/windows.hpp"
#elif defined(_SYLIXOS) || (!defined(_BAREME) && !defined(_FREERTOS) && !defined(_REWORKS) && !defined(_ACOREOS))
#include <dlfcn.h>
#endif

#if !defined(_BAREME) && !defined(_FREERTOS) && !defined(_ACOREOS)
#include <filesystem>
#endif

namespace icraft::osal::module {

using ModuleHandle = void*;

inline bool supported() noexcept {
#if defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS) || defined(_SYLIXOS)
    return false;
#else
    return true;
#endif
}

inline ModuleHandle open(std::string_view abs_path) {
#ifdef _WIN32
    return reinterpret_cast<ModuleHandle>(LoadLibraryA(std::string(abs_path).c_str()));
#elif defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS)
    (void)abs_path;
    return nullptr;
#elif defined(_SYLIXOS)
    return dlopen(std::string(abs_path).c_str(), RTLD_LAZY);
#else
    return dlopen(std::string(abs_path).c_str(), RTLD_LAZY);
#endif
}

inline void* symbol(ModuleHandle handle, const char* symbol_name) {
#ifdef _WIN32
    return reinterpret_cast<void*>(GetProcAddress(reinterpret_cast<HMODULE>(handle), symbol_name));
#elif defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS)
    (void)handle;
    (void)symbol_name;
    return nullptr;
#elif defined(_SYLIXOS)
    return dlsym(handle, symbol_name);
#else
    return dlsym(handle, symbol_name);
#endif
}

inline void close(ModuleHandle handle) {
    if (handle == nullptr) {
        return;
    }
#ifdef _WIN32
    FreeLibrary(reinterpret_cast<HMODULE>(handle));
#elif defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS)
    (void)handle;
#elif defined(_SYLIXOS)
    dlclose(handle);
#else
    dlclose(handle);
#endif
}

inline std::string last_error() {
#ifdef _WIN32
    return std::to_string(GetLastError());
#elif defined(_BAREME) || defined(_FREERTOS) || defined(_REWORKS) || defined(_ACOREOS)
    return "dynamic module is unavailable on this platform";
#elif defined(_SYLIXOS)
    auto* err = dlerror();
    return err ? std::string(err) : std::string();
#else
    auto* err = dlerror();
    return err ? std::string(err) : std::string();
#endif
}

inline std::string decorate_module_name(std::string_view target_name) {
#ifdef _WIN32
    return std::string(target_name) + ".dll";
#else
    return "lib" + std::string(target_name) + ".so";
#endif
}

inline std::string current_module_dir() {
#ifdef _WIN32
    char folder[MAX_PATH + 1] = {0};
    HMODULE module = nullptr;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCSTR>(&current_module_dir), &module)) {
        return {};
    }
    GetModuleFileNameA(module, folder, sizeof(folder));
    return std::filesystem::path(folder).parent_path().string();
#elif defined(_REWORKS)
    return std::filesystem::current_path().string();
#elif defined(_SYLIXOS)
    Dl_info dl_info;
    if (dladdr(reinterpret_cast<void*>(&current_module_dir), &dl_info) == 0) {
        return std::filesystem::current_path().string();
    }
    return std::filesystem::path(dl_info.dli_fname).parent_path().string();
#elif defined(_BAREME) || defined(_FREERTOS) || defined(_ACOREOS)
    return {};
#else
    Dl_info dl_info;
    if (dladdr(reinterpret_cast<void*>(&current_module_dir), &dl_info) == 0) {
        return {};
    }
    return std::filesystem::path(dl_info.dli_fname).parent_path().string();
#endif
}

}  // namespace icraft::osal::module
