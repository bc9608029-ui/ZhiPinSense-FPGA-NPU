#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 二维BatchNorm2d算子 */
	class BatchNorm2dNode : public OpNodeBase<BatchNorm2dNode>{
	public:
		Params variance;		///< Batchnorm的乘数因子
		Params mean;			///< Batchnorm加数因子

		ICRAFT_DECLARE_ATTRS(BatchNorm2dNode) {
			ICRAFT_ATTR_FIELD(variance);
			ICRAFT_ATTR_FIELD(mean);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** 二维BatchNorm2d算子引用类 */
	class BatchNorm2d : public OpBase<BatchNorm2d, BatchNorm2dNode> {
	public:
		/** 默认构造函数 */
		BatchNorm2d() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param variance	乘数因子
		 * @param mean		加数因子
		 */
		XIR_DLL BatchNorm2d(Value input, Params variance, Params mean);
	};


	// 兼容旧接口
	using Batchnorm = BatchNorm2d;
	using BatchnormNode = BatchNorm2dNode;
}
