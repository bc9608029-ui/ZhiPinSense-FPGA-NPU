#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 三维平均池化算子 */
	class AvgPool3dNode : public OpNodeBase<AvgPool3dNode> {
	public:
		int64_t pool_depth;				///< 池化窗口深度
		int64_t pool_width;				///< 池化窗口宽度
		int64_t pool_height;			///< 池化窗口高度
		int64_t stride_depth;			///< 池化滑动深度，默认为1
		int64_t stride_width;			///< 池化滑动宽度，默认为1
		int64_t stride_height;			///< 池化滑动高度，默认为1
		int64_t pad_front;				///< 池化前方Pad，默认为0
		int64_t pad_back;				///< 池化后方Pad，默认为0
		int64_t pad_top;				///< 池化上方Pad，默认为0
		int64_t pad_bottom;				///< 池化下方Pad，默认为0
		int64_t pad_left;				///< 池化左方Pad，默认为0
		int64_t pad_right;				///< 池化右方Pad，默认为0
		bool count_include_pad;			///< 平均时是否包含pad数据，默认不包含
		int64_t divisor_override;		///< 覆盖池化的除数，默认为0表示不覆盖

		ICRAFT_DECLARE_ATTRS(AvgPool3dNode) {
			ICRAFT_ATTR_FIELD(pool_depth).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pool_width).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pool_height).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_depth).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_height).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_front).set_default(0);
			ICRAFT_ATTR_FIELD(pad_back).set_default(0);
			ICRAFT_ATTR_FIELD(pad_top).set_default(0);
			ICRAFT_ATTR_FIELD(pad_bottom).set_default(0);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(count_include_pad).set_default(false);
			ICRAFT_ATTR_FIELD(divisor_override).set_default(0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 三维平均池化算子引用类 */
	class AvgPool3d : public OpBase<AvgPool3d, AvgPool3dNode> {
	public:
		/** 默认构造函数 */
		AvgPool3d() = default;

		/**
		 * @brief 构造函数
		 * @param input				池化的输入
		 * @param pool_depth		池化窗口深度
		 * @param pool_width		池化窗口宽度
		 * @param pool_height		池化窗口高度
		 * @param stride_depth		池化滑动深度
		 * @param stride_width		池化滑动宽度
		 * @param stride_height		池化滑动高度
		 * @param pad_front			池化前方Pad
		 * @param pad_back			池化后方Pad
		 * @param pad_top			池化上方Pad
		 * @param pad_bottom		池化下方Pad
		 * @param pad_left			池化左方Pad
		 * @param pad_right			池化右方Pad
		 * @param count_include_pad	平均时是否包含pads数据，默认为false
		 * @param divisor_override	覆盖池化的除数，默认为0不覆盖
		 */
		XIR_DLL AvgPool3d(
			Value input,
			int64_t pool_depth,
			int64_t pool_width,
			int64_t pool_height,
			int64_t stride_depth,
			int64_t stride_width,
			int64_t stride_height,
			int64_t pad_front,
			int64_t pad_back,
			int64_t pad_top,
			int64_t pad_bottom,
			int64_t pad_left,
			int64_t pad_right,
			bool count_include_pad = false,
			int64_t divisor_override = 0
		);

		/**
		 * @brief 构造函数
		 * @param input					池化的输入
		 * @param pool_size				池化窗口尺寸，深度、高度和宽度相同
		 * @param stride				池化滑动长度，深度、高度和宽度相同
		 * @param pad_front_top_bottom	池化前上下方Pad
		 * @param pad_back_left_right	池化后左右方Pad
		 * @param count_include_pad		平均时是否包含pads数据，默认为false
		 * @param divisor_override		覆盖池化的除数，默认为0不覆盖
		 */
		AvgPool3d(
			Value input,
			int64_t pool_size,
			int64_t stride,
			int64_t pad_front_top_bottom,
			int64_t pad_back_left_right,
			bool count_include_pad = false,
			int64_t divisor_override = 0
		) : AvgPool3d(
			input,
			pool_size, pool_size, pool_size,
			stride, stride, stride,
			pad_front_top_bottom,
			pad_front_top_bottom,
			pad_front_top_bottom,
			pad_back_left_right,
			pad_back_left_right,
			pad_back_left_right,
			count_include_pad,
			divisor_override
		) {}

		/**
		 * @brief 构造函数
		 * @param input				池化的输入
		 * @param pool_size			池化窗口尺寸，深度、高度和宽度相同
		 * @param stride			池化滑动长度，深度、高度和宽度相同
		 * @param pad				池化前后上下左右方Pad
		 * @param count_include_pad	平均时是否包含pads数据，默认为false
		 * @param divisor_override	覆盖池化的除数，默认为0不覆盖
		 */
		AvgPool3d(
			Value input,
			int64_t pool_size,
			int64_t stride,
			int64_t pad,
			bool count_include_pad = false,
			int64_t divisor_override = 0
		) : AvgPool3d(
			input,
			pool_size,
			stride,
			pad, pad,
			count_include_pad,
			divisor_override
		) {}
	};
}
