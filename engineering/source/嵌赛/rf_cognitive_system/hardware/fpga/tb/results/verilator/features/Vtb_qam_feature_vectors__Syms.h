// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VTB_QAM_FEATURE_VECTORS__SYMS_H_
#define VERILATED_VTB_QAM_FEATURE_VECTORS__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vtb_qam_feature_vectors.h"

// INCLUDE MODULE CLASSES
#include "Vtb_qam_feature_vectors___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vtb_qam_feature_vectors__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vtb_qam_feature_vectors* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vtb_qam_feature_vectors___024root TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_tb_qam_feature_vectors;

    // CONSTRUCTORS
    Vtb_qam_feature_vectors__Syms(VerilatedContext* contextp, const char* namep, Vtb_qam_feature_vectors* modelp);
    ~Vtb_qam_feature_vectors__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
