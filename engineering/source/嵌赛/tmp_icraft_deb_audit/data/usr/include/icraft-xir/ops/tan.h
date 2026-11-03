#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Tan算子 */
	class TanNode : public OpNodeBase<TanNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(TanNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Tan算子引用类 */
	class Tan : public OpBase<Tan, TanNode> {
	public:
		/** 默认构造函数 */
		Tan() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Tan(Value input);
	};
}
