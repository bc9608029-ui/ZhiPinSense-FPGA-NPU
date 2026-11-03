#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** LessEqual算子 */
	class LessEqualNode : public OpNodeBase<LessEqualNode> {
	public:
		ICRAFT_DECLARE_ATTRS(LessEqualNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** LessEqual算子引用类 */
	class LessEqual : public OpBase<LessEqual, LessEqualNode> {
	public:
		/** 默认构造函数 */
		LessEqual() = default;

		/**
		 * @brief 构造函数
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 */
		XIR_DLL LessEqual(Value lhs, Value rhs);
	};
}
