#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Sigmoid算子 */
	class SigmoidNode : public OpNodeBase<SigmoidNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(SigmoidNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Sigmoid算子引用类 */
	class Sigmoid : public OpBase<Sigmoid, SigmoidNode> {
	public:
		/** 默认构造函数 */
		Sigmoid() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Sigmoid(Value input);
	};
}
