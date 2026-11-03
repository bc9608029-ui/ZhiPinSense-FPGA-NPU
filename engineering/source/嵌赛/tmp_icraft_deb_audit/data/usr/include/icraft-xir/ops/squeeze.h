#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Squeeze算子 */
	class SqueezeNode : public OpNodeBase<SqueezeNode> {
	public:
		Array<int64_t> axis;	///< 压缩的维度

		ICRAFT_DECLARE_ATTRS(SqueezeNode) {
			ICRAFT_ATTR_FIELD(axis);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Squeeze算子引用类 */
	class Squeeze : public OpBase<Squeeze, SqueezeNode> {
	public:
		/** 默认构造函数 */
		Squeeze() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param axis		压缩的维度
		 */
		XIR_DLL Squeeze(Value input, Array<int64_t> axis);
	};
}
