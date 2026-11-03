// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VLED_TB__SYMS_H_
#define VERILATED_VLED_TB__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vled_tb.h"

// INCLUDE MODULE CLASSES
#include "Vled_tb___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vled_tb__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vled_tb* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vled_tb___024root              TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_led_tb;
    VerilatedScope __Vscope_led_tb__check_led;

    // CONSTRUCTORS
    Vled_tb__Syms(VerilatedContext* contextp, const char* namep, Vled_tb* modelp);
    ~Vled_tb__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
