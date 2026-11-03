#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** SimplifiedLayerNormalization算子 */
	class SimplifiedLayerNormNode : public OpNodeBase<SimplifiedLayerNormNode> {
	public:
		float eps;					///< 防止除以0的小浮点数，默认为1e-5
		Optional<Params> gamma;		///< 仿射计算中的weight

		ICRAFT_DECLARE_ATTRS(SimplifiedLayerNormNode) {
			ICRAFT_ATTR_FIELD(eps).set_default(1e-5);
			ICRAFT_ATTR_FIELD(gamma);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** RMSNorm算子引用类 */
	class SimplifiedLayerNorm : public OpBase<SimplifiedLayerNorm, SimplifiedLayerNormNode> {
	public:
		/** 默认构造函数 */
		SimplifiedLayerNorm() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param eps 防止除以0的小浮点数，默认为1e-5
		 * @param gamma 输入
		 */
		XIR_DLL SimplifiedLayerNorm(
			Value input,
			float eps = 1e-5,
			Optional<Params> gamma = NullOpt
		);
	};
}
