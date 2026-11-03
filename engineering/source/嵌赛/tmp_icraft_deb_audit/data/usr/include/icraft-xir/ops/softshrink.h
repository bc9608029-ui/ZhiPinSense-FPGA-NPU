#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Softshrink算子 */
	class SoftshrinkNode : public OpNodeBase<SoftshrinkNode, IsActivate> {
	public:
		float lambda;	///< 系数λ，默认为0.5

		ICRAFT_DECLARE_ATTRS(SoftshrinkNode) {
			ICRAFT_ATTR_FIELD(lambda).set_default(0.5).set_lower_bound(0.0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Softshrink算子引用类 */
	class Softshrink : public OpBase<Softshrink, SoftshrinkNode> {
	public:
		/** 默认构造函数 */
		Softshrink() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param lambda  系数λ，默认为0.5
		 */
		XIR_DLL Softshrink(Value input, float lambda = 0.5);
	};
}
