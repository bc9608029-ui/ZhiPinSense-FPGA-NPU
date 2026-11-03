#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Transpose算子 */
	class TransposeNode : public OpNodeBase<TransposeNode> {
	public:
		Array<int64_t> dims;	///< 期望的排布维度索引
		Layout layout;			///< 期望的排布

		ICRAFT_DECLARE_ATTRS(TransposeNode) {
			ICRAFT_ATTR_FIELD(dims);
			ICRAFT_ATTR_FIELD(layout);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Transpose算子引用类 */
	class Transpose : public OpBase<Transpose, TransposeNode> {
	public:
		/** 默认构造函数 */
		Transpose() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dims		期望的排布维度索引
		 * @param layout	期望的排布
		 */
		XIR_DLL Transpose(Value input, Array<int64_t> dims, Layout layout);

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dims		期望的排布维度索引
		 */
		XIR_DLL Transpose(Value input, Array<int64_t> dims);
	};
}
