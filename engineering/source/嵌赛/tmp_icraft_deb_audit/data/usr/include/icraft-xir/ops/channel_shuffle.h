#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 通道重组算子 */
	class ChannelShuffleNode : public OpNodeBase<ChannelShuffleNode> {
	public:
		int64_t groups;					///< 要把通道分成的组数

		ICRAFT_DECLARE_ATTRS(ChannelShuffleNode) {
			ICRAFT_ATTR_FIELD(groups).set_lower_bound(1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 通道重组算子引用类 */
	class ChannelShuffle : public OpBase<ChannelShuffle, ChannelShuffleNode> {
	public:
		/** 默认构造函数 */
		ChannelShuffle() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param groups	要把通道分成的组数
		 */
		XIR_DLL ChannelShuffle(Value input, int64_t groups);
	};
}
