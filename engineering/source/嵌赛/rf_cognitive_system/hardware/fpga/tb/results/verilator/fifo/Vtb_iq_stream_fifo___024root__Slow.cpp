// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_iq_stream_fifo.h for the primary calling header

#include "Vtb_iq_stream_fifo__pch.h"
#include "Vtb_iq_stream_fifo__Syms.h"
#include "Vtb_iq_stream_fifo___024root.h"

void Vtb_iq_stream_fifo___024root___ctor_var_reset(Vtb_iq_stream_fifo___024root* vlSelf);

Vtb_iq_stream_fifo___024root::Vtb_iq_stream_fifo___024root(Vtb_iq_stream_fifo__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , __VdlySched{*symsp->_vm_contextp__}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vtb_iq_stream_fifo___024root___ctor_var_reset(this);
}

void Vtb_iq_stream_fifo___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vtb_iq_stream_fifo___024root::~Vtb_iq_stream_fifo___024root() {
}
