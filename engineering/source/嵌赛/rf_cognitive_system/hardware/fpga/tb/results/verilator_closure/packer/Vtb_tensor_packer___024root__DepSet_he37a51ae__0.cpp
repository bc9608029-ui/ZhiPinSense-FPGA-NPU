// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_tensor_packer.h for the primary calling header

#include "Vtb_tensor_packer__pch.h"
#include "Vtb_tensor_packer__Syms.h"
#include "Vtb_tensor_packer___024root.h"

VL_INLINE_OPT VlCoroutine Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__0(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    co_await vlSelfRef.__VtrigSched_hd28c5fbb__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_tensor_packer.clk)", 
                                                         "tb/unit/tb_tensor_packer.sv", 
                                                         72);
    co_await vlSelfRef.__VtrigSched_hd28c5fbb__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_tensor_packer.clk)", 
                                                         "tb/unit/tb_tensor_packer.sv", 
                                                         72);
    co_await vlSelfRef.__VtrigSched_hd28c5fbb__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_tensor_packer.clk)", 
                                                         "tb/unit/tb_tensor_packer.sv", 
                                                         72);
    vlSelfRef.tb_tensor_packer__DOT__rst_n = 1U;
    co_await vlSelfRef.__VdlySched.delay(0x1e8480ULL, 
                                         nullptr, "tb/unit/tb_tensor_packer.sv", 
                                         74);
    VL_WRITEF_NX("[%0t] %%Fatal: tb_tensor_packer.sv:74: Assertion failed in %Ntb_tensor_packer: timeout\n",0,
                 64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
    VL_STOP_MT("tb/unit/tb_tensor_packer.sv", 74, "", false);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_tensor_packer___024root___dump_triggers__act(Vtb_tensor_packer___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_tensor_packer___024root___eval_triggers__act(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((~ (IData)(vlSelfRef.tb_tensor_packer__DOT__clk)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__clk__0)));
    vlSelfRef.__VactTriggered.set(1U, ((IData)(vlSelfRef.tb_tensor_packer__DOT__clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__clk__0))));
    vlSelfRef.__VactTriggered.set(2U, ((~ (IData)(vlSelfRef.tb_tensor_packer__DOT__rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__rst_n__0)));
    vlSelfRef.__VactTriggered.set(3U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__clk__0 
        = vlSelfRef.tb_tensor_packer__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_tensor_packer__DOT__rst_n__0 
        = vlSelfRef.tb_tensor_packer__DOT__rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_tensor_packer___024root___dump_triggers__act(vlSelf);
    }
#endif
}

VL_INLINE_OPT void Vtb_tensor_packer___024root___nba_sequent__TOP__2(Vtb_tensor_packer___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_tensor_packer__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_tensor_packer___024root___nba_sequent__TOP__2\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (((IData)(vlSelfRef.tb_tensor_packer__DOT__rst_n) 
         & (IData)(vlSelfRef.tb_tensor_packer__DOT__m_write_valid))) {
        if (VL_UNLIKELY(((7U & ((IData)(4U) + (IData)(vlSelfRef.tb_tensor_packer__DOT__s_sample_index))) 
                         != (7U & ((IData)(4U) + (IData)(vlSelfRef.tb_tensor_packer__DOT__s_sample_index)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_tensor_packer.sv:56: Assertion failed in %Ntb_tensor_packer: IQ Q address mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_tensor_packer.sv", 56, "", false);
        }
        if (VL_UNLIKELY(((0xfU & ((IData)(4U) + (IData)(vlSelfRef.tb_tensor_packer__DOT__s_sample_index))) 
                         != (0xfU & ((IData)(4U) + (IData)(vlSelfRef.tb_tensor_packer__DOT__s_sample_index)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_tensor_packer.sv:57: Assertion failed in %Ntb_tensor_packer: LagRe address mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_tensor_packer.sv", 57, "", false);
        }
        if (((IData)(vlSelfRef.tb_tensor_packer__DOT__m_write_valid) 
             & (IData)(vlSelfRef.tb_tensor_packer__DOT__s_frame_end))) {
            vlSelfRef.tb_tensor_packer__DOT__buffer_release 
                = ((IData)(vlSelfRef.tb_tensor_packer__DOT__buffer_release) 
                   | (3U & ((IData)(1U) << (IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer))));
        } else {
            vlSelfRef.tb_tensor_packer__DOT__buffer_release = 0U;
        }
        if (VL_UNLIKELY(((0xfU & ((IData)(8U) + (IData)(vlSelfRef.tb_tensor_packer__DOT__s_sample_index))) 
                         != (0xfU & ((IData)(8U) + (IData)(vlSelfRef.tb_tensor_packer__DOT__s_sample_index)))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_tensor_packer.sv:58: Assertion failed in %Ntb_tensor_packer: LagIm address mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_tensor_packer.sv", 58, "", false);
        }
        if (VL_UNLIKELY(((IData)(vlSelfRef.tb_tensor_packer__DOT__dut__DOT__fill_buffer) 
                         != (1U & (IData)(vlSelfRef.tb_tensor_packer__DOT__s_frame_id))))) {
            VL_WRITEF_NX("[%0t] %%Fatal: tb_tensor_packer.sv:59: Assertion failed in %Ntb_tensor_packer: buffer alternation mismatch\n",0,
                         64,VL_TIME_UNITED_Q(1000),
                         -9,vlSymsp->name());
            VL_STOP_MT("tb/unit/tb_tensor_packer.sv", 59, "", false);
        }
        if (VL_UNLIKELY(((1U == (IData)(vlSelfRef.tb_tensor_packer__DOT__s_frame_id)) 
                         & ((IData)(vlSelfRef.tb_tensor_packer__DOT__m_write_valid) 
                            & (IData)(vlSelfRef.tb_tensor_packer__DOT__s_frame_end))))) {
            VL_WRITEF_NX("PASS tb_tensor_packer\n",0);
            VL_FINISH_MT("tb/unit/tb_tensor_packer.sv", 64, "");
        }
    } else {
        vlSelfRef.tb_tensor_packer__DOT__buffer_release = 0U;
    }
}
