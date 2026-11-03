#pragma once

#include <cstdlib>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace icraft::osal::env {

inline std::optional<std::string> get(std::string_view key) {
    if (key.empty()) {
        return std::nullopt;
    }

    std::string key_string(key);
    auto* value = std::getenv(key_string.c_str());
    if (value == nullptr) {
        return std::nullopt;
    }
    return std::string(value);
}

inline char search_path_separator() noexcept {
#ifdef _WIN32
    return ';';
#else
    return ':';
#endif
}

inline std::vector<std::string> split_search_path(std::string_view value) {
    std::vector<std::string> parts;
    std::string current;
    const char separator = search_path_separator();

    for (char ch : value) {
        if (ch == separator) {
            if (!current.empty()) {
                parts.push_back(current);
                current.clear();
            }
            continue;
        }
        current.push_back(ch);
    }

    if (!current.empty()) {
        parts.push_back(current);
    }

    return parts;
}

}  // namespace icraft::osal::env