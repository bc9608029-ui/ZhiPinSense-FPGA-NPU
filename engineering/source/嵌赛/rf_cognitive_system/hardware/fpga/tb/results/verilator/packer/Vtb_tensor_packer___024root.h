// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_tensor_packer.h for the primary calling header

#ifndef VERILATED_VTB_TENSOR_PACKER___024ROOT_H_
#define VERILATED_VTB_TENSOR_PACKER___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_tensor_packer__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_tensor_packer___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ tb_tensor_packer__DOT__clk;
    CData/*0:0*/ tb_tensor_packer__DOT__rst_n;
    CData/*1:0*/ tb_tensor_packer__DOT__s_sample_index;
    CData/*7:0*/ tb_tensor_packer__DOT__s_frame_id;
    CData/*0:0*/ tb_tensor_packer__DOT__s_frame_end;
    CData/*0:0*/ tb_tensor_packer__DOT__s_valid;
    CData/*1:0*/ tb_tensor_packer__DOT__buffer_release;
    CData/*0:0*/ tb_tensor_packer__DOT__m_write_valid;
    CData/*1:0*/ tb_tensor_packer__DOT__buffer_busy;
    CData/*0:0*/ tb_tensor_packer__DOT__dut__DOT__fill_buffer;
    CData/*0:0*/ tb_tensor_packer__DOT__dut__DOT__selected_buffer_available;
    CData/*0:0*/ __Vdly__tb_tensor_packer__DOT__dut__DOT__fill_buffer;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_tensor_packer__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_tensor_packer__DOT__rst_n__0;
    CData/*0:0*/ __VactContinue;
    IData/*31:0*/ tb_tensor_packer__DOT__sample;
    IData/*31:0*/ __Vdly__tb_tensor_packer__DOT__sample;
    IData/*31:0*/ __VactIterCount;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_hd28c5fbb__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<4> __VactTriggered;
    VlTriggerVec<4> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_tensor_packer__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_tensor_packer___024root(Vtb_tensor_packer__Syms* symsp, const char* v__name);
    ~Vtb_tensor_packer___024root();
    VL_UNCOPYABLE(Vtb_tensor_packer___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
