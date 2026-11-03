//                                                                             //
//                                                                             //
//  Author:                                                                    //
//                                                                             //
//  WEB:                                                                       //
//                                                                             //
//*****************************************************************************/
// 
// (c) Copyright 2008 - 2019 xxx. All rights reserved.
// 
// This file contains confidential and proprietary information
// of xxx. and is protected under China and
// international copyright and other intellectual property laws.
// 
//*****************************************************************************/
//-----------------------------------------------------------------------------//
//  Revision History:
//  Revision            Date                By           Change Description
//-----------------------------------------------------------------------------//
//  1.0                 2019/07/09                       new created
//*****************************************************************************/

module cmos_write_req_gen(
	input              rst,
	input              pclk,
	input			         m00_axi_aclk,
	input              cmos_vsync,
	output reg         write_req,
	output [1:0]       write_addr_index_sync,
	output [1:0]       read_addr_index_sync,
	input              write_req_ack
);

reg cmos_vsync_d0;
reg cmos_vsync_d1;
reg [1 : 0] write_addr_index;
reg [1 : 0] read_addr_index;
reg write_index_en;
wire rindex_buf_empty; 
wire windex_buf_empty; 

always@(posedge pclk or posedge rst)
begin
	if(rst == 1'b1)
	begin
		cmos_vsync_d0 <= 1'b0;
		cmos_vsync_d1 <= 1'b0;
	end
	else
	begin
		cmos_vsync_d0 <= cmos_vsync;
		cmos_vsync_d1 <= cmos_vsync_d0;
	end
end
always@(posedge pclk or posedge rst)
begin
	if(rst == 1'b1)
		write_req <= 1'b0;
	else if(cmos_vsync_d0 == 1'b1 && cmos_vsync_d1 == 1'b0)
		write_req <= 1'b1;
	else if(write_req_ack == 1'b1)
		write_req <= 1'b0;
end
always@(posedge pclk or posedge rst)
begin
	if(rst == 1'b1)
		write_addr_index <= 2'b0;
	//else if(cmos_vsync_d0 == 1'b1 && cmos_vsync_d1 == 1'b0)
	//	write_addr_index <= write_addr_index + 2'b1;
end

always@(posedge pclk or posedge rst)
begin
	if(rst == 1'b1)
	    read_addr_index <= 2'b1;
	//	read_addr_index <= 2'b0;
	//else if(cmos_vsync_d0 == 1'b1 && cmos_vsync_d1 == 1'b0)
	//	read_addr_index <= write_addr_index - 2'd2;
end

always@(posedge pclk or posedge rst)
begin
	if(rst == 1'b1)
		write_index_en <= 1'b0;
	else if(cmos_vsync_d0 == 1'b1 && cmos_vsync_d1 == 1'b0)
		write_index_en <= 1'b1;
	else
		write_index_en <= 1'b0;
end

// cross clock domain

windex_buf_2b_16w windex_buf_2b_16w_u0 (
    .rst              (rst            			),          
    .wr_clk           (pclk               		),        
    .rd_clk           (m00_axi_aclk             ),         
    .din              (write_addr_index         ),     
    .wr_en            (write_index_en           ),        
    .rd_en            (~windex_buf_empty        ),   
    .dout             (write_addr_index_sync    ),      
    .full             (							),     
    .empty            (windex_buf_empty         )
);

rindex_buf_2b_16w rindex_buf_2b_16w_u0 (
    .rst              (rst            			),          
    .wr_clk           (pclk                		),        
    .rd_clk           (m00_axi_aclk             ),         
    .din              (read_addr_index          ),     
    .wr_en            (write_index_en           ),        
    .rd_en            (~rindex_buf_empty        ),   
    .dout             (read_addr_index_sync     ),      
    .full             (							),     
    .empty            (rindex_buf_empty         )
);

endmodule 
