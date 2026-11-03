#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Sum算子 */
	class SumNode : public OpNodeBase<SumNode> {
	public:
		Array<int64_t> dim;			///< 进行求和的维度（支持负数索引）
		bool keepdim;				///< 是否保持维度不变

		ICRAFT_DECLARE_ATTRS(SumNode) {
			ICRAFT_ATTR_FIELD(dim);
			ICRAFT_ATTR_FIELD(keepdim).set_default(false);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Sum算子引用类 */
	class Sum : public OpBase<Sum, SumNode> {
	public:
		/** 默认构造函数 */
		Sum() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 */
		XIR_DLL Sum(Value input);

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dim		进行求和的维度
		 * @param keepdim	是否保持维度不变
		 */
		XIR_DLL Sum(Value input, int64_t dim, bool keepdim = false);

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dim		进行求和的维度列表
		 * @param keepdim	是否保持维度不变
		 */
		XIR_DLL Sum(Value input, Array<int64_t> dim, bool keepdim = false);
	};
}
