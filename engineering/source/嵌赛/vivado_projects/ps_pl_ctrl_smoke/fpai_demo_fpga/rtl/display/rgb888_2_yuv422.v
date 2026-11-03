//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : rgb888_2_yuv422.sv
// Author        : WangYinglin 
// Project       : 
// Create Date   : 2025.05.21
// Description   : 
// 
//-----------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
//==============================================================================
module rgb888_2_yuv422(
    input      [23 : 0]    i_rgb           ,
    input                  i_data_valid    ,
    input      [10 : 0]    i_resize_pix_len,

    output     [15 : 0]    o_yuv           ,
    output                 o_data_valid    ,
     
    input                  clk             ,
    input                  rst_n                
);
wire [ 7 : 0] r;
wire [ 7 : 0] g;
wire [ 7 : 0] b;
reg  [15 : 0] y_temp1,y_temp2,y_temp3;                                                                 
reg  [15 : 0] u_temp1,u_temp2,u_temp3;
reg  [15 : 0] v_temp1,v_temp2,v_temp3;
reg  [17 : 0] y_r0;
reg  [17 : 0] u_r0;
reg  [17 : 0] v_r0;
reg  [ 7 : 0] y;
reg  [ 7 : 0] u;
reg  [ 7 : 0] v;
reg  [10 : 0] x_cnt;
reg           i_data_valid_d0;
reg           i_data_valid_d1;
reg           i_data_valid_d2;

//assign r = {i_rgb[15:11],i_rgb[13:11]};
//assign g = {i_rgb[10: 5],i_rgb[ 6: 5]};
//assign b = {i_rgb[ 4: 0],i_rgb[ 2: 0]};
assign r = i_rgb[23:16];
assign g = i_rgb[15: 8];
assign b = i_rgb[ 7: 0];

always@(posedge clk) begin
    if(rst_n==1'b0) begin
        y_temp1 <= 'd0;
        y_temp2 <= 'd0;
        y_temp3 <= 'd0;

        u_temp1 <= 'd0;
        u_temp2 <= 'd0;
        u_temp3 <= 'd0;
        
        v_temp1 <= 'd0;
        v_temp2 <= 'd0;
        v_temp3 <= 'd0;        
    end
    else begin
        y_temp1 <= 8'd77*r;
        y_temp2 <= 8'd150*g;
        y_temp3 <= 8'd29*b;

        u_temp1 <= 8'd43*r;
        u_temp2 <= 8'd85*g;
        u_temp3 <= b<<7;
        
        v_temp1 <= r<<7;
        v_temp2 <= 8'd107*g;
        v_temp3 <= 8'd21*b;
    end
end

always@(posedge clk) begin
    if(rst_n==1'b0) begin
        y_r0 <= 'd0;
        u_r0 <= 'd0;
        v_r0 <= 'd0;
    end
    else begin
        y_r0 <= ( y_temp1 + y_temp2 + y_temp3)>>8;
        u_r0 <= (-u_temp1 - u_temp2 + u_temp3 + 18'h8000)>>8;
        v_r0 <= ( v_temp1 - v_temp2 - v_temp3 + 18'h8000)>>8;
    end
end

always@(posedge clk) begin
    if(rst_n==1'b0) begin
        y <= 0;
        u <= 0;
        v <= 0;
    end
    else begin
        y <= y_r0[9]==1'b1 ? 8'd0 : ((y_r0[8] == 1'b0) ? y_r0[7:0] : 8'd255);                   
        u <= u_r0[9]==1'b1 ? 8'd0 : ((u_r0[8] == 1'b0) ? u_r0[7:0] : 8'd255);
        v <= v_r0[9]==1'b1 ? 8'd0 : ((v_r0[8] == 1'b0) ? v_r0[7:0] : 8'd255);
    end
end

always@(posedge clk) begin
    if(rst_n==1'b0) begin
        {i_data_valid_d2,i_data_valid_d1,i_data_valid_d0} <= 3'b0;
    end
    else begin
        {i_data_valid_d2,i_data_valid_d1,i_data_valid_d0} <= {i_data_valid_d1,i_data_valid_d0,i_data_valid};
    end
end

always@(posedge clk)begin                      
    if(rst_n==1'b0)
        x_cnt <= 'b0;
    else if((x_cnt == (i_resize_pix_len-1)) && (i_data_valid_d2))
        x_cnt <= 'b0;        
    else if(i_data_valid_d2)
        x_cnt <= x_cnt + 'd1;
end

assign o_yuv        = (x_cnt[0] == 1'b0) ? {y,u} :{y,v};
assign o_data_valid = i_data_valid_d2;
endmodule