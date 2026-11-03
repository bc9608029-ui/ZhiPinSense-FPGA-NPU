#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** GELU算子 */
	class GELUNode : public OpNodeBase<GELUNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(GELUNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** GELU算子引用类 */
	class GELU : public OpBase<GELU, GELUNode> {
	public:
		/** 默认构造函数 */
		GELU() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL GELU(Value input);
	};


	// 兼容旧接口
	using Gelu = GELU;
	using GeluNode = GELUNode;
}
