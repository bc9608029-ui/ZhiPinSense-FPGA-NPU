#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Pow算子 */
	class PowNode : public OpNodeBase<PowNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(PowNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Pow算子引用类 */
	class Pow : public OpBase<Pow, PowNode> {
	public:
		/** 默认构造函数 */
		Pow() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param exponent	指数
		 */
		XIR_DLL Pow(Value input, double exponent = 1.0f);

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param exponent	指数
		 */
		XIR_DLL Pow(Value input, Params exponent);
	};
}
