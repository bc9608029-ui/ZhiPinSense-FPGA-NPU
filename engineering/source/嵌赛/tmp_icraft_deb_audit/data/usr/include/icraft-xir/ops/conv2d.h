#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/**
	* @enum		PaddingMode
	* @brief	表示pad的模式
	*/
	// enum class PaddingMode {
	// 	ZEROS,		///< 填充0
	// 	REFLECT,	///< 反射
	// 	REPLICATE,	///< 重复
	// 	CIRCULAR	///< 环形
	// };
	WISE_ENUM_CLASS(PaddingMode, ZEROS, REFLECT, REPLICATE, CIRCULAR);


	/** 二维卷积算子 */
	class Conv2dNode : public OpNodeBase<Conv2dNode> {
	public:
		int64_t stride_width;			///< 卷积滑动宽度，默认为1
		int64_t stride_height;			///< 卷积滑动高度，默认为1
		int64_t pad_top;				///< 卷积上方Pad，默认为0
		int64_t pad_bottom;				///< 卷积下方Pad，默认为0
		int64_t pad_left;				///< 卷积左方Pad，默认为0
		int64_t pad_right;				///< 卷积右方Pad，默认为0
		int64_t dilation_width;			///< 卷积膨胀宽度，默认为1
		int64_t dilation_height;		///< 卷积膨胀高度，默认为1
		int64_t groups;					///< 卷积分组数量，默认为1
		PaddingMode padding_mode;		///< 卷积的pad模式，默认为ZEROS

		QuantizedScaleArray cut_scale;	///< 表示硬件截位时的系数

		ICRAFT_DECLARE_ATTRS(Conv2dNode) {
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_height).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_top).set_default(0);
			ICRAFT_ATTR_FIELD(pad_bottom).set_default(0);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(dilation_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(dilation_height).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(groups).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(padding_mode).set_default(PaddingMode::ZEROS);
			ICRAFT_ATTR_FIELD(cut_scale);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 卷积算子引用类 */
	class Conv2d : public OpBase<Conv2d, Conv2dNode> {
	public:
		/** 默认构造函数 */
		Conv2d() = default;

		/**
		 * @brief 构造函数
		 * @param input				卷积的输入
		 * @param weights			卷积的权重
		 * @param bias				卷积的偏置
		 * @param stride_width		卷积滑动宽度
		 * @param stride_height		卷积滑动高度
		 * @param pad_top			卷积上方Pad
		 * @param pad_bottom		卷积下方Pad
		 * @param pad_left			卷积左方Pad
		 * @param pad_right			卷积右方Pad
		 * @param dilation_width	卷积膨胀宽度
		 * @param dilation_height	卷积膨胀高度
		 * @param groups			卷积分组，默认为1
		 * @param padding_mode		卷积pad模式，默认为ZEROS
		 */
		XIR_DLL Conv2d(
			Value input,
			Value weights,
			Optional<Value> bias,
			int64_t stride_width,
			int64_t stride_height,
			int64_t pad_top,
			int64_t pad_bottom,
			int64_t pad_left,
			int64_t pad_right,
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
		 * @param stride			卷积滑动步长，宽度和高度相同
		 * @param pad				卷积的Pad，上下左右相同
		 * @param dilation			卷积膨胀系数，宽度和高度相同
		 * @param groups			卷积分组，默认为1
		 * @param padding_mode		卷积pad模式，默认为ZEROS
		 */
		Conv2d(
			Value input,
			Value weights,
			Optional<Value> bias,
			int64_t stride,
			int64_t pad,
			int64_t dilation,
			int64_t groups = 1,
			PaddingMode padding_mode = PaddingMode::ZEROS
		) : Conv2d(
			input,
			weights,
			bias,
			stride, stride,
			pad, pad, pad, pad,
			dilation, dilation,
			groups,
			padding_mode
		) {}
	};
}
