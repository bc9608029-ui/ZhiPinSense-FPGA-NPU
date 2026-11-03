#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Pad算子 */
	class PadNode : public OpNodeBase<PadNode> {
	public:

		/**
		 * @enum		Mode
		 * @brief	表示Pad的模式
		 */
		// enum class Mode {
		// 	CONSTANT,		///< 常量
		// 	REFLECTION,		///< 反射
		// 	REPLICATION,	///< 复制
		// 	SYMMETRIC		///< 对称
		// };
		WISE_ENUM_CLASS_MEMBER(Mode, CONSTANT, REFLECTION, REPLICATION, SYMMETRIC);

		Array<int64_t> padding;		///< Pad的数量，维度 = 输入维度*2，每个输入维度对应前后两个padding
		Mode mode;					///< Pad的模式，默认为CONSTANT
		ScalarImm value;			///< Pad为CONSTANT模式时的值，默认为0

		ICRAFT_DECLARE_ATTRS(PadNode) {
			ICRAFT_ATTR_FIELD(padding);
			ICRAFT_ATTR_FIELD(mode).set_default(Mode::CONSTANT);
			ICRAFT_ATTR_FIELD(value).set_default(IntImm(0));
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Pad算子引用类 */
	class Pad : public OpBase<Pad, PadNode> {
	public:
		using Mode = PadNode::Mode;

		/** 默认构造函数 */
		Pad() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param padding Pad的数量，维度 = 输入维度*2，每个输入维度对应前后两个padding
		 * @param mode Pad的模式，默认为CONSTANT
		 * @param value Pad为CONSTANT模式时的值，默认为0
		 */
		XIR_DLL Pad(Value input, Array<int64_t> padding, Mode mode = Mode::CONSTANT, ScalarImm value = IntImm(0));
	};
}
