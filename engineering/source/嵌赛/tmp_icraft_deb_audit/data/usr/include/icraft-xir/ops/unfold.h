#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Unfold算子 */
	class UnfoldNode : public OpNodeBase<UnfoldNode> {
	public:
		int64_t kernel_width;			///< 滑块宽度，默认为1
		int64_t kernel_height;			///< 滑块高度，默认为1
		int64_t stride_width;			///< 滑动宽度，默认为1
		int64_t stride_height;			///< 滑动高度，默认为1
		int64_t pad_top;				///< 上方Pad，默认为0
		int64_t pad_bottom;				///< 下方Pad，默认为0
		int64_t pad_left;				///< 左方Pad，默认为0
		int64_t pad_right;				///< 右方Pad，默认为0
		int64_t dilation_width;			///< 膨胀宽度，默认为1
		int64_t dilation_height;		///< 膨胀高度，默认为1

		ICRAFT_DECLARE_ATTRS(UnfoldNode) {
			ICRAFT_ATTR_FIELD(kernel_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(kernel_height).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_height).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_top).set_default(0);
			ICRAFT_ATTR_FIELD(pad_bottom).set_default(0);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(dilation_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(dilation_height).set_default(1).set_lower_bound(1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Unfold算子引用类 */
	class Unfold : public OpBase<Unfold, UnfoldNode> {
	public:
		/** 默认构造函数 */
		Unfold() = default;

		/**
		 * @brief 构造函数
		 * @param input				输入
		 * @param kernel_width		滑块宽度
		 * @param kernel_height		滑块高度
		 * @param stride_width		滑动宽度
		 * @param stride_height		滑动高度
		 * @param pad_top			上方Pad
		 * @param pad_bottom		下方Pad
		 * @param pad_left			左方Pad
		 * @param pad_right			右方Pad
		 * @param dilation_width	膨胀宽度
		 * @param dilation_height	膨胀高度
		 */
		XIR_DLL Unfold(
			Value input,
			int64_t kernel_width,
			int64_t kernel_height,
			int64_t stride_width,
			int64_t stride_height,
			int64_t pad_top,
			int64_t pad_bottom,
			int64_t pad_left,
			int64_t pad_right,
			int64_t dilation_width,
			int64_t dilation_height
		);

		/**
		 * @brief 构造函数
		 * @param input				输入
		 * @param kernel			滑块大小，宽度和高度相同
		 * @param stride			滑动步长，宽度和高度相同
		 * @param pad				Pad，上下左右相同
		 * @param dilation			膨胀系数，宽度和高度相同
		 */
		Unfold(
			Value input,
			int64_t kernel,
			int64_t stride,
			int64_t pad,
			int64_t dilation
		) : Unfold(
			input,
			kernel, kernel,
			stride, stride,
			pad, pad, pad, pad,
			dilation, dilation
		) {}
	};
}
