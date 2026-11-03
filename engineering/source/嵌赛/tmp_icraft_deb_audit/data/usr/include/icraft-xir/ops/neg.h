#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Neg算子 */
	class NegNode : public OpNodeBase<NegNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(NegNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Neg算子引用类 */
	class Neg : public OpBase<Neg, NegNode> {
	public:
		/** 默认构造函数 */
		Neg() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Neg(Value input);
	};
}
