// hdmi_colorbar_720p_top.v — minimal PL-side pHDMI colorbar for the FMQL30TAI
// (悟净) board, 720p@60.  NEW file (not a frozen official asset).
//
// Reuses the official display IP as-is (color_bar, uihdmitx, TMDSEncoder,
// oserdese2_10to1); only the clock generation and instantiation are new.
//
// Data path (official demo, confirmed): color_bar generates 24-bit RGB888 test
// bars -> uihdmitx -> TMDSEncoder (8b/10b) -> oserdese2_10to1 (OSERDESE2 10:1
// DDR) -> HDMI pins (AC17/AA15/Y16/W16, TMDS_33).  This minimal top generates
// the test bar internally (no PS/DDR/SDI), which is the correct first bring-up
// step before the UI mock data path.
//
// Clock scheme (the one subtlety): the board's only onboard oscillator is
// sys_clk 200 MHz (C8/C7).  200 MHz cannot cleanly produce the 720p pixel
// clock 74.25 MHz or its 5x TMDS clock 371.25 MHz (would need M=297>64), so two
// cascaded MMCMs are used, matching the demo's own 200->27 MHz sys_clk IP:
//   MMCM1  200 MHz -> 27 MHz    (VCO = 200*27/5 = 1080 MHz, /40)
//   MMCM2  27 MHz  -> 742.5 MHz (VCO = 27*55/2 = 742.5 MHz)
//                    -> 74.25 MHz  (/10, pixel)  + 371.25 MHz (/2, 5x TMDS)
// This needs no external oscillator and no FMC clock.
`timescale 1ns / 1ps

module hdmi_colorbar_720p_top (
    input  wire       sys_clk_p,     // 200 MHz diff (C8/C7), DIFF_SSTL15
    input  wire       sys_clk_n,
    input  wire       sys_rst,       // active-high reset (F8), LVCMOS15
    output wire       HDMI_CLK_P,    // AC17, TMDS_33
    output wire       HDMI_CLK_N,    // (differential partner, auto-placed)
    output wire [2:0] HDMI_TX_P,     // AA15/Y16/W16, TMDS_33
    output wire [2:0] HDMI_TX_N,     // (differential partners, auto-placed)
    output wire [1:0] led            // J1/M6, LVCMOS15
);

    // ---- input clock -----------------------------------------------------
    wire clk_200m;
    IBUFDS #(
        .DIFF_TERM("TRUE"),
        .IOSTANDARD("DIFF_SSTL15")
    ) u_ibufds_sysclk (
        .I  (sys_clk_p),
        .IB (sys_clk_n),
        .O  (clk_200m)
    );

    // ---- MMCM1: 200 MHz -> 27 MHz ---------------------------------------
    wire clk_27m, mmcm1_locked, clkfb1;
    MMCME2_BASE #(
        .CLKFBOUT_MULT_F (27.0),
        .CLKIN1_PERIOD   (5.000),
        .CLKOUT0_DIVIDE_F(40.0),
        .DIVCLK_DIVIDE   (5)
    ) u_mmcm_200_27 (
        .CLKIN1  (clk_200m),
        .CLKOUT0 (clk_27m),
        .CLKFBOUT(clkfb1),
        .CLKFBIN (clkfb1),
        .LOCKED  (mmcm1_locked),
        .PWRDWN  (1'b0),
        .RST     (1'b0)
    );
    wire clk_27m_bufg;
    BUFG u_bufg_27 (.I(clk_27m), .O(clk_27m_bufg));

    // ---- MMCM2: 27 MHz -> 74.25 MHz + 371.25 MHz --------------------------
    wire clk_74m25, clk_371m25, mmcm2_locked, clkfb2;
    MMCME2_BASE #(
        .CLKFBOUT_MULT_F (55.0),
        .CLKIN1_PERIOD   (37.037),   // 27 MHz
        .CLKOUT0_DIVIDE_F(10.0),     // 74.25 MHz pixel
        .CLKOUT1_DIVIDE  (2),        // 371.25 MHz 5x TMDS
        .DIVCLK_DIVIDE   (2)
    ) u_mmcm_27_742 (
        .CLKIN1  (clk_27m_bufg),
        .CLKOUT0 (clk_74m25),
        .CLKOUT1 (clk_371m25),
        .CLKFBOUT(clkfb2),
        .CLKFBIN (clkfb2),
        .LOCKED  (mmcm2_locked),
        .PWRDWN  (1'b0),
        .RST     (1'b0)
    );
    wire clk_74m25_bufg, clk_371m25_bufg;
    BUFG u_bufg_74  (.I(clk_74m25),  .O(clk_74m25_bufg));
    BUFG u_bufg_371 (.I(clk_371m25), .O(clk_371m25_bufg));

    // ---- reset: assert until both MMCMs lock, then deassert 4 px clocks ---
    reg [3:0] rst_sr = 4'hF;
    always @(posedge clk_74m25_bufg)
        rst_sr <= {rst_sr[2:0], ~(mmcm1_locked & mmcm2_locked)};
    wire rst = sys_rst | (|rst_sr);

    // ---- color bar (720p) ------------------------------------------------
    wire        hs, vs, de;
    wire [7:0]  rgb_r, rgb_g, rgb_b;
    color_bar u_color_bar (
        .clk  (clk_74m25_bufg),
        .rst  (rst),
        .hs   (hs),
        .vs   (vs),
        .de   (de),
        .rgb_r(rgb_r),
        .rgb_g(rgb_g),
        .rgb_b(rgb_b)
    );

    // ---- HDMI TX (7-series, TMDS_33) -------------------------------------
    uihdmitx #(.FAMILY("7FAMILY")) u_hdmitx (
        .RSTn_i        (~rst),
        .HS_i          (hs),
        .VS_i          (vs),
        .VDE_i         (de),
        .RGB_i         ({rgb_r, rgb_g, rgb_b}),
        .PCLKX1_i      (clk_74m25_bufg),
        .PCLKX2_5_i    (1'b0),          // unused in 7FAMILY
        .PCLKX5_i      (clk_371m25_bufg),
        .TMDS_TX_CLK_P (HDMI_CLK_P),
        .TMDS_TX_CLK_N (HDMI_CLK_N),
        .TMDS_TX_P     (HDMI_TX_P),
        .TMDS_TX_N     (HDMI_TX_N)
    );

    // ---- status LED: [0] = both MMCMs locked, [1] = ~1 Hz blink -----------
    assign led[0] = mmcm1_locked & mmcm2_locked;
    reg [26:0] blink_cnt = 0;
    always @(posedge clk_74m25_bufg)
        blink_cnt <= blink_cnt + 1'b1;
    assign led[1] = blink_cnt[26];

endmodule
