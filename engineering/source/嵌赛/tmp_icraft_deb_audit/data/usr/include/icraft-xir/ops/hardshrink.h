#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Hardshrink算子 */
	class HardshrinkNode : public OpNodeBase<HardshrinkNode, IsActivate> {
	public:
		float lambda;	///< 系数λ，默认为0.5

		ICRAFT_DECLARE_ATTRS(HardshrinkNode) {
			ICRAFT_ATTR_FIELD(lambda).set_default(0.5).set_lower_bound(0.0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Hardshrink算子引用类 */
	class Hardshrink : public OpBase<Hardshrink, HardshrinkNode> {
	public:
		/** 默认构造函数 */
		Hardshrink() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param lambda  系数λ，默认为0.5
		 */
		XIR_DLL Hardshrink(Value input, float lambda = 0.5);
	};
}
