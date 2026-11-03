#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 去无效数据算子 */
	class PruneAxisNode : public OpNodeBase<PruneAxisNode> {
	public:
		Array<int64_t> index;				///< 要执行去无效数据的merged_distr的下标们

		ICRAFT_DECLARE_ATTRS(AlignAxisNode) {
			ICRAFT_ATTR_FIELD(index);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 去无效数据算子引用类 */
	class PruneAxis : public OpBase<PruneAxis, PruneAxisNode> {
	public:
		/** 默认构造函数 */
		PruneAxis() = default;

		/**
		 * @brief 构造函数
		 * @param input			输入
		 * @param index			要执行去无效数据的merged_distr的下标们
		 */
		XIR_DLL PruneAxis(Value input, Array<int64_t> index);
	};
}
