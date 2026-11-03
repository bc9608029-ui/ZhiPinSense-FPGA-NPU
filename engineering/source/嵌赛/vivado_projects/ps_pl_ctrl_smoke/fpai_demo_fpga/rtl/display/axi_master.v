`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 11/12/2019 05:10:42 PM
// Design Name: 
// Module Name: axis_master
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////

module axis_master(
    input                dvp_clk              ,
    input                dvp_rst              ,
    input                dvp_vsync            ,
    input      [23 : 0 ] dvp_data             ,
    input                dvp_href             ,
        
	input                m_axis_video_aclk    ,
	input                m_axis_video_aresetn ,
	output               m_axis_video_tuser   ,
	output     [23 : 0 ] m_axis_video_tdata   ,
	output               m_axis_video_tvalid  ,
	input                m_axis_video_tready  ,
	    
    output               overflow                   
    );
	
	wire            img_clk  ;
	wire            img_rst  ;
	wire            img_start;
    wire [23 : 0 ]  img_data ;
	wire            img_vld  ;
	wire            img_rdy  ;
	
    reg             dvp_vsync_dly;
    wire            dvp_start;
    
    wire            fifo_rst;
    wire            rd_en;
    //wire [15 : 0]   img_data16;
    wire            full;
    wire            empty;
    
	assign img_clk             =  m_axis_video_aclk    ;
	assign img_rst             = ~m_axis_video_aresetn ;
	assign m_axis_video_tuser  =  img_start            ;
	assign m_axis_video_tdata  =  img_data             ;
	assign m_axis_video_tvalid =  img_vld              ;
	assign img_rdy             =  m_axis_video_tready  ;
	 
    always @ (posedge dvp_clk) begin
        if(dvp_rst == 1'b1)
            dvp_vsync_dly <= 1'b0;
        else
            dvp_vsync_dly <= dvp_vsync;
    end
        
    assign dvp_start = dvp_vsync & ~dvp_vsync_dly;
  
    pulse_cross_camera pulse_cross_u0(
        .a2    (img_start),
        .clk2  (img_clk  ),
        .rst2  (img_rst  ),
        
        .a1    (dvp_start),
        .clk1  (dvp_clk  ),
        .rst1  (dvp_rst  )
     );
     
     assign fifo_rst = dvp_rst | img_rst;
     
     afifo_24w_4096d afifo_24w_4096d_u0(
         .rst      (fifo_rst         ),
         .wr_clk   (dvp_clk          ),  // input wire wr_clk
         .rd_clk   (img_clk          ),  // input wire rd_clk
         .din      (dvp_data         ),  // input wire [15 : 0] din
         .wr_en    (dvp_href         ),  // input wire wr_en
         .rd_en    (rd_en            ),  // input wire rd_en
         .dout     (img_data         ),  // output wire [15 : 0] dout
         .full     (full             ),  // output wire full
         .empty    (empty            )   // output wire empty
   ); 

	 
   //assign img_data = {img_data16[15:11], img_data16[13:11], img_data16[10:5], img_data16[6:5], img_data16[4:0], img_data16[2:0]};   
   //assign img_data = {img_data16[15:11], 3'h0, img_data16[10:5], 2'h0, img_data16[4:0], 3'h0};
   
   assign overflow = full & dvp_href;
   
   assign rd_en = ~empty & img_rdy;
   
   assign img_vld = ~empty;
    	 
	 (*KEEP = "TRUE"*)reg [30:0]rd_en_cnt;
	 always @ (posedge img_clk) begin
	  if((img_start == 1'b1))
			rd_en_cnt <= 'b0;
	  else if(rd_en)
			rd_en_cnt <= rd_en_cnt +1'b1;
    end
	 
endmodule
