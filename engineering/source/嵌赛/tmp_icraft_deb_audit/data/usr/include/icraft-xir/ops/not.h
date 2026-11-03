#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Not算子 */
	class NotNode : public OpNodeBase<NotNode> {
	public:
		ICRAFT_DECLARE_ATTRS(NotNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Not算子引用类 */
	class Not : public OpBase<Not, NotNode> {
	public:
		/** 默认构造函数 */
		Not() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 */
		XIR_DLL Not(Value input);
	};
}
