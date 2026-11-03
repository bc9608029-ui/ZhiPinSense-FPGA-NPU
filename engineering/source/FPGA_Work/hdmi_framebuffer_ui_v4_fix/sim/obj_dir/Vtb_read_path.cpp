// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb_read_path__pch.h"

//============================================================
// Constructors

Vtb_read_path::Vtb_read_path(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb_read_path__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vtb_read_path::Vtb_read_path(const char* _vcname__)
    : Vtb_read_path(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb_read_path::~Vtb_read_path() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb_read_path___024root___eval_debug_assertions(Vtb_read_path___024root* vlSelf);
#endif  // VL_DEBUG
void Vtb_read_path___024root___eval_static(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___eval_initial(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___eval_settle(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___eval(Vtb_read_path___024root* vlSelf);

void Vtb_read_path::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb_read_path::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vtb_read_path___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vtb_read_path___024root___eval_static(&(vlSymsp->TOP));
        Vtb_read_path___024root___eval_initial(&(vlSymsp->TOP));
        Vtb_read_path___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vtb_read_path___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vtb_read_path::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vtb_read_path::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb_read_path::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vtb_read_path___024root___eval_final(Vtb_read_path___024root* vlSelf);

VL_ATTR_COLD void Vtb_read_path::final() {
    Vtb_read_path___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb_read_path::hierName() const { return vlSymsp->name(); }
const char* Vtb_read_path::modelName() const { return "Vtb_read_path"; }
unsigned Vtb_read_path::threads() const { return 1; }
void Vtb_read_path::prepareClone() const { contextp()->prepareClone(); }
void Vtb_read_path::atClone() const {
    contextp()->threadPoolpOnClone();
}
