#pragma once
#include <cstdint>
#include "icraft-utils/dllexport.h"


namespace icraft {

	/**
	* @brief 任意自定义的16bit的emxx格式数据 转换成 float32数据;
	*        其中emxx的要求是sign(1bit) + e(指数位bit) + m(尾数位bit数) == 16
	*        bf16、fp16、em78、em69等等都可以用该通用的函数;
	*        该函数为后补充(for fp16、em69等等)，所以一些如bf16ToFp32也进行了保留;
	* @param em_bits: 输入的emxx数据
	* @param e_bits: 输入的em格式数据的指数位bit数，比如fp16，则是5
	* @param m_bits: 输入的em格式数据的尾数位bit数，比如fp16，则是10
	* @return 返回转换后的float数据
	*/
	UTILS_DLL float emxxToFp32(uint16_t em_bits, uint32_t e_bits, uint32_t m_bits);

	/**
	* @brief float32数据转成任意自定义的16bit的emxx格式数据;
	*        其中emxx的要求是sign(1bit) + e(指数位bit) + m(尾数位bit数) == 16
	*        bf16、fp16、em78、em69等等都可以用该通用的函数;
	*        该函数为后补充(for fp16、em69等等)，所以上述的fp32ToBf16等等也依旧进行了保留;
	* @param value: 输入的float数据
	* @param e_bits: 转换的em格式数据的指数位bit数，比如fp16，则是5
	* @param m_bits: 转换的em格式数据的尾数位bit数，比如fp16，则是10
	*/
	UTILS_DLL uint16_t fp32ToEmxx(float value, uint32_t e_bits, uint32_t m_bits);
}
