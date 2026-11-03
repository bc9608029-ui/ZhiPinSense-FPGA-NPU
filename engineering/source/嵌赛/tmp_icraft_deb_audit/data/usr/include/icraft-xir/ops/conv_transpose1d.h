#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 一维反卷积算子 */
	class ConvTranspose1dNode : public OpNodeBase<ConvTranspose1dNode> {
	public:
		int64_t stride_width;			///< 反卷积滑动宽度，默认为1
		int64_t pad_left;				///< 反卷积左方Pad，默认为0
		int64_t pad_right;				///< 反卷积右方Pad，默认为0
		int64_t dilation_width;			///< 反卷积膨胀宽度，默认为1
		int64_t output_pad_width;		///< 反卷积宽度上输出Pad，默认为0
		int64_t groups;					///< 反卷积分组数量，默认为1

		ICRAFT_DECLARE_ATTRS(ConvTranspose1dNode) {
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(dilation_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(output_pad_width).set_default(0);
			ICRAFT_ATTR_FIELD(groups).set_default(1).set_lower_bound(1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 三维反卷积算子引用类 */
	class ConvTranspose1d : public OpBase<ConvTranspose1d, ConvTranspose1dNode> {
	public:
		/** 默认构造函数 */
		ConvTranspose1d() = default;

		/**
		 * @brief 构造函数.
		 * @param input					反卷积的输入
		 * @param weights				反卷积的权重
		 * @param bias					反卷积的偏置
		 * @param stride_width			反卷积滑动宽度
		 * @param pad_left				反卷积左方Pad
		 * @param pad_right				反卷积右方Pad
		 * @param dilation_width		反卷积膨胀宽度
		 * @param output_pad_width		反卷积宽度上输出Pad
		 * @param groups				反卷积分组，默认为1
		 */
		XIR_DLL ConvTranspose1d(
			Value input,
			Value weights,
			Optional<Value> bias,
			int64_t stride_width,
			int64_t pad_left,
			int64_t pad_right,
			int64_t dilation_width,
			int64_t output_pad_width,
			int64_t groups = 1
		);
	};


	// 兼容旧接口
	using Conv1dTranspose = ConvTranspose1d;
	using Conv1dTransposeNode = ConvTranspose1dNode;
}
