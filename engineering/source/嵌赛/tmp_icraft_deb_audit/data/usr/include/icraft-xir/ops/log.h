#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Log算子 */
	class LogNode : public OpNodeBase<LogNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(LogNode) {}

		XIR_DLL virtual void validate() const override;
	};


	/** Log算子引用类 */
	class Log : public OpBase<Log, LogNode> {
	public:
		/** 默认构造函数 */
		Log() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 */
		XIR_DLL Log(Value input);
	};
}
