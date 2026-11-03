// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_feature_quantizer.h for the primary calling header

#include "Vtb_feature_quantizer__pch.h"
#include "Vtb_feature_quantizer___024root.h"

VlCoroutine Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__0(Vtb_feature_quantizer___024root* vlSelf);
VlCoroutine Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__1(Vtb_feature_quantizer___024root* vlSelf);

void Vtb_feature_quantizer___024root___eval_initial(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__clk__0 
        = vlSelfRef.tb_feature_quantizer__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__rst_n__0 
        = vlSelfRef.tb_feature_quantizer__DOT__rst_n;
}

VL_INLINE_OPT VlCoroutine Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__1(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "tb/unit/tb_feature_quantizer.sv", 
                                             15);
        vlSelfRef.tb_feature_quantizer__DOT__clk = 
            (1U & (~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__clk)));
    }
}

void Vtb_feature_quantizer___024root___act_comb__TOP__0(Vtb_feature_quantizer___024root* vlSelf);

void Vtb_feature_quantizer___024root___eval_act(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0xdULL & vlSelfRef.__VactTriggered.word(0U))) {
        Vtb_feature_quantizer___024root___act_comb__TOP__0(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_feature_quantizer___024root___act_comb__TOP__0(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___act_comb__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ tb_feature_quantizer__DOT__dut__DOT__input_negative;
    tb_feature_quantizer__DOT__dut__DOT__input_negative = 0;
    SData/*15:0*/ tb_feature_quantizer__DOT__dut__DOT__magnitude;
    tb_feature_quantizer__DOT__dut__DOT__magnitude = 0;
    QData/*47:0*/ tb_feature_quantizer__DOT__dut__DOT__product;
    tb_feature_quantizer__DOT__dut__DOT__product = 0;
    QData/*48:0*/ tb_feature_quantizer__DOT__dut__DOT__adjusted;
    tb_feature_quantizer__DOT__dut__DOT__adjusted = 0;
    QData/*48:0*/ tb_feature_quantizer__DOT__dut__DOT__rounded_magnitude;
    tb_feature_quantizer__DOT__dut__DOT__rounded_magnitude = 0;
    // Body
    tb_feature_quantizer__DOT__dut__DOT__input_negative 
        = (1U & ((IData)(vlSelfRef.tb_feature_quantizer__DOT__s_data) 
                 >> 0xfU));
    tb_feature_quantizer__DOT__dut__DOT__magnitude 
        = (0xffffU & ((IData)(tb_feature_quantizer__DOT__dut__DOT__input_negative)
                       ? ((IData)(1U) + (~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__s_data)))
                       : (IData)(vlSelfRef.tb_feature_quantizer__DOT__s_data)));
    tb_feature_quantizer__DOT__dut__DOT__product = (QData)((IData)(tb_feature_quantizer__DOT__dut__DOT__magnitude));
    tb_feature_quantizer__DOT__dut__DOT__adjusted = 
        (0x1ffffffffffffULL & (1ULL + tb_feature_quantizer__DOT__dut__DOT__product));
    tb_feature_quantizer__DOT__dut__DOT__rounded_magnitude 
        = (0x1ffffffffffffULL & VL_SHIFTR_QQI(49,49,8, tb_feature_quantizer__DOT__dut__DOT__adjusted, 1U));
    vlSelfRef.tb_feature_quantizer__DOT__dut__DOT__saturated_comb 
        = (0x7fULL < tb_feature_quantizer__DOT__dut__DOT__rounded_magnitude);
    vlSelfRef.tb_feature_quantizer__DOT__dut__DOT__quantized_comb 
        = (0xffU & ((IData)(vlSelfRef.tb_feature_quantizer__DOT__dut__DOT__saturated_comb)
                     ? ((IData)(tb_feature_quantizer__DOT__dut__DOT__input_negative)
                         ? 0x81U : 0x7fU) : ((IData)(tb_feature_quantizer__DOT__dut__DOT__input_negative)
                                              ? (- 
                                                 (0x7fU 
                                                  & (IData)(tb_feature_quantizer__DOT__dut__DOT__rounded_magnitude)))
                                              : (0x7fU 
                                                 & (IData)(tb_feature_quantizer__DOT__dut__DOT__rounded_magnitude)))));
}

void Vtb_feature_quantizer___024root___nba_sequent__TOP__0(Vtb_feature_quantizer___024root* vlSelf);

void Vtb_feature_quantizer___024root___eval_nba(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((3ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_feature_quantizer___024root___nba_sequent__TOP__0(vlSelf);
    }
    if ((0xdULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_feature_quantizer___024root___act_comb__TOP__0(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_feature_quantizer___024root___nba_sequent__TOP__0(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb_feature_quantizer__DOT__rst_n) {
        if (((IData)(vlSelfRef.tb_feature_quantizer__DOT__s_valid) 
             & (IData)(vlSelfRef.tb_feature_quantizer__DOT__dut__DOT__saturated_comb))) {
            vlSelfRef.tb_feature_quantizer__DOT__saturation_count 
                = ((IData)(1U) + vlSelfRef.tb_feature_quantizer__DOT__saturation_count);
        }
        if (vlSelfRef.tb_feature_quantizer__DOT__s_valid) {
            vlSelfRef.tb_feature_quantizer__DOT__m_data 
                = vlSelfRef.tb_feature_quantizer__DOT__dut__DOT__quantized_comb;
            vlSelfRef.tb_feature_quantizer__DOT__m_saturated 
                = vlSelfRef.tb_feature_quantizer__DOT__dut__DOT__saturated_comb;
        }
    } else {
        vlSelfRef.tb_feature_quantizer__DOT__saturation_count = 0U;
        vlSelfRef.tb_feature_quantizer__DOT__m_data = 0U;
        vlSelfRef.tb_feature_quantizer__DOT__m_saturated = 0U;
    }
    vlSelfRef.tb_feature_quantizer__DOT__m_valid = 
        ((IData)(vlSelfRef.tb_feature_quantizer__DOT__rst_n) 
         && (IData)(vlSelfRef.tb_feature_quantizer__DOT__s_valid));
}

void Vtb_feature_quantizer___024root___timing_resume(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_hc1ab7e2d__0.resume(
                                                   "@(posedge tb_feature_quantizer.clk)");
    }
    if ((4ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_hc1ab7eec__0.resume(
                                                   "@(negedge tb_feature_quantizer.clk)");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_feature_quantizer___024root___timing_commit(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___timing_commit\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (1ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_hc1ab7e2d__0.commit(
                                                   "@(posedge tb_feature_quantizer.clk)");
    }
    if ((! (4ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_hc1ab7eec__0.commit(
                                                   "@(negedge tb_feature_quantizer.clk)");
    }
}

void Vtb_feature_quantizer___024root___eval_triggers__act(Vtb_feature_quantizer___024root* vlSelf);

bool Vtb_feature_quantizer___024root___eval_phase__act(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<4> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb_feature_quantizer___024root___eval_triggers__act(vlSelf);
    Vtb_feature_quantizer___024root___timing_commit(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vtb_feature_quantizer___024root___timing_resume(vlSelf);
        Vtb_feature_quantizer___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_feature_quantizer___024root___eval_phase__nba(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vtb_feature_quantizer___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_feature_quantizer___024root___dump_triggers__nba(Vtb_feature_quantizer___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_feature_quantizer___024root___dump_triggers__act(Vtb_feature_quantizer___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_feature_quantizer___024root___eval(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval\n"); );
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
            Vtb_feature_quantizer___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("tb/unit/tb_feature_quantizer.sv", 3, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vtb_feature_quantizer___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("tb/unit/tb_feature_quantizer.sv", 3, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vtb_feature_quantizer___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vtb_feature_quantizer___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vtb_feature_quantizer___024root___eval_debug_assertions(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
