// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_top_lite.h for the primary calling header

#ifndef VERILATED_VTB_TOP_LITE___024ROOT_H_
#define VERILATED_VTB_TOP_LITE___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_top_lite__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_top_lite___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    // Anonymous structures to workaround compiler member-count bugs
    struct {
        CData/*0:0*/ tb_top_lite__DOT__pl_clk;
        CData/*0:0*/ tb_top_lite__DOT__pl_key1_reset;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core_rst_n;
        CData/*0:0*/ tb_top_lite__DOT__s_valid;
        CData/*1:0*/ tb_top_lite__DOT__buffer_release;
        CData/*0:0*/ tb_top_lite__DOT__m_write_valid;
        CData/*0:0*/ tb_top_lite__DOT__m_irq;
        CData/*1:0*/ tb_top_lite__DOT__buffer_busy;
        CData/*3:0*/ tb_top_lite__DOT__pl_led;
        CData/*1:0*/ tb_top_lite__DOT__dut__DOT__reset_release;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__input_activity_toggle;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__frame_complete_toggle;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__sticky_error;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__fifo_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_valid;
        CData/*1:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_sample_index;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_frame_start;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_frame_end;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_error;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qi_s_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qq_s_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qp_s_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qr_s_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qm_s_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qi_valid;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qq_valid;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qp_valid;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qr_valid;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__qm_valid;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__meta_valid;
        CData/*1:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__meta_sample_index;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__meta_frame_start;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__meta_frame_end;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__meta_error;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__bundle_valid;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__meta_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quantizer_input_valid;
        CData/*1:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__write_pointer;
        CData/*1:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer;
        CData/*2:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__count;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__push;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__pop;
        CData/*1:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__sample_index;
        CData/*7:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__frame_id;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__frame_error_sticky;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_valid;
        CData/*1:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_sample_index;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_frame_start;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_frame_end;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_error;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__stage2_ready;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__saturated_comb;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__saturated_comb;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__saturated_comb;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__saturated_comb;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__saturated_comb;
        CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__fill_buffer;
        CData/*1:0*/ __Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer;
        CData/*2:0*/ __Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__count;
        CData/*1:0*/ __Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__sample_index;
        CData/*0:0*/ __Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__frame_error_sticky;
        CData/*0:0*/ __Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__fill_buffer;
        CData/*1:0*/ __VdlyDim0__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem__v0;
        CData/*0:0*/ __VdlySet__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem__v0;
    };
    struct {
        CData/*1:0*/ __VdlyDim0__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem__v0;
        CData/*1:0*/ __VdlyDim0__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__e_mem__v0;
        CData/*0:0*/ __VstlFirstIteration;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_clk__0;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_key1_reset__0;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_top_lite__DOT__dut__DOT__core_rst_n__0;
        CData/*0:0*/ __VactContinue;
        SData/*15:0*/ tb_top_lite__DOT__s_i;
        SData/*15:0*/ tb_top_lite__DOT__s_q;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__frame_i;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__frame_q;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_i;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_q;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__previous_i;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__previous_q;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i;
        SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q;
        SData/*15:0*/ __VdlyVal__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem__v0;
        SData/*15:0*/ __VdlyVal__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem__v0;
        IData/*31:0*/ tb_top_lite__DOT__overflow_count;
        IData/*31:0*/ tb_top_lite__DOT__sat_i;
        IData/*31:0*/ tb_top_lite__DOT__sat_q;
        IData/*31:0*/ tb_top_lite__DOT__sat_power;
        IData/*31:0*/ tb_top_lite__DOT__sat_re;
        IData/*31:0*/ tb_top_lite__DOT__sat_im;
        IData/*31:0*/ tb_top_lite__DOT__sent;
        IData/*31:0*/ tb_top_lite__DOT__received;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_power;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i_square;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q_square;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i_i_prev;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q_q_prev;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q_i_prev;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i_q_prev;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_0;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_1;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_2;
        IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_3;
        IData/*31:0*/ __Vdly__tb_top_lite__DOT__sent;
        IData/*31:0*/ __VactIterCount;
        QData/*32:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_re;
        QData/*32:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_im;
        VlUnpacked<SData/*15:0*/, 4> tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem;
        VlUnpacked<SData/*15:0*/, 4> tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem;
        VlUnpacked<CData/*0:0*/, 4> tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__e_mem;
    };
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_hb1cc4010__0;
    VlTriggerScheduler __VtrigSched_hb1cc4121__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<5> __VactTriggered;
    VlTriggerVec<5> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_top_lite__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_top_lite___024root(Vtb_top_lite__Syms* symsp, const char* v__name);
    ~Vtb_top_lite___024root();
    VL_UNCOPYABLE(Vtb_top_lite___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
