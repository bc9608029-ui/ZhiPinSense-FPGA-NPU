#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Less算子 */
	class LessNode : public OpNodeBase<LessNode> {
	public:
		ICRAFT_DECLARE_ATTRS(LessNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Less算子引用类 */
	class Less : public OpBase<Less, LessNode> {
	public:
		/** 默认构造函数 */
		Less() = default;

		/**
		 * @brief 构造函数
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 */
		XIR_DLL Less(Value lhs, Value rhs);
	};
}
