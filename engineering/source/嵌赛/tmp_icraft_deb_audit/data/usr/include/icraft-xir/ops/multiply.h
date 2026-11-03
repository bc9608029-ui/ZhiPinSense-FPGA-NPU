#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Multiply算子 */
	class MultiplyNode : public OpNodeBase<MultiplyNode> {
	public:
		QuantizedScaleArray cut_scale;	///< 表示硬件截位时的系数

		ICRAFT_DECLARE_ATTRS(MultiplyNode) {
			ICRAFT_ATTR_FIELD(cut_scale);
		};

		XIR_DLL virtual void validate() const override;
	};


	/** Multiply算子引用类 */
	class Multiply : public OpBase<Multiply, MultiplyNode> {
	public:
		/** 默认构造函数 */
		Multiply() = default;

		/**
		 * @brief 构造函数
		 * @param lhs 左操作数
		 * @param rhs 右操作数
		 */
		XIR_DLL Multiply(Value lhs, Value rhs);
	};
}
