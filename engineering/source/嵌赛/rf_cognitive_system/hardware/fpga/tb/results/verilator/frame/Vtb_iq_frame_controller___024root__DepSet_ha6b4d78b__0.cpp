// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_iq_frame_controller.h for the primary calling header

#include "Vtb_iq_frame_controller__pch.h"
#include "Vtb_iq_frame_controller___024root.h"

VlCoroutine Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__0(Vtb_iq_frame_controller___024root* vlSelf);
VlCoroutine Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__1(Vtb_iq_frame_controller___024root* vlSelf);

void Vtb_iq_frame_controller___024root___eval_initial(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__clk__0 
        = vlSelfRef.tb_iq_frame_controller__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__rst_n__0 
        = vlSelfRef.tb_iq_frame_controller__DOT__rst_n;
}

VL_INLINE_OPT VlCoroutine Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__1(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "tb/unit/tb_iq_frame_controller.sv", 
                                             18);
        vlSelfRef.tb_iq_frame_controller__DOT__clk 
            = (1U & (~ (IData)(vlSelfRef.tb_iq_frame_controller__DOT__clk)));
    }
}

void Vtb_iq_frame_controller___024root___eval_act(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vtb_iq_frame_controller___024root___nba_sequent__TOP__0(Vtb_iq_frame_controller___024root* vlSelf);
void Vtb_iq_frame_controller___024root___nba_sequent__TOP__1(Vtb_iq_frame_controller___024root* vlSelf);
void Vtb_iq_frame_controller___024root___nba_sequent__TOP__2(Vtb_iq_frame_controller___024root* vlSelf);
void Vtb_iq_frame_controller___024root___nba_sequent__TOP__3(Vtb_iq_frame_controller___024root* vlSelf);

void Vtb_iq_frame_controller___024root___eval_nba(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_iq_frame_controller___024root___nba_sequent__TOP__0(vlSelf);
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_iq_frame_controller___024root___nba_sequent__TOP__1(vlSelf);
    }
    if ((6ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_iq_frame_controller___024root___nba_sequent__TOP__2(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_iq_frame_controller___024root___nba_sequent__TOP__3(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_iq_frame_controller___024root___nba_sequent__TOP__0(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vdly__tb_iq_frame_controller__DOT__sent 
        = vlSelfRef.tb_iq_frame_controller__DOT__sent;
    vlSelfRef.__Vdly__tb_iq_frame_controller__DOT__m_ready 
        = vlSelfRef.tb_iq_frame_controller__DOT__m_ready;
}

VL_INLINE_OPT void Vtb_iq_frame_controller___024root___nba_sequent__TOP__2(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___nba_sequent__TOP__2\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*1:0*/ __Vdly__tb_iq_frame_controller__DOT__dut__DOT__sample_index;
    __Vdly__tb_iq_frame_controller__DOT__dut__DOT__sample_index = 0;
    CData/*0:0*/ __Vdly__tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky;
    __Vdly__tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky = 0;
    // Body
    __Vdly__tb_iq_frame_controller__DOT__dut__DOT__sample_index 
        = vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__sample_index;
    __Vdly__tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky 
        = vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky;
    if (vlSelfRef.tb_iq_frame_controller__DOT__rst_n) {
        if (((IData)(vlSelfRef.tb_iq_frame_controller__DOT__m_ready) 
             & (IData)(vlSelfRef.tb_iq_frame_controller__DOT__s_valid))) {
            if ((3U == (IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__sample_index))) {
                vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_id 
                    = (0xffU & ((IData)(1U) + (IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_id)));
                __Vdly__tb_iq_frame_controller__DOT__dut__DOT__sample_index = 0U;
                __Vdly__tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky = 0U;
            } else {
                __Vdly__tb_iq_frame_controller__DOT__dut__DOT__sample_index 
                    = (3U & ((IData)(1U) + (IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__sample_index)));
                __Vdly__tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky 
                    = ((IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky) 
                       | (IData)(vlSelfRef.tb_iq_frame_controller__DOT__s_error));
            }
        }
    } else {
        vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_id = 0U;
        __Vdly__tb_iq_frame_controller__DOT__dut__DOT__sample_index = 0U;
        __Vdly__tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky = 0U;
    }
    vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__sample_index 
        = __Vdly__tb_iq_frame_controller__DOT__dut__DOT__sample_index;
    vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky 
        = __Vdly__tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky;
}

VL_INLINE_OPT void Vtb_iq_frame_controller___024root___nba_sequent__TOP__3(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___nba_sequent__TOP__3\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((((IData)(vlSelfRef.tb_iq_frame_controller__DOT__rst_n) 
          & VL_GTS_III(32, 0xaU, vlSelfRef.tb_iq_frame_controller__DOT__sent)) 
         & (IData)(vlSelfRef.tb_iq_frame_controller__DOT__m_ready))) {
        vlSelfRef.tb_iq_frame_controller__DOT__s_valid = 1U;
        vlSelfRef.tb_iq_frame_controller__DOT__s_error 
            = (2U == vlSelfRef.tb_iq_frame_controller__DOT__sent);
        vlSelfRef.__Vdly__tb_iq_frame_controller__DOT__sent 
            = ((IData)(1U) + vlSelfRef.tb_iq_frame_controller__DOT__sent);
    } else if (VL_LTES_III(32, 0xaU, vlSelfRef.tb_iq_frame_controller__DOT__sent)) {
        vlSelfRef.tb_iq_frame_controller__DOT__s_valid = 0U;
    }
    if (((IData)(vlSelfRef.tb_iq_frame_controller__DOT__rst_n) 
         & (5U == vlSelfRef.tb_iq_frame_controller__DOT__received))) {
        vlSelfRef.__Vdly__tb_iq_frame_controller__DOT__m_ready = 0U;
    }
    if ((((IData)(vlSelfRef.tb_iq_frame_controller__DOT__rst_n) 
          & (5U == vlSelfRef.tb_iq_frame_controller__DOT__received)) 
         & (~ (IData)(vlSelfRef.tb_iq_frame_controller__DOT__m_ready)))) {
        vlSelfRef.__Vdly__tb_iq_frame_controller__DOT__m_ready = 1U;
    }
    vlSelfRef.tb_iq_frame_controller__DOT__sent = vlSelfRef.__Vdly__tb_iq_frame_controller__DOT__sent;
    vlSelfRef.tb_iq_frame_controller__DOT__m_ready 
        = vlSelfRef.__Vdly__tb_iq_frame_controller__DOT__m_ready;
}

void Vtb_iq_frame_controller___024root___timing_resume(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_h99a03233__0.resume(
                                                   "@(posedge tb_iq_frame_controller.clk)");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_iq_frame_controller___024root___timing_commit(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___timing_commit\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (2ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_h99a03233__0.commit(
                                                   "@(posedge tb_iq_frame_controller.clk)");
    }
}

void Vtb_iq_frame_controller___024root___eval_triggers__act(Vtb_iq_frame_controller___024root* vlSelf);

bool Vtb_iq_frame_controller___024root___eval_phase__act(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<4> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb_iq_frame_controller___024root___eval_triggers__act(vlSelf);
    Vtb_iq_frame_controller___024root___timing_commit(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vtb_iq_frame_controller___024root___timing_resume(vlSelf);
        Vtb_iq_frame_controller___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_iq_frame_controller___024root___eval_phase__nba(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vtb_iq_frame_controller___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_frame_controller___024root___dump_triggers__nba(Vtb_iq_frame_controller___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_frame_controller___024root___dump_triggers__act(Vtb_iq_frame_controller___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_iq_frame_controller___024root___eval(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval\n"); );
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
            Vtb_iq_frame_controller___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("tb/unit/tb_iq_frame_controller.sv", 3, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vtb_iq_frame_controller___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("tb/unit/tb_iq_frame_controller.sv", 3, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vtb_iq_frame_controller___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vtb_iq_frame_controller___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vtb_iq_frame_controller___024root___eval_debug_assertions(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
