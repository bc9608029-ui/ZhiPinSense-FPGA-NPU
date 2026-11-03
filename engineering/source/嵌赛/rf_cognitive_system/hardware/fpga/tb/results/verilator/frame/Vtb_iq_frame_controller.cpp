// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb_iq_frame_controller__pch.h"

//============================================================
// Constructors

Vtb_iq_frame_controller::Vtb_iq_frame_controller(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb_iq_frame_controller__Syms(contextp(), _vcname__, this)}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vtb_iq_frame_controller::Vtb_iq_frame_controller(const char* _vcname__)
    : Vtb_iq_frame_controller(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb_iq_frame_controller::~Vtb_iq_frame_controller() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb_iq_frame_controller___024root___eval_debug_assertions(Vtb_iq_frame_controller___024root* vlSelf);
#endif  // VL_DEBUG
void Vtb_iq_frame_controller___024root___eval_static(Vtb_iq_frame_controller___024root* vlSelf);
void Vtb_iq_frame_controller___024root___eval_initial(Vtb_iq_frame_controller___024root* vlSelf);
void Vtb_iq_frame_controller___024root___eval_settle(Vtb_iq_frame_controller___024root* vlSelf);
void Vtb_iq_frame_controller___024root___eval(Vtb_iq_frame_controller___024root* vlSelf);

void Vtb_iq_frame_controller::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb_iq_frame_controller::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vtb_iq_frame_controller___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vtb_iq_frame_controller___024root___eval_static(&(vlSymsp->TOP));
        Vtb_iq_frame_controller___024root___eval_initial(&(vlSymsp->TOP));
        Vtb_iq_frame_controller___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vtb_iq_frame_controller___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vtb_iq_frame_controller::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vtb_iq_frame_controller::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb_iq_frame_controller::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vtb_iq_frame_controller___024root___eval_final(Vtb_iq_frame_controller___024root* vlSelf);

VL_ATTR_COLD void Vtb_iq_frame_controller::final() {
    Vtb_iq_frame_controller___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb_iq_frame_controller::hierName() const { return vlSymsp->name(); }
const char* Vtb_iq_frame_controller::modelName() const { return "Vtb_iq_frame_controller"; }
unsigned Vtb_iq_frame_controller::threads() const { return 1; }
void Vtb_iq_frame_controller::prepareClone() const { contextp()->prepareClone(); }
void Vtb_iq_frame_controller::atClone() const {
    contextp()->threadPoolpOnClone();
}
