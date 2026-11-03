#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 表示维度对齐单位的类 */
	class AlignedUnitNode : public NodeBase<AlignedUnitNode, Node> {
	public:
		Array<int64_t> index;		///< 维度索引
		Array<int64_t> unit;		///< 对齐的单位

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL virtual bool reduceAccept(AlignedUnitNode* other, const ReduceVisitor& reduce) const;
	};


	/** 对齐单位的引用类 */
	class AlignedUnit : public HandleBase<AlignedUnit, Handle, AlignedUnitNode> {
	public:
		/** 默认构造函数 */
		AlignedUnit() = default;

		/**
		 * @brief 构造函数
		 * @param index 维度索引
		 * @param unit	对齐的单位
		 */
		XIR_DLL AlignedUnit(Array<int64_t> index, Array<int64_t> unit);
	};


	/** AlignAxis算子 */
	class AlignAxisNode : public OpNodeBase<AlignAxisNode> {
	public:
		Array<AlignedUnit> aligned_units;		///< 对齐的维度和单位

		ICRAFT_DECLARE_ATTRS(AlignAxisNode) {
			ICRAFT_ATTR_FIELD(aligned_units);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** AlignAxis算子引用类 */
	class AlignAxis : public OpBase<AlignAxis, AlignAxisNode> {
	public:
		/** 默认构造函数 */
		AlignAxis() = default;

		/**
		 * @brief 构造函数
		 * @param input			输入
		 * @param aligned_units 对齐的维度和单位
		 */
		XIR_DLL AlignAxis(Value input, Array<AlignedUnit> aligned_units);
	};
}
