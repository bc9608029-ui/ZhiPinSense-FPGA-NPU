#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Cosh算子 */
	class CoshNode : public OpNodeBase<CoshNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(CoshNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Cosh算子引用类 */
	class Cosh : public OpBase<Cosh, CoshNode> {
	public:
		/** 默认构造函数 */
		Cosh() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Cosh(Value input);
	};
}
