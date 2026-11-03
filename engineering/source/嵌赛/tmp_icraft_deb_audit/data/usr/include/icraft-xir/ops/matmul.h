#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Matmul算子 */
	class MatmulNode : public OpNodeBase<MatmulNode> {
	public:
		QuantizedScaleArray cut_scale;	///< 表示硬件截位时的系数

		ICRAFT_DECLARE_ATTRS(MatmulNode) {
			ICRAFT_ATTR_FIELD(cut_scale);
		};

		XIR_DLL virtual void validate() const override;
	};


	/** Matmul算子引用类 */
	class Matmul : public OpBase<Matmul, MatmulNode> {
	public:
		/** 默认构造函数 */
		Matmul() = default;

		/**
		 * @brief 构造函数，y = x * k + b
		 * @param x 因数之一
		 * @param k 因数之二
		 * @param b 偏置，可选
		 */
		XIR_DLL Matmul(Value x, Value k, Optional<Value> b);
	};
}
