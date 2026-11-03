#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ACos算子 */
	class ACosNode : public OpNodeBase<ACosNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(ACosNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** ACos算子引用类 */
	class ACos : public OpBase<ACos, ACosNode> {
	public:
		/** 默认构造函数 */
		ACos() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL ACos(Value input);
	};
}
