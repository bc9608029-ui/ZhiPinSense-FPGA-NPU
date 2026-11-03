#pragma once
#ifndef HOSTBKND_UTILS_PCH_GUARD
#define HOSTBKND_UTILS_PCH_GUARD
#include "icraft-backends/hostbackend/backend.h"
#include "icraft-backends/hostbackend/dllexport.h"
#include "icraft-backends/hostbackend/decode_custom.h"
#include "icraft-xrt/core/tensor.h"


namespace icraft::hostbackend::utils {

	/**
	* @brief 将img_path上的图片通过opencv解析为HostDevice上的Xrt Tensor
	* @param img_path 图片路径
	* @param height Tensor的height，默认参数-1下输出原本大小，否则进行resize
	* @param width Tensor的width，默认参数-1下输出原本大小，否则进行resize
	* @return 转自img的xrtTensor
	*/
	HOSTBKND_DLL xrt::Tensor Image2Tensor(const std::string& img_path, int height = -1, int width = -1);

	/**
	* @brief 将图片文件通过opencv解析为HostDevice上的Xrt Tensor
	* @param 图片路径
	* @param value ftmp对应的Xir Value
	* @return 转自图片的xrtTensor
	*/
	HOSTBKND_DLL xrt::Tensor Image2Tensor(const std::string& img_path, const xir::Value& value, bool bgr_order = true);

	/**
	* @brief 将ftmp文件解析为HostDevice上的Xrt Tensor
	* @param ftmp_path ftmp文件路径
	* @param value ftmp对应的Xir Value
	* @return 转自ftmp的xrtTensor
	*/
	HOSTBKND_DLL xrt::Tensor Ftmp2Tensor(const std::string& ftmp_path, const xir::Value& value);

	/**
	* @brief 将数据文件使用用户提供的CustomDecoder模块解析为HostDevice上的Xrt Tensor
	*        使用方法请参考icraft_backends/host/decode_custom.h
	* @param dll_path dll或so路径
	* @param file_path 数据文件路径
	* @param data_type 输出Tensors的TensorTypes
	* @return 转自数据文件的Tensors
	*/
	HOSTBKND_DLL std::vector<xrt::Tensor> DecodeWithDecoder(const std::string& dll_path, const std::string& file_path, const std::vector<xir::TensorType>& data_type);
	
	/**
	* @brief 将input从input_type cast为output_type，cast内容包括layout和element data type
	* @param input 需要cast的tensor
	* @param input_dtype 输入Tensor的dtype
	* @param output_dtype 输出Tensor的dtype
	* @return cast之后的xrt tensor
	*/
	HOSTBKND_DLL xrt::Tensor Cast(const xrt::Tensor& input, const xrt::TensorType& input_type, const xrt::TensorType& output_type, xrt::HostBackend& backend);
}

#endif //HOSTBKND_UTILS_PCH_GUARD
