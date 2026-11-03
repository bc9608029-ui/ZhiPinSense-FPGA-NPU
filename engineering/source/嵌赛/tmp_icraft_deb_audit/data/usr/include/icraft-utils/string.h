#pragma once
#include <vector>
#include <string>

#include "icraft-utils/dllexport.h"


namespace icraft {

	/**
	 * @brief 分割字符串
	 * @param seq	待分割的字符串
	 * @param delim	字符串的分割字符
	 * @return		字符串列表
	 */
	UTILS_DLL std::vector<std::string> split(const std::string& seq, const std::string& delim);

	/**
	 * @brief RLE压缩
	 * @param input		待压缩的列表
	 * @return			压缩后列表
	 */
	template <typename T>
	std::vector<std::pair<int64_t, T>> rleCompress(const std::vector<T>& input) {

		if (input.empty()) {
			return {};
		}

		std::vector<std::pair<int64_t, T>> ans;

		std::string compressed;
		T currentChar = input[0];
		int count = 1;

		for (size_t i = 1; i < input.size(); ++i) {
			if (input[i] == currentChar) {
				++count;
			}
			else {
				ans.push_back({ count, currentChar });
				currentChar = input[i];
				count = 1;
			}
		}

		ans.push_back({ count, currentChar });

		return ans;
	}

	/**
	 * @brief 原地替换子字符串
	 * @param str	原字符串
	 * @param from	替换前的子字符串
	 * @param to	替换后的子字符串
	 */
	UTILS_DLL void replace_substring_in_place(std::string& str, const std::string& from, const std::string& to);


	UTILS_DLL std::string DecoTypeKey(std::string_view type_key);


	UTILS_DLL std::string UnDecoTypeKey(const std::string& type_name);

		/**
	 * @brief 根据形状生成对应的 "***C" 字符串
	 * @param size		总长度
	 * @return			"***C" 字符串
	 */
	UTILS_DLL std::string getC(int size);
}
