
//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : adder.v
// Author        :
// Project       : 
// Create Date   : 2021.04.05
// Description   :
// - 32 bit adder
//------------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
// 
//==============================================================================

module adder(

    input        [ 31 : 0]  a             ,
    input                   a_valid       ,
    output                  a_ready       ,

    output       [ 63 : 0]  sum           ,
    output                  sum_valid     ,
    input                   sum_ready     ,
    
    input      [ 15: 0]     arsize        ,
    output reg              comp_done     ,

    input                   clk           ,
    input                   rst_n
);

   reg   [ 8 : 0]  cnt           ;
   
   wire  [63 : 0]  sum_rs        ;
   wire            sum_valid_rs  ;
   wire            sum_ready_rs  ;

   assign sum_rs = 1 + a;

   assign a_ready      = sum_ready_rs;
   assign sum_valid_rs = a_valid && a_ready;

   always @(posedge clk or negedge rst_n)begin
     if(rst_n==1'b0)
       cnt <= #0.1 'd0;
     else if(comp_done)
       cnt <= #0.1 'd0;
     else if(sum_valid_rs && sum_ready_rs)
       cnt <= #0.1 cnt + 1'b1;
   end
  
   always @(posedge clk or negedge rst_n)begin
     if(rst_n==1'b0)
       comp_done <= #0.1 1'b0;
     else if(comp_done)
       comp_done <= #0.1 1'b0;
     else if(cnt==arsize)
       comp_done <= #0.1 1'b1;
   end

    avr_rs #(.DW(64)) U_avr_rs(
        .m_data      ( sum_rs         ),//I
        .m_valid     ( sum_valid_rs   ),//I
        .m_ready     ( sum_ready_rs   ),//O

        .s_data      ( sum            ),//O
        .s_valid     ( sum_valid      ),//O
        .s_ready     ( sum_ready      ),//I

        .clk         ( clk            ),
        .rst_n       ( rst_n          )
    );



endmodule


