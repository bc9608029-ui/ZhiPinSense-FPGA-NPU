#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Softplus算子 */
	class SoftplusNode : public OpNodeBase<SoftplusNode, IsActivate> {
	public:
		float beta;		///< 系数β，默认为1.0
		float threshold;	///< 阈值，默认为20.0

		ICRAFT_DECLARE_ATTRS(SoftplusNode) {
			ICRAFT_ATTR_FIELD(beta).set_default(1.0);
			ICRAFT_ATTR_FIELD(threshold).set_default(20.0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Softplus算子引用类 */
	class Softplus : public OpBase<Softplus, SoftplusNode> {
	public:
		/** 默认构造函数 */
		Softplus() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param beta		 系数β，默认为1.0
		 * @param threshold  阈值，默认为20.0
		 */
		XIR_DLL Softplus(Value input, float beta = 1.0, float threshold = 20.0);
	};
}
