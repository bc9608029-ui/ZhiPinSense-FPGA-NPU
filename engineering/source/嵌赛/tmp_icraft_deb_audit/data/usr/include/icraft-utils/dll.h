#pragma once
#include "icraft-utils/midware/path.hpp"
#include "icraft-utils/dllexport.h"
#include <optional>


namespace icraft {

	/**
	 * @brief 加载指定路径的DLL
	 * @param dll_file	DLL的文件路径（不作处理，必须完全正确）
	 * @return	DLL的句柄
	 */
	UTILS_DLL void* LoadDLLByPath(const icraft::midware::path& dll_file);
	/**
	 * @brief 加载当前DLL路径下指定目标名称的DLL
	 * @param target_name	目标名称，即CMake中的target名称
	 */
	UTILS_DLL void* LoadDLLInBinDir(const std::string& target_name);

	/**
	 * @brief 在环境变量所指定的路径中搜索目标对应的DLL
	 * @param target_name	目标名称，即CMake中的target名称
	 * @param env_var		环境变量的名称
	 */
	UTILS_DLL std::optional<std::string> SearchDLLByEnvVar(const std::string& target_name, const std::string& env_var);

	/**
	 * @brief 根据type_key加载对应的DLL（优先去ICRAFT_CUSTOM_DIR找，其次去当前DLL路径下）
	 * @param type_key	目标类型对应的type_key
	 */
	UTILS_DLL int SearchAndLoadDlls(const std::string& type_key);

	/** 获取当前DLL所处路径 */
	UTILS_DLL std::string GetDLLDir();

	/**
	 * @brief 根据目标名称获取其动态链接库的文件名
	 * @param target_name	目标名称
	 * @return Windows下为 target_name + ".dll";
	 *		   Linux下为 "lib" + target_name + ".so";
	 */
	UTILS_DLL std::string GetDLLFileName(const std::string& target_name);
}
