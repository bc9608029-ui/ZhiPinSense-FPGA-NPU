`timescale 1ns/1ps

module tb_feature_quantizer;
    reg clk = 0;
    reg rst_n = 0;
    reg signed [15:0] s_data;
    reg s_valid = 0;
    wire s_ready;
    wire signed [7:0] m_data;
    wire m_saturated;
    wire m_valid;
    reg m_ready = 1;
    wire [31:0] saturation_count;

    always #5 clk = ~clk;

    feature_quantizer #(.INPUT_WIDTH(16), .SIGNED_INPUT(1)) dut (
        .clk(clk), .rst_n(rst_n), .s_data(s_data), .s_valid(s_valid), .s_ready(s_ready),
        .cfg_multiplier(32'd1), .cfg_shift(8'd1), .clear_saturation_count(1'b0),
        .m_data(m_data), .m_saturated(m_saturated), .m_valid(m_valid), .m_ready(m_ready),
        .saturation_count(saturation_count)
    );

    task automatic send_and_check;
        input integer raw;
        input integer expected;
        input integer expected_sat;
        begin
            @(negedge clk);
            while (!s_ready) @(negedge clk);
            s_data = 16'(raw);
            s_valid = 1'b1;
            @(posedge clk); #1;
            if (!m_valid || $signed(m_data) !== 8'(expected)
                    || m_saturated !== 1'(expected_sat)) begin
                $display("FAIL quant raw=%0d got=%0d sat=%0d expected=%0d sat=%0d",
                         raw, $signed(m_data), m_saturated, expected, expected_sat);
                $fatal(1);
            end
            @(negedge clk);
            s_valid = 1'b0;
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        send_and_check(0, 0, 0);
        send_and_check(1, 1, 0);      // +0.5 -> +1
        send_and_check(-1, -1, 0);    // -0.5 -> -1
        send_and_check(2, 1, 0);
        send_and_check(-2, -1, 0);
        send_and_check(253, 127, 0);  // +126.5 -> +127
        send_and_check(-253, -127, 0);
        send_and_check(300, 127, 1);
        send_and_check(-300, -127, 1);
        if (saturation_count !== 2) $fatal(1, "FAIL saturation_count=%0d", saturation_count);
        $display("PASS tb_feature_quantizer");
        $finish;
    end
endmodule
