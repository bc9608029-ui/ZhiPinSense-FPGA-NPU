#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Tanhshrink算子 */
	class TanhshrinkNode : public OpNodeBase<TanhshrinkNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(TanhshrinkNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Tanhshrink算子引用类 */
	class Tanhshrink : public OpBase<Tanhshrink, TanhshrinkNode> {
	public:
		/** 默认构造函数 */
		Tanhshrink() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Tanhshrink(Value input);
	};
}
