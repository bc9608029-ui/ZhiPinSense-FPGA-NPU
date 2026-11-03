#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** DivideScalar算子 */
	class DivideScalarNode : public OpNodeBase<DivideScalarNode> {
	public:
		// /**
		// * @enum		RoundingMode
		// * @brief	取整模式
		// */
		// enum class RoundingMode {
		// 	NONE,		///< 对应true divide
		// 	TRUNC,		///< 对应c语言风格的整除
		// 	FLOOR		///< 对应python风格"//"符合，或floor divide
		// };
		WISE_ENUM_CLASS_MEMBER(RoundingMode, NONE, TRUNC, FLOOR);

		float divisor;					///< 除数
		RoundingMode rounding_mode;		///< 取整模式

		ICRAFT_DECLARE_ATTRS(DivideScalarNode) {
			ICRAFT_ATTR_FIELD(divisor);
			ICRAFT_ATTR_FIELD(rounding_mode).set_default(RoundingMode::NONE);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** DivideScalar算子引用类 */
	class DivideScalar : public OpBase<DivideScalar, DivideScalarNode> {
	public:
		using RoundingMode = DivideScalarNode::RoundingMode;

		/** 默认构造函数 */
		DivideScalar() = default;

		/**
		 * @brief 构造函数
		 * @param input			输入
		 * @param divisor		除数
		 * @param rounding_mode	取整模式
		 */
		XIR_DLL DivideScalar(Value input, float divisor, RoundingMode rounding_mode = RoundingMode::NONE);
	};
}
