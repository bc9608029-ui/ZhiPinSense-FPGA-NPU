// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_top_lite.h for the primary calling header

#include "Vtb_top_lite__pch.h"
#include "Vtb_top_lite__Syms.h"
#include "Vtb_top_lite___024root.h"

VL_INLINE_OPT VlCoroutine Vtb_top_lite___024root___eval_initial__TOP__Vtiming__0(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    co_await vlSelfRef.__VtrigSched_hb1cc4010__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_top_lite.pl_clk)", 
                                                         "tb/integration/tb_top_lite.sv", 
                                                         87);
    co_await vlSelfRef.__VtrigSched_hb1cc4010__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_top_lite.pl_clk)", 
                                                         "tb/integration/tb_top_lite.sv", 
                                                         87);
    co_await vlSelfRef.__VtrigSched_hb1cc4010__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_top_lite.pl_clk)", 
                                                         "tb/integration/tb_top_lite.sv", 
                                                         87);
    co_await vlSelfRef.__VtrigSched_hb1cc4121__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_top_lite.pl_clk)", 
                                                         "tb/integration/tb_top_lite.sv", 
                                                         88);
    vlSelfRef.tb_top_lite__DOT__pl_key1_reset = 0U;
    co_await vlSelfRef.__VdlySched.delay(0x1e8480ULL, 
                                         nullptr, "tb/integration/tb_top_lite.sv", 
                                         90);
    VL_WRITEF_NX("[%0t] %%Fatal: tb_top_lite.sv:90: Assertion failed in %Ntb_top_lite: top_lite timeout\n",0,
                 64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
    VL_STOP_MT("tb/integration/tb_top_lite.sv", 90, "", false);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_top_lite___024root___dump_triggers__act(Vtb_top_lite___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_top_lite___024root___eval_triggers__act(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((~ (IData)(vlSelfRef.tb_top_lite__DOT__pl_clk)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_clk__0)));
    vlSelfRef.__VactTriggered.set(1U, ((IData)(vlSelfRef.tb_top_lite__DOT__pl_clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_clk__0))));
    vlSelfRef.__VactTriggered.set(2U, ((IData)(vlSelfRef.tb_top_lite__DOT__pl_key1_reset) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_key1_reset__0))));
    vlSelfRef.__VactTriggered.set(3U, ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core_rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_top_lite__DOT__dut__DOT__core_rst_n__0)));
    vlSelfRef.__VactTriggered.set(4U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_clk__0 
        = vlSelfRef.tb_top_lite__DOT__pl_clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_key1_reset__0 
        = vlSelfRef.tb_top_lite__DOT__pl_key1_reset;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_top_lite__DOT__dut__DOT__core_rst_n__0 
        = vlSelfRef.tb_top_lite__DOT__dut__DOT__core_rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_top_lite___024root___dump_triggers__act(vlSelf);
    }
#endif
}

VL_INLINE_OPT void Vtb_top_lite___024root___nba_sequent__TOP__3(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___nba_sequent__TOP__3\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vdly__tb_top_lite__DOT__received;
    __Vdly__tb_top_lite__DOT__received = 0;
    // Body
    __Vdly__tb_top_lite__DOT__received = vlSelfRef.tb_top_lite__DOT__received;
    vlSelfRef.tb_top_lite__DOT__buffer_release = 0U;
    if (vlSelfRef.tb_top_lite__DOT__m_write_valid) {
        if (VL_UNLIKELY((1U & (~ (IData)(vlSelfRef.tb_top_lite__DOT__m_write_valid))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_top_lite.sv:72: Assertion failed in %Ntb_top_lite: top_lite frame_valid missing\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/integration/tb_top_lite.sv", 72, "", false);
        }
        if (VL_UNLIKELY((((IData)(vlSelfRef.tb_top_lite__DOT__m_write_valid) 
                          & (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_frame_start)) 
                         != (0U == (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_sample_index))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_top_lite.sv:73: Assertion failed in %Ntb_top_lite: top_lite start mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/integration/tb_top_lite.sv", 73, "", false);
        }
        if (VL_UNLIKELY((((IData)(vlSelfRef.tb_top_lite__DOT__m_write_valid) 
                          & (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_frame_end)) 
                         != (3U == (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_sample_index))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_top_lite.sv:75: Assertion failed in %Ntb_top_lite: top_lite done mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/integration/tb_top_lite.sv", 75, "", false);
        }
        __Vdly__tb_top_lite__DOT__received = ((IData)(1U) 
                                              + vlSelfRef.tb_top_lite__DOT__received);
        if (VL_UNLIKELY(vlSelfRef.tb_top_lite__DOT__m_irq)) {
            if (VL_UNLIKELY((4U != ((IData)(1U) + vlSelfRef.tb_top_lite__DOT__received)))) {
                VL_WRITEF_NX("[%0t] %%Fatal: tb_top_lite.sv:79: Assertion failed in %Ntb_top_lite: top_lite early IRQ\n",0,
                             64,VL_TIME_UNITED_Q(1000),
                             -9,vlSymsp->name());
                VL_STOP_MT("tb/integration/tb_top_lite.sv", 79, "", false);
            }
            vlSelfRef.tb_top_lite__DOT__buffer_release 
                = ((IData)(vlSelfRef.tb_top_lite__DOT__buffer_release) 
                   | (3U & ((IData)(1U) << (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__fill_buffer))));
            VL_WRITEF_NX("PASS tb_top_lite samples=%0d\n",0,
                         32,((IData)(1U) + vlSelfRef.tb_top_lite__DOT__received));
            VL_FINISH_MT("tb/integration/tb_top_lite.sv", 81, "");
        }
    }
    vlSelfRef.tb_top_lite__DOT__received = __Vdly__tb_top_lite__DOT__received;
}
