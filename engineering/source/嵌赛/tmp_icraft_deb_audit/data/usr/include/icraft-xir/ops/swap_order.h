#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** SwapOrder算子 */
	class SwapOrderNode : public OpNodeBase<SwapOrderNode> {
	public:
		Array<int64_t> order;		///< 期望的排布顺序
		int64_t axis;				///< 期望交换顺序的维度（支持负数索引）

		ICRAFT_DECLARE_ATTRS(SwapOrderNode) {
			ICRAFT_ATTR_FIELD(order);
			ICRAFT_ATTR_FIELD(axis).set_default(-1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** SwapOrder算子引用类 */
	class SwapOrder : public OpBase<SwapOrder, SwapOrderNode> {
	public:
		/** 默认构造函数 */
		SwapOrder() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param order		期望的排布顺序
		 * @param axis		期望交换顺序的维度（支持负数索引）
		 */
		XIR_DLL SwapOrder(Value input, Array<int64_t> order, int64_t axis = -1);
	};
}
