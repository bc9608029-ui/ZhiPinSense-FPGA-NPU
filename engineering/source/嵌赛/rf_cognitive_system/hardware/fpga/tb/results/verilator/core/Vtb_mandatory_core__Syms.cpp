// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_mandatory_core__pch.h"
#include "Vtb_mandatory_core.h"
#include "Vtb_mandatory_core___024root.h"

// FUNCTIONS
Vtb_mandatory_core__Syms::~Vtb_mandatory_core__Syms()
{
}

Vtb_mandatory_core__Syms::Vtb_mandatory_core__Syms(VerilatedContext* contextp, const char* namep, Vtb_mandatory_core* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(1858);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_tb_mandatory_core.configure(this, name(), "tb_mandatory_core", "tb_mandatory_core", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
