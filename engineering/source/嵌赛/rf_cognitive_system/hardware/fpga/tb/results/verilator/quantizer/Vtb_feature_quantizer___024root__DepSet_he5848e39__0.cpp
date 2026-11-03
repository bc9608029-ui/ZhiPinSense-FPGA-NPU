// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_feature_quantizer.h for the primary calling header

#include "Vtb_feature_quantizer__pch.h"
#include "Vtb_feature_quantizer__Syms.h"
#include "Vtb_feature_quantizer___024root.h"

VL_INLINE_OPT VlCoroutine Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__0(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__0__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__0__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__1__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__1__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__2__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__2__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__3__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__3__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__4__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__4__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__5__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__5__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__6__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__6__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__7__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__7__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected_sat = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__8__raw;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__8__raw = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected = 0;
    IData/*31:0*/ __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected_sat;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected_sat = 0;
    // Body
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         45);
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         45);
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         45);
    vlSelfRef.tb_feature_quantizer__DOT__rst_n = 1U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected_sat = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__0__raw = 0U;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__0__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__0__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__0__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected_sat = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected = 1U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__1__raw = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__1__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__1__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__1__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected_sat = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected = 0xffffffffU;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__2__raw = 0xffffffffU;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__2__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__2__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__2__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected_sat = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected = 1U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__3__raw = 2U;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__3__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__3__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__3__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected_sat = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected = 0xffffffffU;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__4__raw = 0xfffffffeU;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__4__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__4__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__4__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected_sat = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected = 0x7fU;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__5__raw = 0xfdU;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__5__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__5__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__5__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected_sat = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected = 0xffffff81U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__6__raw = 0xffffff03U;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__6__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__6__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__6__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected_sat = 1U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected = 0x7fU;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__7__raw = 0x12cU;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__7__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__7__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__7__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected_sat = 1U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected = 0xffffff81U;
    __Vtask_tb_feature_quantizer__DOT__send_and_check__8__raw = 0xfffffed4U;
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         29);
    vlSelfRef.tb_feature_quantizer__DOT__s_data = (0xffffU 
                                                   & __Vtask_tb_feature_quantizer__DOT__send_and_check__8__raw);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_hc1ab7e2d__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         33);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_feature_quantizer.sv", 
                                         33);
    if (VL_UNLIKELY((1U & (((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_valid)) 
                            | (VL_EXTENDS_II(32,8, (IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data)) 
                               != __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected)) 
                           | ((IData)(vlSelfRef.tb_feature_quantizer__DOT__m_saturated) 
                              != __Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected_sat))))) {
        VL_WRITEF_NX("FAIL quant raw=%0d got=%0d sat=%0# expected=%0d sat=%0d\n[%0t] %%Fatal: tb_feature_quantizer.sv:37: Assertion failed in %Ntb_feature_quantizer.send_and_check\n",0,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__8__raw,
                     8,(IData)(vlSelfRef.tb_feature_quantizer__DOT__m_data),
                     1,vlSelfRef.tb_feature_quantizer__DOT__m_saturated,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected,
                     32,__Vtask_tb_feature_quantizer__DOT__send_and_check__8__expected_sat,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 37, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hc1ab7eec__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_feature_quantizer.clk)", 
                                                         "tb/unit/tb_feature_quantizer.sv", 
                                                         39);
    vlSelfRef.tb_feature_quantizer__DOT__s_valid = 0U;
    if (VL_UNLIKELY((2U != vlSelfRef.tb_feature_quantizer__DOT__saturation_count))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_feature_quantizer.sv:56: Assertion failed in %Ntb_feature_quantizer: FAIL saturation_count=%0#\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name(),
                     32,vlSelfRef.tb_feature_quantizer__DOT__saturation_count);
        VL_STOP_MT("tb/unit/tb_feature_quantizer.sv", 56, "", false);
    }
    VL_WRITEF_NX("PASS tb_feature_quantizer\n",0);
    VL_FINISH_MT("tb/unit/tb_feature_quantizer.sv", 58, "");
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_feature_quantizer___024root___dump_triggers__act(Vtb_feature_quantizer___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_feature_quantizer___024root___eval_triggers__act(Vtb_feature_quantizer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_feature_quantizer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_feature_quantizer___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((IData)(vlSelfRef.tb_feature_quantizer__DOT__clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__clk__0))));
    vlSelfRef.__VactTriggered.set(1U, ((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__rst_n__0)));
    vlSelfRef.__VactTriggered.set(2U, ((~ (IData)(vlSelfRef.tb_feature_quantizer__DOT__clk)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__clk__0)));
    vlSelfRef.__VactTriggered.set(3U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__clk__0 
        = vlSelfRef.tb_feature_quantizer__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_feature_quantizer__DOT__rst_n__0 
        = vlSelfRef.tb_feature_quantizer__DOT__rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_feature_quantizer___024root___dump_triggers__act(vlSelf);
    }
#endif
}
