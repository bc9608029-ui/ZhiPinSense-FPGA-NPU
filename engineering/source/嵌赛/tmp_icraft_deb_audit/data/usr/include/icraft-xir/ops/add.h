#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Add算子 */
	class AddNode : public OpNodeBase<AddNode> {
	public:
		Array<ScalarImm> alpha = Array<ScalarImm>{ 1.f };	///< 左操作数的系数
		Array<ScalarImm> beta = Array<ScalarImm>{ 1.f };	///< 右操作数的系数

		QuantizedScaleArray cut_scale;						///< 表示硬件截位时的系数

		ICRAFT_DECLARE_ATTRS(AddNode) {
			ICRAFT_ATTR_FIELD(alpha);
			ICRAFT_ATTR_FIELD(beta);
			ICRAFT_ATTR_FIELD(cut_scale);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Add算子引用类 */
	class Add : public OpBase<Add, AddNode> {
	public:
		/** 默认构造函数 */
		Add() = default;

		/**
		 * @brief 构造函数（兼容标量输入）
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 * @param alpha		左操作数的系数
		 * @param beta		右操作数的系数
		 */
		XIR_DLL Add(Value lhs, Value rhs, ScalarImm alpha, ScalarImm beta);

		/**
		 * @brief 构造函数
		 * @param lhs		左操作数
		 * @param rhs		右操作数
		 * @param alpha		左操作数的系数，默认为{ 1.0 }
		 * @param beta		右操作数的系数，默认为{ 1.0 }
		 */
		XIR_DLL Add(Value lhs, Value rhs, Array<ScalarImm> alpha = { 1.f }, Array <ScalarImm> beta = { 1.f });
	};
}
