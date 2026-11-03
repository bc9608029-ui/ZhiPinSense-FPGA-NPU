// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_top_lite.h for the primary calling header

#include "Vtb_top_lite__pch.h"
#include "Vtb_top_lite___024root.h"

VL_ATTR_COLD void Vtb_top_lite___024root___eval_static__TOP(Vtb_top_lite___024root* vlSelf);

VL_ATTR_COLD void Vtb_top_lite___024root___eval_static(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_static\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_top_lite___024root___eval_static__TOP(vlSelf);
}

VL_ATTR_COLD void Vtb_top_lite___024root___eval_static__TOP(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_static__TOP\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb_top_lite__DOT__pl_clk = 0U;
    vlSelfRef.tb_top_lite__DOT__pl_key1_reset = 1U;
    vlSelfRef.tb_top_lite__DOT__s_i = 0U;
    vlSelfRef.tb_top_lite__DOT__s_q = 0U;
    vlSelfRef.tb_top_lite__DOT__s_valid = 0U;
    vlSelfRef.tb_top_lite__DOT__buffer_release = 0U;
    vlSelfRef.tb_top_lite__DOT__sent = 0U;
    vlSelfRef.tb_top_lite__DOT__received = 0U;
}

VL_ATTR_COLD void Vtb_top_lite___024root___eval_final(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_final\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_top_lite___024root___dump_triggers__stl(Vtb_top_lite___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vtb_top_lite___024root___eval_phase__stl(Vtb_top_lite___024root* vlSelf);

VL_ATTR_COLD void Vtb_top_lite___024root___eval_settle(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_settle\n"); );
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
            Vtb_top_lite___024root___dump_triggers__stl(vlSelf);
#endif
            VL_FATAL_MT("tb/integration/tb_top_lite.sv", 3, "", "Settle region did not converge.");
        }
        __VstlIterCount = ((IData)(1U) + __VstlIterCount);
        __VstlContinue = 0U;
        if (Vtb_top_lite___024root___eval_phase__stl(vlSelf)) {
            __VstlContinue = 1U;
        }
        vlSelfRef.__VstlFirstIteration = 0U;
    }
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_top_lite___024root___dump_triggers__stl(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___dump_triggers__stl\n"); );
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

VL_ATTR_COLD void Vtb_top_lite___024root___stl_sequent__TOP__0(Vtb_top_lite___024root* vlSelf);

VL_ATTR_COLD void Vtb_top_lite___024root___eval_stl(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_stl\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VstlTriggered.word(0U))) {
        Vtb_top_lite___024root___stl_sequent__TOP__0(vlSelf);
    }
}

VL_ATTR_COLD void Vtb_top_lite___024root___stl_sequent__TOP__0(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___stl_sequent__TOP__0\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__feature_ready;
    tb_top_lite__DOT__dut__DOT__core__DOT__feature_ready = 0;
    CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume;
    tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume = 0;
    CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__input_negative;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__input_negative = 0;
    SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__magnitude;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__magnitude = 0;
    QData/*47:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__product;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__product = 0;
    QData/*48:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__adjusted;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__adjusted = 0;
    QData/*48:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__rounded_magnitude;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__rounded_magnitude = 0;
    CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__input_negative;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__input_negative = 0;
    SData/*15:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__magnitude;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__magnitude = 0;
    QData/*47:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__product;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__product = 0;
    QData/*48:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__adjusted;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__adjusted = 0;
    QData/*48:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__rounded_magnitude;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__rounded_magnitude = 0;
    IData/*31:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__magnitude;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__magnitude = 0;
    QData/*63:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__product;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__product = 0;
    VlWide<3>/*64:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__adjusted;
    VL_ZERO_W(65, tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__adjusted);
    VlWide<3>/*64:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__rounded_magnitude;
    VL_ZERO_W(65, tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__rounded_magnitude);
    CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__input_negative;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__input_negative = 0;
    QData/*32:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__magnitude;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__magnitude = 0;
    VlWide<3>/*64:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product;
    VL_ZERO_W(65, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product);
    VlWide<3>/*65:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__adjusted;
    VL_ZERO_W(66, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__adjusted);
    VlWide<3>/*65:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__rounded_magnitude;
    VL_ZERO_W(66, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__rounded_magnitude);
    CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__input_negative;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__input_negative = 0;
    QData/*32:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__magnitude;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__magnitude = 0;
    VlWide<3>/*64:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product;
    VL_ZERO_W(65, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product);
    VlWide<3>/*65:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__adjusted;
    VL_ZERO_W(66, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__adjusted);
    VlWide<3>/*65:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__rounded_magnitude;
    VL_ZERO_W(66, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__rounded_magnitude);
    CData/*0:0*/ tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__selected_buffer_available;
    tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__selected_buffer_available = 0;
    VlWide<3>/*95:0*/ __Vtemp_2;
    VlWide<3>/*95:0*/ __Vtemp_3;
    VlWide<3>/*95:0*/ __Vtemp_4;
    VlWide<3>/*95:0*/ __Vtemp_6;
    VlWide<3>/*95:0*/ __Vtemp_7;
    VlWide<3>/*95:0*/ __Vtemp_9;
    VlWide<3>/*95:0*/ __Vtemp_10;
    VlWide<3>/*95:0*/ __Vtemp_11;
    VlWide<3>/*95:0*/ __Vtemp_13;
    VlWide<3>/*95:0*/ __Vtemp_14;
    VlWide<3>/*95:0*/ __Vtemp_15;
    VlWide<3>/*95:0*/ __Vtemp_17;
    VlWide<3>/*95:0*/ __Vtemp_18;
    VlWide<3>/*95:0*/ __Vtemp_20;
    VlWide<3>/*95:0*/ __Vtemp_21;
    VlWide<3>/*95:0*/ __Vtemp_22;
    VlWide<3>/*95:0*/ __Vtemp_24;
    VlWide<3>/*95:0*/ __Vtemp_25;
    VlWide<3>/*95:0*/ __Vtemp_26;
    VlWide<3>/*95:0*/ __Vtemp_28;
    VlWide<3>/*95:0*/ __Vtemp_29;
    // Body
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__push 
        = ((IData)(vlSelfRef.tb_top_lite__DOT__s_valid) 
           & (4U > (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__count)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__frame_i 
        = vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem
        [vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer];
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__frame_q 
        = vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem
        [vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer];
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_0 
        = VL_EXTENDS_II(32,16, vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem
                        [vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer]);
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_1 
        = VL_EXTENDS_II(32,16, vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem
                        [vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer]);
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_2 
        = VL_EXTENDS_II(32,16, ((0U == (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__sample_index))
                                 ? 0U : (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__previous_i)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_3 
        = VL_EXTENDS_II(32,16, ((0U == (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__sample_index))
                                 ? 0U : (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__previous_q)));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__magnitude 
        = vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_power;
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__product 
        = (0x7fULL * (QData)((IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__magnitude)));
    __Vtemp_2[0U] = 0x40000000U;
    __Vtemp_2[1U] = 0U;
    __Vtemp_2[2U] = 0U;
    __Vtemp_3[0U] = (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__product);
    __Vtemp_3[1U] = (IData)((tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__product 
                             >> 0x20U));
    __Vtemp_3[2U] = 0U;
    VL_ADD_W(3, __Vtemp_4, __Vtemp_2, __Vtemp_3);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__adjusted[0U] 
        = __Vtemp_4[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__adjusted[1U] 
        = __Vtemp_4[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__adjusted[2U] 
        = (1U & __Vtemp_4[2U]);
    VL_SHIFTR_WWI(65,65,8, __Vtemp_6, tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__adjusted, 0x1fU);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__rounded_magnitude[0U] 
        = __Vtemp_6[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__rounded_magnitude[1U] 
        = __Vtemp_6[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__rounded_magnitude[2U] 
        = (1U & __Vtemp_6[2U]);
    __Vtemp_7[0U] = 0x7fU;
    __Vtemp_7[1U] = 0U;
    __Vtemp_7[2U] = 0U;
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__saturated_comb 
        = VL_LT_W(3, __Vtemp_7, tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__rounded_magnitude);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__input_negative 
        = (1U & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_i) 
                 >> 0xfU));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__magnitude 
        = (0xffffU & ((IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__input_negative)
                       ? ((IData)(1U) + (~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_i)))
                       : (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_i)));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__product 
        = (0xffffffffffffULL & (0x7fULL * (QData)((IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__magnitude))));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__adjusted 
        = (0x1ffffffffffffULL & (0x4000ULL + tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__product));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__rounded_magnitude 
        = (0x1ffffffffffffULL & VL_SHIFTR_QQI(49,49,8, tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__adjusted, 0xfU));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__saturated_comb 
        = (0x7fULL < tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__rounded_magnitude);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__input_negative 
        = (1U & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_q) 
                 >> 0xfU));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__magnitude 
        = (0xffffU & ((IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__input_negative)
                       ? ((IData)(1U) + (~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_q)))
                       : (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_q)));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__product 
        = (0xffffffffffffULL & (0x7fULL * (QData)((IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__magnitude))));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__adjusted 
        = (0x1ffffffffffffULL & (0x4000ULL + tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__product));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__rounded_magnitude 
        = (0x1ffffffffffffULL & VL_SHIFTR_QQI(49,49,8, tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__adjusted, 0xfU));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__saturated_comb 
        = (0x7fULL < tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__rounded_magnitude);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__input_negative 
        = (1U & (IData)((vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_re 
                         >> 0x20U)));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__magnitude 
        = (0x1ffffffffULL & ((IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__input_negative)
                              ? (1ULL + (~ vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_re))
                              : vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_re));
    __Vtemp_9[0U] = 0x7fU;
    __Vtemp_9[1U] = 0U;
    __Vtemp_9[2U] = 0U;
    __Vtemp_10[0U] = (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__magnitude);
    __Vtemp_10[1U] = (IData)((tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__magnitude 
                              >> 0x20U));
    __Vtemp_10[2U] = 0U;
    VL_MUL_W(3, __Vtemp_11, __Vtemp_9, __Vtemp_10);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product[0U] 
        = __Vtemp_11[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product[1U] 
        = __Vtemp_11[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product[2U] 
        = (1U & __Vtemp_11[2U]);
    __Vtemp_13[0U] = 0x40000000U;
    __Vtemp_13[1U] = 0U;
    __Vtemp_13[2U] = 0U;
    __Vtemp_14[0U] = tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product[0U];
    __Vtemp_14[1U] = tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product[1U];
    __Vtemp_14[2U] = tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__product[2U];
    VL_ADD_W(3, __Vtemp_15, __Vtemp_13, __Vtemp_14);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__adjusted[0U] 
        = __Vtemp_15[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__adjusted[1U] 
        = __Vtemp_15[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__adjusted[2U] 
        = (3U & __Vtemp_15[2U]);
    VL_SHIFTR_WWI(66,66,8, __Vtemp_17, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__adjusted, 0x1fU);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__rounded_magnitude[0U] 
        = __Vtemp_17[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__rounded_magnitude[1U] 
        = __Vtemp_17[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__rounded_magnitude[2U] 
        = (3U & __Vtemp_17[2U]);
    __Vtemp_18[0U] = 0x7fU;
    __Vtemp_18[1U] = 0U;
    __Vtemp_18[2U] = 0U;
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__saturated_comb 
        = VL_LT_W(3, __Vtemp_18, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__rounded_magnitude);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__input_negative 
        = (1U & (IData)((vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_im 
                         >> 0x20U)));
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__magnitude 
        = (0x1ffffffffULL & ((IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__input_negative)
                              ? (1ULL + (~ vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_im))
                              : vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_im));
    __Vtemp_20[0U] = 0x7fU;
    __Vtemp_20[1U] = 0U;
    __Vtemp_20[2U] = 0U;
    __Vtemp_21[0U] = (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__magnitude);
    __Vtemp_21[1U] = (IData)((tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__magnitude 
                              >> 0x20U));
    __Vtemp_21[2U] = 0U;
    VL_MUL_W(3, __Vtemp_22, __Vtemp_20, __Vtemp_21);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product[0U] 
        = __Vtemp_22[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product[1U] 
        = __Vtemp_22[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product[2U] 
        = (1U & __Vtemp_22[2U]);
    __Vtemp_24[0U] = 0x40000000U;
    __Vtemp_24[1U] = 0U;
    __Vtemp_24[2U] = 0U;
    __Vtemp_25[0U] = tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product[0U];
    __Vtemp_25[1U] = tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product[1U];
    __Vtemp_25[2U] = tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__product[2U];
    VL_ADD_W(3, __Vtemp_26, __Vtemp_24, __Vtemp_25);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__adjusted[0U] 
        = __Vtemp_26[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__adjusted[1U] 
        = __Vtemp_26[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__adjusted[2U] 
        = (3U & __Vtemp_26[2U]);
    VL_SHIFTR_WWI(66,66,8, __Vtemp_28, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__adjusted, 0x1fU);
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__rounded_magnitude[0U] 
        = __Vtemp_28[0U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__rounded_magnitude[1U] 
        = __Vtemp_28[1U];
    tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__rounded_magnitude[2U] 
        = (3U & __Vtemp_28[2U]);
    __Vtemp_29[0U] = 0x7fU;
    __Vtemp_29[1U] = 0U;
    __Vtemp_29[2U] = 0U;
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__saturated_comb 
        = VL_LT_W(3, __Vtemp_29, tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__rounded_magnitude);
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core_rst_n 
        = (1U & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__reset_release) 
                 >> 1U));
    tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__selected_buffer_available 
        = (1U & ((~ ((IData)(vlSelfRef.tb_top_lite__DOT__buffer_busy) 
                     >> (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__fill_buffer))) 
                 | ((IData)(vlSelfRef.tb_top_lite__DOT__buffer_release) 
                    >> (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__fill_buffer))));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__bundle_valid 
        = ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_valid) 
           & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qi_valid) 
              & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qp_valid) 
                 & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qq_valid) 
                    & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qm_valid) 
                       & (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qr_valid))))));
    vlSelfRef.tb_top_lite__DOT__pl_led = (((((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__sticky_error) 
                                             | ((0U 
                                                 != vlSelfRef.tb_top_lite__DOT__overflow_count) 
                                                | ((0U 
                                                    != vlSelfRef.tb_top_lite__DOT__sat_i) 
                                                   | ((0U 
                                                       != vlSelfRef.tb_top_lite__DOT__sat_q) 
                                                      | ((0U 
                                                          != vlSelfRef.tb_top_lite__DOT__sat_power) 
                                                         | ((0U 
                                                             != vlSelfRef.tb_top_lite__DOT__sat_re) 
                                                            | (0U 
                                                               != vlSelfRef.tb_top_lite__DOT__sat_im))))))) 
                                            << 3U) 
                                           | ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__frame_complete_toggle) 
                                              << 2U)) 
                                          | (((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__input_activity_toggle) 
                                              << 1U) 
                                             | (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core_rst_n)));
    vlSelfRef.tb_top_lite__DOT__m_write_valid = ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__bundle_valid) 
                                                 & (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__selected_buffer_available));
    tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume 
        = ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__bundle_valid) 
           & (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__selected_buffer_available));
    vlSelfRef.tb_top_lite__DOT__m_irq = ((IData)(vlSelfRef.tb_top_lite__DOT__m_write_valid) 
                                         & (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_frame_end));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_valid)) 
                 | (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qi_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qi_valid)) 
                 | (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qp_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qp_valid)) 
                 | (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qq_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qq_valid)) 
                 | (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qm_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qm_valid)) 
                 | (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qr_s_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qr_valid)) 
                 | (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__bundle_consume)));
    tb_top_lite__DOT__dut__DOT__core__DOT__feature_ready 
        = ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__meta_ready) 
           & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qi_s_ready) 
              & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qp_s_ready) 
                 & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qq_s_ready) 
                    & ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qm_s_ready) 
                       & (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__qr_s_ready))))));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__quantizer_input_valid 
        = ((IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_valid) 
           & (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__feature_ready));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__stage2_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__feature_valid)) 
                 | (IData)(tb_top_lite__DOT__dut__DOT__core__DOT__feature_ready)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__fifo_ready 
        = (1U & ((~ (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_valid)) 
                 | (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__stage2_ready)));
    vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__pop 
        = ((0U != (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__count)) 
           & (IData)(vlSelfRef.tb_top_lite__DOT__dut__DOT__core__DOT__fifo_ready));
}

VL_ATTR_COLD void Vtb_top_lite___024root___eval_triggers__stl(Vtb_top_lite___024root* vlSelf);

VL_ATTR_COLD bool Vtb_top_lite___024root___eval_phase__stl(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___eval_phase__stl\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Init
    CData/*0:0*/ __VstlExecute;
    // Body
    Vtb_top_lite___024root___eval_triggers__stl(vlSelf);
    __VstlExecute = vlSelfRef.__VstlTriggered.any();
    if (__VstlExecute) {
        Vtb_top_lite___024root___eval_stl(vlSelf);
    }
    return (__VstlExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_top_lite___024root___dump_triggers__act(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___dump_triggers__act\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VactTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 0 is active: @(negedge tb_top_lite.pl_clk)\n");
    }
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 1 is active: @(posedge tb_top_lite.pl_clk)\n");
    }
    if ((4ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 2 is active: @(posedge tb_top_lite.pl_key1_reset)\n");
    }
    if ((8ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 3 is active: @(negedge tb_top_lite.dut.core_rst_n)\n");
    }
    if ((0x10ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 4 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_top_lite___024root___dump_triggers__nba(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___dump_triggers__nba\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VnbaTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(negedge tb_top_lite.pl_clk)\n");
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 1 is active: @(posedge tb_top_lite.pl_clk)\n");
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 2 is active: @(posedge tb_top_lite.pl_key1_reset)\n");
    }
    if ((8ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 3 is active: @(negedge tb_top_lite.dut.core_rst_n)\n");
    }
    if ((0x10ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 4 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_top_lite___024root___ctor_var_reset(Vtb_top_lite___024root* vlSelf) {
    (void)vlSelf;  // Prevent unused variable warning
    Vtb_top_lite__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_top_lite___024root___ctor_var_reset\n"); );
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelf->tb_top_lite__DOT__pl_clk = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__pl_key1_reset = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__s_i = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__s_q = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__s_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__buffer_release = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__m_write_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__m_irq = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__buffer_busy = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__overflow_count = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__sat_i = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__sat_q = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__sat_power = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__sat_re = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__sat_im = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__pl_led = VL_RAND_RESET_I(4);
    vlSelf->tb_top_lite__DOT__sent = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__received = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__reset_release = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__dut__DOT__core_rst_n = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__input_activity_toggle = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__frame_complete_toggle = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__sticky_error = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__fifo_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__frame_i = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__frame_q = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_i = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_q = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_power = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_re = VL_RAND_RESET_Q(33);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_lag_im = VL_RAND_RESET_Q(33);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_sample_index = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_frame_start = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_frame_end = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__feature_error = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qi_s_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qq_s_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qp_s_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qr_s_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qm_s_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qi_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qq_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qp_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qr_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__qm_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__meta_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__meta_sample_index = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__meta_frame_start = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__meta_frame_end = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__meta_error = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__bundle_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__meta_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__quantizer_input_valid = VL_RAND_RESET_I(1);
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem[__Vi0] = VL_RAND_RESET_I(16);
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem[__Vi0] = VL_RAND_RESET_I(16);
    }
    for (int __Vi0 = 0; __Vi0 < 4; ++__Vi0) {
        vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__e_mem[__Vi0] = VL_RAND_RESET_I(1);
    }
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__write_pointer = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__count = VL_RAND_RESET_I(3);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__push = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__pop = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__sample_index = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__frame_id = VL_RAND_RESET_I(8);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__frame_error_sticky = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__previous_i = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__previous_q = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_valid = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q = VL_RAND_RESET_I(16);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i_square = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q_square = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i_i_prev = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q_q_prev = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_q_i_prev = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_i_q_prev = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_sample_index = VL_RAND_RESET_I(2);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_frame_start = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_frame_end = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__s1_error = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT__stage2_ready = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_0 = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_1 = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_2 = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__features__DOT____VdfgRegularize_h968ea371_0_3 = VL_RAND_RESET_I(32);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__quant_i__DOT__saturated_comb = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__quant_q__DOT__saturated_comb = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__quant_power__DOT__saturated_comb = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_re__DOT__saturated_comb = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__quant_lag_im__DOT__saturated_comb = VL_RAND_RESET_I(1);
    vlSelf->tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__fill_buffer = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_top_lite__DOT__sent = VL_RAND_RESET_I(32);
    vlSelf->__Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__read_pointer = VL_RAND_RESET_I(2);
    vlSelf->__Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__count = VL_RAND_RESET_I(3);
    vlSelf->__Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__sample_index = VL_RAND_RESET_I(2);
    vlSelf->__Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__framer__DOT__frame_error_sticky = VL_RAND_RESET_I(1);
    vlSelf->__Vdly__tb_top_lite__DOT__dut__DOT__core__DOT__packer__DOT__fill_buffer = VL_RAND_RESET_I(1);
    vlSelf->__VdlyVal__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem__v0 = VL_RAND_RESET_I(16);
    vlSelf->__VdlyDim0__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem__v0 = VL_RAND_RESET_I(2);
    vlSelf->__VdlySet__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__i_mem__v0 = 0;
    vlSelf->__VdlyVal__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem__v0 = VL_RAND_RESET_I(16);
    vlSelf->__VdlyDim0__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__q_mem__v0 = VL_RAND_RESET_I(2);
    vlSelf->__VdlyDim0__tb_top_lite__DOT__dut__DOT__core__DOT__input_fifo__DOT__e_mem__v0 = VL_RAND_RESET_I(2);
    vlSelf->__Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_top_lite__DOT__pl_key1_reset__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__tb_top_lite__DOT__dut__DOT__core_rst_n__0 = VL_RAND_RESET_I(1);
}
