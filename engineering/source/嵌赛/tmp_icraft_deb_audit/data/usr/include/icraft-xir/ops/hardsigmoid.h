#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Hardsigmoid算子 */
	class HardsigmoidNode : public OpNodeBase<HardsigmoidNode, IsActivate> {
	public:
		float alpha;		///< Hardsigmoid的系数α，默认为1/6
		float beta;			///< Hardsigmoid的系数β，默认为0.5

		ICRAFT_DECLARE_ATTRS(HardsigmoidNode) {
			ICRAFT_ATTR_FIELD(alpha).set_default(1.f / 6.f);
			ICRAFT_ATTR_FIELD(beta).set_default(0.5f);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Hardsigmoid算子引用类 */
	class Hardsigmoid : public OpBase<Hardsigmoid, HardsigmoidNode> {
	public:
		/** 默认构造函数 */
		Hardsigmoid() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param alpha	Hardsigmoid的系数α，默认为1/6
		 * @param beta	Hardsigmoid的系数β，默认为0.5
		 */
		XIR_DLL Hardsigmoid(Value input, float alpha = 1.f / 6.f, float beta = 0.5f);
	};
}
