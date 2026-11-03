#pragma once
#include <cstdint>
#include <vector>

#include "icraft-utils/dllexport.h"


namespace icraft {

	/**
	 * @brief 判断两个形状是否可以广播
	 * @param left	形状1
	 * @param right	形状2
	 * @return		可以返回true，不可以返回false
	 */
	UTILS_DLL bool isBroadcastable(const std::vector<int64_t> left, std::vector<int64_t> right);

	/**
	 * @brief 计算两个形状广播后的形状
	 * @param left	形状1
	 * @param right	形状2
	 * @return		两个形状广播后的形状
	 * @throw		如果不能广播则抛出异常
	 */
	UTILS_DLL std::vector<int64_t> getBroadcastShape(std::vector<int64_t> left, std::vector<int64_t> right);

	/**
	 * @brief 生成连续自然数序列
	 * @param stop	序列的结束值，但不包括该值
	 * @return		从0开始的连续自然数序列
	 */
	UTILS_DLL std::vector<int64_t> range(int64_t stop);
}
