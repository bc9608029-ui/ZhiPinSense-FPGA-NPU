// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_iq_frame_controller.h for the primary calling header

#include "Vtb_iq_frame_controller__pch.h"
#include "Vtb_iq_frame_controller___024root.h"

VL_ATTR_COLD void Vtb_iq_frame_controller___024root___eval_static__TOP(Vtb_iq_frame_controller___024root* vlSelf);

VL_ATTR_COLD void Vtb_iq_frame_controller___024root___eval_static(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_static\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_iq_frame_controller___024root___eval_static__TOP(vlSelf);
}

VL_ATTR_COLD void Vtb_iq_frame_controller___024root___eval_static__TOP(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_static__TOP\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_iq_frame_controller__DOT__clk = 0U;
    vlSelfRef.tb_iq_frame_controller__DOT__rst_n = 0U;
    vlSelfRef.tb_iq_frame_controller__DOT__s_error = 0U;
    vlSelfRef.tb_iq_frame_controller__DOT__s_valid = 0U;
    vlSelfRef.tb_iq_frame_controller__DOT__m_ready = 1U;
    vlSelfRef.tb_iq_frame_controller__DOT__sent = 0U;
    vlSelfRef.tb_iq_frame_controller__DOT__received = 0U;
}

VL_ATTR_COLD void Vtb_iq_frame_controller___024root___eval_final(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_final\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vtb_iq_frame_controller___024root___eval_settle(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_settle\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_frame_controller___024root___dump_triggers__act(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___dump_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VactTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 0 is active: @(negedge tb_iq_frame_controller.clk)\n");
    }
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 1 is active: @(posedge tb_iq_frame_controller.clk)\n");
    }
    if ((4ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 2 is active: @(negedge tb_iq_frame_controller.rst_n)\n");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 3 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_frame_controller___024root___dump_triggers__nba(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___dump_triggers__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VnbaTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(negedge tb_iq_frame_controller.clk)\n");
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 1 is active: @(posedge tb_iq_frame_controller.clk)\n");
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 2 is active: @(negedge tb_iq_frame_controller.rst_n)\n");
    }
    if ((8ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 3 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_iq_frame_controller___024root___ctor_var_reset(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___ctor_var_reset\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelf->tb_iq_frame_controller__DOT__clk = VL_RAND_RESET_I(1);
    vlSelf->tb_iq_frame_controller__DOT__rst_n = VL_RAND_RESET_I(1);
    vlSelf->tb_iq_frame_controller__DOT__s_error = VL_RAND_RESET_I(1);
    vlSelf->tb_iq_frame_controller__DOT__s_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_iq_frame_controller__DOT__m_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_iq_frame_controller__DOT__sent = VL_RAND_RESET_I(32);
    vlSelf->tb_iq_frame_controller__DOT__received = VL_RAND_RESET_I(32);
    vlSelf->tb_iq_frame_controller__DOT__dut__DOT__sample_index = VL_RAND_RESET_I(2);
    vlSelf->tb_iq_frame_controller__DOT__dut__DOT__frame_id = VL_RAND_RESET_I(8);
    vlSelf->tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_iq_frame_controller__DOT__sent = VL_RAND_RESET_I(32);
    vlSelf->__Vdly__tb_iq_frame_controller__DOT__m_ready = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__rst_n__0 = VL_RAND_RESET_I(1);
}
