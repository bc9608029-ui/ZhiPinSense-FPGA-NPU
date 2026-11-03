`timescale 1ns/1ps
`default_nettype none

// Transfers a GP-domain request toggle into one destination domain.  Every
// request first resets the complete local datapath, then releases reset and
// emits one start pulse.  The toggle synchronizer itself is held only by the
// platform reset so that resetting the job datapath cannot lose a request.
module job_domain_controller #(
    parameter integer RESET_CYCLES = 4
) (
    input  wire clk,
    input  wire global_rst_n,
    input  wire request_toggle_async,
    output reg  job_rst_n,
    output reg  start_pulse
);
    localparam integer COUNT_WIDTH = (RESET_CYCLES <= 2) ? 1 : $clog2(RESET_CYCLES + 1);
    localparam [1:0] ST_WAIT = 2'd0;
    localparam [1:0] ST_RESET = 2'd1;
    localparam [1:0] ST_RELEASE = 2'd2;

    (* ASYNC_REG = "TRUE" *) reg request_sync1;
    (* ASYNC_REG = "TRUE" *) reg request_sync2;
    (* ASYNC_REG = "TRUE" *) reg request_sync3;
    reg seen_toggle;
    reg [1:0] state;
    reg [COUNT_WIDTH-1:0] reset_count;

    always @(posedge clk or negedge global_rst_n) begin
        if (!global_rst_n) begin
            request_sync1 <= 1'b0;
            request_sync2 <= 1'b0;
            request_sync3 <= 1'b0;
            seen_toggle   <= 1'b0;
            state         <= ST_WAIT;
            reset_count   <= {COUNT_WIDTH{1'b0}};
            job_rst_n     <= 1'b0;
            start_pulse   <= 1'b0;
        end else begin
            request_sync1 <= request_toggle_async;
            request_sync2 <= request_sync1;
            request_sync3 <= request_sync2;
            start_pulse   <= 1'b0;

            case (state)
                ST_WAIT: begin
                    if (request_sync3 != seen_toggle) begin
                        seen_toggle <= request_sync3;
                        job_rst_n   <= 1'b0;
                        reset_count <= RESET_CYCLES[COUNT_WIDTH-1:0];
                        state       <= ST_RESET;
                    end
                end
                ST_RESET: begin
                    job_rst_n <= 1'b0;
                    if (reset_count == 1) begin
                        reset_count <= {COUNT_WIDTH{1'b0}};
                        job_rst_n   <= 1'b1;
                        state       <= ST_RELEASE;
                    end else begin
                        reset_count <= reset_count - 1'b1;
                    end
                end
                ST_RELEASE: begin
                    // One complete destination clock has elapsed since reset
                    // release before start becomes observable by the datapath.
                    job_rst_n   <= 1'b1;
                    start_pulse <= 1'b1;
                    state       <= ST_WAIT;
                end
                default: begin
                    job_rst_n <= 1'b0;
                    state     <= ST_WAIT;
                end
            endcase
        end
    end
endmodule

`default_nettype wire
