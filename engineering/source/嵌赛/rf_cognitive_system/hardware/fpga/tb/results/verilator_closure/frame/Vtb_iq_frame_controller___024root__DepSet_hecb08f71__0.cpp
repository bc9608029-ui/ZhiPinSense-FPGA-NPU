// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_iq_frame_controller.h for the primary calling header

#include "Vtb_iq_frame_controller__pch.h"
#include "Vtb_iq_frame_controller__Syms.h"
#include "Vtb_iq_frame_controller___024root.h"

VL_INLINE_OPT VlCoroutine Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__0(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    co_await vlSelfRef.__VtrigSched_h99a03233__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_frame_controller.clk)", 
                                                         "tb/unit/tb_iq_frame_controller.sv", 
                                                         59);
    co_await vlSelfRef.__VtrigSched_h99a03233__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_frame_controller.clk)", 
                                                         "tb/unit/tb_iq_frame_controller.sv", 
                                                         59);
    co_await vlSelfRef.__VtrigSched_h99a03233__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_iq_frame_controller.clk)", 
                                                         "tb/unit/tb_iq_frame_controller.sv", 
                                                         59);
    vlSelfRef.tb_iq_frame_controller__DOT__rst_n = 1U;
    co_await vlSelfRef.__VdlySched.delay(0x1e8480ULL, 
                                         nullptr, "tb/unit/tb_iq_frame_controller.sv", 
                                         61);
    VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_frame_controller.sv:61: Assertion failed in %Ntb_iq_frame_controller: timeout\n",0,
                 64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
    VL_STOP_MT("tb/unit/tb_iq_frame_controller.sv", 61, "", false);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_iq_frame_controller___024root___dump_triggers__act(Vtb_iq_frame_controller___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_iq_frame_controller___024root___eval_triggers__act(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((~ (IData)(vlSelfRef.tb_iq_frame_controller__DOT__clk)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__clk__0)));
    vlSelfRef.__VactTriggered.set(1U, ((IData)(vlSelfRef.tb_iq_frame_controller__DOT__clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__clk__0))));
    vlSelfRef.__VactTriggered.set(2U, ((~ (IData)(vlSelfRef.tb_iq_frame_controller__DOT__rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__rst_n__0)));
    vlSelfRef.__VactTriggered.set(3U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__clk__0 
        = vlSelfRef.tb_iq_frame_controller__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_iq_frame_controller__DOT__rst_n__0 
        = vlSelfRef.tb_iq_frame_controller__DOT__rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_iq_frame_controller___024root___dump_triggers__act(vlSelf);
    }
#endif
}

VL_INLINE_OPT void Vtb_iq_frame_controller___024root___nba_sequent__TOP__1(Vtb_iq_frame_controller___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_iq_frame_controller__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_iq_frame_controller___024root___nba_sequent__TOP__1\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    IData/*31:0*/ __Vdly__tb_iq_frame_controller__DOT__received;
    __Vdly__tb_iq_frame_controller__DOT__received = 0;
    // Body
    __Vdly__tb_iq_frame_controller__DOT__received = vlSelfRef.tb_iq_frame_controller__DOT__received;
    if ((((IData)(vlSelfRef.tb_iq_frame_controller__DOT__rst_n) 
          & (IData)(vlSelfRef.tb_iq_frame_controller__DOT__s_valid)) 
         & (IData)(vlSelfRef.tb_iq_frame_controller__DOT__m_ready))) {
        if (VL_UNLIKELY(((IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__sample_index) 
                         != (3U & VL_MODDIVS_III(32, vlSelfRef.tb_iq_frame_controller__DOT__received, (IData)(4U)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_frame_controller.sv:44: Assertion failed in %Ntb_iq_frame_controller: sample index mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_iq_frame_controller.sv", 44, "", false);
        }
        if (VL_UNLIKELY(((IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_id) 
                         != (0xffU & VL_DIVS_III(32, vlSelfRef.tb_iq_frame_controller__DOT__received, (IData)(4U)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_frame_controller.sv:45: Assertion failed in %Ntb_iq_frame_controller: frame id mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_iq_frame_controller.sv", 45, "", false);
        }
        if (VL_UNLIKELY(((0U == (IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__sample_index)) 
                         != (0U == VL_MODDIVS_III(32, vlSelfRef.tb_iq_frame_controller__DOT__received, (IData)(4U)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_frame_controller.sv:46: Assertion failed in %Ntb_iq_frame_controller: start mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_iq_frame_controller.sv", 46, "", false);
        }
        if (VL_UNLIKELY(((3U == (IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__sample_index)) 
                         != (3U == VL_MODDIVS_III(32, vlSelfRef.tb_iq_frame_controller__DOT__received, (IData)(4U)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_frame_controller.sv:47: Assertion failed in %Ntb_iq_frame_controller: end mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_iq_frame_controller.sv", 47, "", false);
        }
        if (VL_UNLIKELY((1U & (~ (IData)(vlSelfRef.tb_iq_frame_controller__DOT__s_valid))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_frame_controller.sv:48: Assertion failed in %Ntb_iq_frame_controller: frame_valid mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_iq_frame_controller.sv", 48, "", false);
        }
        if (VL_UNLIKELY((((2U == vlSelfRef.tb_iq_frame_controller__DOT__received) 
                          | (3U == vlSelfRef.tb_iq_frame_controller__DOT__received)) 
                         & (~ ((IData)(vlSelfRef.tb_iq_frame_controller__DOT__dut__DOT__frame_error_sticky) 
                               | (IData)(vlSelfRef.tb_iq_frame_controller__DOT__s_error)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_iq_frame_controller.sv:49: Assertion failed in %Ntb_iq_frame_controller: sticky error lost\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_iq_frame_controller.sv", 49, "", false);
        }
        __Vdly__tb_iq_frame_controller__DOT__received 
            = ((IData)(1U) + vlSelfRef.tb_iq_frame_controller__DOT__received);
        if (VL_UNLIKELY((9U == vlSelfRef.tb_iq_frame_controller__DOT__received))) {
            VL_WRITEF_NX("PASS tb_iq_frame_controller\n",0);
            VL_FINISH_MT("tb/unit/tb_iq_frame_controller.sv", 53, "");
        }
    }
    vlSelfRef.tb_iq_frame_controller__DOT__received 
        = __Vdly__tb_iq_frame_controller__DOT__received;
}
