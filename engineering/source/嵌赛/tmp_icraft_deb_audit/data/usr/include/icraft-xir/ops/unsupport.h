#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Unsupport算子 */
	class UnsupportNode : public OpNodeBase<UnsupportNode> {
	public:
		ICRAFT_DECLARE_ATTRS(UnsupportNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Unsupport算子引用类 */
	class Unsupport : public OpBase<Unsupport, UnsupportNode> {
	public:
		/** 默认构造函数 */
		Unsupport() = default;

		/**
		 * @brief 构造函数
		 * @param inputs 输入
		 */
		XIR_DLL Unsupport(Array<Value> inputs);
	};
}
