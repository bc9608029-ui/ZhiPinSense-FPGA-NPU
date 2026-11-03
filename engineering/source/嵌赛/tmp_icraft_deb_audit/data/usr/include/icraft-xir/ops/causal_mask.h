#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** CausalMask算子 */
	class CausalMaskNode : public OpNodeBase<CausalMaskNode> {
	public:
		float fill_value;		// 默认填充的是-inf
		int64_t prefill_max;	// 最大定长填充长度
		Value input;			// hidden_states，定长填充后的，如[batch_size, prefill_max, hidden_states]  [batch_size, 1, hidden_states]
		Value config_dynamic;	// 包含prompt_length、token_idx的feature map

		ICRAFT_DECLARE_ATTRS(CausalMaskNode) {
			ICRAFT_ATTR_FIELD(fill_value).set_default(-std::numeric_limits<float>::infinity());
			ICRAFT_ATTR_FIELD(prefill_max);
			ICRAFT_ATTR_FIELD(input);
			ICRAFT_ATTR_FIELD(config_dynamic);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** CausalMask算子引用类 */
	class CausalMask : public OpBase<CausalMask, CausalMaskNode> {
	public:
		/** 默认构造函数 */
		CausalMask() = default;

		/**
		 * @brief 构造函数
		 * @param input				输入定长填充后的，如[batch_size, prefill_max, hidden_states]
		 * @param config_dynamic	包含prompt_length、token_idx的feature map
		 * @param prefill_max  最大定长填充长度
		 * @param fill_value   默认填充的是-inf
		 */
		XIR_DLL CausalMask(
			Value input,
			Value config_dynamic,
			int64_t prefill_max,
			float fill_value = -std::numeric_limits<float>::infinity()		// 默认负无穷
		);
	};
}
