#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Split算子 */
	class SplitNode : public OpNodeBase<SplitNode> {
	public:
		Array<int64_t> sections;	///< 分割块
		int64_t axis;				///< 分割的维度，默认为-1，表示最后一维

		ICRAFT_DECLARE_ATTRS(SplitNode) {
			ICRAFT_ATTR_FIELD(sections);
			ICRAFT_ATTR_FIELD(axis).set_default(-1);
		};

		XIR_DLL virtual void validate() const override;
	};


	/** Split算子引用类 */
	class Split : public OpBase<Split, SplitNode> {
	public:
		/** 默认构造函数 */
		Split() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param sections	分割块
		 * @param axis		分割的维度
		 */
		XIR_DLL Split(Value input, Array<int64_t> sections, int64_t axis = -1);
	};
}
