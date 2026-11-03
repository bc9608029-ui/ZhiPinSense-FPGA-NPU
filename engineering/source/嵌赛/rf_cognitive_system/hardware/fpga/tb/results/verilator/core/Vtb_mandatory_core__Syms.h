// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VTB_MANDATORY_CORE__SYMS_H_
#define VERILATED_VTB_MANDATORY_CORE__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vtb_mandatory_core.h"

// INCLUDE MODULE CLASSES
#include "Vtb_mandatory_core___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vtb_mandatory_core__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vtb_mandatory_core* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vtb_mandatory_core___024root   TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_tb_mandatory_core;

    // CONSTRUCTORS
    Vtb_mandatory_core__Syms(VerilatedContext* contextp, const char* namep, Vtb_mandatory_core* modelp);
    ~Vtb_mandatory_core__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
