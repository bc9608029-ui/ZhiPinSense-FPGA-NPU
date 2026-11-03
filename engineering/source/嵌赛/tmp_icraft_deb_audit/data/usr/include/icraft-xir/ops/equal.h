#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Equal算子 */
	class EqualNode : public OpNodeBase<EqualNode> {
	public:
		ICRAFT_DECLARE_ATTRS(EqualNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Equal算子引用类 */
	class Equal : public OpBase<Equal, EqualNode> {
	public:
		/** 默认构造函数 */
		Equal() = default;

		/**
		 * @brief 构造函数
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 */
		XIR_DLL Equal(Value lhs, Value rhs);
	};
}
