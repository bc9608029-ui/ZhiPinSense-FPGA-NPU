#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Stack算子 */
	class StackNode : public OpNodeBase<StackNode> {
	public:
		int64_t dim;		///< 进行堆叠运算的维度（支持负数索引），默认为0

		ICRAFT_DECLARE_ATTRS(StackNode) {
			ICRAFT_ATTR_FIELD(dim).set_default(0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Stack算子引用类 */
	class Stack : public OpBase<Stack, StackNode> {
	public:
		/** 默认构造函数 */
		Stack() = default;

		/**
		 * @brief 构造函数
		 * @param inputs	输入
		 * @param dim		进行堆叠运算的维度（支持负数索引），默认为0
		 */
		XIR_DLL Stack(Array<Value> inputs, int64_t dim = 0);
	};
}
