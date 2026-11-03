#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** PReLU算子 */
	class PReLUNode : public OpNodeBase<PReLUNode, IsActivate> {
	public:
		Params alpha;		///< 负半轴的系数

		ICRAFT_DECLARE_ATTRS(PReLUNode) {
			ICRAFT_ATTR_FIELD(alpha);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** PReLU算子引用类 */
	class PReLU : public OpBase<PReLU, PReLUNode> {
	public:
		/** 默认构造函数 */
		PReLU() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param alpha 负半轴的系数
		 */
		XIR_DLL PReLU(Value input, Params alpha);
	};


	// 兼容旧接口
	using Prelu = PReLU;
	using PreluNode = PReLUNode;
}
