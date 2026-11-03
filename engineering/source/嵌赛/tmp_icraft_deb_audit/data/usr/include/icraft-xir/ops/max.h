#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Max算子 */
	class MaxNode : public OpNodeBase<MaxNode> {
	public:
		Optional<IntImm> dim;		///< 进行求最大值索引的维度（支持负数索引）
		bool keepdim;				///< 是否保持维度不变

		ICRAFT_DECLARE_ATTRS(MaxNode) {
			ICRAFT_ATTR_FIELD(dim);
			ICRAFT_ATTR_FIELD(keepdim).set_default(false);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Max算子引用类 */
	class Max : public OpBase<Max, MaxNode> {
	public:
		/** 默认构造函数 */
		Max() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dim		进行求最大值索引的维度
		 * @param keepdim	是否保持维度不变
		 */
		XIR_DLL Max(Value input, Optional<IntImm> dim = NullOpt, bool keepdim = false);
	};
}
