// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_read_path.h for the primary calling header

#include "Vtb_read_path__pch.h"
#include "Vtb_read_path___024root.h"

VL_ATTR_COLD void Vtb_read_path___024root___eval_initial__TOP(Vtb_read_path___024root* vlSelf);
VlCoroutine Vtb_read_path___024root___eval_initial__TOP__Vtiming__0(Vtb_read_path___024root* vlSelf);
VlCoroutine Vtb_read_path___024root___eval_initial__TOP__Vtiming__1(Vtb_read_path___024root* vlSelf);
VlCoroutine Vtb_read_path___024root___eval_initial__TOP__Vtiming__2(Vtb_read_path___024root* vlSelf);

void Vtb_read_path___024root___eval_initial(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_initial\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_read_path___024root___eval_initial__TOP(vlSelf);
    Vtb_read_path___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_read_path___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    Vtb_read_path___024root___eval_initial__TOP__Vtiming__2(vlSelf);
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__hp_clk__0 
        = vlSelfRef.tb_read_path__DOT__hp_clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_hp__0 
        = vlSelfRef.tb_read_path__DOT__rst_hp;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__cam_clk__0 
        = vlSelfRef.tb_read_path__DOT__cam_clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_cam__0 
        = vlSelfRef.tb_read_path__DOT__rst_cam;
}

VL_INLINE_OPT VlCoroutine Vtb_read_path___024root___eval_initial__TOP__Vtiming__0(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__rst_hp = 1U;
    vlSelfRef.tb_read_path__DOT__rst_cam = 1U;
    co_await vlSelfRef.__VdlySched.delay(0x493e0ULL, 
                                         nullptr, "/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 
                                         445);
    vlSelfRef.tb_read_path__DOT__rst_hp = 0U;
    vlSelfRef.tb_read_path__DOT__rst_cam = 0U;
    co_await vlSelfRef.__VdlySched.delay(0x12a05f2000ULL, 
                                         nullptr, "/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 
                                         452);
    VL_WRITEF_NX("================ READ-PATH RESULT ================\nframe_beat[0] = %0#  (expect 230400)\nframe_beat[1] = %0#  (expect 230400, buf0)\nframe_beat[2] = %0#  (expect 230400)\nframe_beat[3] = %0#  (expect 230400, buf1)\nvalid_px_cnt  = %0#  (expect 921600)\nline_cnt      = %0#  (expect 720)\nmismatch_buf0 = %0#  (expect 0)\nmismatch_buf1 = %0#  (expect 0)\nunderflow_cnt = %0#  (expect 0)\n--- diagnostics ---\nfull_event    = %0d  (FIFO-full rising edges)\nfull_cycles   = %0d  (cycles FIFO full)\n",0,
                 32,vlSelfRef.tb_read_path__DOT__frame_beat
                 [0U],32,vlSelfRef.tb_read_path__DOT__frame_beat
                 [1U],32,vlSelfRef.tb_read_path__DOT__frame_beat
                 [2U],32,vlSelfRef.tb_read_path__DOT__frame_beat
                 [3U],32,vlSelfRef.tb_read_path__DOT__valid_px_cnt,
                 32,vlSelfRef.tb_read_path__DOT__line_cnt,
                 32,vlSelfRef.tb_read_path__DOT__mismatch_buf0,
                 32,vlSelfRef.tb_read_path__DOT__mismatch_buf1,
                 32,vlSelfRef.tb_read_path__DOT__underflow_cnt,
                 32,vlSelfRef.tb_read_path__DOT__full_event,
                 32,vlSelfRef.tb_read_path__DOT__full_cycles);
    VL_WRITEF_NX("drop_we       = %0d  (RD_FIFO_WE while full)\nfirst_mismatch@ (x=%0d, y=%0d)\n",0,
                 32,vlSelfRef.tb_read_path__DOT__drop_we,
                 32,vlSelfRef.tb_read_path__DOT__first_mm_x,
                 32,vlSelfRef.tb_read_path__DOT__first_mm_y);
    if ((((((((0x38400U == vlSelfRef.tb_read_path__DOT__frame_beat
               [1U]) & (0x38400U == vlSelfRef.tb_read_path__DOT__frame_beat
                        [3U])) & (0xe1000U == vlSelfRef.tb_read_path__DOT__valid_px_cnt)) 
            & (0x2d0U == vlSelfRef.tb_read_path__DOT__line_cnt)) 
           & (0U == vlSelfRef.tb_read_path__DOT__mismatch_buf0)) 
          & (0U == vlSelfRef.tb_read_path__DOT__mismatch_buf1)) 
         & (0U == vlSelfRef.tb_read_path__DOT__underflow_cnt))) {
        VL_WRITEF_NX("VERDICT: PASS\n",0);
    } else {
        VL_WRITEF_NX("VERDICT: FAIL\n",0);
    }
    VL_FINISH_MT("/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 478, "");
}

VL_INLINE_OPT VlCoroutine Vtb_read_path___024root___eval_initial__TOP__Vtiming__1(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_initial__TOP__Vtiming__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1a4eULL, 
                                             nullptr, 
                                             "/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 
                                             25);
        vlSelfRef.tb_read_path__DOT__cam_clk = (1U 
                                                & (~ (IData)(vlSelfRef.tb_read_path__DOT__cam_clk)));
    }
}

VL_INLINE_OPT VlCoroutine Vtb_read_path___024root___eval_initial__TOP__Vtiming__2(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_initial__TOP__Vtiming__2\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (1U) {
        co_await vlSelfRef.__VdlySched.delay(0x1388ULL, 
                                             nullptr, 
                                             "/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 
                                             24);
        vlSelfRef.tb_read_path__DOT__hp_clk = (1U & 
                                               (~ (IData)(vlSelfRef.tb_read_path__DOT__hp_clk)));
    }
}

void Vtb_read_path___024root___eval_act(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vtb_read_path___024root___nba_sequent__TOP__0(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__1(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__2(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__3(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__4(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__5(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__6(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__7(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__8(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__9(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__10(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__11(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_comb__TOP__0(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__12(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__13(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__14(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_comb__TOP__1(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__15(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__16(Vtb_read_path___024root* vlSelf);
void Vtb_read_path___024root___nba_sequent__TOP__17(Vtb_read_path___024root* vlSelf);

void Vtb_read_path___024root___eval_nba(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__0(vlSelf);
    }
    if ((0xcULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__1(vlSelf);
    }
    if ((3ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__2(vlSelf);
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__3(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__4(vlSelf);
    }
    if ((6ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__5(vlSelf);
    }
    if ((0xcULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__6(vlSelf);
    }
    if ((3ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__7(vlSelf);
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__8(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__9(vlSelf);
    }
    if ((0xcULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__10(vlSelf);
    }
    if ((3ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__11(vlSelf);
    }
    if ((5ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_comb__TOP__0(vlSelf);
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__12(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__13(vlSelf);
    }
    if ((0xcULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__14(vlSelf);
    }
    if ((5ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_comb__TOP__1(vlSelf);
    }
    if ((3ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__15(vlSelf);
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__16(vlSelf);
    }
    if ((0xcULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        Vtb_read_path___024root___nba_sequent__TOP__17(vlSelf);
    }
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__0(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    SData/*15:0*/ __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr;
    __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr = 0;
    // Body
    vlSelfRef.__Vdly__tb_read_path__DOT__rfin_cnt = vlSelfRef.tb_read_path__DOT__rfin_cnt;
    vlSelfRef.__Vdly__tb_read_path__DOT__beat_frame 
        = vlSelfRef.tb_read_path__DOT__beat_frame;
    vlSelfRef.__VdlySet__tb_read_path__DOT__frame_beat__v0 = 0U;
    vlSelfRef.__Vdly__tb_read_path__DOT__aq_m_arready 
        = vlSelfRef.tb_read_path__DOT__aq_m_arready;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__active 
        = vlSelfRef.tb_read_path__DOT__u_mem__DOT__active;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__remaining 
        = vlSelfRef.tb_read_path__DOT__u_mem__DOT__remaining;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__cur_addr 
        = vlSelfRef.tb_read_path__DOT__u_mem__DOT__cur_addr;
    vlSelfRef.__Vdly__tb_read_path__DOT__aq_s_rvalid 
        = vlSelfRef.tb_read_path__DOT__aq_s_rvalid;
    vlSelfRef.__VdlySet__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0 = 0U;
    __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr 
        = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr;
    if ((0x8000U <= (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used))) {
        vlSelfRef.tb_read_path__DOT__full_cycles = 
            ((IData)(1U) + vlSelfRef.tb_read_path__DOT__full_cycles);
    }
    if (((IData)(vlSelfRef.tb_read_path__DOT__aq_s_rvalid) 
         & (0x8000U <= (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used)))) {
        vlSelfRef.tb_read_path__DOT__drop_we = ((IData)(1U) 
                                                + vlSelfRef.tb_read_path__DOT__drop_we);
    }
    if (((0x8000U <= (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used)) 
         & (~ (IData)(vlSelfRef.tb_read_path__DOT__prev_rfifo_full)))) {
        vlSelfRef.tb_read_path__DOT__full_event = ((IData)(1U) 
                                                   + vlSelfRef.tb_read_path__DOT__full_event);
    }
    if (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_fifo_aclr) {
        __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr = 0U;
    } else if (((IData)(vlSelfRef.tb_read_path__DOT__aq_s_rvalid) 
                & (0x8000U > (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used)))) {
        vlSelfRef.__VdlyVal__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0 
            = (((QData)((IData)((((IData)(vlSelfRef.tb_read_path__DOT__aq_s_rdata) 
                                  << 0x10U) | (0xffffU 
                                               & (IData)(
                                                         (vlSelfRef.tb_read_path__DOT__aq_s_rdata 
                                                          >> 0x10U)))))) 
                << 0x20U) | (QData)((IData)((((IData)(
                                                      (vlSelfRef.tb_read_path__DOT__aq_s_rdata 
                                                       >> 0x20U)) 
                                              << 0x10U) 
                                             | (0xffffU 
                                                & (IData)(
                                                          (vlSelfRef.tb_read_path__DOT__aq_s_rdata 
                                                           >> 0x30U)))))));
        vlSelfRef.__VdlyDim0__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0 
            = (0x7fffU & (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr));
        vlSelfRef.__VdlySet__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0 = 1U;
        __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr 
            = (0xffffU & ((IData)(1U) + (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr)));
    }
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr 
        = __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr;
    vlSelfRef.tb_read_path__DOT__prev_rfifo_full = 
        (0x8000U <= (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used));
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__1(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    SData/*11:0*/ __Vdly__tb_read_path__DOT__u_color_bar__DOT__h_cnt;
    __Vdly__tb_read_path__DOT__u_color_bar__DOT__h_cnt = 0;
    SData/*11:0*/ __Vdly__tb_read_path__DOT__u_color_bar__DOT__v_cnt;
    __Vdly__tb_read_path__DOT__u_color_bar__DOT__v_cnt = 0;
    // Body
    __Vdly__tb_read_path__DOT__u_color_bar__DOT__h_cnt 
        = vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt;
    __Vdly__tb_read_path__DOT__u_color_bar__DOT__v_cnt 
        = vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_color_bar__DOT__vs_reg 
        = vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__vs_reg;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt 
        = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt 
        = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt;
    if (vlSelfRef.tb_read_path__DOT__rst_cam) {
        __Vdly__tb_read_path__DOT__u_color_bar__DOT__h_cnt = 0U;
        __Vdly__tb_read_path__DOT__u_color_bar__DOT__v_cnt = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt = 0U;
    } else {
        __Vdly__tb_read_path__DOT__u_color_bar__DOT__h_cnt 
            = ((0x671U == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt))
                ? 0U : (0xfffU & ((IData)(1U) + (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt))));
        __Vdly__tb_read_path__DOT__u_color_bar__DOT__v_cnt 
            = (0xfffU & ((0x6dU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt))
                          ? ((0x2edU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt))
                              ? 0U : ((IData)(1U) + (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt)))
                          : (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt)));
        vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt 
            = ((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d1)
                ? (0xfffU & ((IData)(1U) + (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt)))
                : 0U);
        vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt 
            = (((~ (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d1)) 
                & (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d0))
                ? 0U : (0xfffU & (((~ (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d0)) 
                                   & (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d1))
                                   ? ((IData)(1U) + (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt))
                                   : (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt))));
    }
    vlSelfRef.__Vdly__tb_read_path__DOT__u_color_bar__DOT__vs_reg 
        = (1U & ((~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam)) 
                 & (((4U == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt)) 
                     & (0x6dU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt))) 
                    | (((9U == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt)) 
                        & (0x6dU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt)))
                        ? (~ (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__vs_reg))
                        : (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__vs_reg)))));
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_active 
        = ((~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam)) 
           & ((0x171U == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt)) 
              | ((0x671U != (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt)) 
                 & (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_active))));
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_active 
        = ((~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam)) 
           & (((0x1dU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt)) 
               & (0x6dU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt))) 
              | ((~ ((0x2edU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt)) 
                     & (0x6dU == (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt)))) 
                 & (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_active))));
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_cnt 
        = __Vdly__tb_read_path__DOT__u_color_bar__DOT__v_cnt;
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_cnt 
        = __Vdly__tb_read_path__DOT__u_color_bar__DOT__h_cnt;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__2(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__2\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len;
    __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len = 0;
    CData/*0:0*/ __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last;
    __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last = 0;
    // Body
    vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state 
        = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch 
        = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch;
    vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr 
        = vlSelfRef.tb_read_path__DOT__rd_burst_addr;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt 
        = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt;
    vlSelfRef.__Vdly__tb_read_path__DOT__ch0_read_req_ack 
        = vlSelfRef.tb_read_path__DOT__ch0_read_req_ack;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state 
        = vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs 
        = vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs;
    __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len 
        = vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid 
        = vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid;
    vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len 
        = vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len;
    __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last 
        = vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last;
    if (vlSelfRef.tb_read_path__DOT__rst_hp) {
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs = 0U;
        __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len = 0U;
    } else if ((0U == (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state))) {
        if (vlSelfRef.tb_read_path__DOT__rd_burst_req) {
            vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 1U;
            vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs 
                = (vlSelfRef.tb_read_path__DOT__rd_burst_addr 
                   << 3U);
            __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len 
                = (((IData)(vlSelfRef.tb_read_path__DOT__rd_burst_len) 
                    << 3U) - (IData)(1U));
        }
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len = 0U;
    } else if ((1U == (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state))) {
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 2U;
    } else if ((2U == (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state))) {
        __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len 
            = ((0x7fU & __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len) 
               | (((vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len 
                    >> 7U) - (IData)(1U)) << 7U));
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 3U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid = 1U;
        if ((0U != (vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len 
                    >> 7U))) {
            __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last = 0U;
            vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len = 0xfU;
        } else {
            __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last = 1U;
            vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len 
                = (0xffU & (vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len 
                            >> 3U));
        }
    } else if ((3U == (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state))) {
        if (vlSelfRef.tb_read_path__DOT__aq_m_arready) {
            vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 4U;
            vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid = 0U;
        }
    } else if ((4U == (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state))) {
        if (vlSelfRef.tb_read_path__DOT__aq_s_rvalid) {
            if (vlSelfRef.tb_read_path__DOT__aq_s_rlast) {
                if (vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last) {
                    vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 5U;
                } else {
                    vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs 
                        = ((IData)(0x80U) + vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs);
                    vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 1U;
                }
            } else {
                vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len 
                    = (0xffU & ((IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len) 
                                - (IData)(1U)));
            }
        }
    } else if ((5U == (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state))) {
        vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = 0U;
    }
    vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len 
        = __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len;
    vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last 
        = __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__3(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__3\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __Vdly__tb_read_path__DOT__measuring;
    __Vdly__tb_read_path__DOT__measuring = 0;
    CData/*0:0*/ __Vdly__tb_read_path__DOT__cur_buf1;
    __Vdly__tb_read_path__DOT__cur_buf1 = 0;
    IData/*31:0*/ __Vdly__tb_read_path__DOT__mismatch_buf0;
    __Vdly__tb_read_path__DOT__mismatch_buf0 = 0;
    IData/*31:0*/ __Vdly__tb_read_path__DOT__valid_px_cnt;
    __Vdly__tb_read_path__DOT__valid_px_cnt = 0;
    IData/*31:0*/ __Vdly__tb_read_path__DOT__line_cnt;
    __Vdly__tb_read_path__DOT__line_cnt = 0;
    IData/*31:0*/ __Vdly__tb_read_path__DOT__underflow_cnt;
    __Vdly__tb_read_path__DOT__underflow_cnt = 0;
    SData/*11:0*/ __Vdly__tb_read_path__DOT__px_in_line;
    __Vdly__tb_read_path__DOT__px_in_line = 0;
    IData/*31:0*/ __Vdly__tb_read_path__DOT__first_mm_x;
    __Vdly__tb_read_path__DOT__first_mm_x = 0;
    IData/*31:0*/ __Vdly__tb_read_path__DOT__mismatch_buf1;
    __Vdly__tb_read_path__DOT__mismatch_buf1 = 0;
    // Body
    vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
        = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr;
    __Vdly__tb_read_path__DOT__measuring = vlSelfRef.tb_read_path__DOT__measuring;
    __Vdly__tb_read_path__DOT__cur_buf1 = vlSelfRef.tb_read_path__DOT__cur_buf1;
    __Vdly__tb_read_path__DOT__mismatch_buf0 = vlSelfRef.tb_read_path__DOT__mismatch_buf0;
    __Vdly__tb_read_path__DOT__valid_px_cnt = vlSelfRef.tb_read_path__DOT__valid_px_cnt;
    __Vdly__tb_read_path__DOT__line_cnt = vlSelfRef.tb_read_path__DOT__line_cnt;
    __Vdly__tb_read_path__DOT__underflow_cnt = vlSelfRef.tb_read_path__DOT__underflow_cnt;
    __Vdly__tb_read_path__DOT__px_in_line = vlSelfRef.tb_read_path__DOT__px_in_line;
    __Vdly__tb_read_path__DOT__first_mm_x = vlSelfRef.tb_read_path__DOT__first_mm_x;
    __Vdly__tb_read_path__DOT__mismatch_buf1 = vlSelfRef.tb_read_path__DOT__mismatch_buf1;
    if (((IData)(vlSelfRef.tb_read_path__DOT__ch0_read_req) 
         & (~ (IData)(vlSelfRef.tb_read_path__DOT__prev_read_req)))) {
        if ((1U == vlSelfRef.tb_read_path__DOT__rreq_cnt)) {
            __Vdly__tb_read_path__DOT__measuring = 1U;
            __Vdly__tb_read_path__DOT__cur_buf1 = 0U;
            __Vdly__tb_read_path__DOT__mismatch_buf0 = 0U;
            __Vdly__tb_read_path__DOT__valid_px_cnt = 0U;
            __Vdly__tb_read_path__DOT__line_cnt = 0U;
            __Vdly__tb_read_path__DOT__underflow_cnt = 0U;
            __Vdly__tb_read_path__DOT__px_in_line = 0U;
            __Vdly__tb_read_path__DOT__first_mm_x = 0xffffffffU;
            vlSelfRef.tb_read_path__DOT__first_mm_y = 0xffffffffU;
        } else if ((2U == vlSelfRef.tb_read_path__DOT__rreq_cnt)) {
            __Vdly__tb_read_path__DOT__measuring = 0U;
        } else if ((3U == vlSelfRef.tb_read_path__DOT__rreq_cnt)) {
            __Vdly__tb_read_path__DOT__measuring = 1U;
            __Vdly__tb_read_path__DOT__cur_buf1 = 1U;
            __Vdly__tb_read_path__DOT__mismatch_buf1 = 0U;
            __Vdly__tb_read_path__DOT__px_in_line = 0U;
        } else if ((4U == vlSelfRef.tb_read_path__DOT__rreq_cnt)) {
            __Vdly__tb_read_path__DOT__measuring = 0U;
        }
        vlSelfRef.tb_read_path__DOT__rreq_cnt = ((IData)(1U) 
                                                 + vlSelfRef.tb_read_path__DOT__rreq_cnt);
    }
    if (((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d2) 
         & (~ (IData)(vlSelfRef.tb_read_path__DOT__prev_de)))) {
        if (((IData)(vlSelfRef.tb_read_path__DOT__measuring) 
             & (~ (IData)(vlSelfRef.tb_read_path__DOT__cur_buf1)))) {
            __Vdly__tb_read_path__DOT__line_cnt = ((IData)(1U) 
                                                   + vlSelfRef.tb_read_path__DOT__line_cnt);
        }
    }
    if (vlSelfRef.tb_read_path__DOT__measuring) {
        if (vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d2) {
            if ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__cur_buf1)))) {
                __Vdly__tb_read_path__DOT__valid_px_cnt 
                    = ((IData)(1U) + vlSelfRef.tb_read_path__DOT__valid_px_cnt);
            }
            if ((0x28U > (IData)(vlSelfRef.tb_read_path__DOT__px_in_line))) {
                if (vlSelfRef.tb_read_path__DOT__cur_buf1) {
                    if ((0xffU != (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__vout_data_r))) {
                        __Vdly__tb_read_path__DOT__mismatch_buf1 
                            = ((IData)(1U) + vlSelfRef.tb_read_path__DOT__mismatch_buf1);
                        if ((0xffffffffU == vlSelfRef.tb_read_path__DOT__first_mm_x)) {
                            __Vdly__tb_read_path__DOT__first_mm_x 
                                = vlSelfRef.tb_read_path__DOT__px_in_line;
                            vlSelfRef.tb_read_path__DOT__first_mm_y 
                                = vlSelfRef.tb_read_path__DOT__line_cnt;
                        }
                    }
                } else if (((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__vout_data_r) 
                            != (IData)(vlSelfRef.tb_read_path__DOT__px_in_line))) {
                    __Vdly__tb_read_path__DOT__mismatch_buf0 
                        = ((IData)(1U) + vlSelfRef.tb_read_path__DOT__mismatch_buf0);
                    if ((0xffffffffU == vlSelfRef.tb_read_path__DOT__first_mm_x)) {
                        __Vdly__tb_read_path__DOT__first_mm_x 
                            = vlSelfRef.tb_read_path__DOT__px_in_line;
                        vlSelfRef.tb_read_path__DOT__first_mm_y 
                            = vlSelfRef.tb_read_path__DOT__line_cnt;
                    }
                }
            } else if ((0U != (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__vout_data_r))) {
                if (vlSelfRef.tb_read_path__DOT__cur_buf1) {
                    __Vdly__tb_read_path__DOT__mismatch_buf1 
                        = ((IData)(1U) + vlSelfRef.tb_read_path__DOT__mismatch_buf1);
                    if ((0xffffffffU == vlSelfRef.tb_read_path__DOT__first_mm_x)) {
                        __Vdly__tb_read_path__DOT__first_mm_x 
                            = vlSelfRef.tb_read_path__DOT__px_in_line;
                        vlSelfRef.tb_read_path__DOT__first_mm_y 
                            = vlSelfRef.tb_read_path__DOT__line_cnt;
                    }
                } else {
                    __Vdly__tb_read_path__DOT__mismatch_buf0 
                        = ((IData)(1U) + vlSelfRef.tb_read_path__DOT__mismatch_buf0);
                    if ((0xffffffffU == vlSelfRef.tb_read_path__DOT__first_mm_x)) {
                        __Vdly__tb_read_path__DOT__first_mm_x 
                            = vlSelfRef.tb_read_path__DOT__px_in_line;
                        vlSelfRef.tb_read_path__DOT__first_mm_y 
                            = vlSelfRef.tb_read_path__DOT__line_cnt;
                    }
                }
            }
            __Vdly__tb_read_path__DOT__px_in_line = 
                (0xfffU & ((IData)(1U) + (IData)(vlSelfRef.tb_read_path__DOT__px_in_line)));
        } else {
            __Vdly__tb_read_path__DOT__px_in_line = 0U;
        }
    }
    if (((IData)(vlSelfRef.tb_read_path__DOT__rd_rfifo_err_w) 
         & (IData)(vlSelfRef.tb_read_path__DOT__measuring))) {
        __Vdly__tb_read_path__DOT__underflow_cnt = 
            ((IData)(1U) + vlSelfRef.tb_read_path__DOT__underflow_cnt);
    }
    vlSelfRef.tb_read_path__DOT__measuring = __Vdly__tb_read_path__DOT__measuring;
    vlSelfRef.tb_read_path__DOT__cur_buf1 = __Vdly__tb_read_path__DOT__cur_buf1;
    vlSelfRef.tb_read_path__DOT__mismatch_buf0 = __Vdly__tb_read_path__DOT__mismatch_buf0;
    vlSelfRef.tb_read_path__DOT__valid_px_cnt = __Vdly__tb_read_path__DOT__valid_px_cnt;
    vlSelfRef.tb_read_path__DOT__line_cnt = __Vdly__tb_read_path__DOT__line_cnt;
    vlSelfRef.tb_read_path__DOT__underflow_cnt = __Vdly__tb_read_path__DOT__underflow_cnt;
    vlSelfRef.tb_read_path__DOT__px_in_line = __Vdly__tb_read_path__DOT__px_in_line;
    vlSelfRef.tb_read_path__DOT__first_mm_x = __Vdly__tb_read_path__DOT__first_mm_x;
    vlSelfRef.tb_read_path__DOT__mismatch_buf1 = __Vdly__tb_read_path__DOT__mismatch_buf1;
    vlSelfRef.tb_read_path__DOT__prev_de = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d2;
    vlSelfRef.tb_read_path__DOT__prev_read_req = vlSelfRef.tb_read_path__DOT__ch0_read_req;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__4(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__4\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb_read_path__DOT__rst_hp) {
        vlSelfRef.__Vdly__tb_read_path__DOT__aq_m_arready = 1U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__active = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__aq_s_rvalid = 0U;
        vlSelfRef.tb_read_path__DOT__aq_s_rlast = 0U;
        vlSelfRef.tb_read_path__DOT__aq_s_rdata = 0ULL;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__cur_addr = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__remaining = 0U;
    } else {
        vlSelfRef.__Vdly__tb_read_path__DOT__aq_m_arready 
            = (1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__u_mem__DOT__active)));
        if ((((~ (IData)(vlSelfRef.tb_read_path__DOT__u_mem__DOT__active)) 
              & (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid)) 
             & (IData)(vlSelfRef.tb_read_path__DOT__aq_m_arready))) {
            vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__active = 1U;
            vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__cur_addr 
                = vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs;
            vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__remaining 
                = (0xffU & ((IData)(1U) + (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len)));
        }
        if (vlSelfRef.tb_read_path__DOT__u_mem__DOT__active) {
            if (vlSelfRef.tb_read_path__DOT__aq_s_rvalid) {
                if (vlSelfRef.tb_read_path__DOT__aq_m_rready) {
                    if ((1U == (IData)(vlSelfRef.tb_read_path__DOT__u_mem__DOT__remaining))) {
                        vlSelfRef.__Vdly__tb_read_path__DOT__aq_s_rvalid = 0U;
                        vlSelfRef.tb_read_path__DOT__aq_s_rlast = 0U;
                        vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__active = 0U;
                    } else {
                        vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__remaining 
                            = (0xffU & ((IData)(vlSelfRef.tb_read_path__DOT__u_mem__DOT__remaining) 
                                        - (IData)(1U)));
                        vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__cur_addr 
                            = vlSelfRef.tb_read_path__DOT__u_mem__DOT__next_addr;
                        vlSelfRef.tb_read_path__DOT__aq_s_rdata 
                            = ((0x707ffU >= (0x7ffffU 
                                             & (vlSelfRef.tb_read_path__DOT__u_mem__DOT__next_addr 
                                                >> 3U)))
                                ? vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem
                               [(0x7ffffU & (vlSelfRef.tb_read_path__DOT__u_mem__DOT__next_addr 
                                             >> 3U))]
                                : 0ULL);
                        vlSelfRef.tb_read_path__DOT__aq_s_rlast 
                            = (2U == (IData)(vlSelfRef.tb_read_path__DOT__u_mem__DOT__remaining));
                    }
                }
            } else {
                vlSelfRef.__Vdly__tb_read_path__DOT__aq_s_rvalid = 1U;
                vlSelfRef.tb_read_path__DOT__aq_s_rdata 
                    = ((0x707ffU >= (0x7ffffU & (vlSelfRef.tb_read_path__DOT__u_mem__DOT__cur_addr 
                                                 >> 3U)))
                        ? vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem
                       [(0x7ffffU & (vlSelfRef.tb_read_path__DOT__u_mem__DOT__cur_addr 
                                     >> 3U))] : 0ULL);
                vlSelfRef.tb_read_path__DOT__aq_s_rlast 
                    = (1U == (IData)(vlSelfRef.tb_read_path__DOT__u_mem__DOT__remaining));
            }
        }
    }
    vlSelfRef.tb_read_path__DOT__u_mem__DOT__active 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__active;
    vlSelfRef.tb_read_path__DOT__u_mem__DOT__remaining 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__remaining;
    vlSelfRef.tb_read_path__DOT__aq_m_arready = vlSelfRef.__Vdly__tb_read_path__DOT__aq_m_arready;
    vlSelfRef.tb_read_path__DOT__u_mem__DOT__cur_addr 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_mem__DOT__cur_addr;
    vlSelfRef.tb_read_path__DOT__u_mem__DOT__next_addr 
        = ((IData)(8U) + vlSelfRef.tb_read_path__DOT__u_mem__DOT__cur_addr);
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__5(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__5\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb_read_path__DOT__rst_hp) {
        vlSelfRef.tb_read_path__DOT__rd_rfifo_err_w = 0U;
    } else if (((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r) 
                & (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__rd_buf_empty))) {
        vlSelfRef.tb_read_path__DOT__rd_rfifo_err_w = 1U;
    }
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__6(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__6\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb_read_path__DOT__rst_cam) {
        vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__vout_data_r = 0U;
        vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d1 = 0U;
        vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d0 = 0U;
    } else {
        vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__vout_data_r 
            = ((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r_d0)
                ? (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__dout_r)
                : (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d1));
        vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d1 
            = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d0;
        vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d0 
            = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d1;
    }
    if ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam)))) {
        vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d2 
            = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d1;
    }
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r_d0 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r));
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d1 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d0));
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d0 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d1));
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__7(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__7\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid;
    vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs;
    vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__8(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__8\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_fifo_aclr) {
        vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr = 0U;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__dout_r = 0U;
    } else if (((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r) 
                & (~ (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__rd_buf_empty)))) {
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__dout_r 
            = (0xffffU & (IData)((vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem
                                  [(0x7fffU & (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rword))] 
                                  >> (0x3fU & VL_SHIFTL_III(6,32,32, 
                                                            ((IData)(3U) 
                                                             - 
                                                             (3U 
                                                              & vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr)), 4U)))));
        vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
            = (0x3ffffU & ((IData)(1U) + vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr));
    }
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d1 
        = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d0;
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr;
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rword 
        = (0xffffU & (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
                      >> 2U));
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d0 = 0U;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__9(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__9\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.__VdlySet__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0) {
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem[vlSelfRef.__VdlyDim0__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0] 
            = vlSelfRef.__VdlyVal__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0;
    }
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__10(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__10\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r 
        = ((~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam)) 
           & (((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d1) 
               & (0x500U > (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt))) 
              & (0x2d0U > (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt))));
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt;
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__11(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__11\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb_read_path__DOT__rst_hp) {
        vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr = 0U;
        vlSelfRef.tb_read_path__DOT__rd_burst_req = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt = 0U;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_fifo_aclr = 0U;
        vlSelfRef.tb_read_path__DOT__rd_burst_len = 0U;
        vlSelfRef.__Vdly__tb_read_path__DOT__ch0_read_req_ack = 0U;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d1 = 0U;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1 = 0U;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d0 = 0U;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d0 = 0U;
    } else {
        if ((0U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state))) {
            if (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d2) {
                vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = 1U;
            }
            vlSelfRef.__Vdly__tb_read_path__DOT__ch0_read_req_ack = 0U;
        } else if ((1U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state))) {
            if (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d2) {
                vlSelfRef.__Vdly__tb_read_path__DOT__ch0_read_req_ack = 1U;
                vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_fifo_aclr = 1U;
                if ((0U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1))) {
                    vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr = 0U;
                } else if ((1U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1))) {
                    vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr = 0x38400U;
                } else if ((2U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1))) {
                    vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr = 0U;
                } else if ((3U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1))) {
                    vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr = 0U;
                }
                vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch 
                    = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d1;
            } else {
                vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = 2U;
                vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_fifo_aclr = 0U;
                vlSelfRef.__Vdly__tb_read_path__DOT__ch0_read_req_ack = 0U;
            }
            vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt = 0U;
        } else if ((2U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state))) {
            if (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d2) {
                vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = 1U;
            } else if ((0x7ff0U > (0x7fffU & (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used)))) {
                vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = 3U;
                vlSelfRef.tb_read_path__DOT__rd_burst_len = 0x10U;
                vlSelfRef.tb_read_path__DOT__rd_burst_req = 1U;
            }
        } else if ((3U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state))) {
            if (vlSelfRef.tb_read_path__DOT__aq_s_rvalid) {
                vlSelfRef.tb_read_path__DOT__rd_burst_req = 0U;
            }
            if ((5U == (IData)(vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state))) {
                vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt 
                    = (0x7ffffffU & ((IData)(0x10U) 
                                     + vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt));
                vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr 
                    = (0x7ffffffU & ((IData)(0x10U) 
                                     + vlSelfRef.tb_read_path__DOT__rd_burst_addr));
                vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = 4U;
            }
        } else {
            vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state 
                = ((4U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state))
                    ? ((IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d2)
                        ? 1U : ((vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt 
                                 < vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch)
                                 ? 2U : 5U)) : 0U);
        }
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d1 
            = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d0;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1 
            = vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d0;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d0 = 0x38400U;
        vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d0 
            = vlSelfRef.tb_read_path__DOT__buf_sel_sync2;
    }
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch;
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt;
    vlSelfRef.tb_read_path__DOT__u_aq_axi_master__DOT__rd_state 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state;
    vlSelfRef.tb_read_path__DOT__rd_burst_addr = vlSelfRef.__Vdly__tb_read_path__DOT__rd_burst_addr;
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d2 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d1));
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d1 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d0));
    vlSelfRef.tb_read_path__DOT__buf_sel_sync2 = ((1U 
                                                   & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
                                                  && (IData)(vlSelfRef.tb_read_path__DOT__buf_sel_sync1));
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d0 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__ch0_read_req_sync));
    vlSelfRef.tb_read_path__DOT__buf_sel_sync1 = ((1U 
                                                   & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
                                                  && (IData)(vlSelfRef.tb_read_path__DOT__read_buf_sel));
    vlSelfRef.tb_read_path__DOT__ch0_read_req_sync 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t2));
    vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t2 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t1));
    vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t1 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d2));
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_comb__TOP__0(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_comb__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__rd_buf_empty 
        = ((0xffffU & (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
                       >> 2U)) == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr));
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used 
        = (0xffffU & ((IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr) 
                      - (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
                         >> 2U)));
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__12(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__12\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d1 
        = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d0;
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d0 
        = vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__video_active_d0;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__13(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__13\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __VdlyVal__tb_read_path__DOT__frame_beat__v0;
    __VdlyVal__tb_read_path__DOT__frame_beat__v0 = 0;
    CData/*1:0*/ __VdlyDim0__tb_read_path__DOT__frame_beat__v0;
    __VdlyDim0__tb_read_path__DOT__frame_beat__v0 = 0;
    // Body
    if (((5U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state)) 
         & (~ (IData)(vlSelfRef.tb_read_path__DOT__prev_read_finish)))) {
        __VdlyVal__tb_read_path__DOT__frame_beat__v0 
            = vlSelfRef.tb_read_path__DOT__beat_frame;
        __VdlyDim0__tb_read_path__DOT__frame_beat__v0 
            = (3U & vlSelfRef.tb_read_path__DOT__rfin_cnt);
        vlSelfRef.__VdlySet__tb_read_path__DOT__frame_beat__v0 = 1U;
        vlSelfRef.__Vdly__tb_read_path__DOT__rfin_cnt 
            = ((IData)(1U) + vlSelfRef.tb_read_path__DOT__rfin_cnt);
        if ((1U == vlSelfRef.tb_read_path__DOT__rfin_cnt)) {
            vlSelfRef.tb_read_path__DOT__read_buf_sel = 1U;
        }
        vlSelfRef.__Vdly__tb_read_path__DOT__beat_frame = 0U;
    }
    if (((IData)(vlSelfRef.tb_read_path__DOT__aq_s_rvalid) 
         & (IData)(vlSelfRef.tb_read_path__DOT__aq_m_rready))) {
        vlSelfRef.__Vdly__tb_read_path__DOT__beat_frame 
            = ((IData)(1U) + vlSelfRef.tb_read_path__DOT__beat_frame);
    }
    vlSelfRef.tb_read_path__DOT__rfin_cnt = vlSelfRef.__Vdly__tb_read_path__DOT__rfin_cnt;
    vlSelfRef.tb_read_path__DOT__beat_frame = vlSelfRef.__Vdly__tb_read_path__DOT__beat_frame;
    if (vlSelfRef.__VdlySet__tb_read_path__DOT__frame_beat__v0) {
        vlSelfRef.tb_read_path__DOT__frame_beat[__VdlyDim0__tb_read_path__DOT__frame_beat__v0] 
            = __VdlyVal__tb_read_path__DOT__frame_beat__v0;
    }
    vlSelfRef.tb_read_path__DOT__aq_s_rvalid = vlSelfRef.__Vdly__tb_read_path__DOT__aq_s_rvalid;
    vlSelfRef.tb_read_path__DOT__prev_read_finish = 
        (5U == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state));
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__14(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__14\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d2 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d1));
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__video_active_d0 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__video_active));
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__video_active 
        = ((IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_active) 
           & (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_active));
    vlSelfRef.tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d1 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__ch0_read_req));
    if (vlSelfRef.tb_read_path__DOT__rst_cam) {
        vlSelfRef.tb_read_path__DOT__ch0_read_req = 0U;
    } else if (((IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_vs_d0) 
                & (~ (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d1)))) {
        vlSelfRef.tb_read_path__DOT__ch0_read_req = 1U;
    } else if (vlSelfRef.tb_read_path__DOT__ch0_read_req_ack_sync) {
        vlSelfRef.tb_read_path__DOT__ch0_read_req = 0U;
    }
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__pos_vs_d0 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d1));
    vlSelfRef.tb_read_path__DOT__ch0_read_req_ack_sync 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t2));
    vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t2 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t1));
    vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t1 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d2));
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_comb__TOP__1(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_comb__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__aq_m_rready = ((0x8000U 
                                                 > (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used)) 
                                                & (IData)(vlSelfRef.tb_read_path__DOT__aq_s_rvalid));
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__15(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__15\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state;
    vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d2 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d1));
    vlSelfRef.tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d1 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_hp))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__ch0_read_req_ack));
    vlSelfRef.tb_read_path__DOT__ch0_read_req_ack = vlSelfRef.__Vdly__tb_read_path__DOT__ch0_read_req_ack;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__16(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__16\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d1 
        = vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d0;
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d0 
        = vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__vs_reg_d0;
}

VL_INLINE_OPT void Vtb_read_path___024root___nba_sequent__TOP__17(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___nba_sequent__TOP__17\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__vs_reg_d0 
        = ((1U & (~ (IData)(vlSelfRef.tb_read_path__DOT__rst_cam))) 
           && (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__vs_reg));
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__vs_reg 
        = vlSelfRef.__Vdly__tb_read_path__DOT__u_color_bar__DOT__vs_reg;
}

void Vtb_read_path___024root___timing_resume(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___timing_resume\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x10ULL & vlSelfRef.__VactTriggered.word(0U))) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_read_path___024root___eval_triggers__act(Vtb_read_path___024root* vlSelf);

bool Vtb_read_path___024root___eval_phase__act(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_phase__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlTriggerVec<5> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb_read_path___024root___eval_triggers__act(vlSelf);
    __VactExecute = vlSelfRef.__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelfRef.__VactTriggered, vlSelfRef.__VnbaTriggered);
        vlSelfRef.__VnbaTriggered.thisOr(vlSelfRef.__VactTriggered);
        Vtb_read_path___024root___timing_resume(vlSelf);
        Vtb_read_path___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_read_path___024root___eval_phase__nba(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_phase__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelfRef.__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vtb_read_path___024root___eval_nba(vlSelf);
        vlSelfRef.__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_read_path___024root___dump_triggers__nba(Vtb_read_path___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_read_path___024root___dump_triggers__act(Vtb_read_path___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_read_path___024root___eval(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval\n"); );
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
            Vtb_read_path___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 19, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelfRef.__VactIterCount = 0U;
        vlSelfRef.__VactContinue = 1U;
        while (vlSelfRef.__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelfRef.__VactIterCount))) {
#ifdef VL_DEBUG
                Vtb_read_path___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 19, "", "Active region did not converge.");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
            vlSelfRef.__VactContinue = 0U;
            if (Vtb_read_path___024root___eval_phase__act(vlSelf)) {
                vlSelfRef.__VactContinue = 1U;
            }
        }
        if (Vtb_read_path___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vtb_read_path___024root___eval_debug_assertions(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_debug_assertions\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
