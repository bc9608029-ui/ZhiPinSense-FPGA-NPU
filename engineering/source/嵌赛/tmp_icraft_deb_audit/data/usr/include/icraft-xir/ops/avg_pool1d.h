#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 一维平均池化算子 */
	class AvgPool1dNode : public OpNodeBase<AvgPool1dNode> {
	public:

		int64_t pool_width;				///< 池化窗口宽度
		int64_t stride_width;			///< 池化滑动宽度，默认为1
		int64_t pad_left;				///< 池化左方Pad，默认为0
		int64_t pad_right;				///< 池化右方Pad，默认为0
		bool count_include_pad;			///< 平均时是否包含pad数据，默认不包含
		int64_t divisor_override;		///< 覆盖池化的除数，默认为0表示不覆盖

		ICRAFT_DECLARE_ATTRS(AvgPool1dNode) {
			ICRAFT_ATTR_FIELD(pool_width).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(stride_width).set_default(1).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(pad_left).set_default(0);
			ICRAFT_ATTR_FIELD(pad_right).set_default(0);
			ICRAFT_ATTR_FIELD(count_include_pad).set_default(false);
			ICRAFT_ATTR_FIELD(divisor_override).set_default(0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 一维平均池化算子引用类 */
	class AvgPool1d : public OpBase<AvgPool1d, AvgPool1dNode> {
	public:
		/** 默认构造函数 */
		AvgPool1d() = default;

		/**
		 * @brief 构造函数
		 * @param input				池化的输入
		 * @param pool_width		池化窗口宽度
		 * @param stride_width		池化滑动宽度
		 * @param pad_left			池化左方Pad
		 * @param pad_right			池化右方Pad
		 * @param count_include_pad	平均时是否包含pads数据，默认为false
		 * @param divisor_override	覆盖池化的除数，默认为0不覆盖
		 */
		XIR_DLL AvgPool1d(
			Value input,
			int64_t pool_width,
			int64_t stride_width,
			int64_t pad_left,
			int64_t pad_right,
			bool count_include_pad = false,
			int64_t divisor_override = 0
		);
	};
}
