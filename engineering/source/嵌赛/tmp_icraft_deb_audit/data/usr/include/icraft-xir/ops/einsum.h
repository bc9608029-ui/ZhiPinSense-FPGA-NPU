#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Einsum算子 */
	class EinsumNode : public OpNodeBase<EinsumNode> {
	public:
		std::string equation;		///< 求和标记

		ICRAFT_DECLARE_ATTRS(EinsumNode) {
			ICRAFT_ATTR_FIELD(equation);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Einsum算子引用类 */
	class Einsum : public OpBase<Einsum, EinsumNode> {
	public:
		/** 默认构造函数 */
		Einsum() = default;

		/**
		 * @brief 构造函数
		 * @param inputs	输入
		 * @param equation	求和标记
		 */
		XIR_DLL Einsum(Array<Value> inputs, std::string equation);
	};
}
