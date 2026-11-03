#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Hardswish算子 */
	class HardswishNode : public OpNodeBase<HardswishNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(HardswishNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Hardswish算子引用类 */
	class Hardswish : public OpBase<Hardswish, HardswishNode> {
	public:
		/** 默认构造函数 */
		Hardswish() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Hardswish(Value input);
	};
}
