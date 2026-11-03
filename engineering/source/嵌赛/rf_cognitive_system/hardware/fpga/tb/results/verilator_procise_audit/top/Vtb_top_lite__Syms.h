// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VTB_TOP_LITE__SYMS_H_
#define VERILATED_VTB_TOP_LITE__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vtb_top_lite.h"

// INCLUDE MODULE CLASSES
#include "Vtb_top_lite___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vtb_top_lite__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vtb_top_lite* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vtb_top_lite___024root         TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_tb_top_lite;

    // CONSTRUCTORS
    Vtb_top_lite__Syms(VerilatedContext* contextp, const char* namep, Vtb_top_lite* modelp);
    ~Vtb_top_lite__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
