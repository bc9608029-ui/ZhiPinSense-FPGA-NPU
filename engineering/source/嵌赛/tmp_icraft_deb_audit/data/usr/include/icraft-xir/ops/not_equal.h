#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** NotEqual算子 */
	class NotEqualNode : public OpNodeBase<NotEqualNode> {
	public:
		ICRAFT_DECLARE_ATTRS(NotEqualNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** NotEqual算子引用类 */
	class NotEqual : public OpBase<NotEqual, NotEqualNode> {
	public:
		/** 默认构造函数 */
		NotEqual() = default;

		/**
		 * @brief 构造函数
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 */
		XIR_DLL NotEqual(Value lhs, Value rhs);
	};
}
