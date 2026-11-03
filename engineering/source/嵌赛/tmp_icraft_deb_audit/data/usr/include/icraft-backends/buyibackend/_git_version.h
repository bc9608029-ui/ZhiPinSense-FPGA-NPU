#pragma once

#include <string>

namespace icraft::buyibackend {
	constexpr uint64_t MAJOR_VERSION_NUM = 3;
	constexpr uint64_t MINOR_VERSION_NUM = 39;
	constexpr uint64_t PATCH_VERSION_NUM = 0;
	constexpr uint64_t COMMITSINCETAG = 0;

	constexpr std::string_view COMMITID = "d06ea38";
	constexpr std::string_view MODIFIED = "";
	constexpr std::string_view BUILDTIME = "2608220046";

	constexpr std::string_view MAIN_VERSION = "3.39.0.0";
	constexpr std::string_view FULL_VERSION = "3.39.0.0-d06ea38(2608220046)";

    static constexpr std::string_view __version_string__ = "full_version: 3.39.0.0-d06ea38(2608220046)";
}
    