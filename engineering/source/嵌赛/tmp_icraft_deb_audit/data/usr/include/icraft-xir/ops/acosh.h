#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ACosh算子 */
	class ACoshNode : public OpNodeBase<ACoshNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(ACoshNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** ACosh算子引用类 */
	class ACosh : public OpBase<ACosh, ACoshNode> {
	public:
		/** 默认构造函数 */
		ACosh() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL ACosh(Value input);
	};
}
