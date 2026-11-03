// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_iq_stream_fifo.h for the primary calling header

#include "Vtb_iq_stream_fifo__pch.h"
#include "Vtb_iq_stream_fifo__Syms.h"
#include "Vtb_iq_stream_fifo___024root.h"

VL_INLINE_OPT VlCoroutine Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__0(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vtask_tb_iq_stream_fifo__DOT__push__0__value;
    __Vtask_tb_iq_stream_fifo__DOT__push__0__value = 0;
    IData/*31:0*/ __Vtask_tb_iq_stream_fifo__DOT__push__1__value;
    __Vtask_tb_iq_stream_fifo__DOT__push__1__value = 0;
    IData/*31:0*/ __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__2__expected;
    __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__2__expected = 0;
    IData/*31:0*/ __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__3__expected;
    __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__3__expected = 0;
    // Body
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         51);
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         51);
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         51);
    vlSelfRef.tb_iq_stream_fifo__DOT__rst_n = 1U;
    __Vtask_tb_iq_stream_fifo__DOT__push__0__value = 0xbU;
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         27);
    if (VL_UNLIKELY((2U <= (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count)))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:28: Assertion failed in %Ntb_iq_stream_fifo.push: FIFO unexpectedly full\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 28, "", false);
    }
    vlSelfRef.tb_iq_stream_fifo__DOT__s_i = (0xffffU 
                                             & __Vtask_tb_iq_stream_fifo__DOT__push__0__value);
    vlSelfRef.tb_iq_stream_fifo__DOT__s_q = (0xffffU 
                                             & (- __Vtask_tb_iq_stream_fifo__DOT__push__0__value));
    vlSelfRef.tb_iq_stream_fifo__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         32);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_iq_stream_fifo.sv", 
                                         32);
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         33);
    vlSelfRef.tb_iq_stream_fifo__DOT__s_valid = 0U;
    __Vtask_tb_iq_stream_fifo__DOT__push__1__value = 0x16U;
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         27);
    if (VL_UNLIKELY((2U <= (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count)))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:28: Assertion failed in %Ntb_iq_stream_fifo.push: FIFO unexpectedly full\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 28, "", false);
    }
    vlSelfRef.tb_iq_stream_fifo__DOT__s_i = (0xffffU 
                                             & __Vtask_tb_iq_stream_fifo__DOT__push__1__value);
    vlSelfRef.tb_iq_stream_fifo__DOT__s_q = (0xffffU 
                                             & (- __Vtask_tb_iq_stream_fifo__DOT__push__1__value));
    vlSelfRef.tb_iq_stream_fifo__DOT__s_valid = 1U;
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         32);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_iq_stream_fifo.sv", 
                                         32);
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         33);
    vlSelfRef.tb_iq_stream_fifo__DOT__s_valid = 0U;
    if (VL_UNLIKELY(((2U > (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count)) 
                     | (2U != (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count))))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:55: Assertion failed in %Ntb_iq_stream_fifo: FIFO full state mismatch\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 55, "", false);
    }
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         58);
    vlSelfRef.tb_iq_stream_fifo__DOT__s_valid = 1U;
    vlSelfRef.tb_iq_stream_fifo__DOT__s_i = 0x21U;
    vlSelfRef.tb_iq_stream_fifo__DOT__s_overflow_event = 0U;
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         59);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_iq_stream_fifo.sv", 
                                         59);
    if (VL_UNLIKELY((0U != vlSelfRef.tb_iq_stream_fifo__DOT__overflow_count))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:60: Assertion failed in %Ntb_iq_stream_fifo: Backpressure counted as overflow\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 60, "", false);
    }
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         63);
    vlSelfRef.tb_iq_stream_fifo__DOT__s_overflow_event = 1U;
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         64);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_iq_stream_fifo.sv", 
                                         64);
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         65);
    vlSelfRef.tb_iq_stream_fifo__DOT__s_overflow_event = 0U;
    vlSelfRef.tb_iq_stream_fifo__DOT__s_valid = 0U;
    if (VL_UNLIKELY((1U != vlSelfRef.tb_iq_stream_fifo__DOT__overflow_count))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:66: Assertion failed in %Ntb_iq_stream_fifo: Explicit overflow was not counted\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 66, "", false);
    }
    __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__2__expected = 0xbU;
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         41);
    if (VL_UNLIKELY(((0U == (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count)) 
                     | (VL_EXTENDS_II(32,16, vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__i_mem
                                      [vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__read_pointer]) 
                        != __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__2__expected)))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:42: Assertion failed in %Ntb_iq_stream_fifo.pop_and_check: FIFO order mismatch\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 42, "", false);
    }
    vlSelfRef.tb_iq_stream_fifo__DOT__m_ready = 1U;
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         44);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_iq_stream_fifo.sv", 
                                         44);
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         45);
    vlSelfRef.tb_iq_stream_fifo__DOT__m_ready = 0U;
    __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__3__expected = 0x16U;
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         41);
    if (VL_UNLIKELY(((0U == (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count)) 
                     | (VL_EXTENDS_II(32,16, vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__i_mem
                                      [vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__read_pointer]) 
                        != __Vtask_tb_iq_stream_fifo__DOT__pop_and_check__3__expected)))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:42: Assertion failed in %Ntb_iq_stream_fifo.pop_and_check: FIFO order mismatch\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 42, "", false);
    }
    vlSelfRef.tb_iq_stream_fifo__DOT__m_ready = 1U;
    co_await vlSelfRef.__VtrigSched_h55ea73d2__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         44);
    co_await vlSelfRef.__VdlySched.delay(0x3e8ULL, 
                                         nullptr, "tb/unit/tb_iq_stream_fifo.sv", 
                                         44);
    co_await vlSelfRef.__VtrigSched_h55ea7393__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_iq_stream_fifo.clk)", 
                                                         "tb/unit/tb_iq_stream_fifo.sv", 
                                                         45);
    vlSelfRef.tb_iq_stream_fifo__DOT__m_ready = 0U;
    if (VL_UNLIKELY((IData)((0U != (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__dut__DOT__count))))) {
        VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_stream_fifo.sv:70: Assertion failed in %Ntb_iq_stream_fifo: FIFO empty state mismatch\n",0,
                     64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
        VL_STOP_MT("tb/unit/tb_iq_stream_fifo.sv", 70, "", false);
    }
    VL_WRITEF_NX("PASS tb_iq_stream_fifo\n",0);
    VL_FINISH_MT("tb/unit/tb_iq_stream_fifo.sv", 72, "");
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_stream_fifo___024root___dump_triggers__act(Vtb_iq_stream_fifo___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_iq_stream_fifo___024root___eval_triggers__act(Vtb_iq_stream_fifo___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_stream_fifo__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_stream_fifo___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((IData)(vlSelfRef.tb_iq_stream_fifo__DOT__clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__clk__0))));
    vlSelfRef.__VactTriggered.set(1U, ((~ (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__rst_n__0)));
    vlSelfRef.__VactTriggered.set(2U, ((~ (IData)(vlSelfRef.tb_iq_stream_fifo__DOT__clk)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__clk__0)));
    vlSelfRef.__VactTriggered.set(3U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__clk__0 
        = vlSelfRef.tb_iq_stream_fifo__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_stream_fifo__DOT__rst_n__0 
        = vlSelfRef.tb_iq_stream_fifo__DOT__rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_iq_stream_fifo___024root___dump_triggers__act(vlSelf);
    }
#endif
}
