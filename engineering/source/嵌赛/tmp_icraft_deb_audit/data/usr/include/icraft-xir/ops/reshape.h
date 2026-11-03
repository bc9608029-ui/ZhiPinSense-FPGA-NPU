#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Reshape算子 */
	class ReshapeNode : public OpNodeBase<ReshapeNode> {
	public:
		Array<int64_t> shape;	///< 目标形状
		Layout layout;			///< 目标排布

		ICRAFT_DECLARE_ATTRS(ReshapeNode) {
			ICRAFT_ATTR_FIELD(shape);
			ICRAFT_ATTR_FIELD(layout);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Reshape算子引用类 */
	class Reshape : public OpBase<Reshape, ReshapeNode> {
	public:
		/** 默认构造函数 */
		Reshape() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param shape		目标形状
		 * @param layout	目标排布
		 */
		XIR_DLL Reshape(Value input, Array<int64_t> shape, Layout layout);
	};
}
