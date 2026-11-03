#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 三维反卷积算子 */
	class ConvTranspose3dNode : public OpNodeBase<ConvTranspose3dNode> {
	public:
		int64_t stride_depth;			///< 反卷积滑动深度，默认为1
		int64_t stride_width;			///< 反卷积滑动宽度，默认为1
		int64_t stride_height;			///< 反卷积滑动高度，默认为1
		int64_t pad_front;				///< 反卷积前方Pad，默认为0
		int64_t pad_back;				///< 反卷积后方Pad，默认为0
		int64_t pad_top;				///< 反卷积上方Pad，默认为0
		int64_t pad_bottom;				///< 反卷积下方Pad，默认为0
		int64_t pad_left;				///< 反卷积左方Pad，默认为0
		int64_t pad_right;				///< 反卷积右方Pad，默认为0
		int64_t dilation_depth;			///< 反卷积膨胀深度，默认为1
		int64_t dilation_width;			///< 反卷积膨胀宽度，默认为1
		int64_t dilation_height;		///< 反卷积膨胀高度，默认为1
		int64_t output_pad_depth;		///< 反卷积深度上输出Pad，默认为0
		int64_t output_pad_width;		///< 反卷积宽度上输出Pad，默认为0
		int64_t output_pad_height;		///< 反卷积高度上输出Pad，默认为0
		int64_t groups;					///< 反卷积分组数量，默认为1

		ICRAFT_DECLARE_ATTRS(ConvTranspose3dNode) {
			ICRAFT_ATTR_FIELD(stride_depth).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_height).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_front).set_default(0);
			ICRAFT_ATTR_FIELD(pad_back).set_default(0);
			ICRAFT_ATTR_FIELD(pad_top).set_default(0);
			ICRAFT_ATTR_FIELD(pad_bottom).set_default(0);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(dilation_depth).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(dilation_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(dilation_height).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(output_pad_depth).set_default(0);
			ICRAFT_ATTR_FIELD(output_pad_width).set_default(0);
			ICRAFT_ATTR_FIELD(output_pad_height).set_default(0);
			ICRAFT_ATTR_FIELD(groups).set_default(1).set_lower_bound(1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 三维反卷积算子引用类 */
	class ConvTranspose3d : public OpBase<ConvTranspose3d, ConvTranspose3dNode> {
	public:
		/** 默认构造函数 */
		ConvTranspose3d() = default;

		/**
		 * @brief 构造函数.
		 * @param input					反卷积的输入
		 * @param weights				反卷积的权重
		 * @param bias					反卷积的偏置
		 * @param stride_depth			反卷积滑动深度
		 * @param stride_width			反卷积滑动宽度
		 * @param stride_height			反卷积滑动高度
		 * @param pad_front				反卷积前方Pad
		 * @param pad_back				反卷积后方Pad
		 * @param pad_top				反卷积上方Pad
		 * @param pad_bottom			反卷积下方Pad
		 * @param pad_left				反卷积左方Pad
		 * @param pad_right				反卷积右方Pad
		 * @param dilation_depth		反卷积膨胀深度
		 * @param dilation_width		反卷积膨胀宽度
		 * @param dilation_height		反卷积膨胀高度
		 * @param output_pad_depth		反卷积深度上输出Pad
		 * @param output_pad_width		反卷积宽度上输出Pad
		 * @param output_pad_height		反卷积高度上输出Pad
		 * @param groups				反卷积分组，默认为1
		 */
		XIR_DLL ConvTranspose3d(
			Value input,
			Value weights,
			Optional<Value> bias,
			int64_t stride_depth,
			int64_t stride_width,
			int64_t stride_height,
			int64_t pad_front,
			int64_t pad_back,
			int64_t pad_top,
			int64_t pad_bottom,
			int64_t pad_left,
			int64_t pad_right,
			int64_t dilation_depth,
			int64_t dilation_width,
			int64_t dilation_height,
			int64_t output_pad_depth,
			int64_t output_pad_width,
			int64_t output_pad_height,
			int64_t groups = 1
		);

		/**
		 * @brief 构造函数.
		 * @param input				反卷积的输入
		 * @param weights			反卷积的权重
		 * @param bias				反卷积的偏置
		 * @param stride			反卷积滑动步长，深度、宽度和高度相同
		 * @param pad				反卷积的Pad，前后上下左右相同
		 * @param dilation			反卷积膨胀系数，深度、宽度和高度相同
		 * @param output_pad		反卷积输出PAD，深度、宽度和高度相同
		 * @param groups			反卷积分组，默认为1
		 */
		ConvTranspose3d(
			Value input,
			Value weights,
			Optional<Value> bias,
			int64_t stride,
			int64_t pad,
			int64_t dilation,
			int64_t output_pad,
			int64_t groups = 1
		) : ConvTranspose3d(
			input,
			weights,
			bias,
			stride, stride, stride,
			pad, pad, pad, pad, pad, pad,
			dilation, dilation, dilation,
			output_pad, output_pad, output_pad,
			groups
		) {}
	};


	// 兼容旧接口
	using Conv3dTranspose = ConvTranspose3d;
	using Conv3dTransposeNode = ConvTranspose3dNode;
}
