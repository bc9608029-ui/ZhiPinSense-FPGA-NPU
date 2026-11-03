`timescale 1ns/1ps

module tb_iq_frame_controller;
    reg clk = 0;
    reg rst_n = 0;
    reg signed [15:0] s_i = 0, s_q = 0;
    reg s_error = 0, s_valid = 0;
    wire s_ready;
    wire signed [15:0] m_i, m_q;
    wire m_error, m_valid;
    reg m_ready = 1;
    wire [1:0] m_sample_index;
    wire [7:0] m_frame_id;
    wire m_frame_start, m_frame_end, m_frame_valid;
    integer sent = 0;
    integer received = 0;

    always #5 clk = ~clk;

    iq_frame_controller #(.FRAME_LENGTH(4), .FRAME_ID_WIDTH(8)) dut (
        .clk(clk), .rst_n(rst_n), .s_i(s_i), .s_q(s_q), .s_error(s_error),
        .s_valid(s_valid), .s_ready(s_ready), .m_i(m_i), .m_q(m_q), .m_error(m_error),
        .m_valid(m_valid), .m_ready(m_ready), .m_sample_index(m_sample_index),
        .m_frame_id(m_frame_id), .m_frame_start(m_frame_start), .m_frame_end(m_frame_end),
        .m_frame_valid(m_frame_valid)
    );

    always @(negedge clk) begin
        if (rst_n && sent < 10 && s_ready) begin
            s_valid <= 1'b1;
            s_i <= 16'(sent);
            s_q <= 16'(-sent);
            s_error <= (sent == 2);
            sent <= sent + 1;
        end else if (sent >= 10) begin
            s_valid <= 1'b0;
        end
        if (rst_n && received == 5) m_ready <= 1'b0;
        if (rst_n && received == 5 && !m_ready) m_ready <= 1'b1;
    end

    always @(posedge clk) begin
        if (rst_n && m_valid && m_ready) begin
            if (m_sample_index !== 2'(received % 4)) $fatal(1, "sample index mismatch");
            if (m_frame_id !== 8'(received / 4)) $fatal(1, "frame id mismatch");
            if (m_frame_start !== ((received % 4) == 0)) $fatal(1, "start mismatch");
            if (m_frame_end !== ((received % 4) == 3)) $fatal(1, "end mismatch");
            if (!m_frame_valid) $fatal(1, "frame_valid mismatch");
            if ((received == 2 || received == 3) && !m_error) $fatal(1, "sticky error lost");
            received <= received + 1;
            if (received == 9) begin
                $display("PASS tb_iq_frame_controller");
                $finish;
            end
        end
    end

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        #2000 $fatal(1, "timeout");
    end
endmodule
