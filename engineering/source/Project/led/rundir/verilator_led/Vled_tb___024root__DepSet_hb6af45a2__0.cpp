// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vled_tb.h for the primary calling header

#include "Vled_tb__pch.h"
#include "Vled_tb__Syms.h"
#include "Vled_tb___024root.h"

VL_INLINE_OPT VlCoroutine Vled_tb___024root___eval_initial__TOP__Vtiming__0(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*3:0*/ __Vtask_led_tb__DOT__check_led__0__expected;
    __Vtask_led_tb__DOT__check_led__0__expected = 0;
    CData/*3:0*/ __Vtask_led_tb__DOT__check_led__1__expected;
    __Vtask_led_tb__DOT__check_led__1__expected = 0;
    CData/*3:0*/ __Vtask_led_tb__DOT__check_led__2__expected;
    __Vtask_led_tb__DOT__check_led__2__expected = 0;
    CData/*3:0*/ __Vtask_led_tb__DOT__check_led__3__expected;
    __Vtask_led_tb__DOT__check_led__3__expected = 0;
    CData/*3:0*/ __Vtask_led_tb__DOT__check_led__4__expected;
    __Vtask_led_tb__DOT__check_led__4__expected = 0;
    CData/*3:0*/ __Vtask_led_tb__DOT__check_led__5__expected;
    __Vtask_led_tb__DOT__check_led__5__expected = 0;
    // Body
    vlSelfRef.led_tb__DOT__rst_n = 0U;
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         38);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         38);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "rundir/simulation/led_tb.v", 
                                         39);
    __Vtask_led_tb__DOT__check_led__0__expected = 1U;
    if (VL_UNLIKELY(((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                     != (IData)(__Vtask_led_tb__DOT__check_led__0__expected)))) {
        VL_WRITEF_NX("FAIL: expected led=%b, actual led=%b\n[%0t] %%Fatal: led_tb.v:31: Assertion failed in %Nled_tb.check_led\n",0,
                     4,__Vtask_led_tb__DOT__check_led__0__expected,
                     4,(IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern),
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("rundir/simulation/led_tb.v", 31, "", false);
    }
    vlSelfRef.led_tb__DOT__rst_n = 1U;
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         42);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "rundir/simulation/led_tb.v", 
                                         43);
    __Vtask_led_tb__DOT__check_led__1__expected = 2U;
    if (VL_UNLIKELY(((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                     != (IData)(__Vtask_led_tb__DOT__check_led__1__expected)))) {
        VL_WRITEF_NX("FAIL: expected led=%b, actual led=%b\n[%0t] %%Fatal: led_tb.v:31: Assertion failed in %Nled_tb.check_led\n",0,
                     4,__Vtask_led_tb__DOT__check_led__1__expected,
                     4,(IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern),
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("rundir/simulation/led_tb.v", 31, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         44);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "rundir/simulation/led_tb.v", 
                                         45);
    __Vtask_led_tb__DOT__check_led__2__expected = 4U;
    if (VL_UNLIKELY(((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                     != (IData)(__Vtask_led_tb__DOT__check_led__2__expected)))) {
        VL_WRITEF_NX("FAIL: expected led=%b, actual led=%b\n[%0t] %%Fatal: led_tb.v:31: Assertion failed in %Nled_tb.check_led\n",0,
                     4,__Vtask_led_tb__DOT__check_led__2__expected,
                     4,(IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern),
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("rundir/simulation/led_tb.v", 31, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         46);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "rundir/simulation/led_tb.v", 
                                         47);
    __Vtask_led_tb__DOT__check_led__3__expected = 8U;
    if (VL_UNLIKELY(((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                     != (IData)(__Vtask_led_tb__DOT__check_led__3__expected)))) {
        VL_WRITEF_NX("FAIL: expected led=%b, actual led=%b\n[%0t] %%Fatal: led_tb.v:31: Assertion failed in %Nled_tb.check_led\n",0,
                     4,__Vtask_led_tb__DOT__check_led__3__expected,
                     4,(IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern),
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("rundir/simulation/led_tb.v", 31, "", false);
    }
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VtrigSched_hbf655e20__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge led_tb.clk)", 
                                                         "rundir/simulation/led_tb.v", 
                                                         48);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "rundir/simulation/led_tb.v", 
                                         49);
    __Vtask_led_tb__DOT__check_led__4__expected = 1U;
    if (VL_UNLIKELY(((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                     != (IData)(__Vtask_led_tb__DOT__check_led__4__expected)))) {
        VL_WRITEF_NX("FAIL: expected led=%b, actual led=%b\n[%0t] %%Fatal: led_tb.v:31: Assertion failed in %Nled_tb.check_led\n",0,
                     4,__Vtask_led_tb__DOT__check_led__4__expected,
                     4,(IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern),
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("rundir/simulation/led_tb.v", 31, "", false);
    }
    vlSelfRef.led_tb__DOT__rst_n = 0U;
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "rundir/simulation/led_tb.v", 
                                         53);
    __Vtask_led_tb__DOT__check_led__5__expected = 1U;
    if (VL_UNLIKELY(((IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern) 
                     != (IData)(__Vtask_led_tb__DOT__check_led__5__expected)))) {
        VL_WRITEF_NX("FAIL: expected led=%b, actual led=%b\n[%0t] %%Fatal: led_tb.v:31: Assertion failed in %Nled_tb.check_led\n",0,
                     4,__Vtask_led_tb__DOT__check_led__5__expected,
                     4,(IData)(vlSelfRef.led_tb__DOT__dut__DOT__led_pattern),
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("rundir/simulation/led_tb.v", 31, "", false);
    }
    VL_WRITEF_NX("PASS: led running-light sequence and reset behavior verified\n",0);
    VL_FINISH_MT("rundir/simulation/led_tb.v", 56, "");
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vled_tb___024root___dump_triggers__act(Vled_tb___024root* vlSelf);
#endif  // VL_DEBUG

void Vled_tb___024root___eval_triggers__act(Vled_tb___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vled_tb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vled_tb___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((IData)(vlSelfRef.led_tb__DOT__clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__led_tb__DOT__clk__0))));
    vlSelfRef.__VactTriggered.set(1U, ((~ (IData)(vlSelfRef.led_tb__DOT__rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__led_tb__DOT__rst_n__0)));
    vlSelfRef.__VactTriggered.set(2U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__led_tb__DOT__clk__0 
        = vlSelfRef.led_tb__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__led_tb__DOT__rst_n__0 
        = vlSelfRef.led_tb__DOT__rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vled_tb___024root___dump_triggers__act(vlSelf);
    }
#endif
}
