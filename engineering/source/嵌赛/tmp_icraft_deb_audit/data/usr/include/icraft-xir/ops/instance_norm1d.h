#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 一维InstanceNorm算子 */
	class InstanceNorm1dNode : public OpNodeBase<InstanceNorm1dNode> {
	public:
		float eps;					///< 防止除以0的小浮点数，默认为1e-5
		Optional<Params> gamma;		///< 仿射计算中的weight
		Optional<Params> beta;		///< 仿射计算中的bias

		ICRAFT_DECLARE_ATTRS(InstanceNorm1dNode) {
			ICRAFT_ATTR_FIELD(eps).set_default(1e-5);
			ICRAFT_ATTR_FIELD(gamma);
			ICRAFT_ATTR_FIELD(beta);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 一维InstanceNorm算子引用类 */
	class InstanceNorm1d : public OpBase<InstanceNorm1d, InstanceNorm1dNode> {
	public:
		/** 默认构造函数 */
		InstanceNorm1d() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param eps 防止除以0的小浮点数，默认为1e-5
		 * @param gamma 输入
		 * @param beta 输入
		 */
		XIR_DLL InstanceNorm1d(
			Value input,
			float eps = 1e-5,
			Optional<Params> gamma = NullOpt,
			Optional<Params> beta = NullOpt
		);
	};
}
