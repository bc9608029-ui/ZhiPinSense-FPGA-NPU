// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_iq_stream_fifo.h for the primary calling header

#ifndef VERILATED_VTB_IQ_STREAM_FIFO___024ROOT_H_
#define VERILATED_VTB_IQ_STREAM_FIFO___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_iq_stream_fifo__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_iq_stream_fifo___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ tb_iq_stream_fifo__DOT__clk;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__rst_n;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__s_valid;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__s_overflow_event;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__m_ready;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__dut__DOT__write_pointer;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__dut__DOT__read_pointer;
    CData/*1:0*/ tb_iq_stream_fifo__DOT__dut__DOT__count;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__dut__DOT__push;
    CData/*0:0*/ tb_iq_stream_fifo__DOT__dut__DOT__pop;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__rst_n__0;
    CData/*0:0*/ __VactContinue;
    SData/*15:0*/ tb_iq_stream_fifo__DOT__s_i;
    SData/*15:0*/ tb_iq_stream_fifo__DOT__s_q;
    IData/*31:0*/ tb_iq_stream_fifo__DOT__overflow_count;
    IData/*31:0*/ __VactIterCount;
    VlUnpacked<SData/*15:0*/, 2> tb_iq_stream_fifo__DOT__dut__DOT__i_mem;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_h55ea73d2__0;
    VlTriggerScheduler __VtrigSched_h55ea7393__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<4> __VactTriggered;
    VlTriggerVec<4> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_iq_stream_fifo__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_iq_stream_fifo___024root(Vtb_iq_stream_fifo__Syms* symsp, const char* v__name);
    ~Vtb_iq_stream_fifo___024root();
    VL_UNCOPYABLE(Vtb_iq_stream_fifo___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
