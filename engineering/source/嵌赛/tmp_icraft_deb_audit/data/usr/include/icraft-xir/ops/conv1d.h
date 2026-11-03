#pragma once
#include <icraft-xir/core/operation.h>
#include <icraft-xir/ops/conv2d.h>


namespace icraft::xir {

	/** 一维卷积算子 */
	class Conv1dNode : public OpNodeBase<Conv1dNode> {
	public:
		int64_t stride_width;			///< 卷积滑动宽度，默认为1
		int64_t pad_left;				///< 卷积左方Pad，默认为0
		int64_t pad_right;				///< 卷积右方Pad，默认为0
		int64_t dilation_width;			///< 卷积膨胀宽度，默认为1
		int64_t groups;					///< 卷积分组数量，默认为1
		PaddingMode padding_mode;		///< 卷积的pad模式，默认为ZEROS

		QuantizedScaleArray cut_scale;	///< 表示硬件截位时的系数

		ICRAFT_DECLARE_ATTRS(Conv1dNode) {
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(dilation_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(groups).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(padding_mode).set_default(PaddingMode::ZEROS);
			ICRAFT_ATTR_FIELD(cut_scale);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 一维卷积算子引用类 */
	class Conv1d : public OpBase<Conv1d, Conv1dNode> {
	public:
		/** 默认构造函数 */
		Conv1d() = default;

		/**
		 * @brief 构造函数
		 * @param input				卷积的输入
		 * @param weights			卷积的权重
		 * @param bias				卷积的偏置
		 * @param stride_width		卷积滑动宽度
		 * @param pad_left			卷积左方Pad
		 * @param pad_right			卷积右方Pad
		 * @param dilation_width	卷积膨胀宽度
		 * @param groups			卷积分组，默认为1
		 * @param padding_mode		卷积pad模式，默认为ZEROS
		 */
		XIR_DLL Conv1d(
			Value input,
			Value weights,
			Optional<Value> bias,
			int64_t stride_width,
			int64_t pad_left,
			int64_t pad_right,
			int64_t dilation_width,
			int64_t groups = 1,
			PaddingMode padding_mode = PaddingMode::ZEROS
		);
	};
}
