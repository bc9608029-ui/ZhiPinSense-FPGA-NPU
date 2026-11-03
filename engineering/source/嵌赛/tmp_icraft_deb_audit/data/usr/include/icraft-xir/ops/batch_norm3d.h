#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 三维BatchNorm算子 */
	class BatchNorm3dNode : public OpNodeBase<BatchNorm3dNode>{
	public:
		Params variance;		///< BatchNorm3d的乘数因子
		Params mean;			///< BatchNorm3d加数因子

		ICRAFT_DECLARE_ATTRS(BatchNorm3dNode) {
			ICRAFT_ATTR_FIELD(variance);
			ICRAFT_ATTR_FIELD(mean);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 三维BatchNorm算子引用类 */
	class BatchNorm3d : public OpBase<BatchNorm3d, BatchNorm3dNode> {
	public:
		/** 默认构造函数 */
		BatchNorm3d() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param variance	乘数因子
		 * @param mean		加数因子
		 */
		XIR_DLL BatchNorm3d(Value input, Params variance, Params mean);
	};
}
