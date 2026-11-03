#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Hardtanh算子 */
	class HardtanhNode : public OpNodeBase<HardtanhNode, IsActivate> {
	public:
		float min_val ;		///< Hardtanh的最小值，默认为-1.0
		float max_val;			///< Hardtanh的最大值，默认为1.0

		ICRAFT_DECLARE_ATTRS(HardtanhNode) {
			ICRAFT_ATTR_FIELD(min_val).set_default(-1.0);
			ICRAFT_ATTR_FIELD(max_val).set_default(1.0);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Hardtanh算子引用类 */
	class Hardtanh : public OpBase<Hardtanh, HardtanhNode> {
	public:
		/** 默认构造函数 */
		Hardtanh() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param min_val Hardtanh的最小值，默认为 -1.0
		 * @param max_val Hardtanh的最大值，默认为  1.0
		 */
		XIR_DLL Hardtanh(Value input, float min_val = -1.0, float max_val = 1.0);
	};
}
