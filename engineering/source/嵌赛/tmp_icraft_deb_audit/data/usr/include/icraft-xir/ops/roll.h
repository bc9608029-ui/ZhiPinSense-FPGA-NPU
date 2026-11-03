#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Roll算子 */
	class RollNode : public OpNodeBase<RollNode> {
	public:
		Array<int64_t> shifts;						///< 滚动位移
		Optional<Array<int64_t>> dims;				///< 滚动轴

		ICRAFT_DECLARE_ATTRS(RollNode) {
			ICRAFT_ATTR_FIELD(shifts);
			ICRAFT_ATTR_FIELD(dims);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Roll算子引用类 */
	class Roll : public OpBase<Roll, RollNode> {
	public:
		/** 默认构造函数 */
		Roll() = default;

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param shift		滚动位移
		 * @param dim		滚动轴
		 */
		XIR_DLL Roll(Value input, int64_t shift, std::optional<int64_t> dim = std::nullopt);

		/**
		 * @brief 构造函数
		 * @param input		输入
		 * @param shifts	滚动位移
		 * @param dims		滚动轴
		 */
		XIR_DLL Roll(Value input, Array<int64_t> shifts, Optional<Array<int64_t>> dims = NullOpt);
	};
}
