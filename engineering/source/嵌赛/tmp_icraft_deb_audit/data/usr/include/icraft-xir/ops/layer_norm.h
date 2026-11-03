#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** LayerNorm算子 */
	class LayerNormNode : public OpNodeBase<LayerNormNode> {
	public:
		Array<int64_t> axis;		///< 待归一化的维度
		float eps;					///< 防止除以0的小浮点数，默认为1e-5
		Optional<Params> gamma;		///< 仿射计算中的weight
		Optional<Params> beta;		///< 仿射计算中的bias

		ICRAFT_DECLARE_ATTRS(LayerNormNode) {
			ICRAFT_ATTR_FIELD(axis);
			ICRAFT_ATTR_FIELD(eps).set_default(1e-5);
			ICRAFT_ATTR_FIELD(gamma);
			ICRAFT_ATTR_FIELD(beta);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** LayerNorm算子引用类 */
	class LayerNorm : public OpBase<LayerNorm, LayerNormNode> {
	public:
		/** 默认构造函数 */
		LayerNorm() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param axis 待归一化的维度
		 * @param eps 防止除以0的小浮点数，默认为1e-5
		 * @param gamma 仿射计算中的weight
		 * @param beta 仿射计算中的bias
		 */
		XIR_DLL LayerNorm(
			Value input,
			Array<int64_t> axis,
			float eps = 1e-5,
			Optional<Params> gamma = NullOpt,
			Optional<Params> beta = NullOpt
		);
	};


	// 兼容旧接口
	using Layernorm = LayerNorm;
	using LayernormNode = LayerNormNode;
}
