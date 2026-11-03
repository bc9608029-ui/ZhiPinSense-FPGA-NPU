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
`timescale 1ns/1ps
module frame_read_write_largebuf
#
(
	parameter MEM_DATA_BITS          = 64,
	parameter READ_DATA_BITS         = 16,
	parameter WRITE_DATA_BITS        = 16,
	parameter ADDR_BITS              = 27,//25,
	parameter BUSRT_BITS             = 10,
	parameter BURST_SIZE             = 16//64
)               
(
	input                            rst,                  
	input                            mem_clk,                    // external memory controller user interface clock
	output                           rd_burst_req,               // to external memory controller,send out a burst read request
	output[BUSRT_BITS - 1:0]         rd_burst_len,               // to external memory controller,data length of the burst read request, not bytes
	output[ADDR_BITS - 1:0]          rd_burst_addr,              // to external memory controller,base address of the burst read request 
	input                            rd_burst_data_valid,        // from external memory controller,read data valid 
	input[MEM_DATA_BITS - 1:0]       rd_burst_data,              // from external memory controller,read request data
	input                            rd_burst_finish,            // from external memory controller,burst read finish
	input                            read_clk,                   // data read module clock
	input                            read_req,                   // data read module read request,keep '1' until read_req_ack = '1'
	output                           read_req_ack,               // data read module read request response
	output                           read_finish,                // data read module read request finish
	input[ADDR_BITS - 1:0]           read_addr_0,                // data read module read request base address 0, used when read_addr_index = 0
	input[ADDR_BITS - 1:0]           read_addr_1,                // data read module read request base address 1, used when read_addr_index = 1
	input[ADDR_BITS - 1:0]           read_addr_2,                // data read module read request base address 1, used when read_addr_index = 2
	input[ADDR_BITS - 1:0]           read_addr_3,                // data read module read request base address 1, used when read_addr_index = 3
	input[1:0]                       read_addr_index,            // select valid base address from read_addr_0 read_addr_1 read_addr_2 read_addr_3
	input[ADDR_BITS - 1:0]           read_len,                   // data read module read request data length
	input                            read_en,                    // data read module read request for one data, read_data valid next clock
	output[READ_DATA_BITS  - 1:0]    read_data,                  // read data

	output                           wr_burst_req,               // to external memory controller,send out a burst write request
	output[BUSRT_BITS - 1:0]         wr_burst_len,               // to external memory controller,data length of the burst write request, not bytes
	output[ADDR_BITS - 1:0]          wr_burst_addr,              // to external memory controller,base address of the burst write request 
	input                            wr_burst_data_req,          // from external memory controller,write data request ,before data 1 clock
	output[MEM_DATA_BITS - 1:0]      wr_burst_data,              // to external memory controller,write data
	input                            wr_burst_finish,            // from external memory controller,burst write finish
	input                            write_clk,                  // data write module clock
	input                            write_req,                  // data write module write request,keep '1' until read_req_ack = '1'
	output                           write_req_ack,              // data write module write request response
	output                           write_finish,               // data write module write request finish
	input[ADDR_BITS - 1:0]           write_addr_0,               // data write module write request base address 0, used when write_addr_index = 0
	input[ADDR_BITS - 1:0]           write_addr_1,               // data write module write request base address 1, used when write_addr_index = 1
	input[ADDR_BITS - 1:0]           write_addr_2,               // data write module write request base address 1, used when write_addr_index = 2
	input[ADDR_BITS - 1:0]           write_addr_3,               // data write module write request base address 1, used when write_addr_index = 3
	input[1:0]                       write_addr_index,           // select valid base address from write_addr_0 write_addr_1 write_addr_2 write_addr_3
	input[ADDR_BITS - 1:0]           write_len,                  // data write module write request data length
	input                            write_en,                   // data write module write request for one data
	input[WRITE_DATA_BITS - 1:0]     write_data,                 // write data
	output reg                       wr_wfifo_err,
	output reg                       rd_rfifo_err,
	output                           wfifo_empty,
	output                           rfifo_full
);
wire[15:0]                           rd_buf_wrusedw;                    // write used words
wire[15:0]                           wr_buf_rdusedw_0;                    // read used words
wire[15:0]                           wr_buf_rdusedw;                    // read used words
wire                                 read_fifo_aclr;             // fifo Asynchronous clear
wire                                 write_fifo_aclr;            // fifo Asynchronous clear

wire                                 wr_buf_full;
wire                                 wr_buf_empty;
wire                                 wr_buf_rd;
wire                                 wr_buf_wr;

wire                                 rd_buf_empty;
wire                                 rd_buf_full;
wire                                 rd_buf_wr;
wire                                 rd_buf_rd;

reg write_req_dly0,write_req_dly1,write_req_syn0;
wire write_req_pos;

assign wr_buf_wr = write_en;
assign wr_buf_rd = wr_burst_data_req;

assign rd_buf_wr = rd_burst_data_valid;
assign rd_buf_rd = read_en;

assign wfifo_empty = wr_buf_empty;
assign rfifo_full  = rd_buf_full;


always @(posedge write_clk) begin
	if(rst)
	    {write_req_syn0,write_req_dly1,write_req_dly0} <= 0;
	else
	    {write_req_syn0,write_req_dly1,write_req_dly0} <= {write_req_dly0,write_req};
end

assign write_req_pos = (~write_req_dly1) && write_req_dly0;

wire wr_wfifo_err_wire;

assign wr_wfifo_err_wire = write_en && wr_buf_full;

always @(posedge write_clk or posedge rst) begin
	if(rst)
	    wr_wfifo_err <= 1'b0;
	else if (write_req_pos)	
	    wr_wfifo_err <= 1'b0;		
	else if (write_en && wr_buf_full)
		wr_wfifo_err <= 1'b1;
end

wire wbuf_wr_en;
assign wbuf_wr_en = write_en && (~wr_wfifo_err);

//instantiate an asynchronous FIFO 
wire [63:0] wrbuf_dout     ;
wire        rd_en_0        ;
wire        full_1         ;
wire        almost_full_1  ;
wire        empty_1        ;
wire        almost_empty_1 ;
afifo_16i_64o_largebuf write_buf (  //
	.rst                         (write_fifo_aclr         ),
	.wr_clk                      (write_clk               ),
	.rd_clk                      (mem_clk                 ),
	.din                         (write_data              ),//{yu/yv}
	.wr_en                       (wbuf_wr_en              ),
	.rd_en                       (rd_en_0                 ),
	.dout                        (wrbuf_dout              ),
	.full                        (wr_buf_full             ),
	.empty                       (wr_buf_empty            ),
	.rd_data_count               (wr_buf_rdusedw_0        ),
	.wr_data_count               (                        )
);

fifo_1 fifo_1_u0(                      
    .clk                         (mem_clk                 ),    
    .srst                        (write_fifo_aclr         ),    
    .din                         (wrbuf_dout              ),    
    .wr_en                       (rd_en_0                 ),    
    .rd_en                       (wr_burst_data_req       ),    
    .dout                        (wr_burst_data           ),    
    .full                        (full_1                  ),  
    .almost_full                 (almost_full_1           ),  
    .empty                       (empty_1                 ),
    .almost_empty                (almost_empty_1          ),
	.data_count                  (wr_buf_rdusedw          )      
);

assign rd_en_0 = (~wr_buf_empty) & (~almost_full_1);

frame_fifo_write
#
(
	.MEM_DATA_BITS              (MEM_DATA_BITS            ),
	.ADDR_BITS                  (ADDR_BITS                ),
	.BUSRT_BITS                 (BUSRT_BITS               ),
	.BURST_SIZE                 (BURST_SIZE               )
) 
frame_fifo_write_m0              
(  
	.rst                        (rst                      ),
	.mem_clk                    (mem_clk                  ),
	.wr_burst_req               (wr_burst_req             ),
	.wr_burst_len               (wr_burst_len             ),
	.wr_burst_addr              (wr_burst_addr            ),
	.wr_burst_data_req          (wr_burst_data_req        ),
	.wr_burst_finish            (wr_burst_finish          ),
	.write_req                  (write_req                ),
	.write_req_ack              (write_req_ack            ),
	.write_finish               (write_finish             ),
	.write_addr_0               (write_addr_0             ),
	.write_addr_1               (write_addr_1             ),
	.write_addr_2               (write_addr_2             ),
	.write_addr_3               (write_addr_3             ),
	.write_addr_index           (write_addr_index         ),    
	.write_len                  (write_len                ),
	.fifo_aclr                  (write_fifo_aclr          ),
	.wr_wfifo_err               (wr_wfifo_err             ),
	.rdusedw                    (wr_buf_rdusedw           ) 
	
);

wire rd_rfifo_err_wire;

assign rd_rfifo_err_wire = read_en && rd_buf_empty;
always @(posedge read_clk or posedge rst) begin
	if(rst)
	    rd_rfifo_err <= 1'b0;
	else if (read_en && rd_buf_empty)
		rd_rfifo_err <= 1'b1;
end

//instantiate an asynchronous FIFO
afifo_64i_16o_128 read_buf (  //depth 8192
	.rst                         (read_fifo_aclr          ),                     
	.wr_clk                      (mem_clk                 ),               
	.rd_clk                      (read_clk                ),               
	.din                         (rd_burst_data           ),                     
	.wr_en                       (rd_burst_data_valid     ),                 
	.rd_en                       (read_en                 ),                 
	.dout                        (read_data               ),                   
	.full                        (rd_buf_full             ),                   
	.empty                       (rd_buf_empty            ),                 
	.rd_data_count               (                        ), 
	.wr_data_count               (rd_buf_wrusedw          )  
);

frame_fifo_read
#
(
	.MEM_DATA_BITS              (MEM_DATA_BITS            ),
	.ADDR_BITS                  (ADDR_BITS                ),
	.BUSRT_BITS                 (BUSRT_BITS               ),
	.FIFO_DEPTH                 (8192*2*2                 ),
	//.FIFO_DEPTH                 (2048                     ),
	.BURST_SIZE                 (BURST_SIZE               )
)
frame_fifo_read_m0
(
	.rst                        (rst                      ),
	.mem_clk                    (mem_clk                  ),
	.rd_burst_req               (rd_burst_req             ),   
	.rd_burst_len               (rd_burst_len             ),  
	.rd_burst_addr              (rd_burst_addr            ),
	.rd_burst_data_valid        (rd_burst_data_valid      ),    
	.rd_burst_finish            (rd_burst_finish          ),
	.read_req                   (read_req                 ),
	.read_req_ack               (read_req_ack             ),
	.read_finish                (read_finish              ),
	.read_addr_0                (read_addr_0              ),
	.read_addr_1                (read_addr_1              ),
	.read_addr_2                (read_addr_2              ),
	.read_addr_3                (read_addr_3              ),
	.read_addr_index            (read_addr_index          ),    
	.read_len                   (read_len                 ),
	.fifo_aclr                  (read_fifo_aclr           ),
	.wrusedw                    (rd_buf_wrusedw           )
);

endmodule
