#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Maximum算子 */
	class MaximumNode : public OpNodeBase<MaximumNode> {
	public:
		ICRAFT_DECLARE_ATTRS(MaximumNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Maximum算子引用类 */
	class Maximum : public OpBase<Maximum, MaximumNode> {
	public:
		/** 默认构造函数 */
		Maximum() = default;

		/**
		 * @brief 构造函数
		 * @param lhs			左操作数
		 * @param rhs			右操作数
		 */
		XIR_DLL Maximum(Value lhs, Value rhs);
	};
}
