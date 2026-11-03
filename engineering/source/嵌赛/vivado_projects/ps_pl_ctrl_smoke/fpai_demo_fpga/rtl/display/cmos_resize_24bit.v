//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : post_ctrl.v
// Author        : wangchenyu 
// Project       : 
// Create Date   : 
// Description   : 
// - cmos_resize
//------------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
//==============================================================================

module cmos_resize_24bit(
		input                  reset_cmos1_pclk ,
		input                  cmos1_pclk	    ,

		// src data
		input                  dvp_href         ,
		input			       dvp_vsync        ,
		input	   [23 : 0]	   dvp_data         ,

		// config para
		input      [15 : 0]	   x0_pos           ,
		input      [15 : 0]	   y0_pos           ,
		input      [15 : 0]	   x1_pos           ,
		input      [15 : 0]	   y1_pos           ,
		input      [15 : 0]	   x_leng           ,
		input      [15 : 0]	   y_leng           ,	
		input      [ 3 : 0]	   hstride          ,
		input      [ 3 : 0]	   vstride          ,
	
		output reg             resize_href      ,
		output reg		       resize_vsync     ,
		output reg [23 : 0]    resize_data
);

		reg  [15 : 0]  cnt_pixel_inh    ;
		reg  [15 : 0]  cnt_hnum_inv     ;
		reg  [ 3 : 0]  cnt_pixel_loop   ;
		reg  [ 3 : 0]  cnt_hnum_loop    ;
		wire           hang_valid       ;
		wire           pixel_valid      ;
		reg  [23 : 0]  dvp_data_d1      ;
		reg  [23 : 0]  dvp_data_d2      ;
		reg            resize_vsync_d1  ;
		reg            resize_vsync_d2  ;
		reg            dvp_href_d1      ;
 	  	reg            pixel_inh_en     ;
 	  	reg            hang_inv_en      ;    
 	  	wire           pic_cut_flag     ;
 	  	wire           pic_res_flag     ;
 	  	wire           pic_cut_href     ;
		wire 		   resize_href_temp ;
		wire [23 : 0]  resize_data_temp ;
		wire           resize_vsync_temp;

// pixel valid
always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		cnt_pixel_inh <= 16'h0;
	else if(dvp_vsync)
		cnt_pixel_inh <= 16'h0;
	else if( (cnt_pixel_inh == x_leng) & dvp_href )
		cnt_pixel_inh <= 16'h1;
	else if( (cnt_pixel_inh == x_leng) & (!dvp_href) )
		cnt_pixel_inh <= 16'h0;
	else if(dvp_href)
		cnt_pixel_inh <= cnt_pixel_inh + 1'b1;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		pixel_inh_en <= 1'b0;
	else if(dvp_vsync)
        pixel_inh_en <= 1'b0;
	else if(cnt_pixel_inh == x0_pos)
		pixel_inh_en <= 1'b1;
	else if(cnt_pixel_inh == x1_pos+1)
		pixel_inh_en <= 1'b0;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		cnt_pixel_loop <= 4'h0;
	else if(dvp_vsync)
		cnt_pixel_loop <= 4'h0;
	else if(!hang_valid)
		cnt_pixel_loop <= 4'h0;
	else if( (cnt_pixel_loop == hstride) & dvp_href_d1 & pixel_inh_en & pic_res_flag)
		cnt_pixel_loop <= 4'h1;
	else if(cnt_pixel_loop == hstride)
		cnt_pixel_loop <= 4'h0;
	else if(dvp_href_d1 & hang_valid & pixel_inh_en & pic_res_flag)
		cnt_pixel_loop <= cnt_pixel_loop + 1'b1;
end

assign pixel_valid = (cnt_pixel_loop == hstride);

// h valid
always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		cnt_hnum_inv <= 16'h0;
	else if(dvp_vsync)
		cnt_hnum_inv <= 16'h0;
	else if( (cnt_hnum_inv == y_leng) & (cnt_pixel_inh == x_leng) )
		cnt_hnum_inv <= 16'h0;
	else if(cnt_pixel_inh == x_leng)
		cnt_hnum_inv <= cnt_hnum_inv + 1'b1;// note
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		hang_inv_en <= 1'b0;
	else if(dvp_vsync)
        hang_inv_en <= 1'b0;
	else if(cnt_hnum_inv == y0_pos)
		hang_inv_en <= 1'b1;
	else if(cnt_hnum_inv == y1_pos+1)
		hang_inv_en <= 1'b0;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		cnt_hnum_loop <= 4'h1;// initial line number for end count
	else if(dvp_vsync)
		cnt_hnum_loop <= 4'h1;
	else if( (cnt_hnum_loop == vstride) & (cnt_pixel_inh == x_leng) )
		cnt_hnum_loop <= 4'h1;
	else if( (cnt_pixel_inh == x_leng) & hang_inv_en & pic_res_flag )
		cnt_hnum_loop <= cnt_hnum_loop + 1'b1;// note line end count for another line
end

assign hang_valid = (cnt_hnum_loop == vstride) & hang_inv_en;

// pic ctl cmd

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		resize_vsync_d1 <= 1'h0;
	else
		resize_vsync_d1 <= dvp_vsync;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		resize_vsync_d2 <= 1'h0;
	else
		resize_vsync_d2 <= resize_vsync_d1;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		dvp_data_d1 <= 24'h0;
	else if(dvp_href)
		dvp_data_d1 <= dvp_data;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		dvp_data_d2 <= 24'h0;
	else
		dvp_data_d2 <= dvp_data_d1;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		dvp_href_d1 <= 1'h0;
	else
		dvp_href_d1 <= dvp_href;
end

assign pic_cut_flag = |{x0_pos,y0_pos,x1_pos,y1_pos};

assign pic_res_flag = |{vstride,hstride};

assign pic_cut_href = dvp_href_d1 && pixel_inh_en && hang_inv_en;

// resize output
//assign resize_flag = |{hstride,vstride,x0_pos,y0_pos,x1_pos,y1_pos};

assign resize_href_temp = pic_res_flag ? pixel_valid : (pic_cut_flag ? pic_cut_href : dvp_href);

assign resize_data_temp = pic_res_flag ? dvp_data_d2 : (pic_cut_flag ? dvp_data_d1 : dvp_data);

assign resize_vsync_temp = pic_res_flag ? resize_vsync_d2 : (pic_cut_flag ? resize_vsync_d1 : dvp_vsync);

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		resize_href <= 1'h0;
	else if(resize_href_temp)
		resize_href <= 1'b1;
	else
		resize_href <= 1'h0;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		resize_data <= 24'h0;
	else if(resize_href_temp)
		resize_data <= resize_data_temp;
end

always@(posedge cmos1_pclk or posedge reset_cmos1_pclk)
begin
	if(reset_cmos1_pclk == 1'b1)
		resize_vsync <= 1'h0;
	else if(resize_vsync_temp)
		resize_vsync <= 1'b1;
	else
		resize_vsync <= 1'h0;
end
endmodule 