#pragma once
#include "icraft-utils/dllexport.h"
#include <map>
#include <string>


namespace icraft {

	/**
	 * @brief 从TOML文件获取某个section下的键值对
	 * @param filename	文件名
	 * @param command	section名称
	 * @return			TOML文件对应的toml::table
	 * @throw			如果没有此section则抛出异常
	 */
	UTILS_DLL std::map<std::string, std::string> getKVfromTomlFile(const std::string& filename, const std::string& command);
}
