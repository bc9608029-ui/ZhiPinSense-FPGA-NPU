// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_iq_stream_fifo.h for the primary calling header

#include "Vtb_iq_stream_fifo__pch.h"
#include "Vtb_iq_stream_fifo___024root.h"

VlCoroutine Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__0(Vtb_iq_stream_fifo___024root* vlSelf);
VlCoroutine Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__1(Vtb_iq_stream_fifo___024root* vlSelf);

void Vtb_iq_stream_fifo___024root___eval_initial(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__clk__0 
        = vlSelfRef.tb_iq_stream_fifo__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__rst_n__0 
        = vlSelfRef.tb_iq_stream_fifo__DOT__rst_n;
}

VL_INLINE_OPT VlCoroutine Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__1(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "tb/unit/tb_iq_stream_fifo.sv", 
                                             15);
        vlSelfRef.tb_iq_stream_fifo__DOT__clk = (1U 
                                                 & (~ (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__clk)));
    }
}

void Vtb_iq_stream_fifo___024root___act_comb__TOP__0(Vtb_iq_stream_fifo___024root* vlSelf);

void Vtb_iq_stream_fifo___024root___eval_act(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0xdULL & vlSelfRef.__VactTriggered.word(0U))) {
        Vtb_iq_stream_fifo___024root___act_comb__TOP__0(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_iq_stream_fifo___024root___act_comb__TOP__0(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___act_comb__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__push 
        = ((IData)(vlSelfRef.tb_iq_stream_fifo__DOT__s_valid) 
           & (2U > (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count)));
    vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__pop 
        = ((0U != (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count)) 
           & (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__m_ready));
}

void Vtb_iq_stream_fifo___024root___nba_sequent__TOP__0(Vtb_iq_stream_fifo___024root* vlSelf);

void Vtb_iq_stream_fifo___024root___eval_nba(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((3ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_iq_stream_fifo___024root___nba_sequent__TOP__0(vlSelf);
    }
    if ((0xfULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_iq_stream_fifo___024root___act_comb__TOP__0(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_iq_stream_fifo___024root___nba_sequent__TOP__0(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlUnpacked<SData/*15:0*/, 2> tb_iq_stream_fifo__DOT__dut__DOT__q_mem;
    for (int __Vi0 = 0; __Vi0 < 2; ++__Vi0) {
        tb_iq_stream_fifo__DOT__dut__DOT__q_mem[__Vi0] = 0;
    }
    VlUnpacked<CData/*0:0*/, 2> tb_iq_stream_fifo__DOT__dut__DOT__e_mem;
    for (int __Vi0 = 0; __Vi0 < 2; ++__Vi0) {
        tb_iq_stream_fifo__DOT__dut__DOT__e_mem[__Vi0] = 0;
    }
    SData/*15:0*/ __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0;
    __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0 = 0;
    CData/*0:0*/ __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0;
    __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0 = 0;
    CData/*0:0*/ __VdlySet__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0;
    __VdlySet__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0 = 0;
    SData/*15:0*/ __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0;
    __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0 = 0;
    CData/*0:0*/ __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0;
    __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0 = 0;
    CData/*0:0*/ __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__e_mem__v0;
    __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__e_mem__v0 = 0;
    // Body
    __VdlySet__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0 = 0U;
    if (vlSelfRef.tb_iq_stream_fifo__DOT__rst_n) {
        if (vlSelfRef.tb_iq_stream_fifo__DOT__s_overflow_event) {
            vlSelfRef.tb_iq_stream_fifo__DOT__overflow_count 
                = ((IData)(1U) + vlSelfRef.tb_iq_stream_fifo__DOT__overflow_count);
        }
        if (vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__pop) {
            vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__read_pointer 
                = (1U & ((~ (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__read_pointer)) 
                         & ((IData)(1U) + (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__read_pointer))));
        }
        vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count 
            = (3U & ((2U == (((IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__push) 
                              << 1U) | (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__pop)))
                      ? ((IData)(1U) + (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count))
                      : ((1U == (((IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__push) 
                                  << 1U) | (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__pop)))
                          ? ((IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count) 
                             - (IData)(1U)) : (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count))));
        if (vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__push) {
            __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0 
                = vlSelfRef.tb_iq_stream_fifo__DOT__s_i;
            __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0 
                = vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__write_pointer;
            __VdlySet__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0 = 1U;
            __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0 
                = vlSelfRef.tb_iq_stream_fifo__DOT__s_q;
            __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0 
                = vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__write_pointer;
            __VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__e_mem__v0 
                = vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__write_pointer;
            vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__write_pointer 
                = (1U & ((~ (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__write_pointer)) 
                         & ((IData)(1U) + (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__write_pointer))));
        }
    } else {
        vlSelfRef.tb_iq_stream_fifo__DOT__overflow_count = 0U;
        vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__read_pointer = 0U;
        vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count = 0U;
        vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__write_pointer = 0U;
    }
    if (__VdlySet__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0) {
        vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__i_mem[__VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0] 
            = __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__i_mem__v0;
        tb_iq_stream_fifo__DOT__dut__DOT__q_mem[__VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0] 
            = __VdlyVal__tb_iq_stream_fifo__DOT__dut__DOT__q_mem__v0;
        tb_iq_stream_fifo__DOT__dut__DOT__e_mem[__VdlyDim0__tb_iq_stream_fifo__DOT__dut__DOT__e_mem__v0] = 0U;
    }
}

void Vtb_iq_stream_fifo___024root___timing_resume(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_h55ea73d2__0.resume(
                                                   "@(posedge tb_iq_stream_fifo.clk)");
    }
    if ((4ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_h55ea7393__0.resume(
                                                   "@(negedge tb_iq_stream_fifo.clk)");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_iq_stream_fifo___024root___timing_commit(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___timing_commit\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (1ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_h55ea73d2__0.commit(
                                                   "@(posedge tb_iq_stream_fifo.clk)");
    }
    if ((! (4ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_h55ea7393__0.commit(
                                                   "@(negedge tb_iq_stream_fifo.clk)");
    }
}

void Vtb_iq_stream_fifo___024root___eval_triggers__act(Vtb_iq_stream_fifo___024root* vlSelf);

bool Vtb_iq_stream_fifo___024root___eval_phase__act(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<4> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb_iq_stream_fifo___024root___eval_triggers__act(vlSelf);
    Vtb_iq_stream_fifo___024root___timing_commit(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vtb_iq_stream_fifo___024root___timing_resume(vlSelf);
        Vtb_iq_stream_fifo___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_iq_stream_fifo___024root___eval_phase__nba(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vtb_iq_stream_fifo___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_stream_fifo___024root___dump_triggers__nba(Vtb_iq_stream_fifo___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_stream_fifo___024root___dump_triggers__act(Vtb_iq_stream_fifo___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_iq_stream_fifo___024root___eval(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval\n"); );
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
            Vtb_iq_stream_fifo___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("tb/unit/tb_iq_stream_fifo.sv", 3, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vtb_iq_stream_fifo___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("tb/unit/tb_iq_stream_fifo.sv", 3, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vtb_iq_stream_fifo___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vtb_iq_stream_fifo___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vtb_iq_stream_fifo___024root___eval_debug_assertions(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
