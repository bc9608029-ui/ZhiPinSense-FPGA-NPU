//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : redge.v
// Author        : wangchenyu 
// Project       : N
// Create Date   : 2020.12.17
// Description   : 
// - Host top control
//------------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
//==============================================================================

module level_cross (
  output reg   a2,
  input       clk2 ,
  input       rst2 ,             

  input       a1,
  input       clk1 ,
  input       rst1              
);

 reg    a1_clk1_d1  ;
 reg    a1_clk1_d2  ;
 reg    a2_clk2_t1  ;
 reg    a2_clk2_t2  ;

always @(posedge clk1 or posedge rst1)
begin
    if(rst1) begin
        a1_clk1_d1   <= 1'b0;   
    end
    else begin
        a1_clk1_d1   <= a1;   
    end
end

always @(posedge clk1 or posedge rst1)
begin
    if(rst1) begin
        a1_clk1_d2   <= 1'b0;   
    end
    else begin
        a1_clk1_d2   <= a1_clk1_d1;   
    end
end

always @(posedge clk2 or posedge rst2)
begin
    if(rst2) begin
        a2_clk2_t1   <= 1'b0;    
    end
    else begin
        a2_clk2_t1   <= a1_clk1_d2;     
    end
end

always @(posedge clk2 or posedge rst2)
begin
    if(rst2) begin
        a2_clk2_t2   <= 1'b0;    
    end
    else begin
        a2_clk2_t2   <= a2_clk2_t1;     
    end
end

always @(posedge clk2 or posedge rst2)
begin
    if(rst2) begin
        a2   <= 1'b0;    
    end
    else begin
        a2   <= a2_clk2_t2;     
    end
end

endmodule
