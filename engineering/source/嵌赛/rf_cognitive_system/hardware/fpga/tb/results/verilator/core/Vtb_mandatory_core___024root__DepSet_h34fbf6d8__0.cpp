// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_mandatory_core.h for the primary calling header

#include "Vtb_mandatory_core__pch.h"
#include "Vtb_mandatory_core__Syms.h"
#include "Vtb_mandatory_core___024root.h"

VL_INLINE_OPT VlCoroutine Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__0(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_initial__TOP__Vtiming__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    VlWide<5>/*159:0*/ __Vtemp_1;
    VlWide<6>/*191:0*/ __Vtemp_2;
    // Body
    __Vtemp_1[0U] = 0x2e686578U;
    __Vtemp_1[1U] = 0x6e707574U;
    __Vtemp_1[2U] = 0x69715f69U;
    __Vtemp_1[3U] = 0x6f72732fU;
    __Vtemp_1[4U] = 0x76656374U;
    VL_READMEM_N(true, 32, 19456, 0, VL_CVT_PACK_STR_NW(5, __Vtemp_1)
                 ,  &(vlSelfRef.tb_mandatory_core__DOT__input_mem)
                 , 0, ~0ULL);
    __Vtemp_2[0U] = 0x2e637376U;
    __Vtemp_2[1U] = 0x636f7265U;
    __Vtemp_2[2U] = 0x72746c5fU;
    __Vtemp_2[3U] = 0x6c74732fU;
    __Vtemp_2[4U] = 0x72657375U;
    __Vtemp_2[5U] = 0x74622fU;
    vlSelfRef.tb_mandatory_core__DOT__output_file = VL_FOPEN_NN(
                                                                VL_CVT_PACK_STR_NW(6, __Vtemp_2)
                                                                , 
                                                                std::string{"w"});
    ;
    VL_FWRITEF_NX(vlSelfRef.tb_mandatory_core__DOT__output_file,"frame_id,sample_index,buffer_id,iq_i_int8,iq_q_int8,power_int8,lag_re_int8,lag_im_int8,iq_i_addr,iq_q_addr,power_addr,lag_re_addr,lag_im_addr\n",0);
    co_await vlSelfRef.__VtrigSched_h103dc9c4__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_mandatory_core.clk)", 
                                                         "tb/integration/tb_mandatory_core.sv", 
                                                         82);
    co_await vlSelfRef.__VtrigSched_h103dc9c4__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_mandatory_core.clk)", 
                                                         "tb/integration/tb_mandatory_core.sv", 
                                                         82);
    co_await vlSelfRef.__VtrigSched_h103dc9c4__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb_mandatory_core.clk)", 
                                                         "tb/integration/tb_mandatory_core.sv", 
                                                         82);
    vlSelfRef.tb_mandatory_core__DOT__rst_n = 1U;
    co_await vlSelfRef.__VdlySched.delay(0x12a05f200ULL, 
                                         nullptr, "tb/integration/tb_mandatory_core.sv", 
                                         84);
    VL_WRITEF_NX("[%0t] %%Fatal: tb_mandatory_core.sv:84: Assertion failed in %Ntb_mandatory_core: timeout\n",0,
                 64,VL_TIME_UNITED_Q(1000),-9,vlSymsp->name());
    VL_STOP_MT("tb/integration/tb_mandatory_core.sv", 84, "", false);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_mandatory_core___024root___dump_triggers__act(Vtb_mandatory_core___024root* vlSelf);
#endif  // VL_DEBUG

void Vtb_mandatory_core___024root___eval_triggers__act(Vtb_mandatory_core___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_mandatory_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_mandatory_core___024root___eval_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__clk)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_mandatory_core__DOT__clk__0)));
    vlSelfRef.__VactTriggered.set(1U, ((IData)(vlSelfRef.tb_mandatory_core__DOT__clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_mandatory_core__DOT__clk__0))));
    vlSelfRef.__VactTriggered.set(2U, ((~ (IData)(vlSelfRef.tb_mandatory_core__DOT__rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_mandatory_core__DOT__rst_n__0)));
    vlSelfRef.__VactTriggered.set(3U, vlSelfRef.__VdlySched.awaitingCurrentTime());
    vlSelfRef.__Vtrigprevexpr___TOP__tb_mandatory_core__DOT__clk__0 
        = vlSelfRef.tb_mandatory_core__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb_mandatory_core__DOT__rst_n__0 
        = vlSelfRef.tb_mandatory_core__DOT__rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_mandatory_core___024root___dump_triggers__act(vlSelf);
    }
#endif
}
