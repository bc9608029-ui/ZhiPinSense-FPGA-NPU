#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ATan算子 */
	class ATanNode : public OpNodeBase<ATanNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(ATanNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** ATan算子引用类 */
	class ATan : public OpBase<ATan, ATanNode> {
	public:
		/** 默认构造函数 */
		ATan() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL ATan(Value input);
	};
}
