#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Minimum算子 */
	class MinimumNode : public OpNodeBase<MinimumNode> {
	public:
		ICRAFT_DECLARE_ATTRS(MinimumNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Minimum算子引用类 */
	class Minimum : public OpBase<Minimum, MinimumNode> {
	public:
		/** 默认构造函数 */
		Minimum() = default;

		/**
		 * @brief 构造函数
		 * @param lhs			左操作数
		 * @param rhs			右操作数
		 */
		XIR_DLL Minimum(Value lhs, Value rhs);
	};
}
