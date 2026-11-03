#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Mean算子 */
	class MeanNode : public OpNodeBase<MeanNode> {
	public:
		Array<int64_t> dim;			///< 进行求平均的维度（支持负数索引）
		bool keepdim;				///< 是否保持维度不变

		ICRAFT_DECLARE_ATTRS(MeanNode) {
			ICRAFT_ATTR_FIELD(dim);
			ICRAFT_ATTR_FIELD(keepdim).set_default(false);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Mean算子引用类 */
	class Mean : public OpBase<Mean, MeanNode> {
	public:
		/** 默认构造函数 */
		Mean() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 */
		XIR_DLL Mean(Value input);

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dim		进行平均的维度
		 * @param keepdim	是否保持维度不变
		 */
		XIR_DLL Mean(Value input, int64_t dim, bool keepdim = false);

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param dim		进行平均的维度列表
		 * @param keepdim	是否保持维度不变
		 */
		XIR_DLL Mean(Value input, Array<int64_t> dim, bool keepdim = false);
	};
}
