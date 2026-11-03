// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VTB_IQ_FRAME_CONTROLLER__SYMS_H_
#define VERILATED_VTB_IQ_FRAME_CONTROLLER__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vtb_iq_frame_controller.h"

// INCLUDE MODULE CLASSES
#include "Vtb_iq_frame_controller___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vtb_iq_frame_controller__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vtb_iq_frame_controller* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vtb_iq_frame_controller___024root TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_tb_iq_frame_controller;

    // CONSTRUCTORS
    Vtb_iq_frame_controller__Syms(VerilatedContext* contextp, const char* namep, Vtb_iq_frame_controller* modelp);
    ~Vtb_iq_frame_controller__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
