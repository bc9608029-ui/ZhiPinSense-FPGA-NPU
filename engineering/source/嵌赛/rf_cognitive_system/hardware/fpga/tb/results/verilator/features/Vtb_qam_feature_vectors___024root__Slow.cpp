// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_qam_feature_vectors.h for the primary calling header

#include "Vtb_qam_feature_vectors__pch.h"
#include "Vtb_qam_feature_vectors__Syms.h"
#include "Vtb_qam_feature_vectors___024root.h"

void Vtb_qam_feature_vectors___024root___ctor_var_reset(Vtb_qam_feature_vectors___024root* vlSelf);

Vtb_qam_feature_vectors___024root::Vtb_qam_feature_vectors___024root(Vtb_qam_feature_vectors__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vtb_qam_feature_vectors___024root___ctor_var_reset(this);
}

void Vtb_qam_feature_vectors___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vtb_qam_feature_vectors___024root::~Vtb_qam_feature_vectors___024root() {
}
