#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Normalize算子 */
	class NormalizeNode : public OpNodeBase<NormalizeNode> {
	public:
		Array<int64_t> axis;		///< 待归一化的维度（支持负数索引）
		float p;					///< 范数公式中的指数值，默认为2
		float eps;					///< 防止除以0的小浮点数，默认为1e-12

		ICRAFT_DECLARE_ATTRS(NormalizeNode) {
			ICRAFT_ATTR_FIELD(axis);
			ICRAFT_ATTR_FIELD(p).set_default(2);
			ICRAFT_ATTR_FIELD(eps).set_default(1e-12);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Normalize算子引用类 */
	class Normalize : public OpBase<Normalize, NormalizeNode> {
	public:
		/** 默认构造函数 */
		Normalize() = default;

		/**
		 * @brief 构造函数
		 * @param input	输入
		 * @param axis 待归一化的维度（支持负数索引）
		 * @param p    范数公式中的指数值，默认为2
		 * @param eps  防止除以0的小浮点数，默认为1e-12
		 */
		XIR_DLL Normalize(Value input, Array<int64_t> axis, float p = 2, float eps = 1e-12);
	};
}
