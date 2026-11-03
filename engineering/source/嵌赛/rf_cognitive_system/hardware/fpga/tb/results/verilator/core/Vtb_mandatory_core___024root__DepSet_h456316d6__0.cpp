// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_mandatory_core.h for the primary calling header

#include "Vtb_mandatory_core__pch.h"
#include "Vtb_mandatory_core___024root.h"

VlCoroutine Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__0(Vtb_mandatory_core___024root* vlSelf);
VlCoroutine Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__1(Vtb_mandatory_core___024root* vlSelf);

void Vtb_mandatory_core___024root___eval_initial(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__tb_mandatory_core__DOT__clk__0 
        = vlSelfRef.tb_mandatory_core__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_mandatory_core__DOT__rst_n__0 
        = vlSelfRef.tb_mandatory_core__DOT__rst_n;
}

VL_INLINE_OPT VlCoroutine Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__1(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "tb/integration/tb_mandatory_core.sv", 
                                             28);
        vlSelfRef.tb_mandatory_core__DOT__clk = (1U 
                                                 & (~ (IData)(vlSelfRef.tb_mandatory_core__DOT__clk)));
    }
}

void Vtb_mandatory_core___024root___eval_act(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vtb_mandatory_core___024root___nba_sequent__TOP__0(Vtb_mandatory_core___024root* vlSelf);
void Vtb_mandatory_core___024root___nba_sequent__TOP__1(Vtb_mandatory_core___024root* vlSelf);
void Vtb_mandatory_core___024root___nba_sequent__TOP__2(Vtb_mandatory_core___024root* vlSelf);
void Vtb_mandatory_core___024root___nba_sequent__TOP__3(Vtb_mandatory_core___024root* vlSelf);
void Vtb_mandatory_core___024root___nba_comb__TOP__0(Vtb_mandatory_core___024root* vlSelf);
void Vtb_mandatory_core___024root___nba_comb__TOP__1(Vtb_mandatory_core___024root* vlSelf);

void Vtb_mandatory_core___024root___eval_nba(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((6ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_mandatory_core___024root___nba_sequent__TOP__0(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_mandatory_core___024root___nba_sequent__TOP__1(vlSelf);
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_mandatory_core___024root___nba_sequent__TOP__2(vlSelf);
    }
    if ((6ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_mandatory_core___024root___nba_sequent__TOP__3(vlSelf);
        Vtb_mandatory_core___024root___nba_comb__TOP__0(vlSelf);
    }
    if ((7ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_mandatory_core___024root___nba_comb__TOP__1(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_mandatory_core___024root___nba_sequent__TOP__0(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*3:0*/ __Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer;
    __Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer = 0;
    CData/*0:0*/ __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky;
    __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky = 0;
    SData/*15:0*/ __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0;
    __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0 = 0;
    CData/*3:0*/ __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0;
    __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0 = 0;
    CData/*0:0*/ __VdlySet__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0;
    __VdlySet__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0 = 0;
    SData/*15:0*/ __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0;
    __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0 = 0;
    CData/*3:0*/ __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0;
    __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0 = 0;
    CData/*3:0*/ __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__e_mem__v0;
    __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__e_mem__v0 = 0;
    // Body
    __Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer;
    vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count;
    vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id;
    __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky;
    vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index;
    __VdlySet__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0 = 0U;
    vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer;
    if (vlSelfRef.tb_mandatory_core__DOT__rst_n) {
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__pop) {
            __Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer 
                = ((0xfU == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer))
                    ? 0U : (0xfU & ((IData)(1U) + (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer))));
        }
        vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count 
            = (0x1fU & ((2U == (((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__push) 
                                 << 1U) | (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__pop)))
                         ? ((IData)(1U) + (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count))
                         : ((1U == (((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__push) 
                                     << 1U) | (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__pop)))
                             ? ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count) 
                                - (IData)(1U)) : (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count))));
        if (((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__fifo_ready) 
             & (0U != (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count)))) {
            if ((0x3ffU == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index))) {
                vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id 
                    = ((IData)(1U) + vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id);
                vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index = 0U;
                __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky = 0U;
            } else {
                vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index 
                    = (0x3ffU & ((IData)(1U) + (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index)));
                __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky 
                    = ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky) 
                       | vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__e_mem
                       [vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer]);
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__push) {
            __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0 
                = vlSelfRef.tb_mandatory_core__DOT__s_i;
            __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer;
            __VdlySet__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0 = 1U;
            __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0 
                = vlSelfRef.tb_mandatory_core__DOT__s_q;
            __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer;
            __VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__e_mem__v0 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer;
            vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer 
                = ((0xfU == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer))
                    ? 0U : (0xfU & ((IData)(1U) + (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer))));
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__fifo_ready) {
            if ((0U != (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count))) {
                if ((0x3ffU == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index))) {
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_i = 0U;
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_q = 0U;
                } else {
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_i 
                        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__frame_i;
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_q 
                        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__frame_q;
                }
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_s_ready) {
            vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_valid 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid;
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_s_ready) {
            vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_valid 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid;
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_s_ready) {
            vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_valid 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid;
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_s_ready) {
            vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_valid 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid;
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_s_ready) {
            vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_valid 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid;
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_ready) {
            vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_valid 
                = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid;
        }
        if ((1U & (IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_release))) {
            vlSelfRef.tb_mandatory_core__DOT__buffer_busy 
                = (2U & (IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_busy));
        }
        if ((2U & (IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_release))) {
            vlSelfRef.tb_mandatory_core__DOT__buffer_busy 
                = (1U & (IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_busy));
        }
        if (((IData)(vlSelfRef.tb_mandatory_core__DOT__m_write_valid) 
             & (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_frame_end))) {
            vlSelfRef.tb_mandatory_core__DOT__buffer_busy 
                = ((IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_busy) 
                   | (3U & ((IData)(1U) << (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer))));
            vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer 
                = (1U & (~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer)));
        }
    } else {
        __Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer = 0U;
        vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count = 0U;
        vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id = 0U;
        vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index = 0U;
        __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__write_pointer = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_i = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_q = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_valid = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_valid = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_valid = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_valid = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_valid = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_valid = 0U;
        vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer = 0U;
        vlSelfRef.tb_mandatory_core__DOT__buffer_busy = 0U;
    }
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky 
        = __Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_error_sticky;
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer 
        = __Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer;
    if (__VdlySet__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0) {
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem[__VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0] 
            = __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem__v0;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem[__VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0] 
            = __VdlyVal__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem__v0;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__e_mem[__VdlyDim0__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__e_mem__v0] = 0U;
    }
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__bundle_valid 
        = ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_valid) 
           & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_valid) 
              & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_valid) 
                 & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_valid) 
                    & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_valid) 
                       & (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_valid))))));
}

VL_INLINE_OPT void Vtb_mandatory_core___024root___nba_sequent__TOP__1(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___nba_sequent__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vdly__tb_mandatory_core__DOT__input_index;
    __Vdly__tb_mandatory_core__DOT__input_index = 0;
    // Body
    __Vdly__tb_mandatory_core__DOT__input_index = vlSelfRef.tb_mandatory_core__DOT__input_index;
    if ((((IData)(vlSelfRef.tb_mandatory_core__DOT__rst_n) 
          & VL_GTS_III(32, 0x4c00U, vlSelfRef.tb_mandatory_core__DOT__input_index)) 
         & (0x10U > (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count)))) {
        vlSelfRef.tb_mandatory_core__DOT__s_i = ((0x4bffU 
                                                  >= 
                                                  (0x7fffU 
                                                   & vlSelfRef.tb_mandatory_core__DOT__input_index))
                                                  ? 
                                                 (0xffffU 
                                                  & vlSelfRef.tb_mandatory_core__DOT__input_mem
                                                  [
                                                  (0x7fffU 
                                                   & vlSelfRef.tb_mandatory_core__DOT__input_index)])
                                                  : 0U);
        vlSelfRef.tb_mandatory_core__DOT__s_valid = 1U;
        vlSelfRef.tb_mandatory_core__DOT__s_q = (((0x4bffU 
                                                   >= 
                                                   (0x7fffU 
                                                    & vlSelfRef.tb_mandatory_core__DOT__input_index))
                                                   ? 
                                                  vlSelfRef.tb_mandatory_core__DOT__input_mem
                                                  [
                                                  (0x7fffU 
                                                   & vlSelfRef.tb_mandatory_core__DOT__input_index)]
                                                   : 0U) 
                                                 >> 0x10U);
        __Vdly__tb_mandatory_core__DOT__input_index 
            = ((IData)(1U) + vlSelfRef.tb_mandatory_core__DOT__input_index);
    } else if (VL_LTES_III(32, 0x4c00U, vlSelfRef.tb_mandatory_core__DOT__input_index)) {
        vlSelfRef.tb_mandatory_core__DOT__s_valid = 0U;
    }
    vlSelfRef.tb_mandatory_core__DOT__input_index = __Vdly__tb_mandatory_core__DOT__input_index;
}

VL_INLINE_OPT void Vtb_mandatory_core___024root___nba_sequent__TOP__2(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___nba_sequent__TOP__2\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vdly__tb_mandatory_core__DOT__output_count;
    __Vdly__tb_mandatory_core__DOT__output_count = 0;
    // Body
    __Vdly__tb_mandatory_core__DOT__output_count = vlSelfRef.tb_mandatory_core__DOT__output_count;
    if (VL_UNLIKELY(((IData)(vlSelfRef.tb_mandatory_core__DOT__rst_n) 
                     & (IData)(vlSelfRef.tb_mandatory_core__DOT__m_write_valid)))) {
        VL_FWRITEF_NX(vlSelfRef.tb_mandatory_core__DOT__output_file,"%0#,%0#,%0#,%0d,%0d,%0d,%0d,%0d,%0#,%0#,%0#,%0#,%0#\n",0,
                      32,vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_frame_id,
                      10,(IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_sample_index),
                      1,vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer,
                      8,(IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_data),
                      8,vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_data,
                      8,(IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_data),
                      8,vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_data,
                      8,(IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_data),
                      11,vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_sample_index,
                      11,(0x7ffU & ((IData)(0x400U) 
                                    + (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_sample_index))),
                      12,(IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_sample_index),
                      12,(0xfffU & ((IData)(0x400U) 
                                    + (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_sample_index))),
                      12,(0xfffU & ((IData)(0x800U) 
                                    + (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_sample_index))));
        __Vdly__tb_mandatory_core__DOT__output_count 
            = ((IData)(1U) + vlSelfRef.tb_mandatory_core__DOT__output_count);
        if (VL_UNLIKELY((0x4c00U == ((IData)(1U) + vlSelfRef.tb_mandatory_core__DOT__output_count)))) {
            VL_FCLOSE_I(vlSelfRef.tb_mandatory_core__DOT__output_file); VL_WRITEF_NX("PASS tb_mandatory_core samples=19456\n",0);
            VL_FINISH_MT("tb/integration/tb_mandatory_core.sv", 73, "");
        }
    }
    vlSelfRef.tb_mandatory_core__DOT__buffer_release = 0U;
    if (((IData)(vlSelfRef.tb_mandatory_core__DOT__rst_n) 
         & ((IData)(vlSelfRef.tb_mandatory_core__DOT__m_write_valid) 
            & (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_frame_end)))) {
        vlSelfRef.tb_mandatory_core__DOT__buffer_release 
            = ((IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_release) 
               | (3U & ((IData)(1U) << (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer))));
    }
    vlSelfRef.tb_mandatory_core__DOT__output_count 
        = __Vdly__tb_mandatory_core__DOT__output_count;
}

VL_INLINE_OPT void Vtb_mandatory_core___024root___nba_sequent__TOP__3(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___nba_sequent__TOP__3\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__input_negative;
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__input_negative = 0;
    SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__magnitude;
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__magnitude = 0;
    QData/*47:0*/ tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__product;
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__product = 0;
    QData/*48:0*/ tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__adjusted;
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__adjusted = 0;
    QData/*48:0*/ tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__rounded_magnitude;
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__rounded_magnitude = 0;
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__saturated_comb;
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__saturated_comb = 0;
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__input_negative;
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__input_negative = 0;
    SData/*15:0*/ tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__magnitude;
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__magnitude = 0;
    QData/*47:0*/ tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__product;
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__product = 0;
    QData/*48:0*/ tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__adjusted;
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__adjusted = 0;
    QData/*48:0*/ tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__rounded_magnitude;
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__rounded_magnitude = 0;
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__saturated_comb;
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__saturated_comb = 0;
    IData/*31:0*/ tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__magnitude;
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__magnitude = 0;
    QData/*63:0*/ tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__product;
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__product = 0;
    VlWide<3>/*64:0*/ tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__adjusted;
    VL_ZERO_W(65, tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__adjusted);
    VlWide<3>/*64:0*/ tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__rounded_magnitude;
    VL_ZERO_W(65, tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__rounded_magnitude);
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__saturated_comb;
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__saturated_comb = 0;
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__input_negative;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__input_negative = 0;
    QData/*32:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__magnitude;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__magnitude = 0;
    VlWide<3>/*64:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product;
    VL_ZERO_W(65, tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product);
    VlWide<3>/*65:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__adjusted;
    VL_ZERO_W(66, tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__adjusted);
    VlWide<3>/*65:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude;
    VL_ZERO_W(66, tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude);
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__saturated_comb;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__saturated_comb = 0;
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__input_negative;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__input_negative = 0;
    QData/*32:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__magnitude;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__magnitude = 0;
    VlWide<3>/*64:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product;
    VL_ZERO_W(65, tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product);
    VlWide<3>/*65:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__adjusted;
    VL_ZERO_W(66, tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__adjusted);
    VlWide<3>/*65:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude;
    VL_ZERO_W(66, tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude);
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__saturated_comb;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__saturated_comb = 0;
    VlWide<3>/*95:0*/ __Vtemp_2;
    VlWide<3>/*95:0*/ __Vtemp_3;
    VlWide<3>/*95:0*/ __Vtemp_4;
    VlWide<3>/*95:0*/ __Vtemp_6;
    VlWide<3>/*95:0*/ __Vtemp_7;
    VlWide<3>/*95:0*/ __Vtemp_9;
    VlWide<3>/*95:0*/ __Vtemp_10;
    VlWide<3>/*95:0*/ __Vtemp_11;
    VlWide<3>/*95:0*/ __Vtemp_13;
    VlWide<3>/*95:0*/ __Vtemp_14;
    VlWide<3>/*95:0*/ __Vtemp_15;
    VlWide<3>/*95:0*/ __Vtemp_17;
    VlWide<3>/*95:0*/ __Vtemp_18;
    VlWide<3>/*95:0*/ __Vtemp_20;
    VlWide<3>/*95:0*/ __Vtemp_21;
    VlWide<3>/*95:0*/ __Vtemp_22;
    VlWide<3>/*95:0*/ __Vtemp_24;
    VlWide<3>/*95:0*/ __Vtemp_25;
    VlWide<3>/*95:0*/ __Vtemp_26;
    VlWide<3>/*95:0*/ __Vtemp_28;
    VlWide<3>/*95:0*/ __Vtemp_29;
    // Body
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer 
        = vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer;
    if (vlSelfRef.tb_mandatory_core__DOT__rst_n) {
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_s_ready) {
            if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_data 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__quantized_comb;
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_s_ready) {
            if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_data 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__quantized_comb;
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_s_ready) {
            if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_data 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__quantized_comb;
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_s_ready) {
            if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_data 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__quantized_comb;
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_s_ready) {
            if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_data 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__quantized_comb;
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_ready) {
            if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_frame_id 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_frame_id;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_sample_index 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_sample_index;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_frame_end 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_frame_end;
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__stage2_ready) {
            if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_valid) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_valid = 1U;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_i 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_q 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_power 
                    = (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_square 
                       + vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_square);
                if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_start) {
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_re = 0ULL;
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_im = 0ULL;
                } else {
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_re 
                        = (0x1ffffffffULL & ((((QData)((IData)(
                                                               (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_i_prev 
                                                                >> 0x1fU))) 
                                               << 0x20U) 
                                              | (QData)((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_i_prev))) 
                                             + (((QData)((IData)(
                                                                 (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_q_prev 
                                                                  >> 0x1fU))) 
                                                 << 0x20U) 
                                                | (QData)((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_q_prev)))));
                    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_im 
                        = (0x1ffffffffULL & ((((QData)((IData)(
                                                               (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_i_prev 
                                                                >> 0x1fU))) 
                                               << 0x20U) 
                                              | (QData)((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_i_prev))) 
                                             - (((QData)((IData)(
                                                                 (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_q_prev 
                                                                  >> 0x1fU))) 
                                                 << 0x20U) 
                                                | (QData)((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_q_prev)))));
                }
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_sample_index 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_sample_index;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_frame_id 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_id;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_frame_end 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_end;
            } else {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_valid = 0U;
            }
        }
        if (vlSelfRef.tb_mandatory_core__DOT__dut__DOT__fifo_ready) {
            if ((0U != (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count))) {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_id 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__frame_i;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__frame_q;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_square 
                    = VL_MULS_III(32, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_0, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_0);
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_square 
                    = VL_MULS_III(32, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_1, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_1);
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_i_prev 
                    = VL_MULS_III(32, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_0, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_2);
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_q_prev 
                    = VL_MULS_III(32, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_1, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_3);
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_q_i_prev 
                    = VL_MULS_III(32, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_1, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_2);
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_i_q_prev 
                    = VL_MULS_III(32, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_0, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_3);
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_start 
                    = (0U == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index));
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_sample_index 
                    = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index;
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_frame_end 
                    = (0x3ffU == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index));
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_valid = 1U;
            } else {
                vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_valid = 0U;
            }
        }
    } else {
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_data = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_data = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_data = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_data = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_data = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_valid = 0U;
        vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_valid = 0U;
    }
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__magnitude 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_power;
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__product 
        = (0x7fULL * (QData)((IData)(tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__magnitude)));
    __Vtemp_2[0U] = 0x40000000U;
    __Vtemp_2[1U] = 0U;
    __Vtemp_2[2U] = 0U;
    __Vtemp_3[0U] = (IData)(tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__product);
    __Vtemp_3[1U] = (IData)((tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__product 
                             >> 0x20U));
    __Vtemp_3[2U] = 0U;
    VL_ADD_W(3, __Vtemp_4, __Vtemp_2, __Vtemp_3);
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__adjusted[0U] 
        = __Vtemp_4[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__adjusted[1U] 
        = __Vtemp_4[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__adjusted[2U] 
        = (1U & __Vtemp_4[2U]);
    VL_SHIFTR_WWI(65,65,8, __Vtemp_6, tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__adjusted, 0x1fU);
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__rounded_magnitude[0U] 
        = __Vtemp_6[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__rounded_magnitude[1U] 
        = __Vtemp_6[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__rounded_magnitude[2U] 
        = (1U & __Vtemp_6[2U]);
    __Vtemp_7[0U] = 0x7fU;
    __Vtemp_7[1U] = 0U;
    __Vtemp_7[2U] = 0U;
    tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__saturated_comb 
        = VL_LT_W(3, __Vtemp_7, tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__rounded_magnitude);
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__quantized_comb 
        = ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__saturated_comb)
            ? 0x7fU : (0x7fU & tb_mandatory_core__DOT__dut__DOT__quant_power__DOT__rounded_magnitude[0U]));
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__input_negative 
        = (1U & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_i) 
                 >> 0xfU));
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__magnitude 
        = (0xffffU & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__input_negative)
                       ? ((IData)(1U) + (~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_i)))
                       : (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_i)));
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__product 
        = (0xffffffffffffULL & (0x7fULL * (QData)((IData)(tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__magnitude))));
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__adjusted 
        = (0x1ffffffffffffULL & (0x4000ULL + tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__product));
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__rounded_magnitude 
        = (0x1ffffffffffffULL & VL_SHIFTR_QQI(49,49,8, tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__adjusted, 0xfU));
    tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__saturated_comb 
        = (0x7fULL < tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__rounded_magnitude);
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__quantized_comb 
        = (0xffU & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__saturated_comb)
                     ? ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__input_negative)
                         ? 0x81U : 0x7fU) : ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__input_negative)
                                              ? (- 
                                                 (0x7fU 
                                                  & (IData)(tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__rounded_magnitude)))
                                              : (0x7fU 
                                                 & (IData)(tb_mandatory_core__DOT__dut__DOT__quant_i__DOT__rounded_magnitude)))));
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__input_negative 
        = (1U & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_q) 
                 >> 0xfU));
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__magnitude 
        = (0xffffU & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__input_negative)
                       ? ((IData)(1U) + (~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_q)))
                       : (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_q)));
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__product 
        = (0xffffffffffffULL & (0x7fULL * (QData)((IData)(tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__magnitude))));
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__adjusted 
        = (0x1ffffffffffffULL & (0x4000ULL + tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__product));
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__rounded_magnitude 
        = (0x1ffffffffffffULL & VL_SHIFTR_QQI(49,49,8, tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__adjusted, 0xfU));
    tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__saturated_comb 
        = (0x7fULL < tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__rounded_magnitude);
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__quantized_comb 
        = (0xffU & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__saturated_comb)
                     ? ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__input_negative)
                         ? 0x81U : 0x7fU) : ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__input_negative)
                                              ? (- 
                                                 (0x7fU 
                                                  & (IData)(tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__rounded_magnitude)))
                                              : (0x7fU 
                                                 & (IData)(tb_mandatory_core__DOT__dut__DOT__quant_q__DOT__rounded_magnitude)))));
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__input_negative 
        = (1U & (IData)((vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_re 
                         >> 0x20U)));
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__magnitude 
        = (0x1ffffffffULL & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__input_negative)
                              ? (1ULL + (~ vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_re))
                              : vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_re));
    __Vtemp_9[0U] = 0x7fU;
    __Vtemp_9[1U] = 0U;
    __Vtemp_9[2U] = 0U;
    __Vtemp_10[0U] = (IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__magnitude);
    __Vtemp_10[1U] = (IData)((tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__magnitude 
                              >> 0x20U));
    __Vtemp_10[2U] = 0U;
    VL_MUL_W(3, __Vtemp_11, __Vtemp_9, __Vtemp_10);
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product[0U] 
        = __Vtemp_11[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product[1U] 
        = __Vtemp_11[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product[2U] 
        = (1U & __Vtemp_11[2U]);
    __Vtemp_13[0U] = 0x40000000U;
    __Vtemp_13[1U] = 0U;
    __Vtemp_13[2U] = 0U;
    __Vtemp_14[0U] = tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product[0U];
    __Vtemp_14[1U] = tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product[1U];
    __Vtemp_14[2U] = tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__product[2U];
    VL_ADD_W(3, __Vtemp_15, __Vtemp_13, __Vtemp_14);
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__adjusted[0U] 
        = __Vtemp_15[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__adjusted[1U] 
        = __Vtemp_15[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__adjusted[2U] 
        = (3U & __Vtemp_15[2U]);
    VL_SHIFTR_WWI(66,66,8, __Vtemp_17, tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__adjusted, 0x1fU);
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude[0U] 
        = __Vtemp_17[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude[1U] 
        = __Vtemp_17[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude[2U] 
        = (3U & __Vtemp_17[2U]);
    __Vtemp_18[0U] = 0x7fU;
    __Vtemp_18[1U] = 0U;
    __Vtemp_18[2U] = 0U;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__saturated_comb 
        = VL_LT_W(3, __Vtemp_18, tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude);
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__quantized_comb 
        = (0xffU & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__saturated_comb)
                     ? ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__input_negative)
                         ? 0x81U : 0x7fU) : ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__input_negative)
                                              ? (- 
                                                 (0x7fU 
                                                  & tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude[0U]))
                                              : (0x7fU 
                                                 & tb_mandatory_core__DOT__dut__DOT__quant_lag_re__DOT__rounded_magnitude[0U]))));
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__input_negative 
        = (1U & (IData)((vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_im 
                         >> 0x20U)));
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__magnitude 
        = (0x1ffffffffULL & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__input_negative)
                              ? (1ULL + (~ vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_im))
                              : vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_lag_im));
    __Vtemp_20[0U] = 0x7fU;
    __Vtemp_20[1U] = 0U;
    __Vtemp_20[2U] = 0U;
    __Vtemp_21[0U] = (IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__magnitude);
    __Vtemp_21[1U] = (IData)((tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__magnitude 
                              >> 0x20U));
    __Vtemp_21[2U] = 0U;
    VL_MUL_W(3, __Vtemp_22, __Vtemp_20, __Vtemp_21);
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product[0U] 
        = __Vtemp_22[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product[1U] 
        = __Vtemp_22[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product[2U] 
        = (1U & __Vtemp_22[2U]);
    __Vtemp_24[0U] = 0x40000000U;
    __Vtemp_24[1U] = 0U;
    __Vtemp_24[2U] = 0U;
    __Vtemp_25[0U] = tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product[0U];
    __Vtemp_25[1U] = tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product[1U];
    __Vtemp_25[2U] = tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__product[2U];
    VL_ADD_W(3, __Vtemp_26, __Vtemp_24, __Vtemp_25);
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__adjusted[0U] 
        = __Vtemp_26[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__adjusted[1U] 
        = __Vtemp_26[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__adjusted[2U] 
        = (3U & __Vtemp_26[2U]);
    VL_SHIFTR_WWI(66,66,8, __Vtemp_28, tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__adjusted, 0x1fU);
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude[0U] 
        = __Vtemp_28[0U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude[1U] 
        = __Vtemp_28[1U];
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude[2U] 
        = (3U & __Vtemp_28[2U]);
    __Vtemp_29[0U] = 0x7fU;
    __Vtemp_29[1U] = 0U;
    __Vtemp_29[2U] = 0U;
    tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__saturated_comb 
        = VL_LT_W(3, __Vtemp_29, tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude);
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__quantized_comb 
        = (0xffU & ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__saturated_comb)
                     ? ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__input_negative)
                         ? 0x81U : 0x7fU) : ((IData)(tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__input_negative)
                                              ? (- 
                                                 (0x7fU 
                                                  & tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude[0U]))
                                              : (0x7fU 
                                                 & tb_mandatory_core__DOT__dut__DOT__quant_lag_im__DOT__rounded_magnitude[0U]))));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id 
        = vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__frame_id;
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__frame_i 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem
        [vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer];
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__frame_q 
        = vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem
        [vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer];
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_1 
        = VL_EXTENDS_II(32,16, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__q_mem
                        [vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer]);
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_0 
        = VL_EXTENDS_II(32,16, vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__i_mem
                        [vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__read_pointer]);
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index 
        = vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index;
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count 
        = vlSelfRef.__Vdly__tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count;
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_2 
        = VL_EXTENDS_II(32,16, ((0U == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index))
                                 ? 0U : (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_i)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT____VdfgRegularize_h0303a7a0_0_3 
        = VL_EXTENDS_II(32,16, ((0U == (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__framer__DOT__sample_index))
                                 ? 0U : (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__previous_q)));
}

VL_INLINE_OPT void Vtb_mandatory_core___024root___nba_comb__TOP__0(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___nba_comb__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__feature_ready;
    tb_mandatory_core__DOT__dut__DOT__feature_ready = 0;
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__bundle_consume;
    tb_mandatory_core__DOT__dut__DOT__bundle_consume = 0;
    CData/*0:0*/ tb_mandatory_core__DOT__dut__DOT__packer__DOT__selected_buffer_available;
    tb_mandatory_core__DOT__dut__DOT__packer__DOT__selected_buffer_available = 0;
    // Body
    tb_mandatory_core__DOT__dut__DOT__packer__DOT__selected_buffer_available 
        = (1U & ((~ ((IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_busy) 
                     >> (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer))) 
                 | ((IData)(vlSelfRef.tb_mandatory_core__DOT__buffer_release) 
                    >> (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__packer__DOT__fill_buffer))));
    vlSelfRef.tb_mandatory_core__DOT__m_write_valid 
        = ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__bundle_valid) 
           & (IData)(tb_mandatory_core__DOT__dut__DOT__packer__DOT__selected_buffer_available));
    tb_mandatory_core__DOT__dut__DOT__bundle_consume 
        = ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__bundle_valid) 
           & (IData)(tb_mandatory_core__DOT__dut__DOT__packer__DOT__selected_buffer_available));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_valid)) 
                 | (IData)(tb_mandatory_core__DOT__dut__DOT__bundle_consume)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_valid)) 
                 | (IData)(tb_mandatory_core__DOT__dut__DOT__bundle_consume)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_valid)) 
                 | (IData)(tb_mandatory_core__DOT__dut__DOT__bundle_consume)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_valid)) 
                 | (IData)(tb_mandatory_core__DOT__dut__DOT__bundle_consume)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_valid)) 
                 | (IData)(tb_mandatory_core__DOT__dut__DOT__bundle_consume)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_valid)) 
                 | (IData)(tb_mandatory_core__DOT__dut__DOT__bundle_consume)));
    tb_mandatory_core__DOT__dut__DOT__feature_ready 
        = ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__meta_ready) 
           & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qi_s_ready) 
              & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qp_s_ready) 
                 & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qq_s_ready) 
                    & ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qm_s_ready) 
                       & (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__qr_s_ready))))));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__quantizer_input_valid 
        = ((IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_valid) 
           & (IData)(tb_mandatory_core__DOT__dut__DOT__feature_ready));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__stage2_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__feature_valid)) 
                 | (IData)(tb_mandatory_core__DOT__dut__DOT__feature_ready)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__fifo_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__s1_valid)) 
                 | (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__features__DOT__stage2_ready)));
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__pop 
        = ((0U != (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count)) 
           & (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__fifo_ready));
}

VL_INLINE_OPT void Vtb_mandatory_core___024root___nba_comb__TOP__1(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___nba_comb__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__push 
        = ((IData)(vlSelfRef.tb_mandatory_core__DOT__s_valid) 
           & (0x10U > (IData)(vlSelfRef.tb_mandatory_core__DOT__dut__DOT__input_fifo__DOT__count)));
}

void Vtb_mandatory_core___024root___timing_resume(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VtrigSched_h103dc9c4__0.resume(
                                                   "@(posedge tb_mandatory_core.clk)");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_mandatory_core___024root___timing_commit(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___timing_commit\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (2ULL & vlSelfRef.__VactTriggered.word(0U)))) {
        vlSelfRef.__VtrigSched_h103dc9c4__0.commit(
                                                   "@(posedge tb_mandatory_core.clk)");
    }
}

void Vtb_mandatory_core___024root___eval_triggers__act(Vtb_mandatory_core___024root* vlSelf);

bool Vtb_mandatory_core___024root___eval_phase__act(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<4> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb_mandatory_core___024root___eval_triggers__act(vlSelf);
    Vtb_mandatory_core___024root___timing_commit(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vtb_mandatory_core___024root___timing_resume(vlSelf);
        Vtb_mandatory_core___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_mandatory_core___024root___eval_phase__nba(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vtb_mandatory_core___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_mandatory_core___024root___dump_triggers__nba(Vtb_mandatory_core___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_mandatory_core___024root___dump_triggers__act(Vtb_mandatory_core___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_mandatory_core___024root___eval(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval\n"); );
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
            Vtb_mandatory_core___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("tb/integration/tb_mandatory_core.sv", 4, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vtb_mandatory_core___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("tb/integration/tb_mandatory_core.sv", 4, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vtb_mandatory_core___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vtb_mandatory_core___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vtb_mandatory_core___024root___eval_debug_assertions(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
