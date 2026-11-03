#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Concat算子 */
	class ConcatNode : public OpNodeBase<ConcatNode> {
	public:
		int64_t axis;				///< 拼接的维度，默认为-1，表示最后一维

		ICRAFT_DECLARE_ATTRS(ConcatNode) {
			ICRAFT_ATTR_FIELD(axis).set_default(-1).set_lower_bound(-1);
		};

		XIR_DLL virtual void validate() const override;
	};


	/** Concat算子引用类 */
	class Concat : public OpBase<Concat, ConcatNode> {
	public:
		/** 默认构造函数 */
		Concat() = default;

		/**
		 * @brief 构造函数
		 * @param inputs	输入
		 * @param axis		拼接的维度，默认为-1，表示最后一维
		 */
		XIR_DLL Concat(Array<Value> inputs, int64_t axis = -1);
	};
}
