`timescale 1ns / 1ps


module uart_tx
#(
    parameter integer CLK_FREQ = 50000000,
    parameter integer BAUD_RATE = 9600
)
(
    input wire clk,
    input wire rst_n,

    input wire tx_start,

    input wire [7:0] tx_data,


    output reg tx,

    output reg busy
);


localparam integer BAUD_CNT_MAX = CLK_FREQ / BAUD_RATE;


reg [12:0] baud_cnt;

reg [3:0] bit_cnt;

reg [9:0] tx_shift;



always @(posedge clk or negedge rst_n)

begin

    if(!rst_n)

    begin

        tx <= 1'b1;

        busy <= 1'b0;

        baud_cnt <= 0;

        bit_cnt <= 0;

        tx_shift <= 10'b1111111111;

    end


    else

    begin


        //¿ªÊ¼·¢ËÍ

        if(tx_start && !busy)

        begin

            busy <= 1'b1;


            /*
            UART:

            stop
            data
            start

            */

            tx_shift <= {
                1'b1,
                tx_data,
                1'b0
            };


            bit_cnt <= 0;

            baud_cnt <= 0;


        end


        else if(busy)

        begin


            if(baud_cnt == BAUD_CNT_MAX-1)

            begin

                baud_cnt <= 0;


                tx <= tx_shift[0];


                tx_shift <= {
                    1'b1,
                    tx_shift[9:1]
                };


                bit_cnt <= bit_cnt + 1'b1;



                if(bit_cnt == 9)

                begin

                    busy <= 1'b0;

                    tx <= 1'b1;

                end


            end


            else

            begin

                baud_cnt <= baud_cnt + 1'b1;

            end

        end


        else

        begin

            tx <= 1'b1;

        end

    end

end


endmodule