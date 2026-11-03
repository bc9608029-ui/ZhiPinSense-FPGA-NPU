#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** LogSigmoid算子 */
	class LogSigmoidNode : public OpNodeBase<LogSigmoidNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(LogSigmoidNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** LogSigmoid算子引用类 */
	class LogSigmoid : public OpBase<LogSigmoid, LogSigmoidNode> {
	public:
		/** 默认构造函数 */
		LogSigmoid() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL LogSigmoid(Value input);
	};
}
