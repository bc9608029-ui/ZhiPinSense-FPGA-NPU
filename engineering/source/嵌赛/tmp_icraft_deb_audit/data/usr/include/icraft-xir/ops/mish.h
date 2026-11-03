#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Mish算子 */
	class MishNode : public OpNodeBase<MishNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(MishNode) {}


		XIR_DLL virtual void validate() const override;
	};


	/** Mish算子引用类 */
	class Mish : public OpBase<Mish, MishNode> {
	public:
		/** 默认构造函数 */
		Mish() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Mish(Value input);
	};
}
