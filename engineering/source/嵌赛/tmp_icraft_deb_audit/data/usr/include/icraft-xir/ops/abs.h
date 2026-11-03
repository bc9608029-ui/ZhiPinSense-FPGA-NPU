#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Abs算子 */
	class AbsNode : public OpNodeBase<AbsNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(AbsNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Abs算子引用类 */
	class Abs : public OpBase<Abs, AbsNode> {
	public:
		/** 默认构造函数 */
		Abs() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Abs(Value input);
	};
}
