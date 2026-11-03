#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Cast算子 */
	class CastNode : public OpNodeBase<CastNode> {
	public:
		TensorType target_dtype;				///< 目标数据类型

		ICRAFT_DECLARE_ATTRS(CastNode) {
			ICRAFT_ATTR_FIELD(target_dtype);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Cast算子引用类 */
	class Cast : public OpBase<Cast, CastNode> {
	public:
		/** 默认构造函数 */
		Cast() = default;

		/**
		 * @brief 构造函数
		 * @param input		   输入
		 * @param target_dtype 目标数据类型
		 */
		XIR_DLL Cast(Value input, TensorType target_dtype);
	};
}
