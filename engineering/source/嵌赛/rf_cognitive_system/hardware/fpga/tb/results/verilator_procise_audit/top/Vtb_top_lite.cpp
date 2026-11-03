// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb_top_lite__pch.h"

//============================================================
// Constructors

Vtb_top_lite::Vtb_top_lite(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb_top_lite__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vtb_top_lite::Vtb_top_lite(const char* _vcname__)
    : Vtb_top_lite(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb_top_lite::~Vtb_top_lite() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb_top_lite___024root___eval_debug_assertions(Vtb_top_lite___024root* vlSelf);
#endif  // VL_DEBUG
void Vtb_top_lite___024root___eval_static(Vtb_top_lite___024root* vlSelf);
void Vtb_top_lite___024root___eval_initial(Vtb_top_lite___024root* vlSelf);
void Vtb_top_lite___024root___eval_settle(Vtb_top_lite___024root* vlSelf);
void Vtb_top_lite___024root___eval(Vtb_top_lite___024root* vlSelf);

void Vtb_top_lite::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb_top_lite::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vtb_top_lite___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vtb_top_lite___024root___eval_static(&(vlSymsp->TOP));
        Vtb_top_lite___024root___eval_initial(&(vlSymsp->TOP));
        Vtb_top_lite___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vtb_top_lite___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vtb_top_lite::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vtb_top_lite::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb_top_lite::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vtb_top_lite___024root___eval_final(Vtb_top_lite___024root* vlSelf);

VL_ATTR_COLD void Vtb_top_lite::final() {
    Vtb_top_lite___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb_top_lite::hierName() const { return vlSymsp->name(); }
const char* Vtb_top_lite::modelName() const { return "Vtb_top_lite"; }
unsigned Vtb_top_lite::threads() const { return 1; }
void Vtb_top_lite::prepareClone() const { contextp()->prepareClone(); }
void Vtb_top_lite::atClone() const {
    contextp()->threadPoolpOnClone();
}
