#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** LogSoftmax算子 */
	class LogSoftmaxNode : public OpNodeBase<LogSoftmaxNode> {
	public:
		int64_t axis;	///< 指定LogSoftmax的维度，默认为-1，表示最后一维

		ICRAFT_DECLARE_ATTRS(LogSoftmaxNode) {
			ICRAFT_ATTR_FIELD(axis).set_default(-1);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** LogSoftmax算子引用类 */
	class LogSoftmax : public OpBase<LogSoftmax, LogSoftmaxNode> {
	public:
		/** 默认构造函数 */
		LogSoftmax() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param axis  指定LogSoftmax的维度，默认为-1，表示最后一维
		 */
		XIR_DLL LogSoftmax(Value input, int64_t axis = -1);
	};
}
