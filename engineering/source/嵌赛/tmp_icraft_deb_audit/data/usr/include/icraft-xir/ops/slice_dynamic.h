#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** SliceDynamic */
	class SliceDynamicNode : public OpNodeBase<SliceDynamicNode> {
	public:
		Params unvalid_mask;	// decoder的ropes输出，如[1,2,1,64]
		Value config_dynamic;	// 包含prompt_length、token_idx的feature map
		Value input;			// hidden_states，定长填充后的，如[batch_size, prefill_max, hidden_states]  [batch_size, 1, hidden_states]
		Value kvcache;			// 输入的历史kv cache
		int64_t prefill_max;	// 最大定长填充长度

		ICRAFT_DECLARE_ATTRS(SliceDynamicNode) {
			ICRAFT_ATTR_FIELD(config_dynamic);
			ICRAFT_ATTR_FIELD(input);
			ICRAFT_ATTR_FIELD(unvalid_mask);
			ICRAFT_ATTR_FIELD(prefill_max);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** SliceDynamic算子引用类 */
	class SliceDynamic : public OpBase<SliceDynamic, SliceDynamicNode> {
	public:
		/** 默认构造函数 */
		SliceDynamic() = default;

		/**
		 * @brief 构造函数
		 * @param input				decoder的ropes输出，如[1,2,1,64]
		 * @param config_dynamic	包含prompt_length、token_idx的feature map
		 * @param sin_cache
		 * @param cos_cache
		 */
		XIR_DLL SliceDynamic(
			Value input,
			Value config_dynamic,
			Value kvcache,
			Params unvalid_mask,
			int64_t prefill_max
		);
	};
}
