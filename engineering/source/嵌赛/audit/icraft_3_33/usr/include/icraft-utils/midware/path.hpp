#pragma once
#include <string>
#include <string_view>

#include "icraft-utils/logging.h"

#ifdef _BAREME
// define fake filesystem path
#include "platform/baremetal/filesystem.hpp"  

#else
#include <filesystem>
#endif  //_BAREME   


namespace icraft::midware {


#if !defined(_BAREME)
    class path {
        public:
        using native_t = std::filesystem::path;

        path() = default;

        explicit path(const char* s) : p_(s) {}
        explicit path(std::string s) : p_(std::move(s)) {}
        explicit path(std::string_view s) : p_(std::string(s)) {}
        explicit path(const std::filesystem::path& p) : p_(p) {}
        explicit path(std::filesystem::path&& p) : p_(std::move(p)) {}

        template <size_t N>
        explicit path(const char(&s)[N]) : p_(std::string(s)) {}

        path& operator/=(const path& other) { p_ /= other.p_; return *this; }
        friend path operator/(path lhs, const path& rhs) { lhs /= rhs; return lhs; }


        path& operator=(const std::filesystem::path& p) { p_ = p; return *this; }
        path& operator=(std::filesystem::path&& p) { p_ = std::move(p); return *this; }

        path parent_path() const { return path{ p_.parent_path() }; }
        path filename() const { return path{ p_.filename() }; }
        path stem() const { return path{ p_.stem() }; }
        path extension() const { return path{ p_.extension() }; }

        path& replace_extension(const path& ext) { p_.replace_extension(ext.p_); return *this; }

        std::string string() const { return p_.string(); }
        bool empty() const { return p_.empty(); }

        friend bool operator==(const path& a, const path& b) { return a.p_ == b.p_; }
        friend bool operator!=(const path& a, const path& b) { return !(a==b); }

        const native_t& native() const { return p_; }

        private:
        native_t p_;
    };

#else // 裸机实现
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
            if (p_.empty()) { p_ = other.p_; return *this; }
            if (p_.back() != '/') p_.push_back('/');
            if (!other.p_.empty() && other.p_.front() == '/') p_ += other.p_.substr(1);
            else p_ += other.p_;
            return *this;
        }
        friend path operator/(path lhs, const path& rhs) { lhs /= rhs; return lhs; }

        path parent_path() const {
            if (p_.empty()) return {};
            auto pos = p_.find_last_of('/');
            if (pos == std::string::npos) return {};
            if (pos == 0) return path("/");
            return path(p_.substr(0, pos));
        }
        path filename() const {
            if (p_.empty()) return {};
            auto pos = p_.find_last_of('/');
            return (pos == std::string::npos) ? path(p_) : path(p_.substr(pos+1));
        }
        path extension() const {
            auto fn = filename().p_;
            auto pos = fn.find_last_of('.');
            if (pos == std::string::npos || pos == 0) return path{};
            return path(fn.substr(pos));
        }
        path stem() const {
            auto fn = filename().p_;
            auto pos = fn.find_last_of('.');
            if (pos == std::string::npos || pos == 0) return path(fn);
            return path(fn.substr(0, pos));
        }
        path& replace_extension(const path& ext) {
            auto base = parent_path() / stem();
            p_ = base.p_ + ext.p_;
            return *this;
        }

        std::string string() const { return p_; }
        bool empty() const { return p_.empty(); }

        friend bool operator==(const path& a, const path& b) { return a.p_ == b.p_; }
        friend bool operator!=(const path& a, const path& b) { return !(a==b); }

        const native_t& native() const { return p_; }

        private:
        native_t p_;
    };

#endif // _BAREME

} // namespace icraft::midware
extern "C" {
    UTILS_DLL bool exists(const icraft::midware::path& path);

    UTILS_DLL bool create_directory(const icraft::midware::path& path);

    UTILS_DLL size_t file_size(const icraft::midware::path& path);

    UTILS_DLL bool is_directory(const icraft::midware::path& path);
}