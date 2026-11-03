#pragma once
#ifndef ICRAFT_XIR_UTILS_MMAP_BUFFER_H_
#define ICRAFT_XIR_UTILS_MMAP_BUFFER_H_

#include <cstdint>
#include <map>
#include <memory>
#include <mutex>
#include <type_traits>
#include <utility>

#include <icraft-xir/base/object.h>
#include <icraft-utils/midware/path.hpp>
#include <icraft-utils/osal/file_view.hpp>

namespace icraft::xir {

inline bool supports_param_swap() noexcept {
    const auto& caps = icraft::osal::capabilities();
    return caps.has_filesystem && caps.has_process_info && caps.has_file_view_writeback;
}

template<typename PathType>
std::pair<char*, uint64_t> MMapFile(const PathType& file_path, bool writable) {
    using NormalizedPathType = std::remove_cv_t<std::remove_reference_t<PathType>>;
    static_assert(
        std::is_constructible_v<icraft::midware::path, NormalizedPathType>,
        "MMapFile only supports types constructible as icraft::midware::path"
    );

    auto normalized_path = icraft::midware::path(file_path);
    auto view = icraft::osal::buffer::open_file_view(normalized_path.string(), writable);
    return {view.data, view.size};
}


class ParamsBufferStorage {
public:
    // 获取单实例对象(引用)
    XIR_DLL static ParamsBufferStorage& GetInstance();

    // 设置缓存文件夹路径
    XIR_DLL static void setBufferDir(const icraft::midware::path&);

    template <typename PathType,
        typename = std::enable_if_t<
            !std::is_same_v<std::remove_cv_t<std::remove_reference_t<PathType>>, icraft::midware::path> &&
            std::is_constructible_v<icraft::midware::path, PathType>>>
    static void setBufferDir(PathType&& dest_dir) {
        setBufferDir(icraft::midware::path(std::forward<PathType>(dest_dir)));
    }

    // 获取缓存文件夹路径
    XIR_DLL const icraft::midware::path& getBufferDir();

    // 返回分配的虚拟内存地址
    XIR_DLL char* _mallocBuffer(uint64_t malloc_size, int64_t v_id);

    // 获取内存映射表
    XIR_DLL std::map<char*, icraft::osal::buffer::FileView>& getMappedPtrsMap();

    // 解除所有内存映射
    XIR_DLL void _closeMapping();

private:
    // 禁止外部构造与析构
    ParamsBufferStorage();
    ~ParamsBufferStorage();

    // 禁止外部拷贝与赋值
    ParamsBufferStorage(const ParamsBufferStorage&) = delete;
    ParamsBufferStorage& operator=(const ParamsBufferStorage&) = delete;

    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}

#endif // ICRAFT_XIR_UTILS_MMAP_BUFFER_H_
