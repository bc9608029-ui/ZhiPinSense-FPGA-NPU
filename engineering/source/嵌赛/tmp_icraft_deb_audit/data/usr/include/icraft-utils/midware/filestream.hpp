#pragma once
#include <memory>
#include <string>
#include <string_view>
#include <cstdint>
#include <istream>
#include <ostream>
#include "icraft-utils/dllexport.h"
#include "icraft-utils/midware/path.hpp"

namespace icraft::midware {

class UTILS_DLL ifstream : public std::istream {
public:
    ifstream();                                      // 构造时先用空 rdbuf
    explicit ifstream(std::string_view path, std::ios_base::openmode mode = std::ios::binary);
    explicit inline ifstream(const std::string& path, std::ios_base::openmode mode = std::ios::binary)
        : ifstream(std::string_view(path), mode) {
    }
    explicit inline ifstream(const char* path, std::ios_base::openmode mode = std::ios::binary)
        : ifstream(std::string_view(path), mode) {
    }

    explicit inline ifstream(const icraft::midware::path& p, std::ios_base::openmode mode = std::ios::binary)
        : ifstream(p.string(), mode) {
    };
    ~ifstream();                                     

    ifstream(const ifstream&) = delete;
    ifstream& operator=(const ifstream&) = delete;
    ifstream(ifstream&&) noexcept;
    ifstream& operator=(ifstream&&) noexcept;

    bool   open(std::string_view path, std::ios_base::openmode mode = std::ios::binary);
    void   close();


    std::size_t read(void* dst, std::size_t bytes);
    std::size_t gcount_ex() const noexcept { return last_read_; }

    bool   seek(int64_t offset, int origin);  
    int64_t tell() const;
    int64_t size() const;

    bool   is_open() const noexcept;                 
    bool   good()   const noexcept;                  
    bool   eof()    const noexcept;                  

private:
    struct impl;
    std::unique_ptr<impl> p_;
    std::size_t last_read_ = 0;
};

class UTILS_DLL ofstream : public std::ostream {
public:
    ofstream();
    explicit ofstream(std::string_view path, std::ios_base::openmode mode = std::ios::binary | std::ios::trunc);
    explicit inline ofstream(const std::string& path, std::ios_base::openmode mode = std::ios::binary | std::ios::trunc)
        : ofstream(std::string_view(path), mode) {
    }
    explicit inline ofstream(const char* path, std::ios_base::openmode mode = std::ios::binary | std::ios::trunc)
        : ofstream(std::string_view(path), mode) {
    }
    explicit inline ofstream(const icraft::midware::path& p, std::ios_base::openmode mode = std::ios::binary | std::ios::trunc)
        : ofstream(p.string(), mode) {
    }
    ~ofstream();

    ofstream(const ofstream&) = delete;
    ofstream& operator=(const ofstream&) = delete;
    ofstream(ofstream&&) noexcept;
    ofstream& operator=(ofstream&&) noexcept;

    bool   open(std::string_view path, std::ios_base::openmode mode = std::ios::binary | std::ios::trunc);
    void   close();

    // 
    std::size_t write(const void* src, std::size_t bytes);
    void   flush();

    bool   seek(int64_t offset, int origin);         
    int64_t tell() const;

    bool   is_open() const noexcept;                 
    bool   good()   const noexcept;                

private:
    struct impl;
    std::unique_ptr<impl> p_;
};

} // namespace icraft::midware
