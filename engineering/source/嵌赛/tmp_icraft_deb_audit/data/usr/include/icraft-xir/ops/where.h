#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Where算子 */
	class WhereNode : public OpNodeBase<WhereNode> {
	public:
		ICRAFT_DECLARE_ATTRS(WhereNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Where算子引用类 */
	class Where : public OpBase<Where, WhereNode> {
	public:
		/** 默认构造函数 */
		Where() = default;

		/**
		 * @brief 构造函数
		 * @param lhs			左操作数
		 * @param rhs			右操作数
		 * @param condition		判断条件
		 */
		XIR_DLL Where(Value lhs, Value rhs, Value condition);
	};
}
