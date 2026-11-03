// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vled_tb__pch.h"
#include "Vled_tb.h"
#include "Vled_tb___024root.h"

// FUNCTIONS
Vled_tb__Syms::~Vled_tb__Syms()
{
}

Vled_tb__Syms::Vled_tb__Syms(VerilatedContext* contextp, const char* namep, Vled_tb* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
        // Check resources
        Verilated::stackCheck(25);
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    // Setup scopes
    __Vscope_led_tb.configure(this, name(), "led_tb", "led_tb", "<null>", -9, VerilatedScope::SCOPE_OTHER);
    __Vscope_led_tb__check_led.configure(this, name(), "led_tb.check_led", "check_led", "<null>", -9, VerilatedScope::SCOPE_OTHER);
}
