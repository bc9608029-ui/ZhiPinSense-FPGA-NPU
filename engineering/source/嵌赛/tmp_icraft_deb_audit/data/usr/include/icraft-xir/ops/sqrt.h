#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Sqrt算子 */
	class SqrtNode : public OpNodeBase<SqrtNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(SqrtNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Sqrt算子引用类 */
	class Sqrt : public OpBase<Sqrt, SqrtNode> {
	public:
		/** 默认构造函数 */
		Sqrt() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Sqrt(Value input);
	};
}
