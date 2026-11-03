#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Sinh算子 */
	class SinhNode : public OpNodeBase<SinhNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(SinhNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Sinh算子引用类 */
	class Sinh : public OpBase<Sinh, SinhNode> {
	public:
		/** 默认构造函数 */
		Sinh() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Sinh(Value input);
	};
}
