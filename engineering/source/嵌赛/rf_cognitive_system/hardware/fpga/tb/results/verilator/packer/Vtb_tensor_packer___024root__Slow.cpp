// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_tensor_packer.h for the primary calling header

#include "Vtb_tensor_packer__pch.h"
#include "Vtb_tensor_packer__Syms.h"
#include "Vtb_tensor_packer___024root.h"

void Vtb_tensor_packer___024root___ctor_var_reset(Vtb_tensor_packer___024root* vlSelf);

Vtb_tensor_packer___024root::Vtb_tensor_packer___024root(Vtb_tensor_packer__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vtb_tensor_packer___024root___ctor_var_reset(this);
}

void Vtb_tensor_packer___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vtb_tensor_packer___024root::~Vtb_tensor_packer___024root() {
}
