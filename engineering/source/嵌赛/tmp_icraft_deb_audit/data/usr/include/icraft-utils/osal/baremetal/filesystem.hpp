#pragma once
#include "ff.h"
#include <string>
#include <vector>
#include <stdexcept>
#include <streambuf>
#include <iostream>


// FileSystem 类的声明
class FileSystem {
    public:
        static FileSystem& instance() {
        std::cout << "FileSystem instance " << std::endl;

        static FileSystem fs;
        return fs;
    }
        FileSystem();
        FileSystem(const FileSystem&) = delete;
        FileSystem(FileSystem&&) = delete;
        FileSystem &operator=(const FileSystem &) = delete;
        FileSystem &operator=(FileSystem &&) = delete;
        ~FileSystem();
        bool exists(const std::string& path);
        void create_directory(const std::string& path);
        void remove(const std::string& path);
        std::vector<std::string> list_directory(const std::string& path);
    
    private:
        FATFS* fs;
    };
    
    // File 类的声明
class File {
    public:
        File(const std::string& path, BYTE mode);
        void write(const std::string& data);
        void close();
        std::string read(UINT size);
        void read(char* to, UINT size);
        void write(const std::vector<BYTE>& data);
        void write(const char* data, uint64_t size);
        std::vector<BYTE> readBinary(UINT size);
        FSIZE_t size() const;
        void seek(FSIZE_t offset);
        FSIZE_t tell() const;
        void flush();
        ~File();
    
    private:
        FIL file;
    };
    
    // FileStreamBuf 类的声明
    class FileStreamBuf : public std::streambuf {
    public:
        FileStreamBuf(File& file);
    protected:
        int_type underflow() override;
        int_type overflow(int_type ch) override;
        int sync() override;
        pos_type seekoff(off_type off, std::ios_base::seekdir way, std::ios_base::openmode which) override;
        pos_type seekpos(pos_type pos, std::ios_base::openmode which) override;
    
    private:
        int_type flushBuffer();
        File& file;
        std::vector<uint8_t> buffer{ std::vector<uint8_t>(1024) };
    };
    
    // FileIStream 类的声明
    class FileIStream : public std::istream {
    public:
        FileIStream(File& file);
    private:
        FileStreamBuf buf;
};
    
    // FileOStream 类的声明
    class FileOStream : public std::ostream {
    public:
        FileOStream(File& file);
    private:
        FileStreamBuf buf;
};