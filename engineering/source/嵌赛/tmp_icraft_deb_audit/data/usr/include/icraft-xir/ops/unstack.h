#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Unstack算子 */
	class UnstackNode : public OpNodeBase<UnstackNode> {
	public:
		int64_t dim;		///< 进行分隔运算的维度（支持负数索引），默认为0

		ICRAFT_DECLARE_ATTRS(UnstackNode) {
			ICRAFT_ATTR_FIELD(dim).set_default(0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Unstack算子引用类 */
	class Unstack : public OpBase<Unstack, UnstackNode> {
	public:
		/** 默认构造函数 */
		Unstack() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param dim	进行分隔运算的维度（支持负数索引），默认为0
		 */
		XIR_DLL Unstack(Value input, int64_t dim = 0);
	};
}
