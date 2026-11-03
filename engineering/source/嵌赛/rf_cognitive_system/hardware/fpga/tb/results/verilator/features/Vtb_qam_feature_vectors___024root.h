// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_qam_feature_vectors.h for the primary calling header

#ifndef VERILATED_VTB_QAM_FEATURE_VECTORS___024ROOT_H_
#define VERILATED_VTB_QAM_FEATURE_VECTORS___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_qam_feature_vectors__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_qam_feature_vectors___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ tb_qam_feature_vectors__DOT__clk;
    CData/*0:0*/ tb_qam_feature_vectors__DOT__rst_n;
    CData/*0:0*/ tb_qam_feature_vectors__DOT__s_valid;
    CData/*0:0*/ tb_qam_feature_vectors__DOT__s_frame_start;
    CData/*0:0*/ tb_qam_feature_vectors__DOT__s_frame_end;
    CData/*0:0*/ tb_qam_feature_vectors__DOT__m_valid;
    CData/*0:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_valid;
    CData/*0:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_frame_start;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_qam_feature_vectors__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_qam_feature_vectors__DOT__rst_n__0;
    CData/*0:0*/ __VactContinue;
    SData/*15:0*/ tb_qam_feature_vectors__DOT__s_i;
    SData/*15:0*/ tb_qam_feature_vectors__DOT__s_q;
    SData/*9:0*/ tb_qam_feature_vectors__DOT__s_sample_index;
    SData/*9:0*/ tb_qam_feature_vectors__DOT__m_sample_index;
    SData/*15:0*/ tb_qam_feature_vectors__DOT__dut__DOT__previous_i;
    SData/*15:0*/ tb_qam_feature_vectors__DOT__dut__DOT__previous_q;
    SData/*9:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_sample_index;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__s_frame_id;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__m_power;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__m_frame_id;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__input_index;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__output_count;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__output_file;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_i_square;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_q_square;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_i_i_prev;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_q_q_prev;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_q_i_prev;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_i_q_prev;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT__s1_frame_id;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_2;
    IData/*31:0*/ tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_3;
    IData/*31:0*/ __Vdly__tb_qam_feature_vectors__DOT__input_index;
    IData/*31:0*/ __VactIterCount;
    QData/*32:0*/ tb_qam_feature_vectors__DOT__m_lag_re;
    QData/*32:0*/ tb_qam_feature_vectors__DOT__m_lag_im;
    VlUnpacked<IData/*31:0*/, 19456> tb_qam_feature_vectors__DOT__input_mem;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_h70362baa__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<4> __VactTriggered;
    VlTriggerVec<4> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_qam_feature_vectors__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_qam_feature_vectors___024root(Vtb_qam_feature_vectors__Syms* symsp, const char* v__name);
    ~Vtb_qam_feature_vectors___024root();
    VL_UNCOPYABLE(Vtb_qam_feature_vectors___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
