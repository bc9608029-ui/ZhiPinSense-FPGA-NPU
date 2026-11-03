//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : frame_trans.v
// Author        : WangYinglin 
// Project       : 
// Create Date   : 2023.02.17
// Description   : 
// 
//-----------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
//==============================================================================

module frame_trans (
    // camera data interface
    input                       cam_vs              ,
    input                       cam_de              ,
    input      [23 : 0]         cam_rgb             ,

    input                       vtc_vs              ,
    input                       vtc_de              ,
    input      [23 : 0]         vtc_data            ,

    input                       cam_clk             ,
    input                       reset_cam_clk       ,
 
    output                      cmos_vsync_out      ,
    output                      cmos_href_out       ,
    output     [23 : 0]         cmos_db_out         ,  
       
    output                      irq_test            ,
    // slave axi lite interface，connect frame_ctrl
    input                       S_AXI_ACLK          ,
    input                       S_AXI_ARESETN       ,
    mna_gp_ww_itf.slave         cam                 , 

    //ps resize
    output     [15 : 0]         ps_x0_pos           ,
    output     [15 : 0]         ps_y0_pos           ,
    output     [15 : 0]         ps_x1_pos           ,
    output     [15 : 0]         ps_y1_pos           ,
    output     [15 : 0]         ps_x_leng           ,
    output     [15 : 0]         ps_y_leng           ,
    output     [ 3 : 0]         ps_hstride          ,
    output     [ 3 : 0]         ps_vstride          ,
    output     [10 : 0]         resize_pix_len      ,	
    output     [31 : 0]         write_ps_size       ,	
    output     [31 : 0]         H_SYNC              ,
    output     [31 : 0]         H_BACK_PORCH        ,
    output     [31 : 0]         H_ACTIVE            ,
    output     [31 : 0]         H_FRONT_PORCH       ,
    output     [31 : 0]         V_SYNC              ,
    output     [31 : 0]         V_BACK_PORCH        ,
    output     [31 : 0]         V_ACTIVE            ,
    output     [31 : 0]         V_FRONT_PORCH       ,

    //img_data for image_make 
    input                       M01_AXI_ACLK        ,
    input                       M01_AXI_ARESETN     ,    
    output                      img_start           ,
    output     [23 : 0]         img_data            ,
    output                      img_valid           ,
    input                       img_ready           ,         
    //frame mode
    output                      continuous_en       , 
    output                      display_en          ,
    output     [31 : 0]         camera_wr_addr      ,
    output     [31 : 0]         camera_rd_addr      ,
    input                       wr_wfifo_err        ,
    input                       rd_rfifo_err        ,
    input                       wr_done_pulse       ,
    //status signal
    input      [ 1 : 0]         write_addr_index    ,
    input      [ 1 : 0]         read_addr_index     ,
    input                       sys_rst_n           ,
    output                      soft_rst      
 );
     
    //wire    [15 : 0]            write_data           ;														      
    // ================= DVP ==================== 
    wire                        dvp_vsync            ;
    wire    [23 : 0]            dvp_data             ;
    wire                        dvp_href             ;
    // ================= AXIS ===================
    wire                        m_axis_video_aclk    ;
    wire                        m_axis_video_aresetn ;
    wire                        m_axis_video_tuser   ;
    wire    [23 : 0]            m_axis_video_tdata   ;
    wire                        m_axis_video_tvalid  ;
    wire                        m_axis_video_tready  ;
    //  ======== resize signal ======== 
    (* mark_debug = "true" *) wire                        resize_vsync         ;
    (* mark_debug = "true" *) wire                        resize_href          ;
    (* mark_debug = "true" *) wire    [23 : 0]            resize_data          ;
    wire    [15 : 0]            x0_pos               ;
    wire    [15 : 0]            y0_pos               ;
    wire    [15 : 0]            x1_pos               ;
    wire    [15 : 0]            y1_pos               ;
    wire    [15 : 0]            x_leng               ;
    wire    [15 : 0]            y_leng               ;
    wire    [ 3 : 0]            hstride              ;
    wire    [ 3 : 0]            vstride              ;
    // ========  Control & Status Signals =========
    wire                        img_en               ;
    wire                        dvp_ov               ;     
    reg                         cmos_vsync_out_d1    ;
    wire                        cmos_vsync_out_pos   ; 
    wire                        cnt_clr              ;
    // ================= AXI-lite ===================
    wire    [ 8 : 0]            S_AXI_AWADDR         ;
    wire    [ 2 : 0]            S_AXI_AWPROT         ;
    wire                        S_AXI_AWVALID        ;
    wire                        S_AXI_AWREADY        ;
    wire    [31 : 0]            S_AXI_WDATA          ;
    wire    [ 3 : 0]            S_AXI_WSTRB          ;
    wire                        S_AXI_WVALID         ;
    wire                        S_AXI_WREADY         ;
    wire    [ 8 : 0]            S_AXI_ARADDR         ;
    wire    [ 2 : 0]            S_AXI_ARPROT         ;
    wire                        S_AXI_ARVALID        ;
    wire                        S_AXI_ARREADY        ;
    wire    [31 : 0]            S_AXI_RDATA          ;
    wire    [ 1 : 0]            S_AXI_RRESP          ;
    wire                        S_AXI_RVALID         ;
    wire                        S_AXI_RREADY         ;  
    wire    [ 8 : 0]            S00_AXI_AWADDR       ;
    wire    [ 2 : 0]            S00_AXI_AWPROT       ;
    wire                        S00_AXI_AWVALID      ;
    wire                        S00_AXI_AWREADY      ;
    wire    [31 : 0]            S00_AXI_WDATA        ;
    wire    [ 3 : 0]            S00_AXI_WSTRB        ;
    wire                        S00_AXI_WVALID       ;
    wire                        S00_AXI_WREADY       ;
    wire    [ 8 : 0]            S00_AXI_ARADDR       ;
    wire    [ 2 : 0]            S00_AXI_ARPROT       ;
    wire                        S00_AXI_ARVALID      ;
    wire                        S00_AXI_ARREADY      ;
    wire    [31 : 0]            S00_AXI_RDATA        ;
    wire    [ 1 : 0]            S00_AXI_RRESP        ;
    wire                        S00_AXI_RVALID       ;
    wire                        S00_AXI_RREADY       ; 
	
    wire                        cmos_vsync           ;
    wire                        cmos_href            ;
    wire    [23 : 0]            cmos_db              ; 
    wire                        frame_debug_en       ;
    wire                        vtc_enable           ;
    wire                        dvp_vsync_in         ;
    wire                        dvp_href_in          ;
    wire    [23 : 0]            dvp_db_in            ; 

    mna_gp2axi mna_gp2axi_u0(
        .gpx                   (cam                 ),                 
        .gpx_clk               (                    ),   
        .gpx_rst               (                    ),   
 
        .S_AXI_ACLK            (                    ),
        .S_AXI_ARESETN         (                    ),        
        .S_AXI_AWADDR          (S_AXI_AWADDR        ),
        .S_AXI_AWPROT          (S_AXI_AWPROT        ),
        .S_AXI_AWVALID         (S_AXI_AWVALID       ),
        .S_AXI_AWREADY         (S_AXI_AWREADY       ),

        .S_AXI_WDATA           (S_AXI_WDATA         ),
        .S_AXI_WSTRB           (S_AXI_WSTRB         ),
        .S_AXI_WVALID          (S_AXI_WVALID        ),
        .S_AXI_WREADY          (S_AXI_WREADY        ),

        .S_AXI_BRESP           (                    ),
        .S_AXI_BVALID          (                    ),
        .S_AXI_BREADY          (                    ),

        .S_AXI_ARADDR          (S_AXI_ARADDR        ),
    	.S_AXI_ARPROT          (S_AXI_ARPROT        ),
    	.S_AXI_ARVALID         (S_AXI_ARVALID       ),
    	.S_AXI_ARREADY         (S_AXI_ARREADY       ),

    	.S_AXI_RDATA           (S_AXI_RDATA         ),
    	.S_AXI_RRESP           (S_AXI_RRESP         ),
    	.S_AXI_RVALID          (S_AXI_RVALID        ),
    	.S_AXI_RREADY          (S_AXI_RREADY        )       
    );

    assign dvp_vsync_in = vtc_enable ? vtc_vs   : cam_vs  ;
    assign dvp_href_in  = vtc_enable ? vtc_de   : cam_de  ;
    assign dvp_db_in    = vtc_enable ? vtc_data : cam_rgb ;

    //assign dvp_vsync_in = cam_vs  ;
    //assign dvp_href_in  = cam_de  ;
    //assign dvp_db_in    = cam_rgb ;
    
    frame_ctrl frame_ctrl_u0(
        // ======== slave axi lite interface ========
        .S_AXI_ACLK           (S_AXI_ACLK          ),
        .S_AXI_ARESETN        (S_AXI_ARESETN       ),
            
        .S_AXI_AWADDR         (S_AXI_AWADDR        ),
        .S_AXI_AWPROT         (S_AXI_AWPROT        ),
        .S_AXI_AWVALID        (S_AXI_AWVALID       ),
        .S_AXI_AWREADY        (S_AXI_AWREADY       ),
    
        .S_AXI_WDATA          (S_AXI_WDATA         ),
        .S_AXI_WSTRB          (S_AXI_WSTRB         ),
        .S_AXI_WVALID         (S_AXI_WVALID        ),
        .S_AXI_WREADY         (S_AXI_WREADY        ),
        
        .S_AXI_ARADDR         (S_AXI_ARADDR        ),
    	.S_AXI_ARPROT         (S_AXI_ARPROT        ),
    	.S_AXI_ARVALID        (S_AXI_ARVALID       ),
    	.S_AXI_ARREADY        (S_AXI_ARREADY       ),
    
    	.S_AXI_RDATA          (S_AXI_RDATA         ),
    	.S_AXI_RRESP          (S_AXI_RRESP         ),
    	.S_AXI_RVALID         (S_AXI_RVALID        ),
    	.S_AXI_RREADY         (S_AXI_RREADY        ),
    	// ======== control & status signals ========

        .dvp_pclk             (cam_clk             ),   
	    .dvp_prst_n           (~reset_cam_clk      ),
       
    	.dvp_vsync_in         (dvp_vsync_in        ),
    	.dvp_href_in          (dvp_href_in         ),
    	.dvp_db_in            (dvp_db_in           ),           
    
    	.vsync_out            (cmos_vsync          ),
    	.href_out             (cmos_href           ),
    	.db_out               (cmos_db             ),

        //======== resize config ==================
        .x0_pos_num           (x0_pos              ),
        .y0_pos_num           (y0_pos              ),
        .x1_pos_num           (x1_pos              ),
        .y1_pos_num           (y1_pos              ),
        .x_len_num            (x_leng              ),
        .y_len_num            (y_leng              ),
        .hresize_num          (hstride             ),
        .vresize_num          (vstride             ),
        //====== ps resize config
        .ps_x0_pos            (ps_x0_pos           ),
        .ps_y0_pos            (ps_y0_pos           ),
        .ps_x1_pos            (ps_x1_pos           ),
        .ps_y1_pos            (ps_y1_pos           ),
        .ps_x_leng            (ps_x_leng           ),
        .ps_y_leng            (ps_y_leng           ),
        .ps_hstride           (ps_hstride          ),
        .ps_vstride           (ps_vstride          ),
        .resize_pix_len       (resize_pix_len      ),        
        .write_ps_size        (write_ps_size       ),
        .H_SYNC               (H_SYNC              ),
        .H_BACK_PORCH         (H_BACK_PORCH        ),
        .H_ACTIVE             (H_ACTIVE            ),
        .H_FRONT_PORCH        (H_FRONT_PORCH       ),
        .V_SYNC               (V_SYNC              ),
        .V_BACK_PORCH         (V_BACK_PORCH        ),
        .V_ACTIVE             (V_ACTIVE            ),
        .V_FRONT_PORCH        (V_FRONT_PORCH       ),
        .vtc_enable          (vtc_enable           ),

    	// ===========================================
        .camera_wr_addr       (camera_wr_addr      ),
        .camera_rd_addr       (camera_rd_addr      ),

        .wr_wfifo_err         (wr_wfifo_err        ),
        .rd_rfifo_err         (rd_rfifo_err        ),
        .wr_done_pulse        (wr_done_pulse       ),
        .network_running      (0                   ), //RFU
    	.wr_buf_index         (write_addr_index    ),
    	.rd_buf_index         (read_addr_index     ),
    	// ===========================================
        .irq_test             (irq_test            ),		   
    	.img_en_sync          (img_en              ),
    	.dvp_ov               (dvp_ov              ),
        .cnt_clr              (cnt_clr             ),
        .continuous_en        (continuous_en       ),
        .display_en           (display_en          ),
        .frame_debug_en       (frame_debug_en      ),

        .M01_AXI_ACLK         (M01_AXI_ACLK        ),
        .M01_AXI_ARESETN      (M01_AXI_ARESETN     ),
        .sys_rst_n            (sys_rst_n           ),
        .soft_rst             (soft_rst            )
    );
    
    add_frame_cnt add_frame_cnt_u0(
        .cam_rst                   (reset_cam_clk       ),
        .cam_clk                   (cam_clk             ),
       
        .frame_debug_en            (frame_debug_en      ),

        .cmos_vs_in                (cmos_vsync          ),
        .cmos_hs_in                (cmos_href           ),
        .cmos_data_in              (cmos_db             ),
    
        .cmos_vs_out               (cmos_vsync_out      ),
        .cmos_hs_out               (cmos_href_out       ),
        .cmos_data_out             (cmos_db_out         )   
    );    
    always @(posedge cam_clk) begin
        if(reset_cam_clk == 1'b1)
            cmos_vsync_out_d1 <= 1'b0;
        else
            cmos_vsync_out_d1 <= cmos_vsync_out;
    end
    assign cmos_vsync_out_pos = cmos_vsync_out & (~cmos_vsync_out_d1);

    //assign write_data = {cmos_db_out[19 +: 5],cmos_db_out[10 +: 6],cmos_db_out[3 +: 5]};
    cmos_resize_24bit cmos_resize_24bit_u0(
        .cmos1_pclk            (cam_clk                ),
        .reset_cmos1_pclk      (reset_cam_clk          ),
        .dvp_href              (cmos_href_out          ),
        .dvp_vsync             (cmos_vsync_out_pos     ),
        .dvp_data              (cmos_db_out            ),
        .x0_pos                (x0_pos                 ),
        .y0_pos                (y0_pos                 ),
        .x1_pos                (x1_pos                 ),
        .y1_pos                (y1_pos                 ),
        .x_leng                (x_leng                 ),
        .y_leng                (y_leng                 ),
        .hstride               (hstride                ),
        .vstride               (vstride                ),
        .resize_href           (resize_href            ),
        .resize_vsync          (resize_vsync           ),
        .resize_data           (resize_data            )
    );

    assign dvp_vsync = resize_vsync  & img_en       ;
    assign dvp_data  = resize_data   & {24{img_en}} ;    
    assign dvp_href  = resize_href   & img_en       ;    
  
    axis_master axis_master_inst(
        .dvp_clk               (cam_clk              ),
        .dvp_rst               (reset_cam_clk        ),
        .dvp_vsync             (dvp_vsync            ),
        .dvp_data              (dvp_data             ),
        .dvp_href              (dvp_href             ),
                                          
	    .m_axis_video_aclk     (M01_AXI_ACLK         ),
	    .m_axis_video_aresetn  (M01_AXI_ARESETN      ),
	    .m_axis_video_tuser    (m_axis_video_tuser   ),
	    .m_axis_video_tdata    (m_axis_video_tdata   ),
	    .m_axis_video_tvalid   (m_axis_video_tvalid  ),
	    .m_axis_video_tready   (m_axis_video_tready  ),
                                 
        .overflow              (dvp_ov               )
    );	

    assign img_start = m_axis_video_tuser  ;
    assign img_data  = m_axis_video_tdata  ;
    assign img_valid = m_axis_video_tvalid ;
    assign m_axis_video_tready = img_ready ;
       
endmodule
