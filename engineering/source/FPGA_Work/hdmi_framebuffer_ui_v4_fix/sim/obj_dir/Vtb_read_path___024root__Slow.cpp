// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_read_path.h for the primary calling header

#include "Vtb_read_path__pch.h"
#include "Vtb_read_path__Syms.h"
#include "Vtb_read_path___024root.h"

void Vtb_read_path___024root___ctor_var_reset(Vtb_read_path___024root* vlSelf);

Vtb_read_path___024root::Vtb_read_path___024root(Vtb_read_path__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vtb_read_path___024root___ctor_var_reset(this);
}

void Vtb_read_path___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vtb_read_path___024root::~Vtb_read_path___024root() {
}
