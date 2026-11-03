#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Softsign算子 */
	class SoftsignNode : public OpNodeBase<SoftsignNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(SoftsignNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Softsign算子引用类 */
	class Softsign : public OpBase<Softsign, SoftsignNode> {
	public:
		/** 默认构造函数 */
		Softsign() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Softsign(Value input);
	};
}
