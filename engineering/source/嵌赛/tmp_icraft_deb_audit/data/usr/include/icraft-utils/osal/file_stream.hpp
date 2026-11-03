#pragma once

#include <cstdint>
#include <ios>
#include <istream>
#include <memory>
#include <ostream>
#include <string>
#include <string_view>

#include "icraft-utils/osal/filesystem.hpp"

#if !defined(_BAREME) && !defined(_FREERTOS)
#include <fstream>
#endif

namespace icraft::osal::fs {

enum class SeekOrigin {
    begin,
    current,
    end,
};

#if defined(_BAREME) || defined(_FREERTOS)
using NativeFile = ::File;
using NativeInputStream = ::FileIStream;
using NativeOutputStream = ::FileOStream;
#else
using NativeInputStream = std::ifstream;
using NativeOutputStream = std::ofstream;
#endif

class InputFile {
public:
    bool open(std::string_view path, std::ios_base::openmode mode = std::ios::binary) {
#if defined(_BAREME) || defined(_FREERTOS)
        (void)mode;
        try {
            file_ = std::make_unique<NativeFile>(std::string(path), static_cast<BYTE>(FA_READ));
            stream_ = std::make_unique<NativeInputStream>(*file_);
            cached_size_ = static_cast<std::int64_t>(file_->size());
            opened_ = true;
            return true;
        }
        catch (...) {
            close();
            return false;
        }
#else
        stream_ = std::make_unique<NativeInputStream>();
        stream_->open(std::string(path), mode);
        if (!stream_->is_open()) {
            close();
            return false;
        }

        auto current_pos = stream_->tellg();
        stream_->seekg(0, std::ios::end);
        cached_size_ = static_cast<std::int64_t>(stream_->tellg());
        stream_->seekg(current_pos);
        opened_ = true;
        return true;
#endif
    }

    void close() {
#if defined(_BAREME) || defined(_FREERTOS)
        if (stream_) {
            stream_.reset();
        }
        if (file_) {
            try {
                file_->close();
            }
            catch (...) {
            }
            file_.reset();
        }
#else
        if (stream_) {
            stream_->close();
            stream_.reset();
        }
#endif
        opened_ = false;
        cached_size_ = -1;
    }

    std::streambuf* rdbuf() const noexcept {
        return stream_ ? stream_->rdbuf() : nullptr;
    }

    std::size_t read(void* dst, std::size_t bytes) {
        if (!stream_) {
            return 0;
        }

        stream_->read(static_cast<char*>(dst), static_cast<std::streamsize>(bytes));
        return static_cast<std::size_t>(stream_->gcount());
    }

    bool is_open() const noexcept {
        return opened_;
    }

    std::int64_t size() const noexcept {
        return cached_size_;
    }

private:
#if defined(_BAREME) || defined(_FREERTOS)
    std::unique_ptr<NativeFile> file_;
#endif
    std::unique_ptr<NativeInputStream> stream_;
    bool opened_ = false;
    std::int64_t cached_size_ = -1;
};

class OutputFile {
public:
    bool open(std::string_view path, std::ios_base::openmode mode = std::ios::binary | std::ios::trunc) {
#if defined(_BAREME) || defined(_FREERTOS)
        try {
            BYTE file_mode = 0;
            if ((mode & std::ios_base::app) != 0) {
                file_mode = static_cast<BYTE>(FA_WRITE | FA_OPEN_APPEND);
            }
            else {
                file_mode = static_cast<BYTE>(FA_WRITE | FA_CREATE_ALWAYS);
            }

            file_ = std::make_unique<NativeFile>(std::string(path), file_mode);
            stream_ = std::make_unique<NativeOutputStream>(*file_);
            opened_ = true;
            return true;
        }
        catch (...) {
            close();
            return false;
        }
#else
        stream_ = std::make_unique<NativeOutputStream>();
        stream_->open(std::string(path), mode);
        if (!stream_->is_open()) {
            close();
            return false;
        }

        opened_ = true;
        return true;
#endif
    }

    void close() {
#if defined(_BAREME) || defined(_FREERTOS)
        if (stream_) {
            stream_.reset();
        }
        if (file_) {
            try {
                file_->close();
            }
            catch (...) {
            }
            file_.reset();
        }
#else
        if (stream_) {
            stream_->close();
            stream_.reset();
        }
#endif
        opened_ = false;
    }

    std::streambuf* rdbuf() const noexcept {
        return stream_ ? stream_->rdbuf() : nullptr;
    }

    std::size_t write(const void* src, std::size_t bytes) {
        if (!stream_) {
            return 0;
        }

        stream_->write(static_cast<const char*>(src), static_cast<std::streamsize>(bytes));
        return stream_->good() ? bytes : 0;
    }

    void flush() {
        if (stream_) {
            stream_->flush();
        }
    }

    bool is_open() const noexcept {
        return opened_;
    }

private:
#if defined(_BAREME) || defined(_FREERTOS)
    std::unique_ptr<NativeFile> file_;
#endif
    std::unique_ptr<NativeOutputStream> stream_;
    bool opened_ = false;
};

}  // namespace icraft::osal::fs