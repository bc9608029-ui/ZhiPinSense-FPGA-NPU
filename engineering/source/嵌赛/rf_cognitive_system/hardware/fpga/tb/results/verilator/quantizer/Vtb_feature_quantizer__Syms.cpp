// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_feature_quantizer__pch.h"
#include "Vtb_feature_quantizer.h"
#include "Vtb_feature_quantizer___024root.h"

// FUNCTIONS
Vtb_feature_quantizer__Syms::~Vtb_feature_quantizer__Syms()
{
}

Vtb_feature_quantizer__Syms::Vtb_feature_quantizer__Syms(VerilatedContext* contextp, const char* namep, Vtb_feature_quantizer* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(288);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_tb_feature_quantizer.configure(this, name(), "tb_feature_quantizer", "tb_feature_quantizer", "<null>", -9, VerilatedScope::SCOPE_OTHER);
    __Vscope_tb_feature_quantizer__send_and_check.configure(this, name(), "tb_feature_quantizer.send_and_check", "send_and_check", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
