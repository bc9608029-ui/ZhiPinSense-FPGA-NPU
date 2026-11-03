// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_qam_feature_vectors__pch.h"
#include "Vtb_qam_feature_vectors.h"
#include "Vtb_qam_feature_vectors___024root.h"

// FUNCTIONS
Vtb_qam_feature_vectors__Syms::~Vtb_qam_feature_vectors__Syms()
{
}

Vtb_qam_feature_vectors__Syms::Vtb_qam_feature_vectors__Syms(VerilatedContext* contextp, const char* namep, Vtb_qam_feature_vectors* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(74);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_tb_qam_feature_vectors.configure(this, name(), "tb_qam_feature_vectors", "tb_qam_feature_vectors", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
