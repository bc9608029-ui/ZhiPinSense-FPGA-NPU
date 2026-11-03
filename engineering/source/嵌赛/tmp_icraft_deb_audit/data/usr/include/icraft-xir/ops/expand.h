#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Expand算子 */
	class ExpandNode : public OpNodeBase<ExpandNode> {
	public:
		Array<int64_t> sizes;			///< 期望广播到的形状

		ICRAFT_DECLARE_ATTRS(ExpandNode) {
			ICRAFT_ATTR_FIELD(sizes);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Expand算子引用类 */
	class Expand : public OpBase<Expand, ExpandNode> {
	public:
		/** 默认构造函数 */
		Expand() = default;

		/**
		 * @brief 构造函数
		 * @param input	输入
		 * @param sizes 期望广播到的形状
		 */
		XIR_DLL Expand(Value input, Array<int64_t> sizes);
	};
}
