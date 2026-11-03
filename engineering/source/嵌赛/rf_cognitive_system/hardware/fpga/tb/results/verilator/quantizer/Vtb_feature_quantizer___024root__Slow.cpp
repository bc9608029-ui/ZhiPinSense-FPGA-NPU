// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_feature_quantizer.h for the primary calling header

#include "Vtb_feature_quantizer__pch.h"
#include "Vtb_feature_quantizer__Syms.h"
#include "Vtb_feature_quantizer___024root.h"

void Vtb_feature_quantizer___024root___ctor_var_reset(Vtb_feature_quantizer___024root* vlSelf);

Vtb_feature_quantizer___024root::Vtb_feature_quantizer___024root(Vtb_feature_quantizer__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vtb_feature_quantizer___024root___ctor_var_reset(this);
}

void Vtb_feature_quantizer___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vtb_feature_quantizer___024root::~Vtb_feature_quantizer___024root() {
}
