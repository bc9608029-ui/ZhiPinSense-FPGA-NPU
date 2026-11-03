#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** SiLU算子 */
	class SiLUNode : public OpNodeBase<SiLUNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(SiLUNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** SiLU算子引用类 */
	class SiLU : public OpBase<SiLU, SiLUNode> {
	public:
		/** 默认构造函数 */
		SiLU() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL SiLU(Value input);
	};


	// 兼容旧接口
	using Silu = SiLU;
	using SiluNode = SiLUNode;
}
