// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb_feature_quantizer__pch.h"

//============================================================
// Constructors

Vtb_feature_quantizer::Vtb_feature_quantizer(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb_feature_quantizer__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vtb_feature_quantizer::Vtb_feature_quantizer(const char* _vcname__)
    : Vtb_feature_quantizer(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb_feature_quantizer::~Vtb_feature_quantizer() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb_feature_quantizer___024root___eval_debug_assertions(Vtb_feature_quantizer___024root* vlSelf);
#endif  // VL_DEBUG
void Vtb_feature_quantizer___024root___eval_static(Vtb_feature_quantizer___024root* vlSelf);
void Vtb_feature_quantizer___024root___eval_initial(Vtb_feature_quantizer___024root* vlSelf);
void Vtb_feature_quantizer___024root___eval_settle(Vtb_feature_quantizer___024root* vlSelf);
void Vtb_feature_quantizer___024root___eval(Vtb_feature_quantizer___024root* vlSelf);

void Vtb_feature_quantizer::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb_feature_quantizer::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vtb_feature_quantizer___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vtb_feature_quantizer___024root___eval_static(&(vlSymsp->TOP));
        Vtb_feature_quantizer___024root___eval_initial(&(vlSymsp->TOP));
        Vtb_feature_quantizer___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vtb_feature_quantizer___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vtb_feature_quantizer::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vtb_feature_quantizer::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb_feature_quantizer::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vtb_feature_quantizer___024root___eval_final(Vtb_feature_quantizer___024root* vlSelf);

VL_ATTR_COLD void Vtb_feature_quantizer::final() {
    Vtb_feature_quantizer___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb_feature_quantizer::hierName() const { return vlSymsp->name(); }
const char* Vtb_feature_quantizer::modelName() const { return "Vtb_feature_quantizer"; }
unsigned Vtb_feature_quantizer::threads() const { return 1; }
void Vtb_feature_quantizer::prepareClone() const { contextp()->prepareClone(); }
void Vtb_feature_quantizer::atClone() const {
    contextp()->threadPoolpOnClone();
}
