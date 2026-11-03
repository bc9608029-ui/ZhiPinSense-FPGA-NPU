// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_tensor_packer.h for the primary calling header

#include "Vtb_tensor_packer__pch.h"
#include "Vtb_tensor_packer___024root.h"

VlCoroutine Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__0(Vtb_tensor_packer___024root* vlSelf);
VlCoroutine Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__1(Vtb_tensor_packer___024root* vlSelf);

void Vtb_tensor_packer___024root___eval_initial(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__clk__0 
        = vlSelfRef.tb_tensor_packer__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__rst_n__0 
        = vlSelfRef.tb_tensor_packer__DOT__rst_n;
}

VL_INLINE_OPT VlCoroutine Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__1(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "tb/unit/tb_tensor_packer.sv", 
                                             25);
        vlSelfRef.tb_tensor_packer__DOT__clk = (1U 
                                                & (~ (IData)(vlSelfRef.tb_tensor_packer__DOT__clk)));
    }
}

void Vtb_tensor_packer___024root___eval_act(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vtb_tensor_packer___024root___nba_sequent__TOP__0(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___nba_sequent__TOP__1(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___nba_sequent__TOP__2(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___nba_sequent__TOP__3(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___nba_sequent__TOP__4(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___nba_comb__TOP__0(Vtb_tensor_packer___024root* vlSelf);
void Vtb_tensor_packer___024root___nba_comb__TOP__1(Vtb_tensor_packer___024root* vlSelf);

void Vtb_tensor_packer___024root___eval_nba(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_tensor_packer___024root___nba_sequent__TOP__0(vlSelf);
    }
    if ((6ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_tensor_packer___024root___nba_sequent__TOP__1(vlSelf);
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_tensor_packer___024root___nba_sequent__TOP__2(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_tensor_packer___024root___nba_sequent__TOP__3(vlSelf);
    }
    if ((6ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_tensor_packer___024root___nba_sequent__TOP__4(vlSelf);
        Vtb_tensor_packer___024root___nba_comb__TOP__0(vlSelf);
    }
    if ((7ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_tensor_packer___024root___nba_comb__TOP__1(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_tensor_packer___024root___nba_sequent__TOP__0(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vdly__tb_tensor_packer__DOT__sample 
        = vlSelfRef.tb_tensor_packer__DOT__sample;
}

VL_INLINE_OPT void Vtb_tensor_packer___024root___nba_sequent__TOP__1(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___nba_sequent__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vdly__tb_tensor_packer__DOT__dut__DOT__fill_buffer 
        = vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer;
    if (vlSelfRef.tb_tensor_packer__DOT__rst_n) {
        if ((1U & (IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_release))) {
            vlSelfRef.tb_tensor_packer__DOT__buffer_busy 
                = (2U & (IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_busy));
        }
        if ((2U & (IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_release))) {
            vlSelfRef.tb_tensor_packer__DOT__buffer_busy 
                = (1U & (IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_busy));
        }
        if (((IData)(vlSelfRef.tb_tensor_packer__DOT__m_write_valid) 
             & (IData)(vlSelfRef.tb_tensor_packer__DOT__s_frame_end))) {
            vlSelfRef.tb_tensor_packer__DOT__buffer_busy 
                = ((IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_busy) 
                   | (3U & ((IData)(1U) << (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer))));
            vlSelfRef.__Vdly__tb_tensor_packer__DOT__dut__DOT__fill_buffer 
                = (1U & (~ (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer)));
        }
    } else {
        vlSelfRef.__Vdly__tb_tensor_packer__DOT__dut__DOT__fill_buffer = 0U;
        vlSelfRef.tb_tensor_packer__DOT__buffer_busy = 0U;
    }
}

VL_INLINE_OPT void Vtb_tensor_packer___024root___nba_sequent__TOP__3(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___nba_sequent__TOP__3\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((((IData)(vlSelfRef.tb_tensor_packer__DOT__rst_n) 
          & VL_GTS_III(32, 8U, vlSelfRef.tb_tensor_packer__DOT__sample)) 
         & (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__selected_buffer_available))) {
        vlSelfRef.tb_tensor_packer__DOT__s_valid = 1U;
        vlSelfRef.tb_tensor_packer__DOT__s_sample_index 
            = (3U & VL_MODDIVS_III(32, vlSelfRef.tb_tensor_packer__DOT__sample, (IData)(4U)));
        vlSelfRef.tb_tensor_packer__DOT__s_frame_id 
            = (0xffU & VL_DIVS_III(32, vlSelfRef.tb_tensor_packer__DOT__sample, (IData)(4U)));
        vlSelfRef.tb_tensor_packer__DOT__s_frame_end 
            = (3U == VL_MODDIVS_III(32, vlSelfRef.tb_tensor_packer__DOT__sample, (IData)(4U)));
        vlSelfRef.__Vdly__tb_tensor_packer__DOT__sample 
            = ((IData)(1U) + vlSelfRef.tb_tensor_packer__DOT__sample);
    } else if (VL_LTES_III(32, 8U, vlSelfRef.tb_tensor_packer__DOT__sample)) {
        vlSelfRef.tb_tensor_packer__DOT__s_valid = 0U;
    }
    vlSelfRef.tb_tensor_packer__DOT__sample = vlSelfRef.__Vdly__tb_tensor_packer__DOT__sample;
}

VL_INLINE_OPT void Vtb_tensor_packer___024root___nba_sequent__TOP__4(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___nba_sequent__TOP__4\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer 
        = vlSelfRef.__Vdly__tb_tensor_packer__DOT__dut__DOT__fill_buffer;
}

VL_INLINE_OPT void Vtb_tensor_packer___024root___nba_comb__TOP__0(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___nba_comb__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_tensor_packer__DOT__dut__DOT__selected_buffer_available 
        = (1U & ((~ ((IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_busy) 
                     >> (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer))) 
                 | ((IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_release) 
                    >> (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer))));
}

VL_INLINE_OPT void Vtb_tensor_packer___024root___nba_comb__TOP__1(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___nba_comb__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_tensor_packer__DOT__m_write_valid 
        = ((IData)(vlSelfRef.tb_tensor_packer__DOT__s_valid) 
           & (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__selected_buffer_available));
}

void Vtb_tensor_packer___024root___timing_resume(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_hd28c5fbb__0.resume(
                                                   "@(posedge tb_tensor_packer.clk)");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_tensor_packer___024root___timing_commit(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___timing_commit\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (2ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_hd28c5fbb__0.commit(
                                                   "@(posedge tb_tensor_packer.clk)");
    }
}

void Vtb_tensor_packer___024root___eval_triggers__act(Vtb_tensor_packer___024root* vlSelf);

bool Vtb_tensor_packer___024root___eval_phase__act(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<4> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb_tensor_packer___024root___eval_triggers__act(vlSelf);
    Vtb_tensor_packer___024root___timing_commit(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vtb_tensor_packer___024root___timing_resume(vlSelf);
        Vtb_tensor_packer___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_tensor_packer___024root___eval_phase__nba(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vtb_tensor_packer___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_tensor_packer___024root___dump_triggers__nba(Vtb_tensor_packer___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_tensor_packer___024root___dump_triggers__act(Vtb_tensor_packer___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_tensor_packer___024root___eval(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval\n"); );
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
            Vtb_tensor_packer___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("tb/unit/tb_tensor_packer.sv", 3, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vtb_tensor_packer___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("tb/unit/tb_tensor_packer.sv", 3, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vtb_tensor_packer___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vtb_tensor_packer___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vtb_tensor_packer___024root___eval_debug_assertions(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
