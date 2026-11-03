#pragma once
#include "icraft-utils/dllexport.h"
#include <filesystem>


namespace icraft {

    /**
     * @brief 获取指定路径所在磁盘的剩余空间（单位：GB）
     * @param path 指定路径
     * @return 指定路径所在磁盘的剩余空间
     * @throw 如果路径无效则抛出异常
     */
    UTILS_DLL double getFreeSpace(const std::filesystem::path& path);

    /** Windows平台下获取指定路径所在磁盘的GUID */
    #ifdef _WIN32
    std::wstring GetVolumeGuid(const std::wstring& path);
    #endif

     /**
     * @brief 判断两个(绝对）路径是否在同一磁盘上
     * @param path1 第一个路径
     * @param path2 第二个路径
     * @return 如果两个路径在同一磁盘上则返回true，否则返回false
     * @throw 如果路径无效则抛出异常
     */
    UTILS_DLL bool isSameDisk(const std::filesystem::path& path1, const std::filesystem::path& path2);
}