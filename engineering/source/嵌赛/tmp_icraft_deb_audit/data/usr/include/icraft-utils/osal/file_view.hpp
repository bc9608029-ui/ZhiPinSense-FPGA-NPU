#pragma once

#include <cstdint>
#include <cstdlib>
#include <string>
#include <string_view>

#include "icraft-utils/osal/capabilities.hpp"
#include "icraft-utils/osal/file_stream.hpp"

#ifdef _WIN32
#include "icraft-utils/osal/windows.hpp"
#elif !defined(_BAREME) && !defined(_FREERTOS) && !defined(_REWORKS) && !defined(_ACOREOS)
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace icraft::osal::buffer {

enum class BackingKind {
    mapped,
    heap,
};

struct FileView {
    char* data = nullptr;
    std::uint64_t size = 0;
    bool writable = false;
    BackingKind backing = BackingKind::heap;
    std::string path;
};

namespace detail {

inline char* allocate_heap_buffer(std::size_t size) {
#if defined(_BAREME) || defined(_FREERTOS)
    return static_cast<char*>(std::malloc(size));
#else
    return new char[size];
#endif
}

inline void free_heap_buffer(char* data) {
#if defined(_BAREME) || defined(_FREERTOS)
    std::free(data);
#else
    delete[] data;
#endif
}

inline void reset(FileView& view) {
    view.data = nullptr;
    view.size = 0;
    view.writable = false;
    view.backing = BackingKind::heap;
    view.path.clear();
}

}  // namespace detail

inline FileView open_file_view(std::string_view path, bool writable) {
    FileView view;
    view.writable = writable;
    view.path = std::string(path);

    if (path.empty()) {
        return view;
    }

#ifdef _WIN32
    if (capabilities().has_real_file_view) {
        auto path_string = std::string(path);
        HANDLE file = CreateFileA(
            path_string.c_str(),
            writable ? (GENERIC_READ | GENERIC_WRITE) : GENERIC_READ,
            FILE_SHARE_READ,
            nullptr,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            nullptr);
        if (file == INVALID_HANDLE_VALUE) {
            detail::reset(view);
            return view;
        }

        LARGE_INTEGER file_size;
        if (!GetFileSizeEx(file, &file_size)) {
            CloseHandle(file);
            detail::reset(view);
            return view;
        }

        if (file_size.QuadPart == 0) {
            CloseHandle(file);
            view.size = 0;
            return view;
        }

        HANDLE mapping = CreateFileMappingA(file, nullptr, writable ? PAGE_READWRITE : PAGE_READONLY, 0, 0, nullptr);
        CloseHandle(file);
        if (mapping == nullptr) {
            detail::reset(view);
            return view;
        }

        void* addr = MapViewOfFile(mapping, writable ? FILE_MAP_WRITE : FILE_MAP_READ, 0, 0, 0);
        CloseHandle(mapping);
        if (addr == nullptr) {
            detail::reset(view);
            return view;
        }

        view.data = static_cast<char*>(addr);
        view.size = static_cast<std::uint64_t>(file_size.QuadPart);
        view.backing = BackingKind::mapped;
        return view;
    }
#elif !defined(_BAREME) && !defined(_FREERTOS) && !defined(_REWORKS) && !defined(_ACOREOS)
    if (capabilities().has_real_file_view) {
        auto path_string = std::string(path);
        int fd = open(path_string.c_str(), writable ? O_RDWR : O_RDONLY);
        if (fd == -1) {
            detail::reset(view);
            return view;
        }

        struct stat stat_buf;
        if (fstat(fd, &stat_buf) == -1) {
            close(fd);
            detail::reset(view);
            return view;
        }

        if (stat_buf.st_size == 0) {
            close(fd);
            view.size = 0;
            return view;
        }

        void* addr = mmap(nullptr, stat_buf.st_size, writable ? (PROT_READ | PROT_WRITE) : PROT_READ, MAP_SHARED, fd, 0);
        close(fd);
        if (addr == MAP_FAILED) {
            detail::reset(view);
            return view;
        }

        view.data = static_cast<char*>(addr);
        view.size = static_cast<std::uint64_t>(stat_buf.st_size);
        view.backing = BackingKind::mapped;
        return view;
    }
#endif

    fs::InputFile file;
    if (!file.open(path, std::ios::binary)) {
        detail::reset(view);
        return view;
    }

    const auto file_size = file.size();
    if (file_size <= 0) {
        file.close();
        view.size = 0;
        return view;
    }

    view.size = static_cast<std::uint64_t>(file_size);
    view.data = detail::allocate_heap_buffer(static_cast<std::size_t>(view.size));
    if (view.data == nullptr) {
        file.close();
        detail::reset(view);
        return view;
    }

    auto read_size = file.read(view.data, static_cast<std::size_t>(view.size));
    file.close();
    if (read_size != view.size) {
        detail::free_heap_buffer(view.data);
        detail::reset(view);
        return view;
    }

    view.backing = BackingKind::heap;
    return view;
}

inline bool sync_file_view(FileView& view) {
    if (view.data == nullptr || !view.writable) {
        return true;
    }

    if (view.backing == BackingKind::mapped) {
#ifdef _WIN32
        return FlushViewOfFile(view.data, static_cast<SIZE_T>(view.size)) != 0;
#elif !defined(_BAREME) && !defined(_FREERTOS) && !defined(_REWORKS) && !defined(_ACOREOS)
        return msync(view.data, static_cast<size_t>(view.size), MS_SYNC) == 0;
#else
        return false;
#endif
    }

    if (view.path.empty()) {
        return false;
    }

    fs::OutputFile file;
    if (!file.open(view.path, std::ios::binary | std::ios::trunc)) {
        return false;
    }

    const auto write_size = file.write(view.data, static_cast<std::size_t>(view.size));
    file.flush();
    file.close();
    return write_size == view.size;
}

inline void close_file_view(FileView& view) {
    if (view.data == nullptr) {
        detail::reset(view);
        return;
    }

    if (view.backing == BackingKind::mapped) {
#ifdef _WIN32
        (void)UnmapViewOfFile(view.data);
#elif !defined(_BAREME) && !defined(_FREERTOS) && !defined(_REWORKS) && !defined(_ACOREOS)
        (void)munmap(view.data, static_cast<size_t>(view.size));
#endif
    }
    else {
        detail::free_heap_buffer(view.data);
    }

    detail::reset(view);
}

}  // namespace icraft::osal::buffer
