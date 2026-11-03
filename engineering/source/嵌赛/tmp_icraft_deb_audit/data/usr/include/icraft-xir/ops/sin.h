#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Sin算子 */
	class SinNode : public OpNodeBase<SinNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(SinNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Sin算子引用类 */
	class Sin : public OpBase<Sin, SinNode> {
	public:
		/** 默认构造函数 */
		Sin() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Sin(Value input);
	};
}
