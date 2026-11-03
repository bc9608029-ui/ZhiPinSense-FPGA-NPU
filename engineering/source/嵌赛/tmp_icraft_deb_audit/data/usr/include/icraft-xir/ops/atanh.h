#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ATanh算子 */
	class ATanhNode : public OpNodeBase<ATanhNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(ATanhNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** ATanh算子引用类 */
	class ATanh : public OpBase<ATanh, ATanhNode> {
	public:
		/** 默认构造函数 */
		ATanh() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL ATanh(Value input);
	};
}
