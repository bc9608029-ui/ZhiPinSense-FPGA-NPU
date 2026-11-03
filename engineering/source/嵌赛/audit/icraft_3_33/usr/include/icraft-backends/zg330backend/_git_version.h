#pragma once

#include <string>

namespace icraft::zg330backend {
	constexpr uint64_t MAJOR_VERSION_NUM = 3;
	constexpr uint64_t MINOR_VERSION_NUM = 33;
	constexpr uint64_t PATCH_VERSION_NUM = 1;
	constexpr uint64_t COMMITSINCETAG = 0;

	constexpr std::string_view COMMITID = "7ff57aa";
	constexpr std::string_view MODIFIED = "";
	constexpr std::string_view BUILDTIME = "2512171413";

	constexpr std::string_view MAIN_VERSION = "3.33.1.0";
	constexpr std::string_view FULL_VERSION = "3.33.1.0-7ff57aa(2512171413)";

    static constexpr std::string_view __version_string__ = "full_version: 3.33.1.0-7ff57aa(2512171413)";
}
    