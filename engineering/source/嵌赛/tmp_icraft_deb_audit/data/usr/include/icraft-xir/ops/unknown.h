#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Unknown算子 */
	class UnknownNode : public OpNodeBase<UnknownNode> {
	public:
		std::string msg_info;						///< 无法解析的算子的原始msg信息
		std::string json_info;						///< 无法解析的算子的原始json信息

		ICRAFT_DECLARE_ATTRS(UnknownNode) {
			ICRAFT_ATTR_FIELD(msg_info);
			ICRAFT_ATTR_FIELD(json_info);
		};

		XIR_DLL virtual void validate() const override;
	};


	/** Unknown算子引用类 */
	class Unknown : public OpBase<Unknown, UnknownNode> {
	public:
		/** 默认构造函数 */
		Unknown() = default;

		/**
		 * @brief 构造函数
		 * @param inputs	输入
		 * @param info		无法解析的算子的原始信息
		 * @param format	该信息的格式，支持"json"、"msgpack"
		 */
		XIR_DLL Unknown(Array<Value> inputs, std::string info, std::string format);
	};
}
