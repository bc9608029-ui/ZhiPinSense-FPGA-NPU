// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VTB_FEATURE_QUANTIZER__SYMS_H_
#define VERILATED_VTB_FEATURE_QUANTIZER__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vtb_feature_quantizer.h"

// INCLUDE MODULE CLASSES
#include "Vtb_feature_quantizer___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vtb_feature_quantizer__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vtb_feature_quantizer* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vtb_feature_quantizer___024root TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_tb_feature_quantizer;
    VerilatedScope __Vscope_tb_feature_quantizer__send_and_check;

    // CONSTRUCTORS
    Vtb_feature_quantizer__Syms(VerilatedContext* contextp, const char* namep, Vtb_feature_quantizer* modelp);
    ~Vtb_feature_quantizer__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
