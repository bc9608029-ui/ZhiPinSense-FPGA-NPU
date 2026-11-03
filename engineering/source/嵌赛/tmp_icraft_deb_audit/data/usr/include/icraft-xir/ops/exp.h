#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

class ExpNode : public OpNodeBase<ExpNode, IsActivate> {
public:
ICRAFT_DECLARE_ATTRS(ExpNode) {}

XIR_DLL virtual void validate() const override;
};


class Exp : public OpBase<Exp, ExpNode> {
public:
Exp() = default;

XIR_DLL Exp(Value input);
};
}
