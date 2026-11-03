// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_tensor_packer__pch.h"
#include "Vtb_tensor_packer.h"
#include "Vtb_tensor_packer___024root.h"

// FUNCTIONS
Vtb_tensor_packer__Syms::~Vtb_tensor_packer__Syms()
{
}

Vtb_tensor_packer__Syms::Vtb_tensor_packer__Syms(VerilatedContext* contextp, const char* namep, Vtb_tensor_packer* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(18);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_tb_tensor_packer.configure(this, name(), "tb_tensor_packer", "tb_tensor_packer", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
