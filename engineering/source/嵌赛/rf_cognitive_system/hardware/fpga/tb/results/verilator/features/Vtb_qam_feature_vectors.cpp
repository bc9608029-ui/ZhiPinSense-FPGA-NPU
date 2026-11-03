// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb_qam_feature_vectors__pch.h"

//============================================================
// Constructors

Vtb_qam_feature_vectors::Vtb_qam_feature_vectors(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb_qam_feature_vectors__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vtb_qam_feature_vectors::Vtb_qam_feature_vectors(const char* _vcname__)
    : Vtb_qam_feature_vectors(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb_qam_feature_vectors::~Vtb_qam_feature_vectors() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb_qam_feature_vectors___024root___eval_debug_assertions(Vtb_qam_feature_vectors___024root* vlSelf);
#endif  // VL_DEBUG
void Vtb_qam_feature_vectors___024root___eval_static(Vtb_qam_feature_vectors___024root* vlSelf);
void Vtb_qam_feature_vectors___024root___eval_initial(Vtb_qam_feature_vectors___024root* vlSelf);
void Vtb_qam_feature_vectors___024root___eval_settle(Vtb_qam_feature_vectors___024root* vlSelf);
void Vtb_qam_feature_vectors___024root___eval(Vtb_qam_feature_vectors___024root* vlSelf);

void Vtb_qam_feature_vectors::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb_qam_feature_vectors::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vtb_qam_feature_vectors___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vtb_qam_feature_vectors___024root___eval_static(&(vlSymsp->TOP));
        Vtb_qam_feature_vectors___024root___eval_initial(&(vlSymsp->TOP));
        Vtb_qam_feature_vectors___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vtb_qam_feature_vectors___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vtb_qam_feature_vectors::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vtb_qam_feature_vectors::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb_qam_feature_vectors::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vtb_qam_feature_vectors___024root___eval_final(Vtb_qam_feature_vectors___024root* vlSelf);

VL_ATTR_COLD void Vtb_qam_feature_vectors::final() {
    Vtb_qam_feature_vectors___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb_qam_feature_vectors::hierName() const { return vlSymsp->name(); }
const char* Vtb_qam_feature_vectors::modelName() const { return "Vtb_qam_feature_vectors"; }
unsigned Vtb_qam_feature_vectors::threads() const { return 1; }
void Vtb_qam_feature_vectors::prepareClone() const { contextp()->prepareClone(); }
void Vtb_qam_feature_vectors::atClone() const {
    contextp()->threadPoolpOnClone();
}
