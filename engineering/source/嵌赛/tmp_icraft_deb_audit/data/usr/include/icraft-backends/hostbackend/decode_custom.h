#pragma once
#ifndef HOSTBKND_DECODE_CUSTOM_PCH_GUARD
#define HOSTBKND_DECODE_CUSTOM_PCH_GUARD
#ifdef _WIN32
#define CUSTOM_API _declspec(dllexport)
#else
#define CUSTOM_API __attribute__ ((used))
#endif

#include "icraft-xrt/core/tensor.h"

using namespace icraft;

/**
 * @brief CustomDecoder使用方法:
 *		  CustomDecoder提供接口帮助用户实现数据文件到xrt::Tensor的自定义转换功能。
 *        构造方法:
 *        用户需要在dll(或so)中继承CustomDecoder虚类实现自定义decode方法，再使用REGISTER_CUSTOM_DECODER导出。
 *        使用方法:
 *        通过icraft::hostbackend::utils::DecodeWithDecoder调用自定义decode函数。
 */
class CustomDecoder {
public:
	virtual std::vector<xrt::Tensor> decode(const std::string& file_path, const std::vector<xrt::TensorType>& data_type) = 0;
};

extern "C" CUSTOM_API CustomDecoder * GetCustomDecoder();

#ifdef _WIN32
	#define REGISTER_CUSTOM_DECODER(CLASS_NAME)		\
	extern "C" __declspec(dllexport) CustomDecoder* GetCustomDecoder(){ return new CLASS_NAME();}
#else
	#define REGISTER_CUSTOM_DECODER(CLASS_NAME)		\
	extern "C" CustomDecoder* GetCustomDecoder(){ return new CLASS_NAME();}
#endif

#endif //HOSTBKND_DECODE_CUSTOM_PCH_GUARD