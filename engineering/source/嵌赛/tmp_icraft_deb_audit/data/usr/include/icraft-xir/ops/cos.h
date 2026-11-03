#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Cos算子 */
	class CosNode : public OpNodeBase<CosNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(CosNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Cos算子引用类 */
	class Cos : public OpBase<Cos, CosNode> {
	public:
		/** 默认构造函数 */
		Cos() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Cos(Value input);
	};
}
