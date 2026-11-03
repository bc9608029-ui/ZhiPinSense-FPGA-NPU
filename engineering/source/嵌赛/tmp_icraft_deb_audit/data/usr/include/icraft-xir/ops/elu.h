#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ELU算子 */
	class ELUNode : public OpNodeBase<ELUNode, IsActivate> {
	public:
		float alpha;		///< 负半轴的系数

		ICRAFT_DECLARE_ATTRS(ELUNode) {
			ICRAFT_ATTR_FIELD(alpha).set_default(1.0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** ELU算子引用类 */
	class ELU : public OpBase<ELU, ELUNode> {
	public:
		/** 默认构造函数 */
		ELU() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param alpha 负半轴的系数
		 */
		XIR_DLL ELU(Value input, float alpha = 1.0);
	};


	// 兼容旧接口
	using Elu = ELU;
	using EluNode = ELUNode;
}
