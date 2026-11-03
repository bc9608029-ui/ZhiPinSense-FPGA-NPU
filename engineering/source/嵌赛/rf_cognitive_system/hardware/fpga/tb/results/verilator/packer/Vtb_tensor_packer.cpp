// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb_tensor_packer__pch.h"

//============================================================
// Constructors

Vtb_tensor_packer::Vtb_tensor_packer(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb_tensor_packer__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vtb_tensor_packer::Vtb_tensor_packer(const char* _vcname__)
    : Vtb_tensor_packer(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb_tensor_packer::~Vtb_tensor_packer() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb_tensor_packer___024root___eval_debug_assertions(Vtb_tensor_packer___024root* vlSelf);
#endif  // VL_DEBUG
void Vtb_tensor_packer___024root___eval_static(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___eval_initial(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___eval_settle(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___eval(Vtb_tensor_packer___024root* vlSelf);

void Vtb_tensor_packer::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb_tensor_packer::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vtb_tensor_packer___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vtb_tensor_packer___024root___eval_static(&(vlSymsp->TOP));
        Vtb_tensor_packer___024root___eval_initial(&(vlSymsp->TOP));
        Vtb_tensor_packer___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vtb_tensor_packer___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vtb_tensor_packer::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vtb_tensor_packer::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb_tensor_packer::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vtb_tensor_packer___024root___eval_final(Vtb_tensor_packer___024root* vlSelf);

VL_ATTR_COLD void Vtb_tensor_packer::final() {
    Vtb_tensor_packer___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb_tensor_packer::hierName() const { return vlSymsp->name(); }
const char* Vtb_tensor_packer::modelName() const { return "Vtb_tensor_packer"; }
unsigned Vtb_tensor_packer::threads() const { return 1; }
void Vtb_tensor_packer::prepareClone() const { contextp()->prepareClone(); }
void Vtb_tensor_packer::atClone() const {
    contextp()->threadPoolpOnClone();
}
