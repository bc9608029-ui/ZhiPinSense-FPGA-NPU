#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	class CumSumNode : public OpNodeBase<CumSumNode> {
	public:
		IntImm axis;
		bool exclusive;
		bool reverse;

		ICRAFT_DECLARE_ATTRS(CumSumNode) {
			ICRAFT_ATTR_FIELD(axis).set_default(0);
			ICRAFT_ATTR_FIELD(exclusive).set_default(false);
			ICRAFT_ATTR_FIELD(reverse).set_default(false);
		}

		XIR_DLL virtual void validate() const override;
	};


	class CumSum : public OpBase<CumSum, CumSumNode> {
	public:
		CumSum() = default;

		XIR_DLL CumSum(Value input, IntImm axis = 0, bool exclusive = false, bool reverse = false);
	};
}
