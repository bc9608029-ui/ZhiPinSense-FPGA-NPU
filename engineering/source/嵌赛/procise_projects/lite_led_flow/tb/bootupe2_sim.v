`timescale 1ns / 1ps

// Simulation-only model for the Procise BOOTUPE2 primitive.
// Do not add this file to the Procise synthesis source set.
module BOOTUPE2 #(
    parameter real SIM_CCLK_FREQ = 0.0
) (
    output reg CFGCLK,
    output reg CFGMCLK,
    output reg EOS,
    output reg PREQ,
    input      CLK,
    input      GSR,
    input      GTS,
    input      KEYCLEARB,
    input      PACK,
    input      USRCCLKO,
    input      USRCCLKTS,
    input      USRDONEO,
    input      USRDONETS
);
    initial begin
        CFGCLK  = 1'b0;
        CFGMCLK = 1'b0;
        EOS     = 1'b1;
        PREQ    = 1'b0;
    end

    always #5 CFGMCLK = ~CFGMCLK;

    // Keep unused inputs visible to lint without affecting the model.
    wire unused_ok = &{1'b0, CLK, GSR, GTS, KEYCLEARB, PACK,
                       USRCCLKO, USRCCLKTS, USRDONEO, USRDONETS};
endmodule
