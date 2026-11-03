#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Tanh算子 */
	class TanhNode : public OpNodeBase<TanhNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(TanhNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Tanh算子引用类 */
	class Tanh : public OpBase<Tanh, TanhNode> {
	public:
		/** 默认构造函数 */
		Tanh() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Tanh(Value input);
	};
}
