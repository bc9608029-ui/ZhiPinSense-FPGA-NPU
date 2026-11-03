// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_iq_stream_fifo__pch.h"
#include "Vtb_iq_stream_fifo.h"
#include "Vtb_iq_stream_fifo___024root.h"

// FUNCTIONS
Vtb_iq_stream_fifo__Syms::~Vtb_iq_stream_fifo__Syms()
{
}

Vtb_iq_stream_fifo__Syms::Vtb_iq_stream_fifo__Syms(VerilatedContext* contextp, const char* namep, Vtb_iq_stream_fifo* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(62);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_tb_iq_stream_fifo.configure(this, name(), "tb_iq_stream_fifo", "tb_iq_stream_fifo", "<null>", -9, VerilatedScope::SCOPE_OTHER);
    __Vscope_tb_iq_stream_fifo__pop_and_check.configure(this, name(), "tb_iq_stream_fifo.pop_and_check", "pop_and_check", "<null>", -9, VerilatedScope::SCOPE_OTHER);
    __Vscope_tb_iq_stream_fifo__push.configure(this, name(), "tb_iq_stream_fifo.push", "push", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
