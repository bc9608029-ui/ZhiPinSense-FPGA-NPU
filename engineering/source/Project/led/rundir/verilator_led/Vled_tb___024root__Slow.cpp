// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vled_tb.h for the primary calling header

#include "Vled_tb__pch.h"
#include "Vled_tb__Syms.h"
#include "Vled_tb___024root.h"

void Vled_tb___024root___ctor_var_reset(Vled_tb___024root* vlSelf);

Vled_tb___024root::Vled_tb___024root(Vled_tb__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vled_tb___024root___ctor_var_reset(this);
}

void Vled_tb___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vled_tb___024root::~Vled_tb___024root() {
}
