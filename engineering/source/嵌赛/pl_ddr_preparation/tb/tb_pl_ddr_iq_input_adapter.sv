`timescale 1ns/1ps
`default_nettype none

module tb_pl_ddr_iq_input_adapter;
    localparam integer TOTAL_SAMPLES = 19 * 1024;
    localparam integer TOTAL_BEATS = TOTAL_SAMPLES / 16;
    localparam integer TOTAL_BYTES = TOTAL_SAMPLES * 4;
    localparam [31:0] BASE_ADDR = 32'h8100_0000; // simulation-only address

    reg ddr_clk = 1'b0;
    reg core_clk = 1'b0;
    always #2.5 ddr_clk = ~ddr_clk;
    always #10 core_clk = ~core_clk;

    reg ddr_rst_n = 1'b0;
    reg core_rst_n = 1'b0;
    reg ddr_start = 1'b0;
    wire ddr_busy, ddr_done, ddr_error;
    wire [31:0] araddr, arinfo;
    wire arvalid;
    reg arready = 1'b0;
    reg [511:0] rdata = 512'd0;
    reg rvalid = 1'b0;
    reg [31:0] rinfo = 32'd1;
    wire rready;
    wire signed [15:0] core_i, core_q;
    wire core_valid;
    reg core_ready = 1'b0;
    wire [31:0] core_accepted_samples;

    integer observed_samples = 0;
    integer core_cycles = 0;
    integer pending_beat = 0;
    integer response_delay = 0;
    reg pending = 1'b0;
    reg [15:0] prng = 16'h1ace;

    function [15:0] sample_i;
        input integer sample_number;
        begin sample_i = (sample_number * 13 + 16'h1234) & 16'hffff; end
    endfunction

    function [15:0] sample_q;
        input integer sample_number;
        begin sample_q = (sample_number * 29 + 16'h8001) & 16'hffff; end
    endfunction

    function [511:0] make_beat;
        input integer beat_number;
        integer lane;
        integer sample_number;
        reg [511:0] value;
        begin
            value = 512'd0;
            for (lane = 0; lane < 16; lane = lane + 1) begin
                sample_number = beat_number * 16 + lane;
                value[(lane*32) +: 32] = {sample_q(sample_number), sample_i(sample_number)};
            end
            make_beat = value;
        end
    endfunction

    pl_ddr_iq_input_adapter #(.FIFO_ADDR_WIDTH(4)) dut (
        .ddr_clk(ddr_clk), .ddr_rst_n(ddr_rst_n), .ddr_start(ddr_start),
        .iq_base_addr(BASE_ADDR), .iq_byte_count(TOTAL_BYTES),
        .ddr_busy(ddr_busy), .ddr_done(ddr_done), .ddr_error(ddr_error),
        .User_Ddr_araddr(araddr), .User_Ddr_arvalid(arvalid),
        .User_Ddr_arinfo(arinfo), .User_Ddr_arready(arready),
        .User_Ddr_rdata(rdata), .User_Ddr_rvalid(rvalid),
        .User_Ddr_rinfo(rinfo), .User_Ddr_rready(rready),
        .core_clk(core_clk), .core_rst_n(core_rst_n), .core_i(core_i),
        .core_q(core_q), .core_valid(core_valid), .core_ready(core_ready),
        .core_accepted_samples(core_accepted_samples)
    );

    // PL-DDR model: accepts a single-beat request, delays the response, and
    // holds rvalid/rdata stable until the adapter accepts it.
    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            arready <= 1'b0;
            rvalid <= 1'b0;
            pending <= 1'b0;
            response_delay <= 0;
            prng <= 16'h1ace;
        end else begin
            prng <= {prng[14:0], prng[15] ^ prng[13] ^ prng[12] ^ prng[10]};
            arready <= !pending && !rvalid && prng[0];

            if (arvalid && arready) begin
                if (arinfo !== 32'd1)
                    $fatal(1, "Incorrect User_Ddr_arinfo: %h", arinfo);
                if (araddr[5:0] != 0 || araddr < BASE_ADDR ||
                    ((araddr - BASE_ADDR) >> 6) >= TOTAL_BEATS)
                    $fatal(1, "Invalid read address: %h", araddr);
                pending_beat <= (araddr - BASE_ADDR) >> 6;
                response_delay <= prng[2:1];
                pending <= 1'b1;
            end

            if (pending && !rvalid) begin
                if (response_delay == 0) begin
                    rdata <= make_beat(pending_beat);
                    rinfo <= 32'd1;
                    rvalid <= 1'b1;
                    pending <= 1'b0;
                end else begin
                    response_delay <= response_delay - 1;
                end
            end

            if (rvalid && rready)
                rvalid <= 1'b0;
        end
    end

    always @(posedge core_clk) begin
        if (!core_rst_n) begin
            core_ready <= 1'b0;
            core_cycles <= 0;
            observed_samples <= 0;
        end else begin
            core_cycles <= core_cycles + 1;
            core_ready <= ((core_cycles % 7) != 2) && ((core_cycles % 11) != 5);
            if (core_valid && core_ready) begin
                if (core_i !== sample_i(observed_samples) ||
                    core_q !== sample_q(observed_samples))
                    $fatal(1, "IQ mismatch at %0d: got %h/%h expected %h/%h",
                        observed_samples, core_i, core_q,
                        sample_i(observed_samples), sample_q(observed_samples));
                observed_samples <= observed_samples + 1;
            end
        end
    end

    initial begin
        #75;
        ddr_rst_n = 1'b1;
        core_rst_n = 1'b1;
        @(negedge ddr_clk);
        ddr_start = 1'b1;
        @(negedge ddr_clk);
        ddr_start = 1'b0;

        wait (observed_samples == TOTAL_SAMPLES);
        repeat (8) @(posedge core_clk);
        if (ddr_error || core_accepted_samples != TOTAL_SAMPLES)
            $fatal(1, "Input adapter status mismatch error=%b count=%0d",
                ddr_error, core_accepted_samples);
        $display("PL_DDR_IQ_INPUT_ADAPTER_PASS samples=%0d beats=%0d",
            observed_samples, TOTAL_BEATS);
        $finish;
    end

    initial begin
        #5000000;
        $fatal(1, "Input adapter simulation timeout, samples=%0d", observed_samples);
    end
endmodule

`default_nettype wire
