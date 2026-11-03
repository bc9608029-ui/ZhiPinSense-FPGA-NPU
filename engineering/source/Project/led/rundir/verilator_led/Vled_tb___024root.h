// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vled_tb.h for the primary calling header

#ifndef VERILATED_VLED_TB___024ROOT_H_
#define VERILATED_VLED_TB___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vled_tb__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vled_tb___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ led_tb__DOT__clk;
    CData/*0:0*/ led_tb__DOT__rst_n;
    CData/*3:0*/ led_tb__DOT__dut__DOT__led_pattern;
    CData/*0:0*/ __Vtrigprevexpr___TOP__led_tb__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__led_tb__DOT__rst_n__0;
    CData/*0:0*/ __VactContinue;
    IData/*31:0*/ led_tb__DOT__dut__DOT__divider_count;
    IData/*31:0*/ __VactIterCount;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_hbf655e20__0;
    VlTriggerVec<3> __VactTriggered;
    VlTriggerVec<3> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vled_tb__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vled_tb___024root(Vled_tb__Syms* symsp, const char* v__name);
    ~Vled_tb___024root();
    VL_UNCOPYABLE(Vled_tb___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
