#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** IndexSelect算子 */
	class IndexSelectNode : public OpNodeBase<IndexSelectNode> {
	public:
		int64_t dim;					///< 进行操作的维度（支持负数索引）

		ICRAFT_DECLARE_ATTRS(IndexSelectNode) {
			ICRAFT_ATTR_FIELD(dim);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** IndexSelect算子引用类 */
	class IndexSelect : public OpBase<IndexSelect, IndexSelectNode> {
	public:
		/** 默认构造函数 */
		IndexSelect() = default;

		/**
		 * @brief 构造函数
		 * @param input	输入
		 * @param index 索引下标
		 * @param dim	进行操作的维度（支持负数索引）
		 */
		XIR_DLL IndexSelect(Value input, Value index, int64_t dim);
	};
}
