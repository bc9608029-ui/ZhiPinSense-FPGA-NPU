// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_feature_quantizer.h for the primary calling header

#ifndef VERILATED_VTB_FEATURE_QUANTIZER___024ROOT_H_
#define VERILATED_VTB_FEATURE_QUANTIZER___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_feature_quantizer__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_feature_quantizer___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ tb_feature_quantizer__DOT__clk;
    CData/*0:0*/ tb_feature_quantizer__DOT__rst_n;
    CData/*0:0*/ tb_feature_quantizer__DOT__s_valid;
    CData/*7:0*/ tb_feature_quantizer__DOT__m_data;
    CData/*0:0*/ tb_feature_quantizer__DOT__m_saturated;
    CData/*0:0*/ tb_feature_quantizer__DOT__m_valid;
    CData/*7:0*/ tb_feature_quantizer__DOT__dut__DOT__quantized_comb;
    CData/*0:0*/ tb_feature_quantizer__DOT__dut__DOT__saturated_comb;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__rst_n__0;
    CData/*0:0*/ __VactContinue;
    SData/*15:0*/ tb_feature_quantizer__DOT__s_data;
    IData/*31:0*/ tb_feature_quantizer__DOT__saturation_count;
    IData/*31:0*/ __VactIterCount;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_hc1ab7e2d__0;
    VlTriggerScheduler __VtrigSched_hc1ab7eec__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<4> __VactTriggered;
    VlTriggerVec<4> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_feature_quantizer__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_feature_quantizer___024root(Vtb_feature_quantizer__Syms* symsp, const char* v__name);
    ~Vtb_feature_quantizer___024root();
    VL_UNCOPYABLE(Vtb_feature_quantizer___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
