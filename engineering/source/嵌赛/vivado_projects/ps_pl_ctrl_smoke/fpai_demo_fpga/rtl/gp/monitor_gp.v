//==============================================================================
// Orgnization   : Shanghai Fudan Microelectronics Co., Ltd. Confidential
// File Name     : monitor_gp
// Author        : wangyinglin
// Project       : NB2338
// Create Date   : 2023.9.18
// Description   :
//------------------------------------------------------------------------------
// Modification History :
// Rev     Date         Who          Description
//==============================================================================

module monitor_gp(
     input                     gp_arvalid       ,
     input                     gp_arready       ,
     input                     gp_rvalid        ,
     input                     gp_rready        ,

     input                     gp_awvalid       ,
     input                     gp_awready       ,  
     input                     gp_wvalid        ,
     input                     gp_wready        ,
     input                     gp_bvalid        ,
     input                     gp_bready        ,

     output  reg [31:0]        gp_ar_cnt        ,
     output  reg [31:0]        gp_r_cnt         ,
     output  reg [31:0]        gp_aw_cnt        ,
     output  reg [31:0]        gp_w_cnt         ,
     output  reg [31:0]        gp_b_cnt         ,

     input                     clk              ,
     input                     rst_n     
);

    always@(posedge clk)begin
        if(~rst_n)
            gp_ar_cnt <= 0;
        else if(gp_arvalid&gp_arready)
            gp_ar_cnt <= gp_ar_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_r_cnt <= 0;
        else if(gp_rvalid&gp_rready)
            gp_r_cnt <= gp_r_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_aw_cnt <= 0;
        else if(gp_awvalid&gp_awready)
            gp_aw_cnt <= gp_aw_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_w_cnt <= 0;
        else if(gp_wvalid&gp_wready)
            gp_w_cnt <= gp_w_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_b_cnt <= 0;
        else if(gp_bvalid&gp_bready)
            gp_b_cnt <= gp_b_cnt + 1'b1;
    end    
endmodule
/*
module monitor_gp(
     input                     GP_ARVALID       ,
     input                     GP_AWVALID       ,
     input                     GP_BREADY        ,
     input                     GP_RREADY        ,
     input                     GP_WLAST         ,
     input                     GP_WVALID        ,
     input       [11 : 0]      GP_ARID          ,
     input       [11 : 0]      GP_AWID          ,
     input       [11 : 0]      GP_WID           ,
     input       [1 : 0]       GP_ARBURST       ,
     input       [1 : 0]       GP_ARLOCK        ,
     input       [2 : 0]       GP_ARSIZE        ,
     input       [1 : 0]       GP_AWBURST       ,
     input       [1 : 0]       GP_AWLOCK        ,
     input       [2 : 0]       GP_AWSIZE        ,
     input       [2 : 0]       GP_ARPROT        ,
     input       [2 : 0]       GP_AWPROT        ,
     input       [31 : 0]      GP_ARADDR        ,
     input       [31 : 0]      GP_AWADDR        ,
     input       [31 : 0]      GP_WDATA         ,
     input       [3 : 0]       GP_ARCACHE       ,
     input       [3 : 0]       GP_ARLEN         ,
     input       [3 : 0]       GP_ARQOS         ,
     input       [3 : 0]       GP_AWCACHE       ,
     input       [3 : 0]       GP_AWLEN         ,
     input       [3 : 0]       GP_AWQOS         ,
     input       [3 : 0]       GP_WSTRB         ,
     input                     GP_ARREADY       ,
     input                     GP_AWREADY       ,
     input                     GP_BVALID        ,
     input                     GP_RLAST         ,
     input                     GP_RVALID        ,
     input                     GP_WREADY        ,
     input       [11 : 0]      GP_BID           ,
     input       [11 : 0]      GP_RID           ,
     input       [1 : 0]       GP_BRESP         ,
     input       [1 : 0]       GP_RRESP         ,
     input       [31 : 0]      GP_RDATA         ,     

     output  reg [31:0]        gp_ar_cnt        ,
     output  reg [31:0]        gp_r_cnt         ,
     output  reg [31:0]        gp_aw_cnt        ,
     output  reg [31:0]        gp_w_cnt         ,
     output  reg [31:0]        gp_b_cnt         ,

     input                     clk              ,
     input                     rst_n     
);

    always@(posedge clk)begin
        if(~rst_n)
            gp_ar_cnt <= 0;
        else if(GP_ARVALID&GP_ARREADY)
            gp_ar_cnt <= gp_ar_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_r_cnt <= 0;
        else if(GP_RVALID&GP_RREADY)
            gp_r_cnt <= gp_r_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_aw_cnt <= 0;
        else if(GP_AWVALID&GP_AWREADY)
            gp_aw_cnt <= gp_aw_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_w_cnt <= 0;
        else if(GP_WVALID&GP_WREADY)
            gp_w_cnt <= gp_w_cnt + 1'b1;
    end

    always@(posedge clk)begin
        if(~rst_n)
            gp_b_cnt <= 0;
        else if(GP_BVALID&GP_BREADY)
            gp_b_cnt <= gp_b_cnt + 1'b1;
    end    
endmodule
*/