#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 像素重组算子 */
	class PixelShuffleNode : public OpNodeBase<PixelShuffleNode> {
	public:
		int64_t upscale_factor;

		ICRAFT_DECLARE_ATTRS(PixelShuffleNode) {
			ICRAFT_ATTR_FIELD(upscale_factor).set_default(1).set_lower_bound(1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 像素重组算子引用类 */
	class PixelShuffle : public OpBase<PixelShuffle, PixelShuffleNode> {
	public:
		/** 默认构造函数 */
		PixelShuffle() = default;

		/**
		 * @brief 构造函数
		 * @param input	输入
		 */
		XIR_DLL PixelShuffle(Value input, int64_t upscale_factor);
	};
}
