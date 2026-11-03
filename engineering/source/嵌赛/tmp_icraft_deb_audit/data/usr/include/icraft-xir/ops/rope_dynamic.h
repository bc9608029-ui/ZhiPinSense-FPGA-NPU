#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** opeDyanmic */
	class RopeDynamicNode : public OpNodeBase<RopeDynamicNode> {
	public:
		Params sin_cache;		// rope的sin_cache
		Params cos_cache;		// rope的cos_cache
		Value config_dynamic;	// 包含prompt_length、token_idx的feature map
		Value input;			// hidden_states，定长填充后的，如[batch_size, prefill_max, hidden_states]  [batch_size, 1, hidden_states]
		int64_t prefill_max;	// 最大定长填充长度

		ICRAFT_DECLARE_ATTRS(RopeDynamicNode) {
			ICRAFT_ATTR_FIELD(config_dynamic);
			ICRAFT_ATTR_FIELD(input);
			ICRAFT_ATTR_FIELD(cos_cache);
			ICRAFT_ATTR_FIELD(sin_cache);
			ICRAFT_ATTR_FIELD(prefill_max);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** RopeDynamic算子引用类 */
	class RopeDynamic : public OpBase<RopeDynamic, RopeDynamicNode> {
	public:
		/** 默认构造函数 */
		RopeDynamic() = default;

		/**
		 * @brief 构造函数
		 * @param input				输入定长填充后的，如[batch_size, prefill_max, hidden_states]
		 * @param config_dynamic   包含prompt_length、token_idx的feature map
		 * @param sin_cache
		 * @param cos_cache
		 */
		XIR_DLL RopeDynamic(
			Value input,
			Value config_dynamic,
			Params cos_cache,
			Params sin_cache,
			int64_t prefill_max
		);
	};
}
