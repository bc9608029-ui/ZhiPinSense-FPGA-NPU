#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Div算子 */
	class DivNode : public OpNodeBase<DivNode> {
	public:
		/**
		 * @enum	Mode
		 * @brief	表示取整的模式
		 */

		/*	enum class Mode {
			NONE,		///< 
			TRUNC,		///< 
			FLOOR		///< 
		};*/
		WISE_ENUM_CLASS_MEMBER(Mode, NONE, TRUNC, FLOOR);


		Mode rounding_mode;					///< 取整的模式

		ICRAFT_DECLARE_ATTRS(DivNode) {
			ICRAFT_ATTR_FIELD(rounding_mode).set_default(Mode::NONE);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Div算子引用类 */
	class Div : public OpBase<Div, DivNode> {
	public:
		using Mode = DivNode::Mode;

		/** 默认构造函数 */
		Div() = default;

		/**
		 * @brief 构造函数
		 * @param lhs			左操作数
		 * @param rhs			右操作数
		 */
		XIR_DLL Div(Value lhs, Value rhs, Mode rounding_mode = Mode::NONE);
	};
}
