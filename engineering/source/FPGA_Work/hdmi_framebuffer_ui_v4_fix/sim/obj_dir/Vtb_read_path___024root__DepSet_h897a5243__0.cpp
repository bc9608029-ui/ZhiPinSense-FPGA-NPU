// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_read_path.h for the primary calling header

#include "Vtb_read_path__pch.h"
#include "Vtb_read_path__Syms.h"
#include "Vtb_read_path___024root.h"

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_read_path___024root___dump_triggers__act(Vtb_read_path___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_read_path___024root___eval_triggers__act(Vtb_read_path___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_read_path__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_read_path___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((IData)(vlSelfRef.tb_read_path__DOT__hp_clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__hp_clk__0))));
    vlSelfRef.__VactTriggered.set(1U, ((IData)(vlSelfRef.tb_read_path__DOT__rst_hp) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_hp__0))));
    vlSelfRef.__VactTriggered.set(2U, ((IData)(vlSelfRef.tb_read_path__DOT__cam_clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__cam_clk__0))));
    vlSelfRef.__VactTriggered.set(3U, ((IData)(vlSelfRef.tb_read_path__DOT__rst_cam) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_cam__0))));
    vlSelfRef.__VactTriggered.set(4U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__hp_clk__0 
        = vlSelfRef.tb_read_path__DOT__hp_clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_hp__0 
        = vlSelfRef.tb_read_path__DOT__rst_hp;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__cam_clk__0 
        = vlSelfRef.tb_read_path__DOT__cam_clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_read_path__DOT__rst_cam__0 
        = vlSelfRef.tb_read_path__DOT__rst_cam;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_read_path___024root___dump_triggers__act(vlSelf);
    }
#endif
}
