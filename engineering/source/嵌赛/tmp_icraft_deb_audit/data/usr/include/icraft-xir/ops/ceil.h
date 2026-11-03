#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	class CeilNode : public OpNodeBase<CeilNode, IsActivate> {
	public:
		ICRAFT_DECLARE_ATTRS(CeilNode) {}

		XIR_DLL virtual void validate() const override;
	};


	class Ceil : public OpBase<Ceil, CeilNode> {
	public:
		Ceil() = default;

		XIR_DLL Ceil(Value input);
	};
}
