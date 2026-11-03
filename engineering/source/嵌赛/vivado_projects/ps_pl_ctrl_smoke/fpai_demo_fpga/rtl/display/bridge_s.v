`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 11/29/2018 10:54:46 AM
// Design Name: 
// Module Name: bridge_s
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
module bridge_s(
    input  clka     ,
    input  clkb     ,
    input  rsta     ,
    input  rstb     ,
    input  a_req    ,
    output a_req_clr,
    output b_en  
     );
reg a_req_b   ;
reg a_req_b_d1;
reg a_req_b_d2;

reg b_ack     ;

reg a_ack     ;

reg b_ack_a   ;
reg b_ack_a_d1;

always @ (posedge clkb)
  begin
    if (rstb)
      begin
        a_req_b    <= 0;
        a_req_b_d1 <= 0;
        a_req_b_d2 <= 0;
      end
    else
      begin
        a_req_b    <= a_req     ;
        a_req_b_d1 <= a_req_b   ;
        a_req_b_d2 <= a_req_b_d1;
      end
  end

always @ (posedge clkb)
  begin
    if (rstb)
      begin
        b_ack <= 0;
      end
    else if (b_en)
      begin
        b_ack <= 1     ;
      end
    else if (~a_req_b_d1)
      begin
        b_ack <=0 ;
      end 
  end

assign b_en = ~a_req_b_d2 & a_req_b_d1;

always @ (posedge clka)    
  begin
    if (rsta)
      begin
        b_ack_a    <= 0;
        b_ack_a_d1 <= 0;
      end
    else
      begin
        b_ack_a    <= b_ack     ;
        b_ack_a_d1 <= b_ack_a   ;
      end
  end
  
assign a_req_clr = b_ack_a_d1;

endmodule
