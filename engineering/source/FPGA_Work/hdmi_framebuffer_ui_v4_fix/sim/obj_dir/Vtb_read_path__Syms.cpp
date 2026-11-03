// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_read_path__pch.h"
#include "Vtb_read_path.h"
#include "Vtb_read_path___024root.h"

// FUNCTIONS
Vtb_read_path__Syms::~Vtb_read_path__Syms()
{
}

Vtb_read_path__Syms::Vtb_read_path__Syms(VerilatedContext* contextp, const char* namep, Vtb_read_path* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(114);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
}
