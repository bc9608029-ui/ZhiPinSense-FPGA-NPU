#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ReLU算子 */
	class ReLUNode : public OpNodeBase<ReLUNode, IsActivate> {
	public:
		float alpha;			///< 负半轴的系数
		float max_value;		///< ReLU的最大值
		float threshold;		///< ReLU的转折点

		ICRAFT_DECLARE_ATTRS(ReLUNode) {
			ICRAFT_ATTR_FIELD(alpha).set_default(0);
			ICRAFT_ATTR_FIELD(max_value).set_default(std::numeric_limits<float>::infinity());
			ICRAFT_ATTR_FIELD(threshold).set_default(0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** ReLU算子引用类 */
	class ReLU : public OpBase<ReLU, ReLUNode> {
	public:
		/** 默认构造函数 */
		ReLU() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param alpha		负半轴的系数
		 * @param max_value Relu的最大值
		 * @param threshold Relu的转折点
		 */
		XIR_DLL ReLU(Value input, float alpha = 0, float max_value = std::numeric_limits<float>::infinity(),
			float threshold = 0);
	};


	// 兼容旧接口
	using Relu = ReLU;
	using ReluNode = ReLUNode;
}
