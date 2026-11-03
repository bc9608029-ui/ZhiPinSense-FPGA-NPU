#pragma once
#include <string>
#include <string_view>

#include "icraft-utils/dllexport.h"

#if !defined(_BAREME) && !defined(_FREERTOS) && !defined(_ACOREOS)
#include <filesystem>
#endif


namespace icraft::midware {

#if !defined(_BAREME) && !defined(_FREERTOS) && !defined(_ACOREOS)

using path = std::filesystem::path;

#else

namespace detail {

inline std::string join_path(std::string_view lhs, std::string_view rhs) {
    std::string joined(lhs);
    if (joined.empty()) {
        return std::string(rhs);
    }
    if (joined.back() != '/' && joined.back() != '\\') {
        joined.push_back('/');
    }
    if (!rhs.empty() && (rhs.front() == '/' || rhs.front() == '\\')) {
        joined.append(rhs.substr(1));
    }
    else {
        joined.append(rhs);
    }
    return joined;
}

inline std::string parent_path(std::string_view value) {
    if (value.empty()) {
        return {};
    }
    auto pos = value.find_last_of("/\\");
    if (pos == std::string_view::npos) {
        return {};
    }
    if (pos == 0) {
        return "/";
    }
    return std::string(value.substr(0, pos));
}

inline std::string filename(std::string_view value) {
    if (value.empty()) {
        return {};
    }
    auto pos = value.find_last_of("/\\");
    if (pos == std::string_view::npos) {
        return std::string(value);
    }
    return std::string(value.substr(pos + 1));
}

inline std::string extension(std::string_view value) {
    auto file = filename(value);
    auto pos = file.find_last_of('.');
    if (pos == std::string::npos || pos == 0) {
        return {};
    }
    return file.substr(pos);
}

inline std::string stem(std::string_view value) {
    auto file = filename(value);
    auto pos = file.find_last_of('.');
    if (pos == std::string::npos || pos == 0) {
        return file;
    }
    return file.substr(0, pos);
}

inline std::string replace_extension(std::string_view value, std::string_view ext) {
    auto base = parent_path(value);
    auto file_stem = stem(value);
    if (base.empty()) {
        return file_stem + std::string(ext);
    }
    return join_path(base, file_stem) + std::string(ext);
}

}  // namespace detail

class path {
public:
    using native_t = std::string;

    path() = default;

    explicit path(const char* s) : p_(s) {}
    explicit path(std::string s) : p_(std::move(s)) {}
    explicit path(std::string_view s) : p_(std::string(s)) {}

    template <size_t N>
    explicit path(const char(&s)[N]) : p_(std::string(s)) {}

    path& operator/=(const path& other) {
        p_ = detail::join_path(p_, other.p_);
        return *this;
    }

    friend path operator/(path lhs, const path& rhs) {
        lhs /= rhs;
        return lhs;
    }

    path parent_path() const { return path(detail::parent_path(p_)); }
    path filename() const { return path(detail::filename(p_)); }
    path stem() const { return path(detail::stem(p_)); }
    path extension() const { return path(detail::extension(p_)); }

    path& replace_extension(const path& ext) {
        p_ = detail::replace_extension(p_, ext.p_);
        return *this;
    }

    std::string string() const { return p_; }
    const char* c_str() const { return p_.c_str(); }
    bool empty() const { return p_.empty(); }

    friend bool operator==(const path& a, const path& b) { return a.p_ == b.p_; }
    friend bool operator!=(const path& a, const path& b) { return !(a == b); }

    const native_t& native() const { return p_; }

private:
    native_t p_;
};

#endif

} // namespace icraft::midware

extern "C" {
    UTILS_DLL bool exists(const icraft::midware::path& path);

    UTILS_DLL bool create_directory(const icraft::midware::path& path);

    UTILS_DLL size_t file_size(const icraft::midware::path& path);

    UTILS_DLL bool is_directory(const icraft::midware::path& path);
}
