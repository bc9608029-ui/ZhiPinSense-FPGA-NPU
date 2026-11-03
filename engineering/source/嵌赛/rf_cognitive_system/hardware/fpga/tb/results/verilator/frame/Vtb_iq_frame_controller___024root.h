// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_iq_frame_controller.h for the primary calling header

#ifndef VERILATED_VTB_IQ_FRAME_CONTROLLER___024ROOT_H_
#define VERILATED_VTB_IQ_FRAME_CONTROLLER___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_iq_frame_controller__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_iq_frame_controller___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ tb_iq_frame_controller__DOT__clk;
    CData/*0:0*/ tb_iq_frame_controller__DOT__rst_n;
    CData/*0:0*/ tb_iq_frame_controller__DOT__s_error;
    CData/*0:0*/ tb_iq_frame_controller__DOT__s_valid;
    CData/*0:0*/ tb_iq_frame_controller__DOT__m_ready;
    CData/*1:0*/ tb_iq_frame_controller__DOT__dut__DOT__sample_index;
    CData/*7:0*/ tb_iq_frame_controller__DOT__dut__DOT__frame_id;
    CData/*0:0*/ tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky;
    CData/*0:0*/ __Vdly__tb_iq_frame_controller__DOT__m_ready;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__rst_n__0;
    CData/*0:0*/ __VactContinue;
    IData/*31:0*/ tb_iq_frame_controller__DOT__sent;
    IData/*31:0*/ tb_iq_frame_controller__DOT__received;
    IData/*31:0*/ __Vdly__tb_iq_frame_controller__DOT__sent;
    IData/*31:0*/ __VactIterCount;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_h99a03233__0;
    VlTriggerVec<4> __VactTriggered;
    VlTriggerVec<4> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_iq_frame_controller__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_iq_frame_controller___024root(Vtb_iq_frame_controller__Syms* symsp, const char* v__name);
    ~Vtb_iq_frame_controller___024root();
    VL_UNCOPYABLE(Vtb_iq_frame_controller___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
