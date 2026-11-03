#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** ClampScalar算子 */
	class ClampScalarNode : public OpNodeBase<ClampScalarNode, IsActivate> {
	public:
		float min;					///< 裁剪的下限，默认负无穷
		float max;					///< 裁剪的上限，默认正无穷

		ICRAFT_DECLARE_ATTRS(ClampScalarNode) {
			ICRAFT_ATTR_FIELD(min).set_default(-std::numeric_limits<float>::infinity());
			ICRAFT_ATTR_FIELD(max).set_default(std::numeric_limits<float>::infinity());
		}

		XIR_DLL virtual void validate() const override;
	};


	/** ClampScalar算子引用类 */
	class ClampScalar : public OpBase<ClampScalar, ClampScalarNode> {
	public:
		/** 默认构造函数 */
		ClampScalar() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param min		裁剪的下限，默认负无穷
		 * @param max		裁剪的上限，默认正无穷
		 */
		XIR_DLL ClampScalar(
			Value input,
			float min = -std::numeric_limits<float>::infinity(),
			float max = std::numeric_limits<float>::infinity()
		);
	};
}
