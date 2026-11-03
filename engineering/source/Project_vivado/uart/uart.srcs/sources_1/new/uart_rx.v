`timescale 1ns / 1ps


module uart_rx
#(
    parameter integer CLK_FREQ = 50000000,
    parameter integer BAUD_RATE = 9600
)
(
    input wire clk,

    input wire rst_n,


    input wire rx,


    output reg [7:0] rx_data,

    output reg rx_valid
);



localparam integer BAUD_CNT_MAX =
CLK_FREQ / BAUD_RATE;


localparam integer HALF_BIT_CNT =
BAUD_CNT_MAX / 2;



localparam IDLE  = 3'd0;
localparam START = 3'd1;
localparam DATA  = 3'd2;
localparam STOP  = 3'd3;



reg [2:0] state;



//Í¬²½Æ÷

reg rx_d0;

reg rx_d1;

reg rx_d2;



always @(posedge clk or negedge rst_n)

begin

    if(!rst_n)

    begin

        rx_d0 <= 1'b1;

        rx_d1 <= 1'b1;

        rx_d2 <= 1'b1;

    end


    else

    begin

        rx_d0 <= rx;

        rx_d1 <= rx_d0;

        rx_d2 <= rx_d1;

    end

end



wire rx_fall;


assign rx_fall =
rx_d2 & (~rx_d1);



reg [12:0] baud_cnt;


reg [2:0] bit_cnt;


reg [7:0] rx_shift;




always @(posedge clk or negedge rst_n)

begin

    if(!rst_n)

    begin

        state <= IDLE;

        baud_cnt <= 0;

        bit_cnt <= 0;

        rx_shift <= 0;

        rx_data <= 0;

        rx_valid <= 0;

    end


    else

    begin

        rx_valid <= 0;



        case(state)


        IDLE:

        begin

            baud_cnt <= 0;

            bit_cnt <= 0;


            if(rx_fall)

            begin

                state <= START;

            end

        end



        START:

        begin

            if(baud_cnt == HALF_BIT_CNT-1)

            begin

                baud_cnt <= 0;


                if(rx_d1 == 0)

                begin

                    state <= DATA;

                    bit_cnt <= 0;

                end

                else

                begin

                    state <= IDLE;

                end

            end

            else

                baud_cnt <= baud_cnt+1;

        end




        DATA:

        begin

            if(baud_cnt == BAUD_CNT_MAX-1)

            begin

                baud_cnt <= 0;


                rx_shift[bit_cnt] <= rx_d1;


                if(bit_cnt == 7)

                begin

                    bit_cnt <= 0;

                    state <= STOP;

                end

                else

                    bit_cnt <= bit_cnt+1;

            end


            else

                baud_cnt <= baud_cnt+1;

        end




        STOP:

        begin

            if(baud_cnt == BAUD_CNT_MAX-1)

            begin

                baud_cnt <= 0;


                if(rx_d1)

                begin

                    rx_data <= rx_shift;

                    rx_valid <= 1;

                end


                state <= IDLE;

            end

            else

                baud_cnt <= baud_cnt+1;

        end



        default:

            state <= IDLE;



        endcase

    end

end


endmodule