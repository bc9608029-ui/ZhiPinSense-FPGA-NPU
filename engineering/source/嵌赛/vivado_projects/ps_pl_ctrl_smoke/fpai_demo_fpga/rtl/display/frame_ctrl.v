//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : host_ctrl.v
// Author        : Xu Yun 
// Project       : NB1916
// Create Date   : 2019.10.11
// Description   : 
// - Host top control
//------------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
//==============================================================================

module frame_ctrl (
    // ======== slave axi lite interface ========
    input                 S_AXI_ACLK          ,
    input                 S_AXI_ARESETN       ,
         
    input      [ 8 : 0]   S_AXI_AWADDR        ,
    input      [ 2 : 0]   S_AXI_AWPROT        ,
    input                 S_AXI_AWVALID       ,
    output                S_AXI_AWREADY       ,
         
    input      [31 : 0]   S_AXI_WDATA         ,
    input      [ 3 : 0]   S_AXI_WSTRB         ,
    input                 S_AXI_WVALID        ,
    output                S_AXI_WREADY        ,
         
    input      [ 8 : 0]   S_AXI_ARADDR        ,
    input      [ 2 : 0]   S_AXI_ARPROT        ,
    input                 S_AXI_ARVALID       ,
    output                S_AXI_ARREADY       ,
         
    output reg [31 : 0]   S_AXI_RDATA         ,
    output reg [ 1 : 0]   S_AXI_RRESP         ,
    output reg            S_AXI_RVALID        ,
    input                 S_AXI_RREADY        ,
         
    // ======== DVP interface ========     
    input                 dvp_pclk            ,
    input                 dvp_prst_n          ,
     
	input                 dvp_vsync_in        ,     
	input                 dvp_href_in         ,     
	input      [23 : 0]   dvp_db_in           ,     
     
 	output reg            vsync_out           ,
	output reg            href_out            , 
	output reg [23 : 0]   db_out              ,
       
    // ======== resize ================     
    output     [15 : 0]   x0_pos_num          ,
    output     [15 : 0]   y0_pos_num          ,
    output     [15 : 0]   x1_pos_num          ,
    output     [15 : 0]   y1_pos_num          ,
    output     [15 : 0]   x_len_num           ,
    output     [15 : 0]   y_len_num           ,
    output     [ 3 : 0]   hresize_num         ,
    output     [ 3 : 0]   vresize_num         ,

        // ======== resize ================
    output reg [15 : 0]   ps_x0_pos           ,
    output reg [15 : 0]   ps_y0_pos           ,
    output reg [15 : 0]   ps_x1_pos           ,
    output reg [15 : 0]   ps_y1_pos           ,
    output reg [15 : 0]   ps_x_leng           ,
    output reg [15 : 0]   ps_y_leng           ,
    output reg [ 3 : 0]   ps_hstride          ,
    output reg [ 3 : 0]   ps_vstride          ,
    output reg [10 : 0]   resize_pix_len      ,
    output reg [31 : 0]   write_ps_size       ,
        
    output reg [31 : 0]   H_SYNC              ,
    output reg [31 : 0]   H_BACK_PORCH        ,
    output reg [31 : 0]   H_ACTIVE            ,
    output reg [31 : 0]   H_FRONT_PORCH       ,
    output reg [31 : 0]   V_SYNC              ,
    output reg [31 : 0]   V_BACK_PORCH        ,
    output reg [31 : 0]   V_ACTIVE            ,
    output reg [31 : 0]   V_FRONT_PORCH       ,
    output reg            vtc_enable          ,
    //=========camera addr for 100ai ===     
    output reg [31 : 0]   camera_wr_addr      ,
    output reg [31 : 0]   camera_rd_addr      ,
     
    input                 wr_wfifo_err        ,
    input                 rd_rfifo_err        ,
    input                 wr_done_pulse       ,
     
	// ========= ctrl & status =======     
    output                irq_test            ,
	input                 network_running     ,	
	input      [ 1 : 0]   wr_buf_index        ,
	input      [ 1 : 0]   rd_buf_index        ,
    output reg            img_en_sync         ,
    input                 dvp_ov              , 
    output reg            cnt_clr             ,
    output reg            continuous_en       ,
    output                display_en          ,
    output reg            frame_debug_en      ,

    input                 M01_AXI_ACLK        ,
    input                 M01_AXI_ARESETN     ,
    input                 sys_rst_n           ,
    output reg            soft_rst     
);

    // axi-lite reg signals 
    reg    [ 8 : 0]     axi_awaddr         ;
    reg    [ 8 : 0]     axi_araddr         ;
    reg    [31 : 0]     slv_reg0           ;
    wire   [31 : 0]     slv_reg1           ;
    wire   [31 : 0]     slv_reg2           ;
    wire   [31 : 0]     slv_reg3           ;
    wire   [31 : 0]     slv_reg4           ;
    wire   [31 : 0]     slv_reg5           ;
    wire   [31 : 0]     slv_reg6           ;
    wire   [31 : 0]     slv_reg7           ;
    wire   [31 : 0]     slv_reg8           ;
    wire   [31 : 0]     slv_reg9           ;
    wire   [31 : 0]     slv_reg10          ;
    wire   [31 : 0]     slv_reg11          ;
    wire   [31 : 0]     slv_reg12          ;
    wire   [31 : 0]     slv_reg13          ;
    wire   [31 : 0]     slv_reg14          ;
    wire   [31 : 0]     slv_reg15          ;
    wire   [31 : 0]     slv_reg16          ;   
    wire   [31 : 0]     slv_reg17          ;   
    wire   [31 : 0]     slv_reg18          ;
    wire   [31 : 0]     slv_reg19          ;
    wire [31:0]         slv_reg20          ;
    wire [31:0]         slv_reg21          ;
    wire [31:0]         slv_reg22          ;
    wire [31:0]         slv_reg23          ;
    wire [31:0]         slv_reg24          ;
    wire [31:0]         slv_reg25          ;
    wire [31:0]         slv_reg26          ;
    wire [31:0]         slv_reg27          ;
    wire [31:0]         slv_reg28          ;
    wire [31:0]         slv_reg29          ;
    wire [31:0]         slv_reg30          ;
    wire [31:0]         slv_reg31          ;
    wire [31:0]         slv_reg32          ;
    wire [31:0]         slv_reg33          ;
    wire [31:0]         slv_reg34          ;
    wire [31:0]         slv_reg35          ;
    wire [31:0]         slv_reg36          ;
    wire [31:0]         slv_reg37          ;
    wire [31:0]         slv_reg38          ;
    wire [31:0]         slv_reg39          ;
    wire [31:0]         slv_reg40          ;
    wire [31:0]         slv_reg41          ;
    wire [31:0]         slv_reg42          ;
    wire [31:0]         slv_reg43          ;
    wire [31:0]         slv_reg44          ;
    wire [31:0]         slv_reg45          ;

    wire                slv_reg_rden       ; 
    wire                slv_reg_wren       ;
    integer             byte_index         ;
    // icore signals
    reg                 aclk_frame_req     ;

    wire                aclk_frame_ack     ;
    wire                pclk_frame_fetch   ;
    reg                 frame_fetch_req    ;
    reg                 frame_en           ;
    reg                 frame_en_switch    ;
    reg    [31 : 0]     frame_ctrl_ver     ;

    reg                img_en              ;
    reg                img_en_t1           ; 
    reg                img_en_t2           ; 
    reg                dvp_ov_dly          ;
    wire               dvp_ov_pulse        ;
    wire               icore_pre_ov_pulse  ;
    reg                icore_pre_ov        ;
    wire               frame_en_switch_sync;
    wire               continuous_mode_sync;
    reg                continuous_mode     ;
    reg    [31 : 0]    resize_confh        ;
    reg                confh_wen           ;
    //wire   [ 3 : 0]    hresize_num         ;
    wire               hresize_fifo_empty  ;    
    reg    [31 : 0]    resize_confv        ;
    reg                confv_wen           ; 
    //wire   [ 3 : 0]    vresize_num         ;
    wire               vresize_fifo_empty  ;
    reg    [31 : 0]    resize_x0_pos       ;
    reg                confx0_wen          ;
    //wire   [15 : 0]    x0_pos_num          ;
    wire               x0_fifo_empty       ;
    reg    [31 : 0]    resize_y0_pos       ;
    reg                confy0_wen          ;
   // wire   [15 : 0]    y0_pos_num          ;
    wire               y0_fifo_empty       ; 
    reg    [31 : 0]    resize_x1_pos       ;
    reg                confx1_wen          ;
    //wire   [15 : 0]    x1_pos_num          ;
    wire               x1_fifo_empty       ;
    reg    [31 : 0]    resize_y1_pos       ;
    reg                confy1_wen          ;
   // wire   [15 : 0]    y1_pos_num          ;
    wire               y1_fifo_empty       ;
    reg    [31 : 0]    resize_x_len        ;
    reg                conf_xlen_wen       ;
    //wire   [15 : 0]    x_len_num           ;
    wire               xlen_fifo_empty     ;
    reg    [31 : 0]    resize_y_len        ;
    reg                conf_ylen_wen       ;
    //wire   [15 : 0]    y_len_num           ;
    wire               ylen_fifo_empty     ;
    reg                plin_valid          ;
    reg    [31 : 0]    rst_cnt             ;
    reg                soft_rst_finished   ;    

    reg                camera_wr_done      ;
    reg                frame_done_req      ;
    reg                frame_done_req_syn0 ;
    reg                frame_done_req_syn1 ;
    reg                frame_done_req_dly0 ;
    wire               frame_done_req_pos  ;    
    
    reg                dvp_vsync_in_dly    ;
    wire               dvp_vsync_start     ;
    reg                dvp_href_in_dly     ;
    reg     [23 : 0]   dvp_db_in_dly       ;    

 	wire               dvp_vsync_out       ;
	wire               dvp_href_out        ; 
	wire    [23 : 0]   dvp_db_out          ;  

    reg                disable_hdmi        ;
    reg                disable_hdmi_0      ;
    reg                disable_hdmi_1      ;
    reg                disable_hdmi_2      ; 
    //reg     [10 : 0]   resize_pix_len      ; 
    reg                conf_pix_len_wen    ; 
    wire               pix_len_fifo_empty  ;  
    reg     [31 : 0]   over_thr            ;
    //------------------------------------------------
    //-- AXI-lite Write Register Control--
    //------------------------------------------------
    assign S_AXI_AWREADY = 1'b1;

    always @( posedge S_AXI_ACLK )
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            axi_awaddr <= 0;
        else if (S_AXI_AWVALID && S_AXI_WVALID)
            axi_awaddr <= S_AXI_AWADDR;
    end

    assign S_AXI_WREADY = 1'b1;

    assign slv_reg_wren = S_AXI_WREADY && S_AXI_WVALID && S_AXI_AWREADY && S_AXI_AWVALID;

    //------------------------------------------------
    //-- AXI-lite Read Register Control--
    //------------------------------------------------
    assign S_AXI_ARREADY = 1'b1;

    always @( posedge S_AXI_ACLK )
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            axi_araddr  <= 9'h0;
        else if (S_AXI_ARVALID)
            axi_araddr  <= S_AXI_ARADDR;
    end    
    
    always @( posedge S_AXI_ACLK )
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            S_AXI_RVALID <= 0;
        else if (S_AXI_ARREADY && S_AXI_ARVALID)
            S_AXI_RVALID <= 1'b1;
        else if (S_AXI_RREADY)
            S_AXI_RVALID <= 1'b0;
    end
    
    always @( posedge S_AXI_ACLK )
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            S_AXI_RRESP  <= 0;
        else if (S_AXI_ARREADY && S_AXI_ARVALID && ~S_AXI_RVALID)
            S_AXI_RRESP  <= 2'b0; // 'OKAY' response
    end

    assign slv_reg_rden = S_AXI_ARREADY & S_AXI_ARVALID;

    //------------------------------------------------
    //-- Registers File Definition --
    //------------------------------------------------
    // 8'h00 : slv_reg0
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            slv_reg0 <= 0;
        else if (slv_reg_wren && S_AXI_AWADDR == 9'h000)
        begin
            for ( byte_index = 0; byte_index <= 3; byte_index = byte_index+1 )
                if ( S_AXI_WSTRB[byte_index] == 1 )
                    slv_reg0[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
        end
    end
    assign irq_test = slv_reg0[0];

    // 8'h04 : slv_reg1
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            aclk_frame_req <= 0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h004 && S_AXI_WSTRB[0]==1'b1)
            aclk_frame_req <= S_AXI_WDATA[0];
        else if(aclk_frame_ack)
            aclk_frame_req <= 1'b0;
    end
    assign slv_reg1 = {31'h0,aclk_frame_req};
       
    //8'h08 : slv_reg2
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            //frame_en_switch <= 1'b1;
            frame_en_switch <= 1'b0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h008 && S_AXI_WSTRB[0]==1'b1)
            frame_en_switch <= S_AXI_WDATA[0];
    end
    assign slv_reg2 = {31'h00000000,frame_en_switch};   
    
    //8'h0C : slv_reg3
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            frame_ctrl_ver <= 0;
        else
            frame_ctrl_ver <= 32'h20230218;
    end
    assign slv_reg3 = frame_ctrl_ver;
    
    //8'h10 : slv_reg4
    assign slv_reg4 = {30'h0,wr_buf_index};
    
    //8'h14 : slv_reg5
    assign slv_reg5 = {30'h0,rd_buf_index};
    
    //8'h18 : slv_reg6
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            img_en <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h018 && S_AXI_WSTRB[0]==1'b1)
            img_en <= S_AXI_WDATA[0];
    end  
    assign slv_reg6 = {31'h0, img_en};    
    
    //8'h1C : slv_reg7
    
	always @( posedge dvp_pclk)
    begin
        if(dvp_prst_n == 1'b0)
          dvp_ov_dly <= 1'b0;
        else
          dvp_ov_dly <= dvp_ov;
    end
    assign dvp_ov_pulse = dvp_ov & ~dvp_ov_dly;

    pulse_cross_camera pulse_cross_dvp_ov(
        .a2    (icore_pre_ov_pulse),
        .clk2  (S_AXI_ACLK      ),
        .rst2  (~S_AXI_ARESETN  ),
        
        .a1    (dvp_ov_pulse    ),
        .clk1  (dvp_pclk        ),
        .rst1  (~dvp_prst_n     )
    ); 

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            icore_pre_ov <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h01C && S_AXI_WSTRB[0]==1'b1&&S_AXI_WDATA[0]==1'b1)
            icore_pre_ov <= 1'b0;
        else if(icore_pre_ov_pulse)
            icore_pre_ov <= 1'b1;
    end
    assign slv_reg7 = {31'h0, icore_pre_ov};
        
    //8'h20 : slv_reg8
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_confh <= 32'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h020 && S_AXI_WSTRB[0]==1'b1)
            resize_confh <= S_AXI_WDATA;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            confh_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h020 && S_AXI_WSTRB[0]==1'b1 && confh_wen == 1'b0)
            confh_wen <= 1'b1;
        else 
            confh_wen <= 1'b0;
    end

    assign hresize_num = resize_confh[3:0];
    assign slv_reg8 = {28'h0,hresize_num};  

    //buf_4b_16w hresize_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (hresize_num               ),     
    //    .wr_en            (confh_wen                 ),        
    //    .rd_en            (~hresize_fifo_empty       ),   
    //    .dout             (hstride_sync              ),      
    //    .full             (),     
    //    .empty            (hresize_fifo_empty        )
    //);

    //8'h24 : slv_reg9
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_confv <= 32'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h024 && S_AXI_WSTRB[0]==1'b1)
            resize_confv <= S_AXI_WDATA;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            confv_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h024 && S_AXI_WSTRB[0]==1'b1 && confv_wen==1'b0)
            confv_wen <= 1'b1;
        else 
            confv_wen <= 1'b0;
    end

    assign vresize_num = resize_confv[3:0];
    assign slv_reg9 = {28'h0,vresize_num}; 

    //buf_4b_16w vresize_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (vresize_num               ),     
    //    .wr_en            (confv_wen                 ),        
    //    .rd_en            (~vresize_fifo_empty       ),   
    //    .dout             (vstride_sync              ),      
    //    .full             (),     
    //    .empty            (vresize_fifo_empty        )
    //);

    //8'h28 : slv_reg10
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_x0_pos <= 32'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h028 && S_AXI_WSTRB[0]==1'b1)
            resize_x0_pos <= S_AXI_WDATA;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            confx0_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h028 && S_AXI_WSTRB[0]==1'b1 && confx0_wen == 1'b0)
            confx0_wen <= 1'b1;
        else 
            confx0_wen <= 1'b0;
    end

     assign x0_pos_num = resize_x0_pos[15:0];
     assign slv_reg10 = {16'h0,x0_pos_num};  

    //buf_16b_16w x0_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (x0_pos_num                ),     
    //    .wr_en            (confx0_wen                ),        
    //    .rd_en            (~x0_fifo_empty            ),   
    //    .dout             (x0_pos_sync               ),      
    //    .full             (),     
    //    .empty            (x0_fifo_empty             )
    //);

    //8'h2C : slv_reg11
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_y0_pos <= 32'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h02C && S_AXI_WSTRB[0]==1'b1)
            resize_y0_pos <= S_AXI_WDATA;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            confy0_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h02C && S_AXI_WSTRB[0]==1'b1 && confy0_wen == 1'b0)
            confy0_wen <= 1'b1;
        else 
            confy0_wen <= 1'b0;
    end

     assign y0_pos_num = resize_y0_pos[15:0];
     assign slv_reg11 = {16'h0,y0_pos_num};  

    //buf_16b_16w y0_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (y0_pos_num                ),     
    //    .wr_en            (confy0_wen                ),        
    //    .rd_en            (~y0_fifo_empty            ),   
    //    .dout             (y0_pos_sync               ),      
    //    .full             (),     
    //    .empty            (y0_fifo_empty             )
    //);        
    //8'h30 : slv_reg12 
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_x1_pos <= 32'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h030 && S_AXI_WSTRB[0]==1'b1)
            resize_x1_pos <= S_AXI_WDATA;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            confx1_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h030 && S_AXI_WSTRB[0]==1'b1 && confx1_wen == 1'b0)
            confx1_wen <= 1'b1;
        else 
            confx1_wen <= 1'b0;
    end

     assign x1_pos_num = resize_x1_pos[15:0];
     assign slv_reg12 = {16'h0,x1_pos_num};  

    //buf_16b_16w x1_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (x1_pos_num                ),     
    //    .wr_en            (confx1_wen                ),        
    //    .rd_en            (~x1_fifo_empty            ),   
    //    .dout             (x1_pos_sync               ),      
    //    .full             (),     
    //    .empty            (x1_fifo_empty             )
    //);     
    //8'h34 : slv_reg13   
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_y1_pos <= 32'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h034 && S_AXI_WSTRB[0]==1'b1)
            resize_y1_pos <= S_AXI_WDATA;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            confy1_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h034 && S_AXI_WSTRB[0]==1'b1 && confy1_wen == 1'b0)
            confy1_wen <= 1'b1;
        else 
            confy1_wen <= 1'b0;
    end

     assign y1_pos_num = resize_y1_pos[15:0];
     assign slv_reg13 = {16'h0,y1_pos_num};  

    //buf_16b_16w y1_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (y1_pos_num                ),     
    //    .wr_en            (confy1_wen                ),        
    //    .rd_en            (~y1_fifo_empty            ),   
    //    .dout             (y1_pos_sync               ),      
    //    .full             (),     
    //    .empty            (y1_fifo_empty             )
    //);         
    //8'h38 : slv_reg14
    always @( posedge S_AXI_ACLK ) 
     begin
         if ( S_AXI_ARESETN == 1'b0 )
             resize_x_len <= 32'h0;
         else if (slv_reg_wren && S_AXI_AWADDR==9'h038 && S_AXI_WSTRB[0]==1'b1)
             resize_x_len <= S_AXI_WDATA;
     end

    always @( posedge S_AXI_ACLK ) 
     begin
         if ( S_AXI_ARESETN == 1'b0 )
             conf_xlen_wen <= 1'h0;
         else if (slv_reg_wren && S_AXI_AWADDR==9'h038 && S_AXI_WSTRB[0]==1'b1 && conf_xlen_wen == 1'b0)
             conf_xlen_wen <= 1'b1;
         else 
             conf_xlen_wen <= 1'b0;
     end

     assign x_len_num = resize_x_len[15:0];
     assign slv_reg14 = {16'h0,x_len_num};  

     //buf_16b_16w xlen_buf_u0 (
     //    .rst              (!S_AXI_ARESETN            ),          
     //    .wr_clk           (S_AXI_ACLK                ),        
     //    .rd_clk           (dvp_pclk                  ),         
     //    .din              (x_len_num                 ),     
     //    .wr_en            (conf_xlen_wen             ),        
     //    .rd_en            (~xlen_fifo_empty          ),   
     //    .dout             (x_leng_sync               ),      
     //    .full             (),     
     //    .empty            (xlen_fifo_empty           )
     //); 

    //8'h3C : slv_reg15
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_y_len <= 32'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h03C && S_AXI_WSTRB[0]==1'b1)
            resize_y_len <= S_AXI_WDATA;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            conf_ylen_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h03C && S_AXI_WSTRB[0]==1'b1 && conf_ylen_wen == 1'b0)
            conf_ylen_wen <= 1'b1;
        else 
            conf_ylen_wen <= 1'b0;
    end

    assign y_len_num = resize_y_len[15:0];
    assign slv_reg15 = {16'h0,y_len_num};  

    //buf_16b_16w ylen_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (y_len_num                 ),     
    //    .wr_en            (conf_ylen_wen             ),        
    //    .rd_en            (~ylen_fifo_empty          ),   
    //    .dout             (y_leng_sync               ),      
    //    .full             (),     
    //    .empty            (ylen_fifo_empty           )
    //);

    //8'h40 : slv_reg16
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            cnt_clr <= 0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h040 && S_AXI_WSTRB[0]==1'b1)
            cnt_clr <= S_AXI_WDATA[0];
    end
    assign slv_reg16 = {31'h00000000,cnt_clr}; 

    //8'h44 : slv_reg17
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            continuous_mode <= 0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h044 && S_AXI_WSTRB[0]==1'b1)
            continuous_mode <= S_AXI_WDATA[0];
    end
    assign slv_reg17 = {31'h00000000,continuous_mode};   
    
    //8'h48 : slv_reg18
    assign slv_reg18 = {31'h0,network_running};    
    
    //8'h4C : slv_reg19
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            plin_valid <= 1'b0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h04C && S_AXI_WSTRB[0]==1'b1)
            plin_valid <= S_AXI_WDATA[0];
    end
    assign slv_reg19 = {31'h00000000,plin_valid};       

    //8'h50 : slv_reg20
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            camera_wr_addr <= 27'h7C0_0000;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h050 && S_AXI_WSTRB[0]==1'b1)
            camera_wr_addr <= S_AXI_WDATA;
    end
    assign slv_reg20 = camera_wr_addr;       

    //8'h54 : slv_reg21
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            camera_rd_addr <= 27'h7E0_0000;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h054 && S_AXI_WSTRB[0]==1'b1)
            camera_rd_addr <= S_AXI_WDATA;
    end
    assign slv_reg21 = camera_rd_addr;       

    //8'h58 : slv_reg22

    always @( posedge S_AXI_ACLK ) begin
        if (S_AXI_ARESETN == 1'b0)
          {frame_done_req_dly0,frame_done_req_syn1,frame_done_req_syn0} <= 3'b0;
        else 
          {frame_done_req_dly0,frame_done_req_syn1,frame_done_req_syn0} <= {frame_done_req_syn1,frame_done_req_syn0,frame_done_req};

    end

    assign frame_done_req_pos = (~frame_done_req_dly0) & (frame_done_req_syn1);

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            camera_wr_done <= 1'b0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h004 && S_AXI_WSTRB[0]==1'b1)   //write fetch one : aclk_frame_req
            camera_wr_done <= 1'b0;
        else if (frame_done_req_pos)    
            camera_wr_done <= 1'b1;
    end

    assign slv_reg22 = {29'h0,wr_wfifo_err,rd_rfifo_err,camera_wr_done};  


    //8'h5C : slv_reg23  {ps_x0_pos,ps_x1_pos}          default£º{16'd0,16'd1919}
    //8'h60 : slv_reg24  {ps_y0_pos,ps_y1_pos}          default£º{16'd0,16'd1079}
    //8'h64 : slv_reg25  {ps_x_leng,ps_y_leng}          default£º{16'd1920,16'd1080}
    //8'h68 : slv_reg26  {24'h0,ps_hstride,ps_vstride}  default£º{4'd1,4'd1}

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            {ps_x0_pos,ps_x1_pos} <= {16'd0,16'd1919};
        else if (slv_reg_wren && S_AXI_AWADDR==9'h05C && S_AXI_WSTRB[0]==1'b1) 
            {ps_x0_pos,ps_x1_pos} <= S_AXI_WDATA;
    end
    assign slv_reg23 = {ps_x0_pos,ps_x1_pos};  

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            {ps_y0_pos,ps_y1_pos} <= {16'd0,16'd1079};
        else if (slv_reg_wren && S_AXI_AWADDR==9'h060 && S_AXI_WSTRB[0]==1'b1) 
            {ps_y0_pos,ps_y1_pos} <= S_AXI_WDATA;
    end
    assign slv_reg24 = {ps_y0_pos,ps_y1_pos};  

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            {ps_x_leng,ps_y_leng} <= {16'd1920,16'd1080};
        else if (slv_reg_wren && S_AXI_AWADDR==9'h064 && S_AXI_WSTRB[0]==1'b1) 
            {ps_x_leng,ps_y_leng} <= S_AXI_WDATA;
    end
    assign slv_reg25 = {ps_x_leng,ps_y_leng};  

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            {ps_hstride,ps_vstride} <= {4'd1,4'd1};
        else if (slv_reg_wren && S_AXI_AWADDR==9'h068 && S_AXI_WSTRB[0]==1'b1) 
            {ps_hstride,ps_vstride} <= S_AXI_WDATA[7:0];
    end
    assign slv_reg26 = {24'h0,ps_hstride,ps_vstride};  

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
             write_ps_size <= 32'd518400 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h06C && S_AXI_WSTRB[0]==1'b1) 
             write_ps_size <= S_AXI_WDATA;
    end
    assign slv_reg27 = write_ps_size;  

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( sys_rst_n == 1'b0 )
             soft_rst <= 1'b0 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h070 && S_AXI_WSTRB[0]==1'b1) 
             soft_rst <= S_AXI_WDATA[0];
        else if(rst_cnt == 'd100)
             soft_rst <= 1'b0;
    end
    assign slv_reg28 = {31'd0,soft_rst};  

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( sys_rst_n == 1'b0 )
             rst_cnt <= 1'b0 ;
        else if (rst_cnt == 'd100)
             rst_cnt <= 'd0;
        else if (soft_rst==1'b1) 
             rst_cnt <= rst_cnt + 1;
    end

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( sys_rst_n == 1'b0 )
             soft_rst_finished <= 1'b0 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h070 && S_AXI_WSTRB[0]==1'b1) 
             soft_rst_finished <= 1'b0;
        else if(rst_cnt == 'd100)
             soft_rst_finished <= 1'b1;
    end
    assign slv_reg29 = {31'd0,soft_rst_finished}; 

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( sys_rst_n == 1'b0 )
             disable_hdmi <= 1'b0 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h078 && S_AXI_WSTRB[0]==1'b1) 
             disable_hdmi <= S_AXI_WDATA[0];
    end
    assign slv_reg30 = {31'd0,disable_hdmi}; 

    always @( posedge M01_AXI_ACLK ) 
    begin
        if ( M01_AXI_ARESETN == 1'b0 )
             {disable_hdmi_2,disable_hdmi_1,disable_hdmi_0} <= 3'b0;
        else  
             {disable_hdmi_2,disable_hdmi_1,disable_hdmi_0} <= {disable_hdmi_1,disable_hdmi_0,disable_hdmi};
    end    
    assign display_en = ~disable_hdmi_2;

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            resize_pix_len <= 11'b0 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h07C && S_AXI_WSTRB[1:0]==2'b11) 
            resize_pix_len <= S_AXI_WDATA[10:0];
    end
    assign slv_reg31 = {21'd0,resize_pix_len}; 

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            conf_pix_len_wen <= 1'h0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h07C && S_AXI_WSTRB[1:0]==2'b11 && conf_pix_len_wen == 1'b0)
            conf_pix_len_wen <= 1'b1;
        else 
            conf_pix_len_wen <= 1'b0;
    end

    //buf_11b_16w resize_pix_len_buf_u0 (
    //    .rst              (!S_AXI_ARESETN            ),          
    //    .wr_clk           (S_AXI_ACLK                ),        
    //    .rd_clk           (dvp_pclk                  ),         
    //    .din              (resize_pix_len            ),     
    //    .wr_en            (conf_pix_len_wen          ),        
    //    .rd_en            (~pix_len_fifo_empty       ),   
    //    .dout             (resize_pix_len_sync       ),      
    //    .full             (),     
    //    .empty            (pix_len_fifo_empty        )
    //);
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            frame_debug_en <= 1'b0 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h080 && S_AXI_WSTRB[0]==1'b1) 
            frame_debug_en <= S_AXI_WDATA[0];
    end
    assign slv_reg32 = {31'd0,frame_debug_en}; 
// reg read out
    always@(posedge S_AXI_ACLK) begin
        if(S_AXI_ARESETN==1'b0)
            S_AXI_RDATA <= #0.1 0;
        else if(slv_reg_rden) begin
            case(S_AXI_ARADDR[8:0])
                9'h000 : S_AXI_RDATA <= slv_reg0;
                9'h004 : S_AXI_RDATA <= slv_reg1;
                9'h008 : S_AXI_RDATA <= slv_reg2;
                9'h00C : S_AXI_RDATA <= slv_reg3;
                9'h010 : S_AXI_RDATA <= slv_reg4;
                9'h014 : S_AXI_RDATA <= slv_reg5;
                9'h018 : S_AXI_RDATA <= slv_reg6;
                9'h01C : S_AXI_RDATA <= slv_reg7;  
                9'h020 : S_AXI_RDATA <= slv_reg8;  
                9'h024 : S_AXI_RDATA <= slv_reg9;
                9'h028 : S_AXI_RDATA <= slv_reg10;  
                9'h02C : S_AXI_RDATA <= slv_reg11;  
                9'h030 : S_AXI_RDATA <= slv_reg12;
                9'h034 : S_AXI_RDATA <= slv_reg13;
                9'h038 : S_AXI_RDATA <= slv_reg14;
                9'h03C : S_AXI_RDATA <= slv_reg15;
                9'h040 : S_AXI_RDATA <= slv_reg16;       
                9'h044 : S_AXI_RDATA <= slv_reg17;            
                9'h048 : S_AXI_RDATA <= slv_reg18;
                9'h04C : S_AXI_RDATA <= slv_reg19;  
                9'h050 : S_AXI_RDATA <= slv_reg20;  
                9'h054 : S_AXI_RDATA <= slv_reg21;
                9'h058 : S_AXI_RDATA <= slv_reg22;  
                9'h05C : S_AXI_RDATA <= slv_reg23;  
                9'h060 : S_AXI_RDATA <= slv_reg24;
                9'h064 : S_AXI_RDATA <= slv_reg25;
                9'h068 : S_AXI_RDATA <= slv_reg26;
                9'h06C : S_AXI_RDATA <= slv_reg27;      
                9'h070 : S_AXI_RDATA <= slv_reg28;   
                9'h074 : S_AXI_RDATA <= slv_reg29;
                9'h078 : S_AXI_RDATA <= slv_reg30; 
                9'h07C : S_AXI_RDATA <= slv_reg31; 
                9'h080 : S_AXI_RDATA <= slv_reg32;       
                9'h084 : S_AXI_RDATA <= slv_reg33;
                9'h088 : S_AXI_RDATA <= slv_reg34; 
                9'h08C : S_AXI_RDATA <= slv_reg35; 
                9'h090 : S_AXI_RDATA <= slv_reg36;  
                9'h094 : S_AXI_RDATA <= slv_reg37; 
                9'h098 : S_AXI_RDATA <= slv_reg38;      
                9'h09C : S_AXI_RDATA <= slv_reg39;
                9'h0A0 : S_AXI_RDATA <= slv_reg40; 
                9'h0A4 : S_AXI_RDATA <= slv_reg41; 
                9'h0A8 : S_AXI_RDATA <= slv_reg42;    
                9'h0AC : S_AXI_RDATA <= slv_reg43;
                9'h0B0 : S_AXI_RDATA <= slv_reg44;
                9'h0B4 : S_AXI_RDATA <= slv_reg45;                                  
                default : S_AXI_RDATA <= 32'h0000_0000;
            endcase
        end
    end    
    //------------------------------------------------
    //-- req & ack --
    //------------------------------------------------
  
    bridge_s bridge_s_u1(
                      .clka      (S_AXI_ACLK       ),
                      .clkb      (dvp_pclk         ),
                      .rsta      (~S_AXI_ARESETN   ),
                      .rstb      (~S_AXI_ARESETN   ),
                      .a_req     (aclk_frame_req   ),
                      .a_req_clr (aclk_frame_ack   ),
                      .b_en      (pclk_frame_fetch )
                       );
    
    always @( posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        frame_fetch_req <= 1'b0;
      else if(pclk_frame_fetch == 1'b1)
        frame_fetch_req <= 1'b1;
      else if(dvp_vsync_start)
        frame_fetch_req <= 1'b0;
    end

    always @(posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        frame_en <= 1'b0;//frame_en <= 1'b1;
      else if(dvp_vsync_start & frame_fetch_req)
        frame_en <= 1'b1;
      else if(dvp_vsync_start & ~frame_fetch_req)
        frame_en <= 1'b0;
    end

    always @( posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        frame_done_req <= 1'b0;
      else if(pclk_frame_fetch)
        frame_done_req <= 1'b0;
      else if(wr_done_pulse)
        frame_done_req <= 1'b1;
    end        

    always @(posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        dvp_vsync_in_dly <= 1'b0;
      else
        dvp_vsync_in_dly <= dvp_vsync_in;
    end
    assign dvp_vsync_start = (~dvp_vsync_in_dly) & dvp_vsync_in;

    reg [31:0]pix_cnt;
    always @(posedge dvp_pclk)
    begin
      if(sys_rst_n == 1'b0)
        pix_cnt <= 'b0;
      else if(dvp_vsync_start)
        pix_cnt <= 'b0;
      else 
        pix_cnt <= pix_cnt + 1'b1;
    end

    reg [31:0]done_cnt;
    always @(posedge dvp_pclk)
    begin
      if(sys_rst_n == 1'b0)
        done_cnt <= 'b0;
      else if(wr_done_pulse)
        done_cnt <= 'b0;
      else 
        done_cnt <= done_cnt + 1'b1;
    end

    reg [31:0]done_2_fetch_cnt;
    always @(posedge dvp_pclk)
    begin
      if(sys_rst_n == 1'b0)
        done_2_fetch_cnt <= 'b0;
      else if(pclk_frame_fetch)
        done_2_fetch_cnt <= done_cnt;
    end
    assign slv_reg33 = done_2_fetch_cnt; //8'h84

    reg [31:0]fetch_cnt;
    always @(posedge dvp_pclk)
    begin
      if(sys_rst_n == 1'b0)
        fetch_cnt <= 'b0;
      else if(pclk_frame_fetch)
        fetch_cnt <= fetch_cnt + 1'b1;
    end
    assign slv_reg34 = fetch_cnt; //8'h88

    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
             over_thr <= 32'd98000 ; //for 1080p=2200*44 pix
        else if (slv_reg_wren && S_AXI_AWADDR==9'h08C && S_AXI_WSTRB[0]==1'b1) 
             over_thr <= S_AXI_WDATA;
    end
    assign slv_reg35 = over_thr; //8'h8C

    reg pclk_frame_fetch_d1;
    always @(posedge dvp_pclk)
    begin
      if(sys_rst_n == 1'b0)
        pclk_frame_fetch_d1 <= 'b0;
      else 
        pclk_frame_fetch_d1 <= pclk_frame_fetch;
    end

    reg [31:0]over_cnt;
    always @(posedge dvp_pclk)
    begin
      if(sys_rst_n == 1'b0)
        over_cnt <= 'b0;
      else if((done_2_fetch_cnt >= over_thr)&&(pclk_frame_fetch_d1))
        over_cnt <= over_cnt + 1'b1;
    end
    assign slv_reg36 = over_cnt; //8'h90  

    //slv_reg37:0x094
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            H_SYNC <= 32'd44 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h094) 
            H_SYNC <= S_AXI_WDATA[31:0];
    end
    assign slv_reg37 = H_SYNC; 

    //slv_reg38:0x098
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            H_BACK_PORCH <= 32'd148 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h098) 
            H_BACK_PORCH <= S_AXI_WDATA[31:0];
    end
    assign slv_reg38 = H_BACK_PORCH;  

    //slv_reg39:0x09C
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            H_ACTIVE <= 32'd1920 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h09C) 
            H_ACTIVE <= S_AXI_WDATA[31:0];
    end
    assign slv_reg39 = H_ACTIVE;  

    //slv_reg40:0x0A0
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            H_FRONT_PORCH <= 32'd88 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h0A0) 
            H_FRONT_PORCH <= S_AXI_WDATA[31:0];
    end
    assign slv_reg40 = H_FRONT_PORCH;  

    //slv_reg41:0x0A4
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            V_SYNC <= 32'd5 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h0A4) 
            V_SYNC <= S_AXI_WDATA[31:0];
    end
    assign slv_reg41 = V_SYNC;  

    //slv_reg42:0x0A8
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            V_BACK_PORCH <= 32'd4 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h0A8) 
            V_BACK_PORCH <= S_AXI_WDATA[31:0];
    end
    assign slv_reg42 = V_BACK_PORCH;  

    //slv_reg43:0x0AC
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            V_ACTIVE <= 32'd1080 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h0AC) 
            V_ACTIVE <= S_AXI_WDATA[31:0];
    end
    assign slv_reg43 = V_ACTIVE;  

    //slv_reg44:0x0B0
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            V_FRONT_PORCH <= 32'd36 ;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h0B0) 
            V_FRONT_PORCH <= S_AXI_WDATA[31:0];
    end
    assign slv_reg44 = V_FRONT_PORCH;          

    //slv_reg45:0x0B4
    always @( posedge S_AXI_ACLK ) 
    begin
        if ( S_AXI_ARESETN == 1'b0 )
            vtc_enable <= 1'd0;
        else if (slv_reg_wren && S_AXI_AWADDR==9'h0B4 && S_AXI_WSTRB[0]==1'b1)
            vtc_enable <= S_AXI_WDATA[0];
    end
    assign slv_reg45 = {31'd0,vtc_enable};  

    always @(posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        dvp_href_in_dly <= 1'b0;
      else
        dvp_href_in_dly <= dvp_href_in;
    end

    always @(posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        dvp_db_in_dly <= 24'b0;
      else
        dvp_db_in_dly <= dvp_db_in;
    end

    always @(posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        img_en_t1 <= 1'h0;
      else
        img_en_t1 <= img_en;
    end

    always @(posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        img_en_t2 <= 1'h0;
      else
        img_en_t2 <= img_en_t1;
    end

    always @(posedge dvp_pclk)
    begin
      if(dvp_prst_n == 1'b0)
        img_en_sync <= 1'h0;
      else
        img_en_sync <= img_en_t2;
    end

    level_cross level_cross_u4(
      .a2         (frame_en_switch_sync    ),
      .clk2       (dvp_pclk                ),
      .rst2       (!dvp_prst_n          ),

      .a1         (frame_en_switch         ),
      .clk1       (S_AXI_ACLK             ),
      .rst1       (~S_AXI_ARESETN         )
    );

    level_cross level_cross_u5(
      .a2         (continuous_mode_sync    ),
      .clk2       (dvp_pclk                ),
      .rst2       (!dvp_prst_n          ),

      .a1         (continuous_mode         ),
      .clk1       (S_AXI_ACLK             ),
      .rst1       (~S_AXI_ARESETN         )
    );
    always @(posedge dvp_pclk)
    begin
        if(dvp_prst_n == 1'b0)
            continuous_en <= 1'b0;
        else if(continuous_mode_sync == 1'd0)
            continuous_en <= 1'b0;
        else if((dvp_vsync_start) && continuous_mode_sync)
            continuous_en <= 1'b1;
    end

    assign dvp_vsync_out = dvp_vsync_in_dly & (frame_en | frame_en_switch_sync | continuous_en);
    assign dvp_href_out  = dvp_href_in_dly  & (frame_en | frame_en_switch_sync | continuous_en);
    assign dvp_db_out    = dvp_db_in_dly    & {24{frame_en | frame_en_switch_sync | continuous_en}};

    always @(posedge dvp_pclk)
    begin
        if(dvp_prst_n == 1'b0) begin
            vsync_out   <= 0;
            href_out    <= 0;
            db_out      <= 0;
        end
        else begin
            vsync_out   <= dvp_vsync_out ;
            href_out    <= dvp_href_out ;
            db_out      <= dvp_db_out ;
        end
    end

endmodule
