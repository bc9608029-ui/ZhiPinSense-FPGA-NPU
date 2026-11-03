#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Argmin算子 */
	class ArgminNode : public OpNodeBase<ArgminNode> {
	public:
		Optional<IntImm> dim;		///< 进行求最小值索引的维度（支持负数索引）
		bool keepdim;				///< 是否保持维度不变

		ICRAFT_DECLARE_ATTRS(ArgminNode) {
			ICRAFT_ATTR_FIELD(dim);
			ICRAFT_ATTR_FIELD(keepdim).set_default(false);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Argmin算子引用类 */
	class Argmin : public OpBase<Argmin, ArgminNode> {
	public:
		/** 默认构造函数 */
		Argmin() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dim		进行求最小值索引的维度
		 * @param keepdim	是否保持维度不变
		 */
		XIR_DLL Argmin(Value input, Optional<IntImm> dim = NullOpt, bool keepdim = false);
	};
}
