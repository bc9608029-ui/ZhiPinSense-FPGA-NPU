// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_tensor_packer.h for the primary calling header

#include "Vtb_tensor_packer__pch.h"
#include "Vtb_tensor_packer___024root.h"

VL_ATTR_COLD void Vtb_tensor_packer___024root___eval_static__TOP(Vtb_tensor_packer___024root* vlSelf);

VL_ATTR_COLD void Vtb_tensor_packer___024root___eval_static(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_static\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_tensor_packer___024root___eval_static__TOP(vlSelf);
}

VL_ATTR_COLD void Vtb_tensor_packer___024root___eval_static__TOP(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_static__TOP\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_tensor_packer__DOT__clk = 0U;
    vlSelfRef.tb_tensor_packer__DOT__rst_n = 0U;
    vlSelfRef.tb_tensor_packer__DOT__s_sample_index = 0U;
    vlSelfRef.tb_tensor_packer__DOT__s_frame_id = 0U;
    vlSelfRef.tb_tensor_packer__DOT__s_frame_end = 0U;
    vlSelfRef.tb_tensor_packer__DOT__s_valid = 0U;
    vlSelfRef.tb_tensor_packer__DOT__buffer_release = 0U;
    vlSelfRef.tb_tensor_packer__DOT__sample = 0U;
}

VL_ATTR_COLD void Vtb_tensor_packer___024root___eval_final(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_final\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_tensor_packer___024root___dump_triggers__stl(Vtb_tensor_packer___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vtb_tensor_packer___024root___eval_phase__stl(Vtb_tensor_packer___024root* vlSelf);

VL_ATTR_COLD void Vtb_tensor_packer___024root___eval_settle(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_settle\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __VstlIterCount;
    CData/*0:0*/ __VstlContinue;
    // Body
    __VstlIterCount = 0U;
    vlSelfRef.__VstlFirstIteration = 1U;
    __VstlContinue = 1U;
    while (__VstlContinue) {
        if (VL_UNLIKELY((0x64U < __VstlIterCount))) {
#ifdef VL_DEBUG
            Vtb_tensor_packer___024root___dump_triggers__stl(vlSelf);
#endif
            VL_FATAL_MT("tb/unit/tb_tensor_packer.sv", 3, "", "Settle region did not converge.");
        }
        __VstlIterCount = ((IData)(1U) + __VstlIterCount);
        __VstlContinue = 0U;
        if (Vtb_tensor_packer___024root___eval_phase__stl(vlSelf)) {
            __VstlContinue = 1U;
        }
        vlSelfRef.__VstlFirstIteration = 0U;
    }
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_tensor_packer___024root___dump_triggers__stl(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___dump_triggers__stl\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VstlTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VstlTriggered.word(0U))) {
        VL_DBG_MSGF("         'stl' region trigger index 0 is active: Internal 'stl' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_tensor_packer___024root___stl_sequent__TOP__0(Vtb_tensor_packer___024root* vlSelf);

VL_ATTR_COLD void Vtb_tensor_packer___024root___eval_stl(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_stl\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VstlTriggered.word(0U))) {
        Vtb_tensor_packer___024root___stl_sequent__TOP__0(vlSelf);
    }
}

VL_ATTR_COLD void Vtb_tensor_packer___024root___stl_sequent__TOP__0(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___stl_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_tensor_packer__DOT__dut__DOT__selected_buffer_available 
        = (1U & ((~ ((IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_busy) 
                     >> (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer))) 
                 | ((IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_release) 
                    >> (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer))));
    vlSelfRef.tb_tensor_packer__DOT__m_write_valid 
        = ((IData)(vlSelfRef.tb_tensor_packer__DOT__s_valid) 
           & (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__selected_buffer_available));
}

VL_ATTR_COLD void Vtb_tensor_packer___024root___eval_triggers__stl(Vtb_tensor_packer___024root* vlSelf);

VL_ATTR_COLD bool Vtb_tensor_packer___024root___eval_phase__stl(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_phase__stl\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VstlExecute;
    // Body
    Vtb_tensor_packer___024root___eval_triggers__stl(vlSelf);
    __VstlExecute = vlSelfRef.__VstlTriggered.any();
    if (__VstlExecute) {
        Vtb_tensor_packer___024root___eval_stl(vlSelf);
    }
    return (__VstlExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_tensor_packer___024root___dump_triggers__act(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___dump_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VactTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 0 is active: @(negedge tb_tensor_packer.clk)\n");
    }
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 1 is active: @(posedge tb_tensor_packer.clk)\n");
    }
    if ((4ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 2 is active: @(negedge tb_tensor_packer.rst_n)\n");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 3 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_tensor_packer___024root___dump_triggers__nba(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___dump_triggers__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VnbaTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(negedge tb_tensor_packer.clk)\n");
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 1 is active: @(posedge tb_tensor_packer.clk)\n");
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 2 is active: @(negedge tb_tensor_packer.rst_n)\n");
    }
    if ((8ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 3 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_tensor_packer___024root___ctor_var_reset(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___ctor_var_reset\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelf->tb_tensor_packer__DOT__clk = VL_RAND_RESET_I(1);
    vlSelf->tb_tensor_packer__DOT__rst_n = VL_RAND_RESET_I(1);
    vlSelf->tb_tensor_packer__DOT__s_sample_index = VL_RAND_RESET_I(2);
    vlSelf->tb_tensor_packer__DOT__s_frame_id = VL_RAND_RESET_I(8);
    vlSelf->tb_tensor_packer__DOT__s_frame_end = VL_RAND_RESET_I(1);
    vlSelf->tb_tensor_packer__DOT__s_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_tensor_packer__DOT__buffer_release = VL_RAND_RESET_I(2);
    vlSelf->tb_tensor_packer__DOT__m_write_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_tensor_packer__DOT__buffer_busy = VL_RAND_RESET_I(2);
    vlSelf->tb_tensor_packer__DOT__sample = VL_RAND_RESET_I(32);
    vlSelf->tb_tensor_packer__DOT__dut__DOT__fill_buffer = VL_RAND_RESET_I(1);
    vlSelf->tb_tensor_packer__DOT__dut__DOT__selected_buffer_available = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_tensor_packer__DOT__sample = VL_RAND_RESET_I(32);
    vlSelf->__Vdly__tb_tensor_packer__DOT__dut__DOT__fill_buffer = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__rst_n__0 = VL_RAND_RESET_I(1);
}
