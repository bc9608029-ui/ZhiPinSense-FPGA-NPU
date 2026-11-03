#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Greater算子 */
	class GreaterNode : public OpNodeBase<GreaterNode> {
	public:
		ICRAFT_DECLARE_ATTRS(GreaterNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Greater算子引用类 */
	class Greater : public OpBase<Greater, GreaterNode> {
	public:
		/** 默认构造函数 */
		Greater() = default;

		/**
		 * @brief 构造函数
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 */
		XIR_DLL Greater(Value lhs, Value rhs);
	};
}
