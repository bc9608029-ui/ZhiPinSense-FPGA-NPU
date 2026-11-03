// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_mandatory_core.h for the primary calling header

#ifndef VERILATED_VTB_MANDATORY_CORE___024ROOT_H_
#define VERILATED_VTB_MANDATORY_CORE___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_mandatory_core__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_mandatory_core___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    // Anonymous structures to workaround compiler member-count bugs
    struct {
        CData/*0:0*/ tb_mandatory_core__DOT__clk;
        CData/*0:0*/ tb_mandatory_core__DOT__rst_n;
        CData/*0:0*/ tb_mandatory_core__DOT__s_valid;
        CData/*1:0*/ tb_mandatory_core__DOT__buffer_release;
        CData/*0:0*/ tb_mandatory_core__DOT__m_write_valid;
        CData/*1:0*/ tb_mandatory_core__DOT__buffer_busy;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__fifo_ready;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__feature_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__feature_frame_end;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qi_s_ready;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qq_s_ready;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qp_s_ready;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qr_s_ready;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qm_s_ready;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qi_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qq_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qp_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qr_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__qm_valid;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__qi_data;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__qq_data;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__qp_data;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__qr_data;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__qm_data;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__meta_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__meta_frame_end;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__bundle_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__meta_ready;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid;
        CData/*3:0*/ tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer;
        CData/*3:0*/ tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer;
        CData/*4:0*/ tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__push;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__pop;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_valid;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_start;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_end;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__stage2_ready;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__quantized_comb;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__quantized_comb;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__quantized_comb;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__quantized_comb;
        CData/*7:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__quantized_comb;
        CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer;
        CData/*4:0*/ __Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count;
        CData/*0:0*/ __Vdly__tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer;
        CData/*0:0*/ __VstlFirstIteration;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_mandatory_core__DOT__clk__0;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_mandatory_core__DOT__rst_n__0;
        CData/*0:0*/ __VactContinue;
        SData/*15:0*/ tb_mandatory_core__DOT__s_i;
        SData/*15:0*/ tb_mandatory_core__DOT__s_q;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__frame_i;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__frame_q;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__feature_i;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__feature_q;
        SData/*9:0*/ tb_mandatory_core__DOT__dut__DOT__feature_sample_index;
        SData/*9:0*/ tb_mandatory_core__DOT__dut__DOT__meta_sample_index;
        SData/*9:0*/ tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_i;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_q;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i;
        SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q;
    };
    struct {
        SData/*9:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_sample_index;
        SData/*9:0*/ __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index;
        IData/*31:0*/ tb_mandatory_core__DOT__input_index;
        IData/*31:0*/ tb_mandatory_core__DOT__output_count;
        IData/*31:0*/ tb_mandatory_core__DOT__output_file;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__feature_power;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__feature_frame_id;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__meta_frame_id;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_square;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_square;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_i_prev;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_q_prev;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_i_prev;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_q_prev;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_id;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_0;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_1;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_2;
        IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_3;
        IData/*31:0*/ __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id;
        IData/*31:0*/ __VactIterCount;
        QData/*32:0*/ tb_mandatory_core__DOT__dut__DOT__feature_lag_re;
        QData/*32:0*/ tb_mandatory_core__DOT__dut__DOT__feature_lag_im;
        VlUnpacked<IData/*31:0*/, 19456> tb_mandatory_core__DOT__input_mem;
        VlUnpacked<SData/*15:0*/, 16> tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem;
        VlUnpacked<SData/*15:0*/, 16> tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem;
        VlUnpacked<CData/*0:0*/, 16> tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__e_mem;
    };
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_h103dc9c4__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<4> __VactTriggered;
    VlTriggerVec<4> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_mandatory_core__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_mandatory_core___024root(Vtb_mandatory_core__Syms* symsp, const char* v__name);
    ~Vtb_mandatory_core___024root();
    VL_UNCOPYABLE(Vtb_mandatory_core___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
