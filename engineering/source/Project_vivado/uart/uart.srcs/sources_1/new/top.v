`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2026/09/19 21:39:55
// Design Name: 
// Module Name: top
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


module top
#(
    parameter integer CLK_FREQ = 50000000,
    parameter integer BAUD_RATE = 9600
)
(
    input wire CLK_50M,
    input wire rst_n,
    
    input wire [7:0] DATA_IN,
    input wire DATA_VALID,
    
    input wire RX,
    output wire TX

);

wire [7:0] tx_data;
wire tx_start;
wire tx_busy;

wire [7:0] rx_data;
wire rx_valid;

uart_rx
#(
    .CLK_FREQ(CLK_FREQ),
    .BAUD_RATE(BAUD_RATE)
   )
u_uart_rx  
(
    .clk(CLK_50M),
    .rst_n(rst_n),
    .rx(RX),
    .rx_data(rx_data),
    .rx_valid(rx_valid)
   );
   
uart_ctrl u_uart_ctrl
(
    .clk(CLK_50M),
    .rst_n(rst_n),
    .data_in(DATA_IN),
    .data_valid(DATA_VALID),
    .tx_busy(tx_busy),
    .tx_start(tx_start),
    .tx_data(tx_data)
);

uart_tx
#(
    .CLK_FREQ(CLK_FREQ),
    .BAUD_RATE(BAUD_RATE)
)
u_uart_tx
(
    .clk(CLK_50M),
    .rst_n(rst_n),
    .tx_start(tx_start),
    .tx_data(tx_data),
    .tx(TX),
    .busy(tx_busy)
);


endmodule
