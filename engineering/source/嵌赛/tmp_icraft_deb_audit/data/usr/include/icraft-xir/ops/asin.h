#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ASin算子 */
	class ASinNode : public OpNodeBase<ASinNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(ASinNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** ASin算子引用类 */
	class ASin : public OpBase<ASin, ASinNode> {
	public:
		/** 默认构造函数 */
		ASin() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL ASin(Value input);
	};
}
