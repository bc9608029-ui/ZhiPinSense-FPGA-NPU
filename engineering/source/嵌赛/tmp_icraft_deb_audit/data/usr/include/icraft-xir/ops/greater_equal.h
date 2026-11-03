#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** GreaterEqual算子 */
	class GreaterEqualNode : public OpNodeBase<GreaterEqualNode> {
	public:
		ICRAFT_DECLARE_ATTRS(GreaterEqualNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** GreaterEqual算子引用类 */
	class GreaterEqual : public OpBase<GreaterEqual, GreaterEqualNode> {
	public:
		/** 默认构造函数 */
		GreaterEqual() = default;

		/**
		 * @brief 构造函数
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 */
		XIR_DLL GreaterEqual(Value lhs, Value rhs);
	};
}
