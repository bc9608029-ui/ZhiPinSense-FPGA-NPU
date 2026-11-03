// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vled_tb__pch.h"

//============================================================
// Constructors

Vled_tb::Vled_tb(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vled_tb__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vled_tb::Vled_tb(const char* _vcname__)
    : Vled_tb(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vled_tb::~Vled_tb() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vled_tb___024root___eval_debug_assertions(Vled_tb___024root* vlSelf);
#endif  // VL_DEBUG
void Vled_tb___024root___eval_static(Vled_tb___024root* vlSelf);
void Vled_tb___024root___eval_initial(Vled_tb___024root* vlSelf);
void Vled_tb___024root___eval_settle(Vled_tb___024root* vlSelf);
void Vled_tb___024root___eval(Vled_tb___024root* vlSelf);

void Vled_tb::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vled_tb::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vled_tb___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vled_tb___024root___eval_static(&(vlSymsp->TOP));
        Vled_tb___024root___eval_initial(&(vlSymsp->TOP));
        Vled_tb___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vled_tb___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vled_tb::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vled_tb::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vled_tb::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vled_tb___024root___eval_final(Vled_tb___024root* vlSelf);

VL_ATTR_COLD void Vled_tb::final() {
    Vled_tb___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vled_tb::hierName() const { return vlSymsp->name(); }
const char* Vled_tb::modelName() const { return "Vled_tb"; }
unsigned Vled_tb::threads() const { return 1; }
void Vled_tb::prepareClone() const { contextp()->prepareClone(); }
void Vled_tb::atClone() const {
    contextp()->threadPoolpOnClone();
}
