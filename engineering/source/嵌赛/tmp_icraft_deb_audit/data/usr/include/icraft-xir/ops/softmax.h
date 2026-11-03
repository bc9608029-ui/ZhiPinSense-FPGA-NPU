#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Softmax算子 */
	class SoftmaxNode : public OpNodeBase<SoftmaxNode> {
	public:
		int64_t axis;	///< 指定Softmax的维度（支持负数索引），默认为-1，表示最后一维

		ICRAFT_DECLARE_ATTRS(SoftmaxNode) {
			ICRAFT_ATTR_FIELD(axis).set_default(-1).set_lower_bound(-1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Softmax算子引用类 */
	class Softmax : public OpBase<Softmax, SoftmaxNode> {
	public:
		/** 默认构造函数 */
		Softmax() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param axis  指定Softmax的维度（支持负数索引），默认为-1，表示最后一维
		 */
		XIR_DLL Softmax(Value input, int64_t axis = -1);
	};
}
