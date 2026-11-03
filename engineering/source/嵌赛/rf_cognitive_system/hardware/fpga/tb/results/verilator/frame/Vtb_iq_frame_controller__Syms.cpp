// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_iq_frame_controller__pch.h"
#include "Vtb_iq_frame_controller.h"
#include "Vtb_iq_frame_controller___024root.h"

// FUNCTIONS
Vtb_iq_frame_controller__Syms::~Vtb_iq_frame_controller__Syms()
{
}

Vtb_iq_frame_controller__Syms::Vtb_iq_frame_controller__Syms(VerilatedContext* contextp, const char* namep, Vtb_iq_frame_controller* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(23);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_tb_iq_frame_controller.configure(this, name(), "tb_iq_frame_controller", "tb_iq_frame_controller", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
