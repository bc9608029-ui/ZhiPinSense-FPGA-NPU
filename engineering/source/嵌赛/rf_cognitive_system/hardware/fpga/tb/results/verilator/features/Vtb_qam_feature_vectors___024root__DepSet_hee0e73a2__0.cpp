// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_qam_feature_vectors.h for the primary calling header

#include "Vtb_qam_feature_vectors__pch.h"
#include "Vtb_qam_feature_vectors___024root.h"

VlCoroutine Vtb_qam_feature_vectors___024root___eval_initial__TOP__Vtiming__0(Vtb_qam_feature_vectors___024root* vlSelf);
VlCoroutine Vtb_qam_feature_vectors___024root___eval_initial__TOP__Vtiming__1(Vtb_qam_feature_vectors___024root* vlSelf);

void Vtb_qam_feature_vectors___024root___eval_initial(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_qam_feature_vectors___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_qam_feature_vectors___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__tb_qam_feature_vectors__DOT__clk__0 
        = vlSelfRef.tb_qam_feature_vectors__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_qam_feature_vectors__DOT__rst_n__0 
        = vlSelfRef.tb_qam_feature_vectors__DOT__rst_n;
}

VL_INLINE_OPT VlCoroutine Vtb_qam_feature_vectors___024root___eval_initial__TOP__Vtiming__1(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "tb/integration/tb_qam_feature_vectors.sv", 
                                             27);
        vlSelfRef.tb_qam_feature_vectors__DOT__clk 
            = (1U & (~ (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__clk)));
    }
}

void Vtb_qam_feature_vectors___024root___eval_act(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__0(Vtb_qam_feature_vectors___024root* vlSelf);
void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__1(Vtb_qam_feature_vectors___024root* vlSelf);
void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__2(Vtb_qam_feature_vectors___024root* vlSelf);
void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__3(Vtb_qam_feature_vectors___024root* vlSelf);
void Vtb_qam_feature_vectors___024root___nba_comb__TOP__0(Vtb_qam_feature_vectors___024root* vlSelf);

void Vtb_qam_feature_vectors___024root___eval_nba(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_qam_feature_vectors___024root___nba_sequent__TOP__0(vlSelf);
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_qam_feature_vectors___024root___nba_sequent__TOP__1(vlSelf);
    }
    if ((6ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_qam_feature_vectors___024root___nba_sequent__TOP__2(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_qam_feature_vectors___024root___nba_sequent__TOP__3(vlSelf);
    }
    if ((7ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_qam_feature_vectors___024root___nba_comb__TOP__0(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__0(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vdly__tb_qam_feature_vectors__DOT__input_index 
        = vlSelfRef.tb_qam_feature_vectors__DOT__input_index;
}

VL_INLINE_OPT void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__1(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___nba_sequent__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vdly__tb_qam_feature_vectors__DOT__output_count;
    __Vdly__tb_qam_feature_vectors__DOT__output_count = 0;
    // Body
    __Vdly__tb_qam_feature_vectors__DOT__output_count 
        = vlSelfRef.tb_qam_feature_vectors__DOT__output_count;
    if (VL_UNLIKELY(((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__rst_n) 
                     & (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__m_valid)))) {
        VL_FWRITEF_NX(vlSelfRef.tb_qam_feature_vectors__DOT__output_file,"%0#,%0#,%0#,%0d,%0d\n",0,
                      32,vlSelfRef.tb_qam_feature_vectors__DOT__m_frame_id,
                      10,(IData)(vlSelfRef.tb_qam_feature_vectors__DOT__m_sample_index),
                      32,vlSelfRef.tb_qam_feature_vectors__DOT__m_power,
                      33,vlSelfRef.tb_qam_feature_vectors__DOT__m_lag_re,
                      33,vlSelfRef.tb_qam_feature_vectors__DOT__m_lag_im);
        __Vdly__tb_qam_feature_vectors__DOT__output_count 
            = ((IData)(1U) + vlSelfRef.tb_qam_feature_vectors__DOT__output_count);
        if (VL_UNLIKELY((0x4c00U == ((IData)(1U) + vlSelfRef.tb_qam_feature_vectors__DOT__output_count)))) {
            VL_FCLOSE_I(vlSelfRef.tb_qam_feature_vectors__DOT__output_file); VL_WRITEF_NX("PASS tb_qam_feature_vectors samples=19456\n",0);
            VL_FINISH_MT("tb/integration/tb_qam_feature_vectors.sv", 61, "");
        }
    }
    vlSelfRef.tb_qam_feature_vectors__DOT__output_count 
        = __Vdly__tb_qam_feature_vectors__DOT__output_count;
}

VL_INLINE_OPT void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__2(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___nba_sequent__TOP__2\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb_qam_feature_vectors__DOT__rst_n) {
        if (vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_valid) {
            vlSelfRef.tb_qam_feature_vectors__DOT__m_valid = 1U;
            vlSelfRef.tb_qam_feature_vectors__DOT__m_power 
                = (vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_square 
                   + vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_square);
            if (vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_frame_start) {
                vlSelfRef.tb_qam_feature_vectors__DOT__m_lag_re = 0ULL;
                vlSelfRef.tb_qam_feature_vectors__DOT__m_lag_im = 0ULL;
            } else {
                vlSelfRef.tb_qam_feature_vectors__DOT__m_lag_re 
                    = (0x1ffffffffULL & ((((QData)((IData)(
                                                           (vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_i_prev 
                                                            >> 0x1fU))) 
                                           << 0x20U) 
                                          | (QData)((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_i_prev))) 
                                         + (((QData)((IData)(
                                                             (vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_q_prev 
                                                              >> 0x1fU))) 
                                             << 0x20U) 
                                            | (QData)((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_q_prev)))));
                vlSelfRef.tb_qam_feature_vectors__DOT__m_lag_im 
                    = (0x1ffffffffULL & ((((QData)((IData)(
                                                           (vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_i_prev 
                                                            >> 0x1fU))) 
                                           << 0x20U) 
                                          | (QData)((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_i_prev))) 
                                         - (((QData)((IData)(
                                                             (vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_q_prev 
                                                              >> 0x1fU))) 
                                             << 0x20U) 
                                            | (QData)((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_q_prev)))));
            }
            vlSelfRef.tb_qam_feature_vectors__DOT__m_sample_index 
                = vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_sample_index;
            vlSelfRef.tb_qam_feature_vectors__DOT__m_frame_id 
                = vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_frame_id;
        } else {
            vlSelfRef.tb_qam_feature_vectors__DOT__m_valid = 0U;
        }
        if (vlSelfRef.tb_qam_feature_vectors__DOT__s_valid) {
            if (vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_end) {
                vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_i = 0U;
                vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_q = 0U;
            } else {
                vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_i 
                    = vlSelfRef.tb_qam_feature_vectors__DOT__s_i;
                vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_q 
                    = vlSelfRef.tb_qam_feature_vectors__DOT__s_q;
            }
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_sample_index 
                = vlSelfRef.tb_qam_feature_vectors__DOT__s_sample_index;
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_frame_id 
                = vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_id;
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_square 
                = VL_MULS_III(32, VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_i)), 
                              VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_i)));
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_square 
                = VL_MULS_III(32, VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_q)), 
                              VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_q)));
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_frame_start 
                = vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_start;
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_i_prev 
                = VL_MULS_III(32, VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_i)), vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_2);
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_q_prev 
                = VL_MULS_III(32, VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_q)), vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_3);
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_q_i_prev 
                = VL_MULS_III(32, VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_q)), vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_2);
            vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_i_q_prev 
                = VL_MULS_III(32, VL_EXTENDS_II(32,16, (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_i)), vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_3);
        }
    } else {
        vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_i = 0U;
        vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_q = 0U;
        vlSelfRef.tb_qam_feature_vectors__DOT__m_valid = 0U;
    }
    vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__s1_valid 
        = ((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__rst_n) 
           && (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_valid));
}

VL_INLINE_OPT void Vtb_qam_feature_vectors___024root___nba_sequent__TOP__3(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___nba_sequent__TOP__3\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__rst_n) 
         & VL_GTS_III(32, 0x4c00U, vlSelfRef.tb_qam_feature_vectors__DOT__input_index))) {
        vlSelfRef.tb_qam_feature_vectors__DOT__s_i 
            = ((0x4bffU >= (0x7fffU & vlSelfRef.tb_qam_feature_vectors__DOT__input_index))
                ? (0xffffU & vlSelfRef.tb_qam_feature_vectors__DOT__input_mem
                   [(0x7fffU & vlSelfRef.tb_qam_feature_vectors__DOT__input_index)])
                : 0U);
        vlSelfRef.tb_qam_feature_vectors__DOT__s_valid = 1U;
        vlSelfRef.tb_qam_feature_vectors__DOT__s_q 
            = (((0x4bffU >= (0x7fffU & vlSelfRef.tb_qam_feature_vectors__DOT__input_index))
                 ? vlSelfRef.tb_qam_feature_vectors__DOT__input_mem
                [(0x7fffU & vlSelfRef.tb_qam_feature_vectors__DOT__input_index)]
                 : 0U) >> 0x10U);
        vlSelfRef.tb_qam_feature_vectors__DOT__s_sample_index 
            = (0x3ffU & VL_MODDIVS_III(32, vlSelfRef.tb_qam_feature_vectors__DOT__input_index, (IData)(0x400U)));
        vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_id 
            = VL_DIVS_III(32, vlSelfRef.tb_qam_feature_vectors__DOT__input_index, (IData)(0x400U));
        vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_start 
            = (0U == VL_MODDIVS_III(32, vlSelfRef.tb_qam_feature_vectors__DOT__input_index, (IData)(0x400U)));
        vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_end 
            = (0x3ffU == VL_MODDIVS_III(32, vlSelfRef.tb_qam_feature_vectors__DOT__input_index, (IData)(0x400U)));
        vlSelfRef.__Vdly__tb_qam_feature_vectors__DOT__input_index 
            = ((IData)(1U) + vlSelfRef.tb_qam_feature_vectors__DOT__input_index);
    } else if (VL_LTES_III(32, 0x4c00U, vlSelfRef.tb_qam_feature_vectors__DOT__input_index)) {
        vlSelfRef.tb_qam_feature_vectors__DOT__s_valid = 0U;
    }
    vlSelfRef.tb_qam_feature_vectors__DOT__input_index 
        = vlSelfRef.__Vdly__tb_qam_feature_vectors__DOT__input_index;
}

VL_INLINE_OPT void Vtb_qam_feature_vectors___024root___nba_comb__TOP__0(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___nba_comb__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_2 
        = VL_EXTENDS_II(32,16, ((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_start)
                                 ? 0U : (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_i)));
    vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT____VdfgRegularize_h2ec6e184_0_3 
        = VL_EXTENDS_II(32,16, ((IData)(vlSelfRef.tb_qam_feature_vectors__DOT__s_frame_start)
                                 ? 0U : (IData)(vlSelfRef.tb_qam_feature_vectors__DOT__dut__DOT__previous_q)));
}

void Vtb_qam_feature_vectors___024root___timing_resume(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_h70362baa__0.resume(
                                                   "@(posedge tb_qam_feature_vectors.clk)");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_qam_feature_vectors___024root___timing_commit(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___timing_commit\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (2ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_h70362baa__0.commit(
                                                   "@(posedge tb_qam_feature_vectors.clk)");
    }
}

void Vtb_qam_feature_vectors___024root___eval_triggers__act(Vtb_qam_feature_vectors___024root* vlSelf);

bool Vtb_qam_feature_vectors___024root___eval_phase__act(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<4> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb_qam_feature_vectors___024root___eval_triggers__act(vlSelf);
    Vtb_qam_feature_vectors___024root___timing_commit(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vtb_qam_feature_vectors___024root___timing_resume(vlSelf);
        Vtb_qam_feature_vectors___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_qam_feature_vectors___024root___eval_phase__nba(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vtb_qam_feature_vectors___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_qam_feature_vectors___024root___dump_triggers__nba(Vtb_qam_feature_vectors___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_qam_feature_vectors___024root___dump_triggers__act(Vtb_qam_feature_vectors___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_qam_feature_vectors___024root___eval(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __VnbaIterCount;
    CData/*0:0*/ __VnbaContinue;
    // Body
    __VnbaIterCount = 0U;
    __VnbaContinue = 1U;
    while (__VnbaContinue) {
        if (VL_UNLIKELY((0x64U < __VnbaIterCount))) {
#ifdef VL_DEBUG
            Vtb_qam_feature_vectors___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("tb/integration/tb_qam_feature_vectors.sv", 4, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vtb_qam_feature_vectors___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("tb/integration/tb_qam_feature_vectors.sv", 4, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vtb_qam_feature_vectors___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vtb_qam_feature_vectors___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vtb_qam_feature_vectors___024root___eval_debug_assertions(Vtb_qam_feature_vectors___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_qam_feature_vectors__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_qam_feature_vectors___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
