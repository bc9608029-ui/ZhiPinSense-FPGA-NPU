#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 一维最大池化算子 */
	class MaxPool1dNode : public OpNodeBase<MaxPool1dNode> {
	public:
		int64_t pool_width;				///< 池化窗口宽度
		int64_t stride_width;			///< 池化滑动宽度，默认为1
		int64_t pad_left;				///< 池化左方Pad，默认为0
		int64_t pad_right;				///< 池化右方Pad，默认为0
		int64_t dilation_width;			///< 池化膨胀宽度，默认为1

		ICRAFT_DECLARE_ATTRS(MaxPool1dNode) {
			ICRAFT_ATTR_FIELD(pool_width).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(dilation_width).set_default(1).set_lower_bound(1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 一维最大池化算子引用类 */
	class MaxPool1d : public OpBase<MaxPool1d, MaxPool1dNode> {
	public:
		/** 默认构造函数 */
		MaxPool1d() = default;

		/**
		 * @brief 构造函数
		 * @param input				池化的输入
		 * @param pool_width		池化窗口宽度
		 * @param stride_width		池化滑动宽度
		 * @param pad_left			池化左方Pad
		 * @param pad_right			池化右方Pad
		 * @param dilation_width	池化膨胀宽度
		 */
		XIR_DLL MaxPool1d(
			Value input,
			int64_t pool_width,
			int64_t stride_width,
			int64_t pad_left,
			int64_t pad_right,
			int64_t dilation_width
		);
	};
}
