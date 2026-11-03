#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 一维BatchNorm算子 */
	class BatchNorm1dNode : public OpNodeBase<BatchNorm1dNode>{
	public:
		Params variance;		///< BatchNorm1d的乘数因子
		Params mean;			///< BatchNorm1d加数因子

		ICRAFT_DECLARE_ATTRS(BatchNorm1dNode) {
			ICRAFT_ATTR_FIELD(variance);
			ICRAFT_ATTR_FIELD(mean);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 一维BatchNorm算子引用类 */
	class BatchNorm1d : public OpBase<BatchNorm1d, BatchNorm1dNode> {
	public:
		/** 默认构造函数 */
		BatchNorm1d() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param variance	乘数因子
		 * @param mean		加数因子
		 */
		XIR_DLL BatchNorm1d(Value input, Params variance, Params mean);
	};
}
