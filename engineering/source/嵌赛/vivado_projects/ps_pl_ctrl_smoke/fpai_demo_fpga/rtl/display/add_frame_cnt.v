//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : add_frame_cnt.v
// Author        : WangYinglin 
// Project       : 
// Create Date   : 2023.12.15
// Description   : 
// 
//-----------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
//==============================================================================

module add_frame_cnt(
    input                          cam_rst             ,
    input                          cam_clk             ,

    input                          frame_debug_en      ,
   
    input                          cmos_vs_in          ,
    input                          cmos_hs_in          ,
    input         [23 : 0]         cmos_data_in        ,

    output                         cmos_vs_out         ,
    output                         cmos_hs_out         ,
    output  reg   [23 : 0]         cmos_data_out          
);

    reg         cmos_vs_in_d1;
    reg         cmos_hs_in_d1;
    reg         cmos_vs_in_d2;
    reg         cmos_hs_in_d2; 
    reg [23 : 0]cmos_data_in_d1;  
    reg [4:0]   frame_cnt    ;
    reg [10:0]  hs_cnt       ;
    wire        cmos_vs_pos  ;
    wire        cmos_hs_pos  ;

    always @(posedge cam_clk) begin
        if(cam_rst == 1'b1) begin
            cmos_vs_in_d1 <= 1'b0;
            cmos_vs_in_d2 <= 1'b0;
        end
        else begin
            cmos_vs_in_d1 <= cmos_vs_in;
            cmos_vs_in_d2 <= cmos_vs_in_d1;
        end
    end
    assign cmos_vs_pos = cmos_vs_in & (~cmos_vs_in_d1);

    always @(posedge cam_clk) begin
        if(cam_rst == 1'b1)begin
            cmos_hs_in_d1 <= 1'b0;
            cmos_hs_in_d2 <= 1'b0;
        end
        else begin
            cmos_hs_in_d1 <= cmos_hs_in;
            cmos_hs_in_d2 <= cmos_hs_in_d1;
        end
    end    
    assign cmos_hs_pos = cmos_hs_in & (~cmos_hs_in_d1);

    always @(posedge cam_clk) begin
        if(cam_rst == 1'b1)
            frame_cnt <= 5'b0;
        else if(cmos_vs_pos)
            frame_cnt <= frame_cnt + 1'b1;
    end   

    always @(posedge cam_clk) begin
        if(cam_rst == 1'b1)
            hs_cnt <= 1'b0;
        else if(cmos_vs_pos)
            hs_cnt <= 1'b0;
        else if(cmos_hs_pos)
            hs_cnt <= hs_cnt + 1'b1;
    end       

    always @(posedge cam_clk) begin
        if(cam_rst == 1'b1)
            cmos_data_in_d1 <= 24'b0;
        else
            cmos_data_in_d1 <= cmos_data_in;
    end 

    always @(posedge cam_clk) begin
        if(cam_rst == 1'b1)
            cmos_data_out <= 24'b0;
        else if((hs_cnt>='d539 & hs_cnt<='d541) & frame_debug_en)
            cmos_data_out <= {3{frame_cnt,3'b0}};
        else
            cmos_data_out <= cmos_data_in_d1;
    end   

    assign cmos_vs_out = cmos_vs_in_d2;
    assign cmos_hs_out = cmos_hs_in_d2;
endmodule