#pragma once

#include <string>

namespace cp {
	constexpr uint64_t MAJOR_VERSION_NUM = 3;
	constexpr uint64_t MINOR_VERSION_NUM = 38;
	constexpr uint64_t PATCH_VERSION_NUM = 0;
	constexpr uint64_t COMMITSINCETAG = 0;

	constexpr std::string_view COMMITID = "d0b6fc4";
	constexpr std::string_view MODIFIED = "";
	constexpr std::string_view BUILDTIME = "2608220058";

	constexpr std::string_view MAIN_VERSION = "3.38.0.0";
	constexpr std::string_view FULL_VERSION = "3.38.0.0-d0b6fc4(2608220058)";

    static constexpr std::string_view __version_string__ = "full_version: 3.38.0.0-d0b6fc4(2608220058)";
}
    