#include <string>
#include <string_view>
#include <vector>
#include "icraft-utils/midware/path.hpp"
#include "icraft-utils/midware/filestream.hpp"
#include "icraft-utils/dllexport.h"


namespace icraft {

	/**
	 * @brief 安全加载文件
	 * @param filename	文件名
	 * @param mode		加载模式
	 * @return			文件流
	 * @throw			如果文件不存在或无法正常打开则抛出异常
	 */
	UTILS_DLL icraft::midware::ifstream safeLoadFile(std::string_view filename,
		std::ios_base::openmode mode = std::ios_base::in);

	UTILS_DLL icraft::midware::ifstream safeLoadFile(const std::string& filename,
		std::ios_base::openmode mode = std::ios_base::in);

	UTILS_DLL icraft::midware::ifstream safeLoadFile(const char* filename,
		std::ios_base::openmode mode = std::ios_base::in);

	UTILS_DLL icraft::midware::ifstream safeLoadFile(const icraft::midware::path& filename, 
		std::ios_base::openmode mode = std::ios_base::in);

	/**
 * @brief 安全创建文件夹
 * @param dirname	文件夹路径
 * @throw			如果文件夹路径是一个已存在的文件则抛出异常
 */
	UTILS_DLL void safeCreateDirectory(const icraft::midware::path& dirname);

	/**
	 * @brief 获取文件后缀名
	 * @param file_name 文件名
	 * @return 文件后缀名
	 */
	UTILS_DLL std::string getSuffix(const std::string& file_name);

	/**
	 * @brief 判断文件是否为图片
	 * @param file_name 文件名
	 * @return 如果是图片则返回true，否则返回false
	 */
	UTILS_DLL bool isPicture(const std::string& file_name);

	/**
	 * @brief 判断文件是否为FTMP
	 * @param file_name 文件名
	 * @return 如果是FTMP则返回true，否则返回false
	 */
	UTILS_DLL bool isFtmp(const std::string& file_name);

	/**
	 * @brief 从输入字符串中获取所有符合条件的文件名
	 * @param input_str 输入字符串
	 * @return			如果输入字符串是txt文件，则将txt中内容视为输入字符串
						将输入字符串按行或分号切割，获取所有符合条件的文件名
	 */
	UTILS_DLL std::vector<std::string> getFiles(std::string input_str);
}
