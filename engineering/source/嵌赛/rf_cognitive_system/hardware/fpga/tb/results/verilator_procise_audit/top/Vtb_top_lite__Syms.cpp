// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_top_lite__pch.h"
#include "Vtb_top_lite.h"
#include "Vtb_top_lite___024root.h"

// FUNCTIONS
Vtb_top_lite__Syms::~Vtb_top_lite__Syms()
{
}

Vtb_top_lite__Syms::Vtb_top_lite__Syms(VerilatedContext* contextp, const char* namep, Vtb_top_lite* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(1768);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_tb_top_lite.configure(this, name(), "tb_top_lite", "tb_top_lite", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
