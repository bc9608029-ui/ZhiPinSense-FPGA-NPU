#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Slice算子 */
	class SliceNode : public OpNodeBase<SliceNode> {
	public:
		Array<int64_t> begin;	///< 切片的起始点，对应每个维度，从0开始
		Array<int64_t> end;		///< 切片的结束点，对应每个维度，开空间
		Array<int64_t> stride;	///< 切片的滑动步长，对应每个维度

		ICRAFT_DECLARE_ATTRS(SliceNode) {
			ICRAFT_ATTR_FIELD(begin);
			ICRAFT_ATTR_FIELD(end);
			ICRAFT_ATTR_FIELD(stride);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Slice算子引用类 */
	class Slice : public OpBase<Slice, SliceNode> {
	public:
		/** 默认构造函数 */
		Slice() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param begin		切片的起始点，对应每个维度，从0开始
		 * @param end		切片的结束点，对应每个维度，开空间
		 * @param stride	切片的滑动步长，对应每个维度
		 */
		XIR_DLL Slice(Value input, Array<int64_t> begin, Array<int64_t> end, Array<int64_t> stride);
	};
}
