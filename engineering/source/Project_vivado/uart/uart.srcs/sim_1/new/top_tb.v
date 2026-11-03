`timescale 1ns / 1ps


module top_tb;


//====================
// 时钟和复位
//====================

reg CLK_50M;

reg rst_n;



//====================
// 模拟外部设备输入
//====================

reg [7:0] DATA_IN;

reg DATA_VALID;



//====================
// UART
//====================

reg RX;

wire TX;



//====================
// DUT
//====================

top
#(
    // 仿真参数降低
    .CLK_FREQ(10000000),
    .BAUD_RATE(1000000)
)
u_top
(
    .CLK_50M(CLK_50M),

    .rst_n(rst_n),


    .DATA_IN(DATA_IN),

    .DATA_VALID(DATA_VALID),


    .RX(RX),

    .TX(TX)

);



//====================
// 10MHz时钟
// 周期100ns
//====================

initial
begin

    CLK_50M = 1'b0;

    forever #50 CLK_50M = ~CLK_50M;

end



//====================
// 模拟外部设备产生数据
//====================

task send_data;

input [7:0] data;


begin


    DATA_IN = data;


    // 数据有效一个周期

    DATA_VALID = 1'b1;

    #100;


    DATA_VALID = 1'b0;


end


endtask



//====================
// 仿真流程
//====================

initial
begin


    // 初始状态

    DATA_IN = 8'h00;

    DATA_VALID = 1'b0;


    // RX空闲

    RX = 1'b1;



    //复位

    rst_n = 1'b0;

    #500;


    rst_n = 1'b1;



    #1000;



    //发送第一个外部数据

    send_data(8'h55);



    #20000;



    //发送第二个数据

    send_data(8'hAA);



    #20000;



    //发送第三个数据

    send_data(8'h33);



    #20000;



    $stop;


end


endmodule