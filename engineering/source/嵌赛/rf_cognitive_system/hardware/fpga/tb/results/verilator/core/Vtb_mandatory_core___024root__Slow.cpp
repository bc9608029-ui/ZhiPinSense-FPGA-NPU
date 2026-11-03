// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_mandatory_core.h for the primary calling header

#include "Vtb_mandatory_core__pch.h"
#include "Vtb_mandatory_core__Syms.h"
#include "Vtb_mandatory_core___024root.h"

void Vtb_mandatory_core___024root___ctor_var_reset(Vtb_mandatory_core___024root* vlSelf);

Vtb_mandatory_core___024root::Vtb_mandatory_core___024root(Vtb_mandatory_core__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vtb_mandatory_core___024root___ctor_var_reset(this);
}

void Vtb_mandatory_core___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vtb_mandatory_core___024root::~Vtb_mandatory_core___024root() {
}
