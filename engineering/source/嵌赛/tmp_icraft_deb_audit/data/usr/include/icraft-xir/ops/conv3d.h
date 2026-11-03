#pragma once
#include <icraft-xir/core/operation.h>
#include <icraft-xir/ops/conv2d.h>


namespace icraft::xir {

	/** 三维卷积算子 */
	class Conv3dNode : public OpNodeBase<Conv3dNode> {
	public:
		int64_t stride_depth;			///< 卷积滑动深度，默认为1
		int64_t stride_width;			///< 卷积滑动宽度，默认为1
		int64_t stride_height;			///< 卷积滑动高度，默认为1
		int64_t pad_front;				///< 卷积前方Pad，默认为0
		int64_t pad_back;				///< 卷积后方Pad，默认为0
		int64_t pad_top;				///< 卷积上方Pad，默认为0
		int64_t pad_bottom;				///< 卷积下方Pad，默认为0
		int64_t pad_left;				///< 卷积左方Pad，默认为0
		int64_t pad_right;				///< 卷积右方Pad，默认为0
		int64_t dilation_depth;			///< 卷积膨胀深度，默认为1
		int64_t dilation_width;			///< 卷积膨胀宽度，默认为1
		int64_t dilation_height;		///< 卷积膨胀高度，默认为1
		int64_t groups;					///< 卷积分组数量，默认为1
		PaddingMode padding_mode;		///< 卷积的pad模式，默认为ZEROS

		QuantizedScaleArray cut_scale;	///< 表示硬件截位时的系数

		ICRAFT_DECLARE_ATTRS(Conv3dNode) {
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
			ICRAFT_ATTR_FIELD(groups).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(padding_mode).set_default(PaddingMode::ZEROS);
			ICRAFT_ATTR_FIELD(cut_scale);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 卷积算子引用类 */
	class Conv3d : public OpBase<Conv3d, Conv3dNode> {
	public:
		/** 默认构造函数 */
		Conv3d() = default;

		/**
		 * @brief 构造函数
		 * @param input				卷积的输入
		 * @param weights			卷积的权重
		 * @param bias				卷积的偏置
		 * @param stride_depth		卷积滑动深度
		 * @param stride_width		卷积滑动宽度
		 * @param stride_height		卷积滑动高度
		 * @param pad_front			卷积前方Pad
		 * @param pad_back			卷积后方Pad
		 * @param pad_top			卷积上方Pad
		 * @param pad_bottom		卷积下方Pad
		 * @param pad_left			卷积左方Pad
		 * @param pad_right			卷积右方Pad
		 * @param dilation_depth	卷积膨胀深度
		 * @param dilation_width	卷积膨胀宽度
		 * @param dilation_height	卷积膨胀高度
		 * @param groups			卷积分组，默认为1
		 * @param padding_mode		卷积pad模式，默认为ZEROS
		 */
		XIR_DLL Conv3d(
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
			int64_t groups = 1,
			PaddingMode padding_mode = PaddingMode::ZEROS
		);

		/**
		 * @brief 构造函数
		 * @param input				卷积的输入
		 * @param weights			卷积的权重
		 * @param bias				卷积的偏置
		 * @param stride			卷积滑动步长，深度、宽度和高度相同
		 * @param pad				卷积的Pad，前后上下左右相同
		 * @param dilation			卷积膨胀系数，深度、宽度和高度相同
		 * @param groups			卷积分组，默认为1
		 * @param padding_mode		卷积pad模式，默认为ZEROS
		 */
		Conv3d(
			Value input,
			Value weights,
			Optional<Value> bias,
			int64_t stride,
			int64_t pad,
			int64_t dilation,
			int64_t groups = 1,
			PaddingMode padding_mode = PaddingMode::ZEROS
		) : Conv3d(
			input,
			weights,
			bias,
			stride, stride, stride,
			pad, pad, pad, pad, pad, pad,
			dilation, dilation, dilation,
			groups,
			padding_mode
		) {}
	};
}
