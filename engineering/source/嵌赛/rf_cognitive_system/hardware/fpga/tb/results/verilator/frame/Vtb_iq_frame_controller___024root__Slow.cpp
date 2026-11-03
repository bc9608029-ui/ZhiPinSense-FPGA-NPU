// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_iq_frame_controller.h for the primary calling header

#include "Vtb_iq_frame_controller__pch.h"
#include "Vtb_iq_frame_controller__Syms.h"
#include "Vtb_iq_frame_controller___024root.h"

void Vtb_iq_frame_controller___024root___ctor_var_reset(Vtb_iq_frame_controller___024root* vlSelf);

Vtb_iq_frame_controller___024root::Vtb_iq_frame_controller___024root(Vtb_iq_frame_controller__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vtb_iq_frame_controller___024root___ctor_var_reset(this);
}

void Vtb_iq_frame_controller___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vtb_iq_frame_controller___024root::~Vtb_iq_frame_controller___024root() {
}
