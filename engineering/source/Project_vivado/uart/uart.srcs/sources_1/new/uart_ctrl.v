`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2026/09/19 21:20:07
// Design Name: 
// Module Name: uart_ctrl
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


module uart_ctrl(
    input wire clk,
    input wire rst_n,
    
    input wire [7:0] data_in,
    input wire data_valid,
    
    input wire tx_busy,
    
    output reg tx_start,
    output reg [7:0] tx_data
   );
   
always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_start <= 1'b0;
        tx_data <= 8'd0;
    end
        
    else
    begin
        tx_start <= 1'd0;
        if(data_valid && !tx_busy)
        begin
            tx_data <= data_in;
            tx_start <= 1'b1;
        end
    end
end

endmodule
