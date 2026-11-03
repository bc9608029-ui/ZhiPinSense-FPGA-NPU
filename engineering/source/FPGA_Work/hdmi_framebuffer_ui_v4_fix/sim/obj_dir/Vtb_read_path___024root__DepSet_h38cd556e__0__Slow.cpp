// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_read_path.h for the primary calling header

#include "Vtb_read_path__pch.h"
#include "Vtb_read_path___024root.h"

VL_ATTR_COLD void Vtb_read_path___024root___eval_static__TOP(Vtb_read_path___024root* vlSelf);

VL_ATTR_COLD void Vtb_read_path___024root___eval_static(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_static\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_read_path___024root___eval_static__TOP(vlSelf);
}

VL_ATTR_COLD void Vtb_read_path___024root___eval_static__TOP(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_static__TOP\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__hp_clk = 0U;
    vlSelfRef.tb_read_path__DOT__cam_clk = 0U;
    vlSelfRef.tb_read_path__DOT__rst_hp = 1U;
    vlSelfRef.tb_read_path__DOT__rst_cam = 1U;
    vlSelfRef.tb_read_path__DOT__read_buf_sel = 0U;
    vlSelfRef.tb_read_path__DOT__rfin_cnt = 0U;
    vlSelfRef.tb_read_path__DOT__beat_frame = 0U;
    vlSelfRef.tb_read_path__DOT__full_event = 0U;
    vlSelfRef.tb_read_path__DOT__full_cycles = 0U;
    vlSelfRef.tb_read_path__DOT__drop_we = 0U;
    vlSelfRef.tb_read_path__DOT__rreq_cnt = 0U;
    vlSelfRef.tb_read_path__DOT__measuring = 0U;
    vlSelfRef.tb_read_path__DOT__cur_buf1 = 0U;
    vlSelfRef.tb_read_path__DOT__mismatch_buf0 = 0U;
    vlSelfRef.tb_read_path__DOT__mismatch_buf1 = 0U;
    vlSelfRef.tb_read_path__DOT__valid_px_cnt = 0U;
    vlSelfRef.tb_read_path__DOT__line_cnt = 0U;
    vlSelfRef.tb_read_path__DOT__underflow_cnt = 0U;
    vlSelfRef.tb_read_path__DOT__px_in_line = 0U;
    vlSelfRef.tb_read_path__DOT__first_mm_x = 0xffffffffU;
    vlSelfRef.tb_read_path__DOT__first_mm_y = 0xffffffffU;
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt = 0U;
    vlSelfRef.tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt = 0U;
}

VL_ATTR_COLD void Vtb_read_path___024root___eval_initial__TOP(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_initial__TOP\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ tb_read_path__DOT__u_mem__DOT__y;
    tb_read_path__DOT__u_mem__DOT__y = 0;
    IData/*31:0*/ tb_read_path__DOT__u_mem__DOT__i;
    tb_read_path__DOT__u_mem__DOT__i = 0;
    // Body
    tb_read_path__DOT__u_mem__DOT__i = 0U;
    while (VL_GTS_III(32, 0x70800U, tb_read_path__DOT__u_mem__DOT__i)) {
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h5db7fe97__0 = 0ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & tb_read_path__DOT__u_mem__DOT__i)))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & tb_read_path__DOT__u_mem__DOT__i)] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h5db7fe97__0;
        }
        tb_read_path__DOT__u_mem__DOT__i = ((IData)(1U) 
                                            + tb_read_path__DOT__u_mem__DOT__i);
    }
    tb_read_path__DOT__u_mem__DOT__y = 0U;
    while (VL_GTS_III(32, 0x2d0U, tb_read_path__DOT__u_mem__DOT__y)) {
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x3000200010000ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x7000600050004ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(1U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(1U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0xb000a00090008ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(2U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(2U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0xf000e000d000cULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(3U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(3U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x13001200110010ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(4U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(4U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x17001600150014ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(5U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(5U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x1b001a00190018ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(6U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(6U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x1f001e001d001cULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(7U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(7U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x23002200210020ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(8U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(8U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = 0x27002600250024ULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(9U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(9U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        }
        tb_read_path__DOT__u_mem__DOT__i = 0xaU;
        tb_read_path__DOT__u_mem__DOT__y = ((IData)(1U) 
                                            + tb_read_path__DOT__u_mem__DOT__y);
    }
    tb_read_path__DOT__u_mem__DOT__y = 0U;
    while (VL_GTS_III(32, 0x2d0U, tb_read_path__DOT__u_mem__DOT__y)) {
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38400U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38400U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38401U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38401U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38402U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38402U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38403U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38403U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38404U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38404U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38405U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38405U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38406U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38406U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38407U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38407U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38408U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38408U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = 0xff00ff00ff00ffULL;
        if (VL_LIKELY((0x707ffU >= (0x7ffffU & ((IData)(0x38409U) 
                                                + VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))))) {
            vlSelfRef.tb_read_path__DOT__u_mem__DOT__mem[(0x7ffffU 
                                                          & ((IData)(0x38409U) 
                                                             + 
                                                             VL_MULS_III(32, (IData)(0x140U), tb_read_path__DOT__u_mem__DOT__y)))] 
                = vlSelfRef.tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        }
        tb_read_path__DOT__u_mem__DOT__i = 0xaU;
        tb_read_path__DOT__u_mem__DOT__y = ((IData)(1U) 
                                            + tb_read_path__DOT__u_mem__DOT__y);
    }
}

VL_ATTR_COLD void Vtb_read_path___024root___eval_final(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_final\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_read_path___024root___dump_triggers__stl(Vtb_read_path___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vtb_read_path___024root___eval_phase__stl(Vtb_read_path___024root* vlSelf);

VL_ATTR_COLD void Vtb_read_path___024root___eval_settle(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_settle\n"); );
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
            Vtb_read_path___024root___dump_triggers__stl(vlSelf);
#endif
            VL_FATAL_MT("/mnt/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/sim/tb_read_path.sv", 19, "", "Settle region did not converge.");
        }
        __VstlIterCount = ((IData)(1U) + __VstlIterCount);
        __VstlContinue = 0U;
        if (Vtb_read_path___024root___eval_phase__stl(vlSelf)) {
            __VstlContinue = 1U;
        }
        vlSelfRef.__VstlFirstIteration = 0U;
    }
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_read_path___024root___dump_triggers__stl(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___dump_triggers__stl\n"); );
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

VL_ATTR_COLD void Vtb_read_path___024root___stl_sequent__TOP__0(Vtb_read_path___024root* vlSelf);

VL_ATTR_COLD void Vtb_read_path___024root___eval_stl(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_stl\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VstlTriggered.word(0U))) {
        Vtb_read_path___024root___stl_sequent__TOP__0(vlSelf);
    }
}

VL_ATTR_COLD void Vtb_read_path___024root___stl_sequent__TOP__0(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___stl_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rword 
        = (0xffffU & (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
                      >> 2U));
    vlSelfRef.tb_read_path__DOT__u_mem__DOT__next_addr 
        = ((IData)(8U) + vlSelfRef.tb_read_path__DOT__u_mem__DOT__cur_addr);
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__rd_buf_empty 
        = ((0xffffU & (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
                       >> 2U)) == (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr));
    vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__video_active 
        = ((IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__h_active) 
           & (IData)(vlSelfRef.tb_read_path__DOT__u_color_bar__DOT__v_active));
    vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used 
        = (0xffffU & ((IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr) 
                      - (vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr 
                         >> 2U)));
    vlSelfRef.tb_read_path__DOT__aq_m_rready = ((0x8000U 
                                                 > (IData)(vlSelfRef.tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used)) 
                                                & (IData)(vlSelfRef.tb_read_path__DOT__aq_s_rvalid));
}

VL_ATTR_COLD void Vtb_read_path___024root___eval_triggers__stl(Vtb_read_path___024root* vlSelf);

VL_ATTR_COLD bool Vtb_read_path___024root___eval_phase__stl(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_phase__stl\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VstlExecute;
    // Body
    Vtb_read_path___024root___eval_triggers__stl(vlSelf);
    __VstlExecute = vlSelfRef.__VstlTriggered.any();
    if (__VstlExecute) {
        Vtb_read_path___024root___eval_stl(vlSelf);
    }
    return (__VstlExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_read_path___024root___dump_triggers__act(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___dump_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VactTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 0 is active: @(posedge tb_read_path.hp_clk)\n");
    }
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 1 is active: @(posedge tb_read_path.rst_hp)\n");
    }
    if ((4ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 2 is active: @(posedge tb_read_path.cam_clk)\n");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 3 is active: @(posedge tb_read_path.rst_cam)\n");
    }
    if ((0x10ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 4 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_read_path___024root___dump_triggers__nba(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___dump_triggers__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VnbaTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(posedge tb_read_path.hp_clk)\n");
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 1 is active: @(posedge tb_read_path.rst_hp)\n");
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 2 is active: @(posedge tb_read_path.cam_clk)\n");
    }
    if ((8ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 3 is active: @(posedge tb_read_path.rst_cam)\n");
    }
    if ((0x10ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 4 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_read_path___024root___ctor_var_reset(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___ctor_var_reset\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelf->tb_read_path__DOT__hp_clk = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__cam_clk = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__rst_hp = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__rst_cam = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__read_buf_sel = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__ch0_read_req = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__ch0_read_req_ack_sync = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__ch0_read_req_sync = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__ch0_read_req_ack = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__buf_sel_sync1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__buf_sel_sync2 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__rd_burst_req = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__rd_burst_len = VL_RAND_RESET_I(10);
    vlSelf->tb_read_path__DOT__rd_burst_addr = VL_RAND_RESET_I(27);
    vlSelf->tb_read_path__DOT__rd_rfifo_err_w = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__aq_m_arready = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__aq_s_rvalid = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__aq_s_rlast = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__aq_m_rready = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__aq_s_rdata = VL_RAND_RESET_Q(64);
    vlSelf->tb_read_path__DOT__prev_read_finish = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__rfin_cnt = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__beat_frame = VL_RAND_RESET_I(32);
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        vlSelf->tb_read_path__DOT__frame_beat[__Vi0] = VL_RAND_RESET_I(32);
    }
    vlSelf->tb_read_path__DOT__prev_rfifo_full = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__full_event = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__full_cycles = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__drop_we = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__prev_read_req = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__rreq_cnt = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__measuring = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__cur_buf1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__mismatch_buf0 = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__mismatch_buf1 = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__valid_px_cnt = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__line_cnt = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__underflow_cnt = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__px_in_line = VL_RAND_RESET_I(12);
    vlSelf->tb_read_path__DOT__prev_de = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__first_mm_x = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__first_mm_y = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__vs_reg = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__vs_reg_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__h_cnt = VL_RAND_RESET_I(12);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__v_cnt = VL_RAND_RESET_I(12);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__h_active = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__v_active = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__video_active = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_color_bar__DOT__video_active_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d0 = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d1 = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__pos_vs_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d2 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__vout_data_r = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d0 = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d1 = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt = VL_RAND_RESET_I(12);
    vlSelf->tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt = VL_RAND_RESET_I(12);
    vlSelf->tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d2 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t2 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d2 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t2 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_fifo_aclr = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__rd_buf_empty = VL_RAND_RESET_I(1);
    for (int __Vi0 = 0; __Vi0 < 32768; ++__Vi0) {
        vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem[__Vi0] = VL_RAND_RESET_Q(64);
    }
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr = VL_RAND_RESET_I(18);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rword = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__dout_r = VL_RAND_RESET_I(16);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d0 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d1 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d2 = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d0 = VL_RAND_RESET_I(27);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d1 = VL_RAND_RESET_I(27);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch = VL_RAND_RESET_I(27);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt = VL_RAND_RESET_I(27);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = VL_RAND_RESET_I(4);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d0 = VL_RAND_RESET_I(2);
    vlSelf->tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1 = VL_RAND_RESET_I(2);
    vlSelf->tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = VL_RAND_RESET_I(3);
    vlSelf->tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len = VL_RAND_RESET_I(8);
    for (int __Vi0 = 0; __Vi0 < 460800; ++__Vi0) {
        vlSelf->tb_read_path__DOT__u_mem__DOT__mem[__Vi0] = VL_RAND_RESET_Q(64);
    }
    vlSelf->tb_read_path__DOT__u_mem__DOT__cur_addr = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__u_mem__DOT__remaining = VL_RAND_RESET_I(8);
    vlSelf->tb_read_path__DOT__u_mem__DOT__active = VL_RAND_RESET_I(1);
    vlSelf->tb_read_path__DOT__u_mem__DOT__next_addr = VL_RAND_RESET_I(32);
    vlSelf->tb_read_path__DOT__u_mem__DOT____Vlvbound_h5db7fe97__0 = VL_RAND_RESET_Q(64);
    vlSelf->tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0 = VL_RAND_RESET_Q(64);
    vlSelf->tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0 = VL_RAND_RESET_Q(64);
    vlSelf->__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state = VL_RAND_RESET_I(4);
    vlSelf->__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch = VL_RAND_RESET_I(27);
    vlSelf->__Vdly__tb_read_path__DOT__rd_burst_addr = VL_RAND_RESET_I(27);
    vlSelf->__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt = VL_RAND_RESET_I(27);
    vlSelf->__Vdly__tb_read_path__DOT__ch0_read_req_ack = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_read_path__DOT__rfin_cnt = VL_RAND_RESET_I(32);
    vlSelf->__Vdly__tb_read_path__DOT__beat_frame = VL_RAND_RESET_I(32);
    vlSelf->__Vdly__tb_read_path__DOT__aq_m_arready = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_read_path__DOT__u_mem__DOT__active = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_read_path__DOT__aq_s_rvalid = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_read_path__DOT__u_mem__DOT__cur_addr = VL_RAND_RESET_I(32);
    vlSelf->__Vdly__tb_read_path__DOT__u_mem__DOT__remaining = VL_RAND_RESET_I(8);
    vlSelf->__Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr = VL_RAND_RESET_I(18);
    vlSelf->__Vdly__tb_read_path__DOT__u_color_bar__DOT__vs_reg = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt = VL_RAND_RESET_I(12);
    vlSelf->__Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt = VL_RAND_RESET_I(12);
    vlSelf->__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state = VL_RAND_RESET_I(3);
    vlSelf->__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs = VL_RAND_RESET_I(32);
    vlSelf->__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len = VL_RAND_RESET_I(8);
    vlSelf->__VdlySet__tb_read_path__DOT__frame_beat__v0 = 0;
    vlSelf->__VdlyVal__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0 = VL_RAND_RESET_Q(64);
    vlSelf->__VdlyDim0__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0 = VL_RAND_RESET_I(15);
    vlSelf->__VdlySet__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0 = 0;
    vlSelf->__Vtrigprevexpr___TOP__tb_read_path__DOT__hp_clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_hp__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_read_path__DOT__cam_clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_cam__0 = VL_RAND_RESET_I(1);
}
