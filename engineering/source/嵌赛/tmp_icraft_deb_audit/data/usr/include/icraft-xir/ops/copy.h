#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Copy算子 */
	class CopyNode : public OpNodeBase<CopyNode> {
	public:
		ICRAFT_DECLARE_ATTRS(CopyNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Copy算子引用类 */
	class Copy : public OpBase<Copy, CopyNode> {
	public:
		/** 默认构造函数 */
		Copy() = default;

		/**
		 * @brief 构造函数
		 * @param input	输入
		 */
		XIR_DLL Copy(Value input);
	};
}
