// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_read_path.h for the primary calling header

#ifndef VERILATED_VTB_READ_PATH___024ROOT_H_
#define VERILATED_VTB_READ_PATH___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_read_path__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_read_path___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    // Anonymous structures to workaround compiler member-count bugs
    struct {
        CData/*0:0*/ tb_read_path__DOT__hp_clk;
        CData/*0:0*/ tb_read_path__DOT__cam_clk;
        CData/*0:0*/ tb_read_path__DOT__rst_hp;
        CData/*0:0*/ tb_read_path__DOT__rst_cam;
        CData/*0:0*/ tb_read_path__DOT__read_buf_sel;
        CData/*0:0*/ tb_read_path__DOT__ch0_read_req;
        CData/*0:0*/ tb_read_path__DOT__ch0_read_req_ack_sync;
        CData/*0:0*/ tb_read_path__DOT__ch0_read_req_sync;
        CData/*0:0*/ tb_read_path__DOT__ch0_read_req_ack;
        CData/*0:0*/ tb_read_path__DOT__buf_sel_sync1;
        CData/*0:0*/ tb_read_path__DOT__buf_sel_sync2;
        CData/*0:0*/ tb_read_path__DOT__rd_burst_req;
        CData/*0:0*/ tb_read_path__DOT__rd_rfifo_err_w;
        CData/*0:0*/ tb_read_path__DOT__aq_m_arready;
        CData/*0:0*/ tb_read_path__DOT__aq_s_rvalid;
        CData/*0:0*/ tb_read_path__DOT__aq_s_rlast;
        CData/*0:0*/ tb_read_path__DOT__aq_m_rready;
        CData/*0:0*/ tb_read_path__DOT__prev_read_finish;
        CData/*0:0*/ tb_read_path__DOT__prev_rfifo_full;
        CData/*0:0*/ tb_read_path__DOT__prev_read_req;
        CData/*0:0*/ tb_read_path__DOT__measuring;
        CData/*0:0*/ tb_read_path__DOT__cur_buf1;
        CData/*0:0*/ tb_read_path__DOT__prev_de;
        CData/*0:0*/ tb_read_path__DOT__u_color_bar__DOT__vs_reg;
        CData/*0:0*/ tb_read_path__DOT__u_color_bar__DOT__vs_reg_d0;
        CData/*0:0*/ tb_read_path__DOT__u_color_bar__DOT__h_active;
        CData/*0:0*/ tb_read_path__DOT__u_color_bar__DOT__v_active;
        CData/*0:0*/ tb_read_path__DOT__u_color_bar__DOT__video_active;
        CData/*0:0*/ tb_read_path__DOT__u_color_bar__DOT__video_active_d0;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__pos_vs_d0;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d0;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d1;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__pos_de_d2;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__read_en_r_d0;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d0;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__de_d1;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d0;
        CData/*0:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__vs_d1;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d1;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_req__DOT__a1_clk1_d2;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t1;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_req__DOT__a2_clk2_t2;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d1;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_ack__DOT__a1_clk1_d2;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t1;
        CData/*0:0*/ tb_read_path__DOT__u_level_cross_ack__DOT__a2_clk2_t2;
        CData/*0:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_fifo_aclr;
        CData/*0:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__rd_buf_empty;
        CData/*0:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d0;
        CData/*0:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d1;
        CData/*0:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_req_d2;
        CData/*3:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state;
        CData/*1:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d0;
        CData/*1:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_addr_index_d1;
        CData/*2:0*/ tb_read_path__DOT__u_aq_axi_master__DOT__rd_state;
        CData/*0:0*/ tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid;
        CData/*0:0*/ tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_last;
        CData/*7:0*/ tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len;
        CData/*7:0*/ tb_read_path__DOT__u_mem__DOT__remaining;
        CData/*0:0*/ tb_read_path__DOT__u_mem__DOT__active;
        CData/*3:0*/ __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__state;
        CData/*0:0*/ __Vdly__tb_read_path__DOT__ch0_read_req_ack;
        CData/*0:0*/ __Vdly__tb_read_path__DOT__aq_m_arready;
    };
    struct {
        CData/*0:0*/ __Vdly__tb_read_path__DOT__u_mem__DOT__active;
        CData/*0:0*/ __Vdly__tb_read_path__DOT__aq_s_rvalid;
        CData/*7:0*/ __Vdly__tb_read_path__DOT__u_mem__DOT__remaining;
        CData/*0:0*/ __Vdly__tb_read_path__DOT__u_color_bar__DOT__vs_reg;
        CData/*2:0*/ __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__rd_state;
        CData/*0:0*/ __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_arvalid;
        CData/*7:0*/ __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_r_len;
        CData/*0:0*/ __VdlySet__tb_read_path__DOT__frame_beat__v0;
        CData/*0:0*/ __VdlySet__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0;
        CData/*0:0*/ __VstlFirstIteration;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_read_path__DOT__hp_clk__0;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_read_path__DOT__rst_hp__0;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_read_path__DOT__cam_clk__0;
        CData/*0:0*/ __Vtrigprevexpr___TOP__tb_read_path__DOT__rst_cam__0;
        CData/*0:0*/ __VactContinue;
        SData/*9:0*/ tb_read_path__DOT__rd_burst_len;
        SData/*11:0*/ tb_read_path__DOT__px_in_line;
        SData/*11:0*/ tb_read_path__DOT__u_color_bar__DOT__h_cnt;
        SData/*11:0*/ tb_read_path__DOT__u_color_bar__DOT__v_cnt;
        SData/*15:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d0;
        SData/*15:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__pos_data_d1;
        SData/*15:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__vout_data_r;
        SData/*15:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d0;
        SData/*15:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__i_data_d1;
        SData/*11:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt;
        SData/*11:0*/ tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt;
        SData/*15:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__wptr;
        SData/*15:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rword;
        SData/*15:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__used;
        SData/*15:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__dout_r;
        SData/*11:0*/ __Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__x_cnt;
        SData/*11:0*/ __Vdly__tb_read_path__DOT__u_video_rect_read_data__DOT__timing_gen_xy_m0__DOT__y_cnt;
        SData/*14:0*/ __VdlyDim0__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0;
        IData/*26:0*/ tb_read_path__DOT__rd_burst_addr;
        IData/*31:0*/ tb_read_path__DOT__rfin_cnt;
        IData/*31:0*/ tb_read_path__DOT__beat_frame;
        IData/*31:0*/ tb_read_path__DOT__full_event;
        IData/*31:0*/ tb_read_path__DOT__full_cycles;
        IData/*31:0*/ tb_read_path__DOT__drop_we;
        IData/*31:0*/ tb_read_path__DOT__rreq_cnt;
        IData/*31:0*/ tb_read_path__DOT__mismatch_buf0;
        IData/*31:0*/ tb_read_path__DOT__mismatch_buf1;
        IData/*31:0*/ tb_read_path__DOT__valid_px_cnt;
        IData/*31:0*/ tb_read_path__DOT__line_cnt;
        IData/*31:0*/ tb_read_path__DOT__underflow_cnt;
        IData/*31:0*/ tb_read_path__DOT__first_mm_x;
        IData/*31:0*/ tb_read_path__DOT__first_mm_y;
        IData/*17:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr;
        IData/*26:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d0;
        IData/*26:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_d1;
        IData/*26:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch;
        IData/*26:0*/ tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt;
        IData/*31:0*/ tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs;
        IData/*31:0*/ tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_len;
        IData/*31:0*/ tb_read_path__DOT__u_mem__DOT__cur_addr;
        IData/*31:0*/ tb_read_path__DOT__u_mem__DOT__next_addr;
        IData/*26:0*/ __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_len_latch;
        IData/*26:0*/ __Vdly__tb_read_path__DOT__rd_burst_addr;
        IData/*26:0*/ __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__frame_fifo_read_m0__DOT__read_cnt;
        IData/*31:0*/ __Vdly__tb_read_path__DOT__rfin_cnt;
        IData/*31:0*/ __Vdly__tb_read_path__DOT__beat_frame;
        IData/*31:0*/ __Vdly__tb_read_path__DOT__u_mem__DOT__cur_addr;
        IData/*17:0*/ __Vdly__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__rptr;
        IData/*31:0*/ __Vdly__tb_read_path__DOT__u_aq_axi_master__DOT__reg_rd_adrs;
    };
    struct {
        IData/*31:0*/ __VactIterCount;
        QData/*63:0*/ tb_read_path__DOT__aq_s_rdata;
        QData/*63:0*/ tb_read_path__DOT__u_mem__DOT____Vlvbound_h5db7fe97__0;
        QData/*63:0*/ tb_read_path__DOT__u_mem__DOT____Vlvbound_h72d6fd65__0;
        QData/*63:0*/ tb_read_path__DOT__u_mem__DOT____Vlvbound_hb38c97ac__0;
        QData/*63:0*/ __VdlyVal__tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem__v0;
        VlUnpacked<IData/*31:0*/, 4> tb_read_path__DOT__frame_beat;
        VlUnpacked<QData/*63:0*/, 32768> tb_read_path__DOT__u_frame_read_write_largebuf__DOT__read_buf__DOT__mem;
        VlUnpacked<QData/*63:0*/, 460800> tb_read_path__DOT__u_mem__DOT__mem;
    };
    VlDelayScheduler __VdlySched;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<5> __VactTriggered;
    VlTriggerVec<5> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb_read_path__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb_read_path___024root(Vtb_read_path__Syms* symsp, const char* v__name);
    ~Vtb_read_path___024root();
    VL_UNCOPYABLE(Vtb_read_path___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
