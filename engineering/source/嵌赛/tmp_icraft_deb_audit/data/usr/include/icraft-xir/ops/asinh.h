#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ASinh算子 */
	class ASinhNode : public OpNodeBase<ASinhNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(ASinhNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** ASinh算子引用类 */
	class ASinh : public OpBase<ASinh, ASinhNode> {
	public:
		/** 默认构造函数 */
		ASinh() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL ASinh(Value input);
	};
}
