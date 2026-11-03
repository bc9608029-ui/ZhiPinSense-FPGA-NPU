// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vled_tb.h for the primary calling header

#include "Vled_tb__pch.h"
#include "Vled_tb___024root.h"

VL_ATTR_COLD void Vled_tb___024root___eval_initial__TOP(Vled_tb___024root* vlSelf);
VlCoroutine Vled_tb___024root___eval_initial__TOP__Vtiming__0(Vled_tb___024root* vlSelf);
VlCoroutine Vled_tb___024root___eval_initial__TOP__Vtiming__1(Vled_tb___024root* vlSelf);

void Vled_tb___024root___eval_initial(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vled_tb___024root___eval_initial__TOP(vlSelf);
    Vled_tb___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vled_tb___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__led_tb__DOT__clk__0 
        = vlSelfRef.led_tb__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__led_tb__DOT__rst_n__0 
        = vlSelfRef.led_tb__DOT__rst_n;
}

VL_INLINE_OPT VlCoroutine Vled_tb___024root___eval_initial__TOP__Vtiming__1(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "rundir/simulation/led_tb.v", 
                                             24);
        vlSelfRef.led_tb__DOT__clk = (1U & (~ (IData)(vlSelfRef.led_tb__DOT__clk)));
    }
}

void Vled_tb___024root___eval_act(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vled_tb___024root___nba_sequent__TOP__0(Vled_tb___024root* vlSelf);

void Vled_tb___024root___eval_nba(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((3ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vled_tb___024root___nba_sequent__TOP__0(vlSelf);
    }
}

VL_INLINE_OPT void Vled_tb___024root___nba_sequent__TOP__0(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vdly__led_tb__DOT__dut__DOT__divider_count;
    __Vdly__led_tb__DOT__dut__DOT__divider_count = 0;
    // Body
    __Vdly__led_tb__DOT__dut__DOT__divider_count = vlSelfRef.led_tb__DOT__dut__DOT__divider_count;
    if (vlSelfRef.led_tb__DOT__rst_n) {
        if ((9U <= vlSelfRef.led_tb__DOT__dut__DOT__divider_count)) {
            vlSelfRef.led_tb__DOT__dut__DOT__led_pattern 
                = ((0xeU & ((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                            << 1U)) | (1U & ((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                                             >> 3U)));
            __Vdly__led_tb__DOT__dut__DOT__divider_count = 0U;
        } else {
            __Vdly__led_tb__DOT__dut__DOT__divider_count 
                = ((IData)(1U) + vlSelfRef.led_tb__DOT__dut__DOT__divider_count);
        }
    } else {
        vlSelfRef.led_tb__DOT__dut__DOT__led_pattern = 1U;
        __Vdly__led_tb__DOT__dut__DOT__divider_count = 0U;
    }
    vlSelfRef.led_tb__DOT__dut__DOT__divider_count 
        = __Vdly__led_tb__DOT__dut__DOT__divider_count;
}

void Vled_tb___024root___timing_resume(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_hbf655e20__0.resume(
                                                   "@(posedge led_tb.clk)");
    }
    if ((4ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vled_tb___024root___timing_commit(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___timing_commit\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (1ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_hbf655e20__0.commit(
                                                   "@(posedge led_tb.clk)");
    }
}

void Vled_tb___024root___eval_triggers__act(Vled_tb___024root* vlSelf);

bool Vled_tb___024root___eval_phase__act(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<3> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vled_tb___024root___eval_triggers__act(vlSelf);
    Vled_tb___024root___timing_commit(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vled_tb___024root___timing_resume(vlSelf);
        Vled_tb___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vled_tb___024root___eval_phase__nba(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vled_tb___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vled_tb___024root___dump_triggers__nba(Vled_tb___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vled_tb___024root___dump_triggers__act(Vled_tb___024root* vlSelf);
#endif  // VL_DEBUG

void Vled_tb___024root___eval(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval\n"); );
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
            Vled_tb___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("rundir/simulation/led_tb.v", 3, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vled_tb___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("rundir/simulation/led_tb.v", 3, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vled_tb___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vled_tb___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vled_tb___024root___eval_debug_assertions(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
