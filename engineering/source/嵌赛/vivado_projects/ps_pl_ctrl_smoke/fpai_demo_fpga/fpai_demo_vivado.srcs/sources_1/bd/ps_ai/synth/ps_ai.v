//Copyright 1986-2018 Xilinx, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2018.3 (win64) Build 2405991 Thu Dec  6 23:38:27 MST 2018
//Date        : Sun Sep 27 17:16:44 2026
//Host        : colorfulshadow running 64-bit major release  (build 9200)
//Command     : generate_target ps_ai.bd
//Design      : ps_ai
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module m00_couplers_imp_1D6FAED
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [11:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input [0:0]M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output [0:0]M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [11:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input [0:0]M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output [0:0]M_AXI_awvalid;
  input [11:0]M_AXI_bid;
  output [0:0]M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input [0:0]M_AXI_bvalid;
  input [31:0]M_AXI_rdata;
  input [11:0]M_AXI_rid;
  input [0:0]M_AXI_rlast;
  output [0:0]M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input [0:0]M_AXI_rvalid;
  output [31:0]M_AXI_wdata;
  output [11:0]M_AXI_wid;
  output [0:0]M_AXI_wlast;
  input [0:0]M_AXI_wready;
  output [3:0]M_AXI_wstrb;
  output [0:0]M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [11:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output [0:0]S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input [0:0]S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [11:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output [0:0]S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input [0:0]S_AXI_awvalid;
  output [11:0]S_AXI_bid;
  input [0:0]S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output [0:0]S_AXI_bvalid;
  output [31:0]S_AXI_rdata;
  output [11:0]S_AXI_rid;
  output [0:0]S_AXI_rlast;
  input [0:0]S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output [0:0]S_AXI_rvalid;
  input [31:0]S_AXI_wdata;
  input [11:0]S_AXI_wid;
  input [0:0]S_AXI_wlast;
  output [0:0]S_AXI_wready;
  input [3:0]S_AXI_wstrb;
  input [0:0]S_AXI_wvalid;

  wire [31:0]m00_couplers_to_m00_couplers_ARADDR;
  wire [1:0]m00_couplers_to_m00_couplers_ARBURST;
  wire [3:0]m00_couplers_to_m00_couplers_ARCACHE;
  wire [11:0]m00_couplers_to_m00_couplers_ARID;
  wire [3:0]m00_couplers_to_m00_couplers_ARLEN;
  wire [1:0]m00_couplers_to_m00_couplers_ARLOCK;
  wire [2:0]m00_couplers_to_m00_couplers_ARPROT;
  wire [3:0]m00_couplers_to_m00_couplers_ARQOS;
  wire [0:0]m00_couplers_to_m00_couplers_ARREADY;
  wire [2:0]m00_couplers_to_m00_couplers_ARSIZE;
  wire [0:0]m00_couplers_to_m00_couplers_ARVALID;
  wire [31:0]m00_couplers_to_m00_couplers_AWADDR;
  wire [1:0]m00_couplers_to_m00_couplers_AWBURST;
  wire [3:0]m00_couplers_to_m00_couplers_AWCACHE;
  wire [11:0]m00_couplers_to_m00_couplers_AWID;
  wire [3:0]m00_couplers_to_m00_couplers_AWLEN;
  wire [1:0]m00_couplers_to_m00_couplers_AWLOCK;
  wire [2:0]m00_couplers_to_m00_couplers_AWPROT;
  wire [3:0]m00_couplers_to_m00_couplers_AWQOS;
  wire [0:0]m00_couplers_to_m00_couplers_AWREADY;
  wire [2:0]m00_couplers_to_m00_couplers_AWSIZE;
  wire [0:0]m00_couplers_to_m00_couplers_AWVALID;
  wire [11:0]m00_couplers_to_m00_couplers_BID;
  wire [0:0]m00_couplers_to_m00_couplers_BREADY;
  wire [1:0]m00_couplers_to_m00_couplers_BRESP;
  wire [0:0]m00_couplers_to_m00_couplers_BVALID;
  wire [31:0]m00_couplers_to_m00_couplers_RDATA;
  wire [11:0]m00_couplers_to_m00_couplers_RID;
  wire [0:0]m00_couplers_to_m00_couplers_RLAST;
  wire [0:0]m00_couplers_to_m00_couplers_RREADY;
  wire [1:0]m00_couplers_to_m00_couplers_RRESP;
  wire [0:0]m00_couplers_to_m00_couplers_RVALID;
  wire [31:0]m00_couplers_to_m00_couplers_WDATA;
  wire [11:0]m00_couplers_to_m00_couplers_WID;
  wire [0:0]m00_couplers_to_m00_couplers_WLAST;
  wire [0:0]m00_couplers_to_m00_couplers_WREADY;
  wire [3:0]m00_couplers_to_m00_couplers_WSTRB;
  wire [0:0]m00_couplers_to_m00_couplers_WVALID;

  assign M_AXI_araddr[31:0] = m00_couplers_to_m00_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = m00_couplers_to_m00_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = m00_couplers_to_m00_couplers_ARCACHE;
  assign M_AXI_arid[11:0] = m00_couplers_to_m00_couplers_ARID;
  assign M_AXI_arlen[3:0] = m00_couplers_to_m00_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = m00_couplers_to_m00_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = m00_couplers_to_m00_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = m00_couplers_to_m00_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = m00_couplers_to_m00_couplers_ARSIZE;
  assign M_AXI_arvalid[0] = m00_couplers_to_m00_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = m00_couplers_to_m00_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = m00_couplers_to_m00_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = m00_couplers_to_m00_couplers_AWCACHE;
  assign M_AXI_awid[11:0] = m00_couplers_to_m00_couplers_AWID;
  assign M_AXI_awlen[3:0] = m00_couplers_to_m00_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = m00_couplers_to_m00_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = m00_couplers_to_m00_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = m00_couplers_to_m00_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = m00_couplers_to_m00_couplers_AWSIZE;
  assign M_AXI_awvalid[0] = m00_couplers_to_m00_couplers_AWVALID;
  assign M_AXI_bready[0] = m00_couplers_to_m00_couplers_BREADY;
  assign M_AXI_rready[0] = m00_couplers_to_m00_couplers_RREADY;
  assign M_AXI_wdata[31:0] = m00_couplers_to_m00_couplers_WDATA;
  assign M_AXI_wid[11:0] = m00_couplers_to_m00_couplers_WID;
  assign M_AXI_wlast[0] = m00_couplers_to_m00_couplers_WLAST;
  assign M_AXI_wstrb[3:0] = m00_couplers_to_m00_couplers_WSTRB;
  assign M_AXI_wvalid[0] = m00_couplers_to_m00_couplers_WVALID;
  assign S_AXI_arready[0] = m00_couplers_to_m00_couplers_ARREADY;
  assign S_AXI_awready[0] = m00_couplers_to_m00_couplers_AWREADY;
  assign S_AXI_bid[11:0] = m00_couplers_to_m00_couplers_BID;
  assign S_AXI_bresp[1:0] = m00_couplers_to_m00_couplers_BRESP;
  assign S_AXI_bvalid[0] = m00_couplers_to_m00_couplers_BVALID;
  assign S_AXI_rdata[31:0] = m00_couplers_to_m00_couplers_RDATA;
  assign S_AXI_rid[11:0] = m00_couplers_to_m00_couplers_RID;
  assign S_AXI_rlast[0] = m00_couplers_to_m00_couplers_RLAST;
  assign S_AXI_rresp[1:0] = m00_couplers_to_m00_couplers_RRESP;
  assign S_AXI_rvalid[0] = m00_couplers_to_m00_couplers_RVALID;
  assign S_AXI_wready[0] = m00_couplers_to_m00_couplers_WREADY;
  assign m00_couplers_to_m00_couplers_ARADDR = S_AXI_araddr[31:0];
  assign m00_couplers_to_m00_couplers_ARBURST = S_AXI_arburst[1:0];
  assign m00_couplers_to_m00_couplers_ARCACHE = S_AXI_arcache[3:0];
  assign m00_couplers_to_m00_couplers_ARID = S_AXI_arid[11:0];
  assign m00_couplers_to_m00_couplers_ARLEN = S_AXI_arlen[3:0];
  assign m00_couplers_to_m00_couplers_ARLOCK = S_AXI_arlock[1:0];
  assign m00_couplers_to_m00_couplers_ARPROT = S_AXI_arprot[2:0];
  assign m00_couplers_to_m00_couplers_ARQOS = S_AXI_arqos[3:0];
  assign m00_couplers_to_m00_couplers_ARREADY = M_AXI_arready[0];
  assign m00_couplers_to_m00_couplers_ARSIZE = S_AXI_arsize[2:0];
  assign m00_couplers_to_m00_couplers_ARVALID = S_AXI_arvalid[0];
  assign m00_couplers_to_m00_couplers_AWADDR = S_AXI_awaddr[31:0];
  assign m00_couplers_to_m00_couplers_AWBURST = S_AXI_awburst[1:0];
  assign m00_couplers_to_m00_couplers_AWCACHE = S_AXI_awcache[3:0];
  assign m00_couplers_to_m00_couplers_AWID = S_AXI_awid[11:0];
  assign m00_couplers_to_m00_couplers_AWLEN = S_AXI_awlen[3:0];
  assign m00_couplers_to_m00_couplers_AWLOCK = S_AXI_awlock[1:0];
  assign m00_couplers_to_m00_couplers_AWPROT = S_AXI_awprot[2:0];
  assign m00_couplers_to_m00_couplers_AWQOS = S_AXI_awqos[3:0];
  assign m00_couplers_to_m00_couplers_AWREADY = M_AXI_awready[0];
  assign m00_couplers_to_m00_couplers_AWSIZE = S_AXI_awsize[2:0];
  assign m00_couplers_to_m00_couplers_AWVALID = S_AXI_awvalid[0];
  assign m00_couplers_to_m00_couplers_BID = M_AXI_bid[11:0];
  assign m00_couplers_to_m00_couplers_BREADY = S_AXI_bready[0];
  assign m00_couplers_to_m00_couplers_BRESP = M_AXI_bresp[1:0];
  assign m00_couplers_to_m00_couplers_BVALID = M_AXI_bvalid[0];
  assign m00_couplers_to_m00_couplers_RDATA = M_AXI_rdata[31:0];
  assign m00_couplers_to_m00_couplers_RID = M_AXI_rid[11:0];
  assign m00_couplers_to_m00_couplers_RLAST = M_AXI_rlast[0];
  assign m00_couplers_to_m00_couplers_RREADY = S_AXI_rready[0];
  assign m00_couplers_to_m00_couplers_RRESP = M_AXI_rresp[1:0];
  assign m00_couplers_to_m00_couplers_RVALID = M_AXI_rvalid[0];
  assign m00_couplers_to_m00_couplers_WDATA = S_AXI_wdata[31:0];
  assign m00_couplers_to_m00_couplers_WID = S_AXI_wid[11:0];
  assign m00_couplers_to_m00_couplers_WLAST = S_AXI_wlast[0];
  assign m00_couplers_to_m00_couplers_WREADY = M_AXI_wready[0];
  assign m00_couplers_to_m00_couplers_WSTRB = S_AXI_wstrb[3:0];
  assign m00_couplers_to_m00_couplers_WVALID = S_AXI_wvalid[0];
endmodule

module m00_couplers_imp_OID2TJ
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [5:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [5:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output M_AXI_awvalid;
  input [5:0]M_AXI_bid;
  output M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input M_AXI_bvalid;
  input [63:0]M_AXI_rdata;
  input [5:0]M_AXI_rid;
  input M_AXI_rlast;
  output M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input M_AXI_rvalid;
  output [63:0]M_AXI_wdata;
  output [5:0]M_AXI_wid;
  output M_AXI_wlast;
  input M_AXI_wready;
  output [7:0]M_AXI_wstrb;
  output M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [5:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [5:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input S_AXI_awvalid;
  output [5:0]S_AXI_bid;
  input S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output S_AXI_bvalid;
  output [63:0]S_AXI_rdata;
  output [5:0]S_AXI_rid;
  output S_AXI_rlast;
  input S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output S_AXI_rvalid;
  input [63:0]S_AXI_wdata;
  input [5:0]S_AXI_wid;
  input S_AXI_wlast;
  output S_AXI_wready;
  input [7:0]S_AXI_wstrb;
  input S_AXI_wvalid;

  wire M_ACLK_1;
  wire M_ARESETN_1;
  wire [31:0]m00_couplers_to_m00_regslice_ARADDR;
  wire [1:0]m00_couplers_to_m00_regslice_ARBURST;
  wire [3:0]m00_couplers_to_m00_regslice_ARCACHE;
  wire [5:0]m00_couplers_to_m00_regslice_ARID;
  wire [3:0]m00_couplers_to_m00_regslice_ARLEN;
  wire [1:0]m00_couplers_to_m00_regslice_ARLOCK;
  wire [2:0]m00_couplers_to_m00_regslice_ARPROT;
  wire [3:0]m00_couplers_to_m00_regslice_ARQOS;
  wire m00_couplers_to_m00_regslice_ARREADY;
  wire [2:0]m00_couplers_to_m00_regslice_ARSIZE;
  wire m00_couplers_to_m00_regslice_ARVALID;
  wire [31:0]m00_couplers_to_m00_regslice_AWADDR;
  wire [1:0]m00_couplers_to_m00_regslice_AWBURST;
  wire [3:0]m00_couplers_to_m00_regslice_AWCACHE;
  wire [5:0]m00_couplers_to_m00_regslice_AWID;
  wire [3:0]m00_couplers_to_m00_regslice_AWLEN;
  wire [1:0]m00_couplers_to_m00_regslice_AWLOCK;
  wire [2:0]m00_couplers_to_m00_regslice_AWPROT;
  wire [3:0]m00_couplers_to_m00_regslice_AWQOS;
  wire m00_couplers_to_m00_regslice_AWREADY;
  wire [2:0]m00_couplers_to_m00_regslice_AWSIZE;
  wire m00_couplers_to_m00_regslice_AWVALID;
  wire [5:0]m00_couplers_to_m00_regslice_BID;
  wire m00_couplers_to_m00_regslice_BREADY;
  wire [1:0]m00_couplers_to_m00_regslice_BRESP;
  wire m00_couplers_to_m00_regslice_BVALID;
  wire [63:0]m00_couplers_to_m00_regslice_RDATA;
  wire [5:0]m00_couplers_to_m00_regslice_RID;
  wire m00_couplers_to_m00_regslice_RLAST;
  wire m00_couplers_to_m00_regslice_RREADY;
  wire [1:0]m00_couplers_to_m00_regslice_RRESP;
  wire m00_couplers_to_m00_regslice_RVALID;
  wire [63:0]m00_couplers_to_m00_regslice_WDATA;
  wire [5:0]m00_couplers_to_m00_regslice_WID;
  wire m00_couplers_to_m00_regslice_WLAST;
  wire m00_couplers_to_m00_regslice_WREADY;
  wire [7:0]m00_couplers_to_m00_regslice_WSTRB;
  wire m00_couplers_to_m00_regslice_WVALID;
  wire [31:0]m00_regslice_to_m00_couplers_ARADDR;
  wire [1:0]m00_regslice_to_m00_couplers_ARBURST;
  wire [3:0]m00_regslice_to_m00_couplers_ARCACHE;
  wire [5:0]m00_regslice_to_m00_couplers_ARID;
  wire [3:0]m00_regslice_to_m00_couplers_ARLEN;
  wire [1:0]m00_regslice_to_m00_couplers_ARLOCK;
  wire [2:0]m00_regslice_to_m00_couplers_ARPROT;
  wire [3:0]m00_regslice_to_m00_couplers_ARQOS;
  wire m00_regslice_to_m00_couplers_ARREADY;
  wire [2:0]m00_regslice_to_m00_couplers_ARSIZE;
  wire m00_regslice_to_m00_couplers_ARVALID;
  wire [31:0]m00_regslice_to_m00_couplers_AWADDR;
  wire [1:0]m00_regslice_to_m00_couplers_AWBURST;
  wire [3:0]m00_regslice_to_m00_couplers_AWCACHE;
  wire [5:0]m00_regslice_to_m00_couplers_AWID;
  wire [3:0]m00_regslice_to_m00_couplers_AWLEN;
  wire [1:0]m00_regslice_to_m00_couplers_AWLOCK;
  wire [2:0]m00_regslice_to_m00_couplers_AWPROT;
  wire [3:0]m00_regslice_to_m00_couplers_AWQOS;
  wire m00_regslice_to_m00_couplers_AWREADY;
  wire [2:0]m00_regslice_to_m00_couplers_AWSIZE;
  wire m00_regslice_to_m00_couplers_AWVALID;
  wire [5:0]m00_regslice_to_m00_couplers_BID;
  wire m00_regslice_to_m00_couplers_BREADY;
  wire [1:0]m00_regslice_to_m00_couplers_BRESP;
  wire m00_regslice_to_m00_couplers_BVALID;
  wire [63:0]m00_regslice_to_m00_couplers_RDATA;
  wire [5:0]m00_regslice_to_m00_couplers_RID;
  wire m00_regslice_to_m00_couplers_RLAST;
  wire m00_regslice_to_m00_couplers_RREADY;
  wire [1:0]m00_regslice_to_m00_couplers_RRESP;
  wire m00_regslice_to_m00_couplers_RVALID;
  wire [63:0]m00_regslice_to_m00_couplers_WDATA;
  wire [5:0]m00_regslice_to_m00_couplers_WID;
  wire m00_regslice_to_m00_couplers_WLAST;
  wire m00_regslice_to_m00_couplers_WREADY;
  wire [7:0]m00_regslice_to_m00_couplers_WSTRB;
  wire m00_regslice_to_m00_couplers_WVALID;

  assign M_ACLK_1 = M_ACLK;
  assign M_ARESETN_1 = M_ARESETN;
  assign M_AXI_araddr[31:0] = m00_regslice_to_m00_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = m00_regslice_to_m00_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = m00_regslice_to_m00_couplers_ARCACHE;
  assign M_AXI_arid[5:0] = m00_regslice_to_m00_couplers_ARID;
  assign M_AXI_arlen[3:0] = m00_regslice_to_m00_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = m00_regslice_to_m00_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = m00_regslice_to_m00_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = m00_regslice_to_m00_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = m00_regslice_to_m00_couplers_ARSIZE;
  assign M_AXI_arvalid = m00_regslice_to_m00_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = m00_regslice_to_m00_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = m00_regslice_to_m00_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = m00_regslice_to_m00_couplers_AWCACHE;
  assign M_AXI_awid[5:0] = m00_regslice_to_m00_couplers_AWID;
  assign M_AXI_awlen[3:0] = m00_regslice_to_m00_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = m00_regslice_to_m00_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = m00_regslice_to_m00_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = m00_regslice_to_m00_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = m00_regslice_to_m00_couplers_AWSIZE;
  assign M_AXI_awvalid = m00_regslice_to_m00_couplers_AWVALID;
  assign M_AXI_bready = m00_regslice_to_m00_couplers_BREADY;
  assign M_AXI_rready = m00_regslice_to_m00_couplers_RREADY;
  assign M_AXI_wdata[63:0] = m00_regslice_to_m00_couplers_WDATA;
  assign M_AXI_wid[5:0] = m00_regslice_to_m00_couplers_WID;
  assign M_AXI_wlast = m00_regslice_to_m00_couplers_WLAST;
  assign M_AXI_wstrb[7:0] = m00_regslice_to_m00_couplers_WSTRB;
  assign M_AXI_wvalid = m00_regslice_to_m00_couplers_WVALID;
  assign S_AXI_arready = m00_couplers_to_m00_regslice_ARREADY;
  assign S_AXI_awready = m00_couplers_to_m00_regslice_AWREADY;
  assign S_AXI_bid[5:0] = m00_couplers_to_m00_regslice_BID;
  assign S_AXI_bresp[1:0] = m00_couplers_to_m00_regslice_BRESP;
  assign S_AXI_bvalid = m00_couplers_to_m00_regslice_BVALID;
  assign S_AXI_rdata[63:0] = m00_couplers_to_m00_regslice_RDATA;
  assign S_AXI_rid[5:0] = m00_couplers_to_m00_regslice_RID;
  assign S_AXI_rlast = m00_couplers_to_m00_regslice_RLAST;
  assign S_AXI_rresp[1:0] = m00_couplers_to_m00_regslice_RRESP;
  assign S_AXI_rvalid = m00_couplers_to_m00_regslice_RVALID;
  assign S_AXI_wready = m00_couplers_to_m00_regslice_WREADY;
  assign m00_couplers_to_m00_regslice_ARADDR = S_AXI_araddr[31:0];
  assign m00_couplers_to_m00_regslice_ARBURST = S_AXI_arburst[1:0];
  assign m00_couplers_to_m00_regslice_ARCACHE = S_AXI_arcache[3:0];
  assign m00_couplers_to_m00_regslice_ARID = S_AXI_arid[5:0];
  assign m00_couplers_to_m00_regslice_ARLEN = S_AXI_arlen[3:0];
  assign m00_couplers_to_m00_regslice_ARLOCK = S_AXI_arlock[1:0];
  assign m00_couplers_to_m00_regslice_ARPROT = S_AXI_arprot[2:0];
  assign m00_couplers_to_m00_regslice_ARQOS = S_AXI_arqos[3:0];
  assign m00_couplers_to_m00_regslice_ARSIZE = S_AXI_arsize[2:0];
  assign m00_couplers_to_m00_regslice_ARVALID = S_AXI_arvalid;
  assign m00_couplers_to_m00_regslice_AWADDR = S_AXI_awaddr[31:0];
  assign m00_couplers_to_m00_regslice_AWBURST = S_AXI_awburst[1:0];
  assign m00_couplers_to_m00_regslice_AWCACHE = S_AXI_awcache[3:0];
  assign m00_couplers_to_m00_regslice_AWID = S_AXI_awid[5:0];
  assign m00_couplers_to_m00_regslice_AWLEN = S_AXI_awlen[3:0];
  assign m00_couplers_to_m00_regslice_AWLOCK = S_AXI_awlock[1:0];
  assign m00_couplers_to_m00_regslice_AWPROT = S_AXI_awprot[2:0];
  assign m00_couplers_to_m00_regslice_AWQOS = S_AXI_awqos[3:0];
  assign m00_couplers_to_m00_regslice_AWSIZE = S_AXI_awsize[2:0];
  assign m00_couplers_to_m00_regslice_AWVALID = S_AXI_awvalid;
  assign m00_couplers_to_m00_regslice_BREADY = S_AXI_bready;
  assign m00_couplers_to_m00_regslice_RREADY = S_AXI_rready;
  assign m00_couplers_to_m00_regslice_WDATA = S_AXI_wdata[63:0];
  assign m00_couplers_to_m00_regslice_WID = S_AXI_wid[5:0];
  assign m00_couplers_to_m00_regslice_WLAST = S_AXI_wlast;
  assign m00_couplers_to_m00_regslice_WSTRB = S_AXI_wstrb[7:0];
  assign m00_couplers_to_m00_regslice_WVALID = S_AXI_wvalid;
  assign m00_regslice_to_m00_couplers_ARREADY = M_AXI_arready;
  assign m00_regslice_to_m00_couplers_AWREADY = M_AXI_awready;
  assign m00_regslice_to_m00_couplers_BID = M_AXI_bid[5:0];
  assign m00_regslice_to_m00_couplers_BRESP = M_AXI_bresp[1:0];
  assign m00_regslice_to_m00_couplers_BVALID = M_AXI_bvalid;
  assign m00_regslice_to_m00_couplers_RDATA = M_AXI_rdata[63:0];
  assign m00_regslice_to_m00_couplers_RID = M_AXI_rid[5:0];
  assign m00_regslice_to_m00_couplers_RLAST = M_AXI_rlast;
  assign m00_regslice_to_m00_couplers_RRESP = M_AXI_rresp[1:0];
  assign m00_regslice_to_m00_couplers_RVALID = M_AXI_rvalid;
  assign m00_regslice_to_m00_couplers_WREADY = M_AXI_wready;
  ps_ai_m00_regslice_0 m00_regslice
       (.aclk(M_ACLK_1),
        .aresetn(M_ARESETN_1),
        .m_axi_araddr(m00_regslice_to_m00_couplers_ARADDR),
        .m_axi_arburst(m00_regslice_to_m00_couplers_ARBURST),
        .m_axi_arcache(m00_regslice_to_m00_couplers_ARCACHE),
        .m_axi_arid(m00_regslice_to_m00_couplers_ARID),
        .m_axi_arlen(m00_regslice_to_m00_couplers_ARLEN),
        .m_axi_arlock(m00_regslice_to_m00_couplers_ARLOCK),
        .m_axi_arprot(m00_regslice_to_m00_couplers_ARPROT),
        .m_axi_arqos(m00_regslice_to_m00_couplers_ARQOS),
        .m_axi_arready(m00_regslice_to_m00_couplers_ARREADY),
        .m_axi_arsize(m00_regslice_to_m00_couplers_ARSIZE),
        .m_axi_arvalid(m00_regslice_to_m00_couplers_ARVALID),
        .m_axi_awaddr(m00_regslice_to_m00_couplers_AWADDR),
        .m_axi_awburst(m00_regslice_to_m00_couplers_AWBURST),
        .m_axi_awcache(m00_regslice_to_m00_couplers_AWCACHE),
        .m_axi_awid(m00_regslice_to_m00_couplers_AWID),
        .m_axi_awlen(m00_regslice_to_m00_couplers_AWLEN),
        .m_axi_awlock(m00_regslice_to_m00_couplers_AWLOCK),
        .m_axi_awprot(m00_regslice_to_m00_couplers_AWPROT),
        .m_axi_awqos(m00_regslice_to_m00_couplers_AWQOS),
        .m_axi_awready(m00_regslice_to_m00_couplers_AWREADY),
        .m_axi_awsize(m00_regslice_to_m00_couplers_AWSIZE),
        .m_axi_awvalid(m00_regslice_to_m00_couplers_AWVALID),
        .m_axi_bid(m00_regslice_to_m00_couplers_BID),
        .m_axi_bready(m00_regslice_to_m00_couplers_BREADY),
        .m_axi_bresp(m00_regslice_to_m00_couplers_BRESP),
        .m_axi_bvalid(m00_regslice_to_m00_couplers_BVALID),
        .m_axi_rdata(m00_regslice_to_m00_couplers_RDATA),
        .m_axi_rid(m00_regslice_to_m00_couplers_RID),
        .m_axi_rlast(m00_regslice_to_m00_couplers_RLAST),
        .m_axi_rready(m00_regslice_to_m00_couplers_RREADY),
        .m_axi_rresp(m00_regslice_to_m00_couplers_RRESP),
        .m_axi_rvalid(m00_regslice_to_m00_couplers_RVALID),
        .m_axi_wdata(m00_regslice_to_m00_couplers_WDATA),
        .m_axi_wid(m00_regslice_to_m00_couplers_WID),
        .m_axi_wlast(m00_regslice_to_m00_couplers_WLAST),
        .m_axi_wready(m00_regslice_to_m00_couplers_WREADY),
        .m_axi_wstrb(m00_regslice_to_m00_couplers_WSTRB),
        .m_axi_wvalid(m00_regslice_to_m00_couplers_WVALID),
        .s_axi_araddr(m00_couplers_to_m00_regslice_ARADDR),
        .s_axi_arburst(m00_couplers_to_m00_regslice_ARBURST),
        .s_axi_arcache(m00_couplers_to_m00_regslice_ARCACHE),
        .s_axi_arid(m00_couplers_to_m00_regslice_ARID),
        .s_axi_arlen(m00_couplers_to_m00_regslice_ARLEN),
        .s_axi_arlock(m00_couplers_to_m00_regslice_ARLOCK),
        .s_axi_arprot(m00_couplers_to_m00_regslice_ARPROT),
        .s_axi_arqos(m00_couplers_to_m00_regslice_ARQOS),
        .s_axi_arready(m00_couplers_to_m00_regslice_ARREADY),
        .s_axi_arsize(m00_couplers_to_m00_regslice_ARSIZE),
        .s_axi_arvalid(m00_couplers_to_m00_regslice_ARVALID),
        .s_axi_awaddr(m00_couplers_to_m00_regslice_AWADDR),
        .s_axi_awburst(m00_couplers_to_m00_regslice_AWBURST),
        .s_axi_awcache(m00_couplers_to_m00_regslice_AWCACHE),
        .s_axi_awid(m00_couplers_to_m00_regslice_AWID),
        .s_axi_awlen(m00_couplers_to_m00_regslice_AWLEN),
        .s_axi_awlock(m00_couplers_to_m00_regslice_AWLOCK),
        .s_axi_awprot(m00_couplers_to_m00_regslice_AWPROT),
        .s_axi_awqos(m00_couplers_to_m00_regslice_AWQOS),
        .s_axi_awready(m00_couplers_to_m00_regslice_AWREADY),
        .s_axi_awsize(m00_couplers_to_m00_regslice_AWSIZE),
        .s_axi_awvalid(m00_couplers_to_m00_regslice_AWVALID),
        .s_axi_bid(m00_couplers_to_m00_regslice_BID),
        .s_axi_bready(m00_couplers_to_m00_regslice_BREADY),
        .s_axi_bresp(m00_couplers_to_m00_regslice_BRESP),
        .s_axi_bvalid(m00_couplers_to_m00_regslice_BVALID),
        .s_axi_rdata(m00_couplers_to_m00_regslice_RDATA),
        .s_axi_rid(m00_couplers_to_m00_regslice_RID),
        .s_axi_rlast(m00_couplers_to_m00_regslice_RLAST),
        .s_axi_rready(m00_couplers_to_m00_regslice_RREADY),
        .s_axi_rresp(m00_couplers_to_m00_regslice_RRESP),
        .s_axi_rvalid(m00_couplers_to_m00_regslice_RVALID),
        .s_axi_wdata(m00_couplers_to_m00_regslice_WDATA),
        .s_axi_wid(m00_couplers_to_m00_regslice_WID),
        .s_axi_wlast(m00_couplers_to_m00_regslice_WLAST),
        .s_axi_wready(m00_couplers_to_m00_regslice_WREADY),
        .s_axi_wstrb(m00_couplers_to_m00_regslice_WSTRB),
        .s_axi_wvalid(m00_couplers_to_m00_regslice_WVALID));
endmodule

module m00_couplers_imp_SJGDOD
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [11:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input [0:0]M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output [0:0]M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [11:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input [0:0]M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output [0:0]M_AXI_awvalid;
  input [11:0]M_AXI_bid;
  output [0:0]M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input [0:0]M_AXI_bvalid;
  input [31:0]M_AXI_rdata;
  input [11:0]M_AXI_rid;
  input [0:0]M_AXI_rlast;
  output [0:0]M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input [0:0]M_AXI_rvalid;
  output [31:0]M_AXI_wdata;
  output [11:0]M_AXI_wid;
  output [0:0]M_AXI_wlast;
  input [0:0]M_AXI_wready;
  output [3:0]M_AXI_wstrb;
  output [0:0]M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [11:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output [0:0]S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input [0:0]S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [11:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output [0:0]S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input [0:0]S_AXI_awvalid;
  output [11:0]S_AXI_bid;
  input [0:0]S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output [0:0]S_AXI_bvalid;
  output [31:0]S_AXI_rdata;
  output [11:0]S_AXI_rid;
  output [0:0]S_AXI_rlast;
  input [0:0]S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output [0:0]S_AXI_rvalid;
  input [31:0]S_AXI_wdata;
  input [11:0]S_AXI_wid;
  input [0:0]S_AXI_wlast;
  output [0:0]S_AXI_wready;
  input [3:0]S_AXI_wstrb;
  input [0:0]S_AXI_wvalid;

  wire [31:0]m00_couplers_to_m00_couplers_ARADDR;
  wire [1:0]m00_couplers_to_m00_couplers_ARBURST;
  wire [3:0]m00_couplers_to_m00_couplers_ARCACHE;
  wire [11:0]m00_couplers_to_m00_couplers_ARID;
  wire [3:0]m00_couplers_to_m00_couplers_ARLEN;
  wire [1:0]m00_couplers_to_m00_couplers_ARLOCK;
  wire [2:0]m00_couplers_to_m00_couplers_ARPROT;
  wire [3:0]m00_couplers_to_m00_couplers_ARQOS;
  wire [0:0]m00_couplers_to_m00_couplers_ARREADY;
  wire [2:0]m00_couplers_to_m00_couplers_ARSIZE;
  wire [0:0]m00_couplers_to_m00_couplers_ARVALID;
  wire [31:0]m00_couplers_to_m00_couplers_AWADDR;
  wire [1:0]m00_couplers_to_m00_couplers_AWBURST;
  wire [3:0]m00_couplers_to_m00_couplers_AWCACHE;
  wire [11:0]m00_couplers_to_m00_couplers_AWID;
  wire [3:0]m00_couplers_to_m00_couplers_AWLEN;
  wire [1:0]m00_couplers_to_m00_couplers_AWLOCK;
  wire [2:0]m00_couplers_to_m00_couplers_AWPROT;
  wire [3:0]m00_couplers_to_m00_couplers_AWQOS;
  wire [0:0]m00_couplers_to_m00_couplers_AWREADY;
  wire [2:0]m00_couplers_to_m00_couplers_AWSIZE;
  wire [0:0]m00_couplers_to_m00_couplers_AWVALID;
  wire [11:0]m00_couplers_to_m00_couplers_BID;
  wire [0:0]m00_couplers_to_m00_couplers_BREADY;
  wire [1:0]m00_couplers_to_m00_couplers_BRESP;
  wire [0:0]m00_couplers_to_m00_couplers_BVALID;
  wire [31:0]m00_couplers_to_m00_couplers_RDATA;
  wire [11:0]m00_couplers_to_m00_couplers_RID;
  wire [0:0]m00_couplers_to_m00_couplers_RLAST;
  wire [0:0]m00_couplers_to_m00_couplers_RREADY;
  wire [1:0]m00_couplers_to_m00_couplers_RRESP;
  wire [0:0]m00_couplers_to_m00_couplers_RVALID;
  wire [31:0]m00_couplers_to_m00_couplers_WDATA;
  wire [11:0]m00_couplers_to_m00_couplers_WID;
  wire [0:0]m00_couplers_to_m00_couplers_WLAST;
  wire [0:0]m00_couplers_to_m00_couplers_WREADY;
  wire [3:0]m00_couplers_to_m00_couplers_WSTRB;
  wire [0:0]m00_couplers_to_m00_couplers_WVALID;

  assign M_AXI_araddr[31:0] = m00_couplers_to_m00_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = m00_couplers_to_m00_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = m00_couplers_to_m00_couplers_ARCACHE;
  assign M_AXI_arid[11:0] = m00_couplers_to_m00_couplers_ARID;
  assign M_AXI_arlen[3:0] = m00_couplers_to_m00_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = m00_couplers_to_m00_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = m00_couplers_to_m00_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = m00_couplers_to_m00_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = m00_couplers_to_m00_couplers_ARSIZE;
  assign M_AXI_arvalid[0] = m00_couplers_to_m00_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = m00_couplers_to_m00_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = m00_couplers_to_m00_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = m00_couplers_to_m00_couplers_AWCACHE;
  assign M_AXI_awid[11:0] = m00_couplers_to_m00_couplers_AWID;
  assign M_AXI_awlen[3:0] = m00_couplers_to_m00_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = m00_couplers_to_m00_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = m00_couplers_to_m00_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = m00_couplers_to_m00_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = m00_couplers_to_m00_couplers_AWSIZE;
  assign M_AXI_awvalid[0] = m00_couplers_to_m00_couplers_AWVALID;
  assign M_AXI_bready[0] = m00_couplers_to_m00_couplers_BREADY;
  assign M_AXI_rready[0] = m00_couplers_to_m00_couplers_RREADY;
  assign M_AXI_wdata[31:0] = m00_couplers_to_m00_couplers_WDATA;
  assign M_AXI_wid[11:0] = m00_couplers_to_m00_couplers_WID;
  assign M_AXI_wlast[0] = m00_couplers_to_m00_couplers_WLAST;
  assign M_AXI_wstrb[3:0] = m00_couplers_to_m00_couplers_WSTRB;
  assign M_AXI_wvalid[0] = m00_couplers_to_m00_couplers_WVALID;
  assign S_AXI_arready[0] = m00_couplers_to_m00_couplers_ARREADY;
  assign S_AXI_awready[0] = m00_couplers_to_m00_couplers_AWREADY;
  assign S_AXI_bid[11:0] = m00_couplers_to_m00_couplers_BID;
  assign S_AXI_bresp[1:0] = m00_couplers_to_m00_couplers_BRESP;
  assign S_AXI_bvalid[0] = m00_couplers_to_m00_couplers_BVALID;
  assign S_AXI_rdata[31:0] = m00_couplers_to_m00_couplers_RDATA;
  assign S_AXI_rid[11:0] = m00_couplers_to_m00_couplers_RID;
  assign S_AXI_rlast[0] = m00_couplers_to_m00_couplers_RLAST;
  assign S_AXI_rresp[1:0] = m00_couplers_to_m00_couplers_RRESP;
  assign S_AXI_rvalid[0] = m00_couplers_to_m00_couplers_RVALID;
  assign S_AXI_wready[0] = m00_couplers_to_m00_couplers_WREADY;
  assign m00_couplers_to_m00_couplers_ARADDR = S_AXI_araddr[31:0];
  assign m00_couplers_to_m00_couplers_ARBURST = S_AXI_arburst[1:0];
  assign m00_couplers_to_m00_couplers_ARCACHE = S_AXI_arcache[3:0];
  assign m00_couplers_to_m00_couplers_ARID = S_AXI_arid[11:0];
  assign m00_couplers_to_m00_couplers_ARLEN = S_AXI_arlen[3:0];
  assign m00_couplers_to_m00_couplers_ARLOCK = S_AXI_arlock[1:0];
  assign m00_couplers_to_m00_couplers_ARPROT = S_AXI_arprot[2:0];
  assign m00_couplers_to_m00_couplers_ARQOS = S_AXI_arqos[3:0];
  assign m00_couplers_to_m00_couplers_ARREADY = M_AXI_arready[0];
  assign m00_couplers_to_m00_couplers_ARSIZE = S_AXI_arsize[2:0];
  assign m00_couplers_to_m00_couplers_ARVALID = S_AXI_arvalid[0];
  assign m00_couplers_to_m00_couplers_AWADDR = S_AXI_awaddr[31:0];
  assign m00_couplers_to_m00_couplers_AWBURST = S_AXI_awburst[1:0];
  assign m00_couplers_to_m00_couplers_AWCACHE = S_AXI_awcache[3:0];
  assign m00_couplers_to_m00_couplers_AWID = S_AXI_awid[11:0];
  assign m00_couplers_to_m00_couplers_AWLEN = S_AXI_awlen[3:0];
  assign m00_couplers_to_m00_couplers_AWLOCK = S_AXI_awlock[1:0];
  assign m00_couplers_to_m00_couplers_AWPROT = S_AXI_awprot[2:0];
  assign m00_couplers_to_m00_couplers_AWQOS = S_AXI_awqos[3:0];
  assign m00_couplers_to_m00_couplers_AWREADY = M_AXI_awready[0];
  assign m00_couplers_to_m00_couplers_AWSIZE = S_AXI_awsize[2:0];
  assign m00_couplers_to_m00_couplers_AWVALID = S_AXI_awvalid[0];
  assign m00_couplers_to_m00_couplers_BID = M_AXI_bid[11:0];
  assign m00_couplers_to_m00_couplers_BREADY = S_AXI_bready[0];
  assign m00_couplers_to_m00_couplers_BRESP = M_AXI_bresp[1:0];
  assign m00_couplers_to_m00_couplers_BVALID = M_AXI_bvalid[0];
  assign m00_couplers_to_m00_couplers_RDATA = M_AXI_rdata[31:0];
  assign m00_couplers_to_m00_couplers_RID = M_AXI_rid[11:0];
  assign m00_couplers_to_m00_couplers_RLAST = M_AXI_rlast[0];
  assign m00_couplers_to_m00_couplers_RREADY = S_AXI_rready[0];
  assign m00_couplers_to_m00_couplers_RRESP = M_AXI_rresp[1:0];
  assign m00_couplers_to_m00_couplers_RVALID = M_AXI_rvalid[0];
  assign m00_couplers_to_m00_couplers_WDATA = S_AXI_wdata[31:0];
  assign m00_couplers_to_m00_couplers_WID = S_AXI_wid[11:0];
  assign m00_couplers_to_m00_couplers_WLAST = S_AXI_wlast[0];
  assign m00_couplers_to_m00_couplers_WREADY = M_AXI_wready[0];
  assign m00_couplers_to_m00_couplers_WSTRB = S_AXI_wstrb[3:0];
  assign m00_couplers_to_m00_couplers_WVALID = S_AXI_wvalid[0];
endmodule

module m01_couplers_imp_1PX0PUD
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [11:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input [0:0]M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output [0:0]M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [11:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input [0:0]M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output [0:0]M_AXI_awvalid;
  input [11:0]M_AXI_bid;
  output [0:0]M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input [0:0]M_AXI_bvalid;
  input [31:0]M_AXI_rdata;
  input [11:0]M_AXI_rid;
  input [0:0]M_AXI_rlast;
  output [0:0]M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input [0:0]M_AXI_rvalid;
  output [31:0]M_AXI_wdata;
  output [11:0]M_AXI_wid;
  output [0:0]M_AXI_wlast;
  input [0:0]M_AXI_wready;
  output [3:0]M_AXI_wstrb;
  output [0:0]M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [11:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output [0:0]S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input [0:0]S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [11:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output [0:0]S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input [0:0]S_AXI_awvalid;
  output [11:0]S_AXI_bid;
  input [0:0]S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output [0:0]S_AXI_bvalid;
  output [31:0]S_AXI_rdata;
  output [11:0]S_AXI_rid;
  output [0:0]S_AXI_rlast;
  input [0:0]S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output [0:0]S_AXI_rvalid;
  input [31:0]S_AXI_wdata;
  input [11:0]S_AXI_wid;
  input [0:0]S_AXI_wlast;
  output [0:0]S_AXI_wready;
  input [3:0]S_AXI_wstrb;
  input [0:0]S_AXI_wvalid;

  wire [31:0]m01_couplers_to_m01_couplers_ARADDR;
  wire [1:0]m01_couplers_to_m01_couplers_ARBURST;
  wire [3:0]m01_couplers_to_m01_couplers_ARCACHE;
  wire [11:0]m01_couplers_to_m01_couplers_ARID;
  wire [3:0]m01_couplers_to_m01_couplers_ARLEN;
  wire [1:0]m01_couplers_to_m01_couplers_ARLOCK;
  wire [2:0]m01_couplers_to_m01_couplers_ARPROT;
  wire [3:0]m01_couplers_to_m01_couplers_ARQOS;
  wire [0:0]m01_couplers_to_m01_couplers_ARREADY;
  wire [2:0]m01_couplers_to_m01_couplers_ARSIZE;
  wire [0:0]m01_couplers_to_m01_couplers_ARVALID;
  wire [31:0]m01_couplers_to_m01_couplers_AWADDR;
  wire [1:0]m01_couplers_to_m01_couplers_AWBURST;
  wire [3:0]m01_couplers_to_m01_couplers_AWCACHE;
  wire [11:0]m01_couplers_to_m01_couplers_AWID;
  wire [3:0]m01_couplers_to_m01_couplers_AWLEN;
  wire [1:0]m01_couplers_to_m01_couplers_AWLOCK;
  wire [2:0]m01_couplers_to_m01_couplers_AWPROT;
  wire [3:0]m01_couplers_to_m01_couplers_AWQOS;
  wire [0:0]m01_couplers_to_m01_couplers_AWREADY;
  wire [2:0]m01_couplers_to_m01_couplers_AWSIZE;
  wire [0:0]m01_couplers_to_m01_couplers_AWVALID;
  wire [11:0]m01_couplers_to_m01_couplers_BID;
  wire [0:0]m01_couplers_to_m01_couplers_BREADY;
  wire [1:0]m01_couplers_to_m01_couplers_BRESP;
  wire [0:0]m01_couplers_to_m01_couplers_BVALID;
  wire [31:0]m01_couplers_to_m01_couplers_RDATA;
  wire [11:0]m01_couplers_to_m01_couplers_RID;
  wire [0:0]m01_couplers_to_m01_couplers_RLAST;
  wire [0:0]m01_couplers_to_m01_couplers_RREADY;
  wire [1:0]m01_couplers_to_m01_couplers_RRESP;
  wire [0:0]m01_couplers_to_m01_couplers_RVALID;
  wire [31:0]m01_couplers_to_m01_couplers_WDATA;
  wire [11:0]m01_couplers_to_m01_couplers_WID;
  wire [0:0]m01_couplers_to_m01_couplers_WLAST;
  wire [0:0]m01_couplers_to_m01_couplers_WREADY;
  wire [3:0]m01_couplers_to_m01_couplers_WSTRB;
  wire [0:0]m01_couplers_to_m01_couplers_WVALID;

  assign M_AXI_araddr[31:0] = m01_couplers_to_m01_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = m01_couplers_to_m01_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = m01_couplers_to_m01_couplers_ARCACHE;
  assign M_AXI_arid[11:0] = m01_couplers_to_m01_couplers_ARID;
  assign M_AXI_arlen[3:0] = m01_couplers_to_m01_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = m01_couplers_to_m01_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = m01_couplers_to_m01_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = m01_couplers_to_m01_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = m01_couplers_to_m01_couplers_ARSIZE;
  assign M_AXI_arvalid[0] = m01_couplers_to_m01_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = m01_couplers_to_m01_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = m01_couplers_to_m01_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = m01_couplers_to_m01_couplers_AWCACHE;
  assign M_AXI_awid[11:0] = m01_couplers_to_m01_couplers_AWID;
  assign M_AXI_awlen[3:0] = m01_couplers_to_m01_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = m01_couplers_to_m01_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = m01_couplers_to_m01_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = m01_couplers_to_m01_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = m01_couplers_to_m01_couplers_AWSIZE;
  assign M_AXI_awvalid[0] = m01_couplers_to_m01_couplers_AWVALID;
  assign M_AXI_bready[0] = m01_couplers_to_m01_couplers_BREADY;
  assign M_AXI_rready[0] = m01_couplers_to_m01_couplers_RREADY;
  assign M_AXI_wdata[31:0] = m01_couplers_to_m01_couplers_WDATA;
  assign M_AXI_wid[11:0] = m01_couplers_to_m01_couplers_WID;
  assign M_AXI_wlast[0] = m01_couplers_to_m01_couplers_WLAST;
  assign M_AXI_wstrb[3:0] = m01_couplers_to_m01_couplers_WSTRB;
  assign M_AXI_wvalid[0] = m01_couplers_to_m01_couplers_WVALID;
  assign S_AXI_arready[0] = m01_couplers_to_m01_couplers_ARREADY;
  assign S_AXI_awready[0] = m01_couplers_to_m01_couplers_AWREADY;
  assign S_AXI_bid[11:0] = m01_couplers_to_m01_couplers_BID;
  assign S_AXI_bresp[1:0] = m01_couplers_to_m01_couplers_BRESP;
  assign S_AXI_bvalid[0] = m01_couplers_to_m01_couplers_BVALID;
  assign S_AXI_rdata[31:0] = m01_couplers_to_m01_couplers_RDATA;
  assign S_AXI_rid[11:0] = m01_couplers_to_m01_couplers_RID;
  assign S_AXI_rlast[0] = m01_couplers_to_m01_couplers_RLAST;
  assign S_AXI_rresp[1:0] = m01_couplers_to_m01_couplers_RRESP;
  assign S_AXI_rvalid[0] = m01_couplers_to_m01_couplers_RVALID;
  assign S_AXI_wready[0] = m01_couplers_to_m01_couplers_WREADY;
  assign m01_couplers_to_m01_couplers_ARADDR = S_AXI_araddr[31:0];
  assign m01_couplers_to_m01_couplers_ARBURST = S_AXI_arburst[1:0];
  assign m01_couplers_to_m01_couplers_ARCACHE = S_AXI_arcache[3:0];
  assign m01_couplers_to_m01_couplers_ARID = S_AXI_arid[11:0];
  assign m01_couplers_to_m01_couplers_ARLEN = S_AXI_arlen[3:0];
  assign m01_couplers_to_m01_couplers_ARLOCK = S_AXI_arlock[1:0];
  assign m01_couplers_to_m01_couplers_ARPROT = S_AXI_arprot[2:0];
  assign m01_couplers_to_m01_couplers_ARQOS = S_AXI_arqos[3:0];
  assign m01_couplers_to_m01_couplers_ARREADY = M_AXI_arready[0];
  assign m01_couplers_to_m01_couplers_ARSIZE = S_AXI_arsize[2:0];
  assign m01_couplers_to_m01_couplers_ARVALID = S_AXI_arvalid[0];
  assign m01_couplers_to_m01_couplers_AWADDR = S_AXI_awaddr[31:0];
  assign m01_couplers_to_m01_couplers_AWBURST = S_AXI_awburst[1:0];
  assign m01_couplers_to_m01_couplers_AWCACHE = S_AXI_awcache[3:0];
  assign m01_couplers_to_m01_couplers_AWID = S_AXI_awid[11:0];
  assign m01_couplers_to_m01_couplers_AWLEN = S_AXI_awlen[3:0];
  assign m01_couplers_to_m01_couplers_AWLOCK = S_AXI_awlock[1:0];
  assign m01_couplers_to_m01_couplers_AWPROT = S_AXI_awprot[2:0];
  assign m01_couplers_to_m01_couplers_AWQOS = S_AXI_awqos[3:0];
  assign m01_couplers_to_m01_couplers_AWREADY = M_AXI_awready[0];
  assign m01_couplers_to_m01_couplers_AWSIZE = S_AXI_awsize[2:0];
  assign m01_couplers_to_m01_couplers_AWVALID = S_AXI_awvalid[0];
  assign m01_couplers_to_m01_couplers_BID = M_AXI_bid[11:0];
  assign m01_couplers_to_m01_couplers_BREADY = S_AXI_bready[0];
  assign m01_couplers_to_m01_couplers_BRESP = M_AXI_bresp[1:0];
  assign m01_couplers_to_m01_couplers_BVALID = M_AXI_bvalid[0];
  assign m01_couplers_to_m01_couplers_RDATA = M_AXI_rdata[31:0];
  assign m01_couplers_to_m01_couplers_RID = M_AXI_rid[11:0];
  assign m01_couplers_to_m01_couplers_RLAST = M_AXI_rlast[0];
  assign m01_couplers_to_m01_couplers_RREADY = S_AXI_rready[0];
  assign m01_couplers_to_m01_couplers_RRESP = M_AXI_rresp[1:0];
  assign m01_couplers_to_m01_couplers_RVALID = M_AXI_rvalid[0];
  assign m01_couplers_to_m01_couplers_WDATA = S_AXI_wdata[31:0];
  assign m01_couplers_to_m01_couplers_WID = S_AXI_wid[11:0];
  assign m01_couplers_to_m01_couplers_WLAST = S_AXI_wlast[0];
  assign m01_couplers_to_m01_couplers_WREADY = M_AXI_wready[0];
  assign m01_couplers_to_m01_couplers_WSTRB = S_AXI_wstrb[3:0];
  assign m01_couplers_to_m01_couplers_WVALID = S_AXI_wvalid[0];
endmodule

module m01_couplers_imp_2FMNIL
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [11:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input [0:0]M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output [0:0]M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [11:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input [0:0]M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output [0:0]M_AXI_awvalid;
  input [11:0]M_AXI_bid;
  output [0:0]M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input [0:0]M_AXI_bvalid;
  input [31:0]M_AXI_rdata;
  input [11:0]M_AXI_rid;
  input [0:0]M_AXI_rlast;
  output [0:0]M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input [0:0]M_AXI_rvalid;
  output [31:0]M_AXI_wdata;
  output [11:0]M_AXI_wid;
  output [0:0]M_AXI_wlast;
  input [0:0]M_AXI_wready;
  output [3:0]M_AXI_wstrb;
  output [0:0]M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [11:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output [0:0]S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input [0:0]S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [11:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output [0:0]S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input [0:0]S_AXI_awvalid;
  output [11:0]S_AXI_bid;
  input [0:0]S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output [0:0]S_AXI_bvalid;
  output [31:0]S_AXI_rdata;
  output [11:0]S_AXI_rid;
  output [0:0]S_AXI_rlast;
  input [0:0]S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output [0:0]S_AXI_rvalid;
  input [31:0]S_AXI_wdata;
  input [11:0]S_AXI_wid;
  input [0:0]S_AXI_wlast;
  output [0:0]S_AXI_wready;
  input [3:0]S_AXI_wstrb;
  input [0:0]S_AXI_wvalid;

  wire [31:0]m01_couplers_to_m01_couplers_ARADDR;
  wire [1:0]m01_couplers_to_m01_couplers_ARBURST;
  wire [3:0]m01_couplers_to_m01_couplers_ARCACHE;
  wire [11:0]m01_couplers_to_m01_couplers_ARID;
  wire [3:0]m01_couplers_to_m01_couplers_ARLEN;
  wire [1:0]m01_couplers_to_m01_couplers_ARLOCK;
  wire [2:0]m01_couplers_to_m01_couplers_ARPROT;
  wire [3:0]m01_couplers_to_m01_couplers_ARQOS;
  wire [0:0]m01_couplers_to_m01_couplers_ARREADY;
  wire [2:0]m01_couplers_to_m01_couplers_ARSIZE;
  wire [0:0]m01_couplers_to_m01_couplers_ARVALID;
  wire [31:0]m01_couplers_to_m01_couplers_AWADDR;
  wire [1:0]m01_couplers_to_m01_couplers_AWBURST;
  wire [3:0]m01_couplers_to_m01_couplers_AWCACHE;
  wire [11:0]m01_couplers_to_m01_couplers_AWID;
  wire [3:0]m01_couplers_to_m01_couplers_AWLEN;
  wire [1:0]m01_couplers_to_m01_couplers_AWLOCK;
  wire [2:0]m01_couplers_to_m01_couplers_AWPROT;
  wire [3:0]m01_couplers_to_m01_couplers_AWQOS;
  wire [0:0]m01_couplers_to_m01_couplers_AWREADY;
  wire [2:0]m01_couplers_to_m01_couplers_AWSIZE;
  wire [0:0]m01_couplers_to_m01_couplers_AWVALID;
  wire [11:0]m01_couplers_to_m01_couplers_BID;
  wire [0:0]m01_couplers_to_m01_couplers_BREADY;
  wire [1:0]m01_couplers_to_m01_couplers_BRESP;
  wire [0:0]m01_couplers_to_m01_couplers_BVALID;
  wire [31:0]m01_couplers_to_m01_couplers_RDATA;
  wire [11:0]m01_couplers_to_m01_couplers_RID;
  wire [0:0]m01_couplers_to_m01_couplers_RLAST;
  wire [0:0]m01_couplers_to_m01_couplers_RREADY;
  wire [1:0]m01_couplers_to_m01_couplers_RRESP;
  wire [0:0]m01_couplers_to_m01_couplers_RVALID;
  wire [31:0]m01_couplers_to_m01_couplers_WDATA;
  wire [11:0]m01_couplers_to_m01_couplers_WID;
  wire [0:0]m01_couplers_to_m01_couplers_WLAST;
  wire [0:0]m01_couplers_to_m01_couplers_WREADY;
  wire [3:0]m01_couplers_to_m01_couplers_WSTRB;
  wire [0:0]m01_couplers_to_m01_couplers_WVALID;

  assign M_AXI_araddr[31:0] = m01_couplers_to_m01_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = m01_couplers_to_m01_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = m01_couplers_to_m01_couplers_ARCACHE;
  assign M_AXI_arid[11:0] = m01_couplers_to_m01_couplers_ARID;
  assign M_AXI_arlen[3:0] = m01_couplers_to_m01_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = m01_couplers_to_m01_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = m01_couplers_to_m01_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = m01_couplers_to_m01_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = m01_couplers_to_m01_couplers_ARSIZE;
  assign M_AXI_arvalid[0] = m01_couplers_to_m01_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = m01_couplers_to_m01_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = m01_couplers_to_m01_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = m01_couplers_to_m01_couplers_AWCACHE;
  assign M_AXI_awid[11:0] = m01_couplers_to_m01_couplers_AWID;
  assign M_AXI_awlen[3:0] = m01_couplers_to_m01_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = m01_couplers_to_m01_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = m01_couplers_to_m01_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = m01_couplers_to_m01_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = m01_couplers_to_m01_couplers_AWSIZE;
  assign M_AXI_awvalid[0] = m01_couplers_to_m01_couplers_AWVALID;
  assign M_AXI_bready[0] = m01_couplers_to_m01_couplers_BREADY;
  assign M_AXI_rready[0] = m01_couplers_to_m01_couplers_RREADY;
  assign M_AXI_wdata[31:0] = m01_couplers_to_m01_couplers_WDATA;
  assign M_AXI_wid[11:0] = m01_couplers_to_m01_couplers_WID;
  assign M_AXI_wlast[0] = m01_couplers_to_m01_couplers_WLAST;
  assign M_AXI_wstrb[3:0] = m01_couplers_to_m01_couplers_WSTRB;
  assign M_AXI_wvalid[0] = m01_couplers_to_m01_couplers_WVALID;
  assign S_AXI_arready[0] = m01_couplers_to_m01_couplers_ARREADY;
  assign S_AXI_awready[0] = m01_couplers_to_m01_couplers_AWREADY;
  assign S_AXI_bid[11:0] = m01_couplers_to_m01_couplers_BID;
  assign S_AXI_bresp[1:0] = m01_couplers_to_m01_couplers_BRESP;
  assign S_AXI_bvalid[0] = m01_couplers_to_m01_couplers_BVALID;
  assign S_AXI_rdata[31:0] = m01_couplers_to_m01_couplers_RDATA;
  assign S_AXI_rid[11:0] = m01_couplers_to_m01_couplers_RID;
  assign S_AXI_rlast[0] = m01_couplers_to_m01_couplers_RLAST;
  assign S_AXI_rresp[1:0] = m01_couplers_to_m01_couplers_RRESP;
  assign S_AXI_rvalid[0] = m01_couplers_to_m01_couplers_RVALID;
  assign S_AXI_wready[0] = m01_couplers_to_m01_couplers_WREADY;
  assign m01_couplers_to_m01_couplers_ARADDR = S_AXI_araddr[31:0];
  assign m01_couplers_to_m01_couplers_ARBURST = S_AXI_arburst[1:0];
  assign m01_couplers_to_m01_couplers_ARCACHE = S_AXI_arcache[3:0];
  assign m01_couplers_to_m01_couplers_ARID = S_AXI_arid[11:0];
  assign m01_couplers_to_m01_couplers_ARLEN = S_AXI_arlen[3:0];
  assign m01_couplers_to_m01_couplers_ARLOCK = S_AXI_arlock[1:0];
  assign m01_couplers_to_m01_couplers_ARPROT = S_AXI_arprot[2:0];
  assign m01_couplers_to_m01_couplers_ARQOS = S_AXI_arqos[3:0];
  assign m01_couplers_to_m01_couplers_ARREADY = M_AXI_arready[0];
  assign m01_couplers_to_m01_couplers_ARSIZE = S_AXI_arsize[2:0];
  assign m01_couplers_to_m01_couplers_ARVALID = S_AXI_arvalid[0];
  assign m01_couplers_to_m01_couplers_AWADDR = S_AXI_awaddr[31:0];
  assign m01_couplers_to_m01_couplers_AWBURST = S_AXI_awburst[1:0];
  assign m01_couplers_to_m01_couplers_AWCACHE = S_AXI_awcache[3:0];
  assign m01_couplers_to_m01_couplers_AWID = S_AXI_awid[11:0];
  assign m01_couplers_to_m01_couplers_AWLEN = S_AXI_awlen[3:0];
  assign m01_couplers_to_m01_couplers_AWLOCK = S_AXI_awlock[1:0];
  assign m01_couplers_to_m01_couplers_AWPROT = S_AXI_awprot[2:0];
  assign m01_couplers_to_m01_couplers_AWQOS = S_AXI_awqos[3:0];
  assign m01_couplers_to_m01_couplers_AWREADY = M_AXI_awready[0];
  assign m01_couplers_to_m01_couplers_AWSIZE = S_AXI_awsize[2:0];
  assign m01_couplers_to_m01_couplers_AWVALID = S_AXI_awvalid[0];
  assign m01_couplers_to_m01_couplers_BID = M_AXI_bid[11:0];
  assign m01_couplers_to_m01_couplers_BREADY = S_AXI_bready[0];
  assign m01_couplers_to_m01_couplers_BRESP = M_AXI_bresp[1:0];
  assign m01_couplers_to_m01_couplers_BVALID = M_AXI_bvalid[0];
  assign m01_couplers_to_m01_couplers_RDATA = M_AXI_rdata[31:0];
  assign m01_couplers_to_m01_couplers_RID = M_AXI_rid[11:0];
  assign m01_couplers_to_m01_couplers_RLAST = M_AXI_rlast[0];
  assign m01_couplers_to_m01_couplers_RREADY = S_AXI_rready[0];
  assign m01_couplers_to_m01_couplers_RRESP = M_AXI_rresp[1:0];
  assign m01_couplers_to_m01_couplers_RVALID = M_AXI_rvalid[0];
  assign m01_couplers_to_m01_couplers_WDATA = S_AXI_wdata[31:0];
  assign m01_couplers_to_m01_couplers_WID = S_AXI_wid[11:0];
  assign m01_couplers_to_m01_couplers_WLAST = S_AXI_wlast[0];
  assign m01_couplers_to_m01_couplers_WREADY = M_AXI_wready[0];
  assign m01_couplers_to_m01_couplers_WSTRB = S_AXI_wstrb[3:0];
  assign m01_couplers_to_m01_couplers_WVALID = S_AXI_wvalid[0];
endmodule

(* CORE_GENERATION_INFO = "ps_ai,IP_Integrator,{x_ipVendor=xilinx.com,x_ipLibrary=BlockDiagram,x_ipName=ps_ai,x_ipVersion=1.00.a,x_ipLanguage=VERILOG,numBlks=24,numReposBlks=12,numNonXlnxBlks=0,numHierBlks=12,maxHierDepth=0,numSysgenBlks=0,numHlsBlks=0,numHdlrefBlks=0,numPkgbdBlks=0,bdsource=USER,da_axi4_cnt=1,da_board_cnt=2,da_clkrst_cnt=3,synth_mode=OOC_per_IP}" *) (* HW_HANDOFF = "ps_ai.hwdef" *) 
module ps_ai
   (AI_BIST_0_pl_bist_done,
    AI_BIST_0_pl_bist_en,
    AI_BIST_0_pl_bist_err,
    AI_BIST_0_pl_bist_err_inv,
    AI_BIST_0_pl_repair_done,
    AI_BIST_0_pl_repair_fail,
    AI_IRQ_0_pl_int_info,
    AI_IRQ_0_pl_int_ready,
    AI_IRQ_0_pl_int_valid,
    AI_SCAN_0_pl_scan_compression_mode,
    AI_SCAN_0_pl_scan_cs,
    AI_SCAN_0_pl_scan_en,
    AI_SCAN_0_pl_scan_in,
    AI_SCAN_0_pl_scan_mode_b,
    AI_SCAN_0_pl_scan_occ_bypass,
    AI_SCAN_0_pl_scan_occ_mode,
    AI_SCAN_0_pl_scan_occ_reset,
    AI_SCAN_0_pl_scan_out,
    AI_SCAN_0_pl_scan_wrp_mode,
    AI_SCAN_0_pl_scan_wrp_shift,
    BYolo_GP0_araddr,
    BYolo_GP0_arburst,
    BYolo_GP0_arcache,
    BYolo_GP0_arid,
    BYolo_GP0_arlen,
    BYolo_GP0_arlock,
    BYolo_GP0_arprot,
    BYolo_GP0_arqos,
    BYolo_GP0_arready,
    BYolo_GP0_arsize,
    BYolo_GP0_arvalid,
    BYolo_GP0_awaddr,
    BYolo_GP0_awburst,
    BYolo_GP0_awcache,
    BYolo_GP0_awid,
    BYolo_GP0_awlen,
    BYolo_GP0_awlock,
    BYolo_GP0_awprot,
    BYolo_GP0_awqos,
    BYolo_GP0_awready,
    BYolo_GP0_awsize,
    BYolo_GP0_awvalid,
    BYolo_GP0_bid,
    BYolo_GP0_bready,
    BYolo_GP0_bresp,
    BYolo_GP0_bvalid,
    BYolo_GP0_rdata,
    BYolo_GP0_rid,
    BYolo_GP0_rlast,
    BYolo_GP0_rready,
    BYolo_GP0_rresp,
    BYolo_GP0_rvalid,
    BYolo_GP0_wdata,
    BYolo_GP0_wid,
    BYolo_GP0_wlast,
    BYolo_GP0_wready,
    BYolo_GP0_wstrb,
    BYolo_GP0_wvalid,
    BYolo_GP1_araddr,
    BYolo_GP1_arburst,
    BYolo_GP1_arcache,
    BYolo_GP1_arid,
    BYolo_GP1_arlen,
    BYolo_GP1_arlock,
    BYolo_GP1_arprot,
    BYolo_GP1_arqos,
    BYolo_GP1_arready,
    BYolo_GP1_arsize,
    BYolo_GP1_arvalid,
    BYolo_GP1_awaddr,
    BYolo_GP1_awburst,
    BYolo_GP1_awcache,
    BYolo_GP1_awid,
    BYolo_GP1_awlen,
    BYolo_GP1_awlock,
    BYolo_GP1_awprot,
    BYolo_GP1_awqos,
    BYolo_GP1_awready,
    BYolo_GP1_awsize,
    BYolo_GP1_awvalid,
    BYolo_GP1_bid,
    BYolo_GP1_bready,
    BYolo_GP1_bresp,
    BYolo_GP1_bvalid,
    BYolo_GP1_rdata,
    BYolo_GP1_rid,
    BYolo_GP1_rlast,
    BYolo_GP1_rready,
    BYolo_GP1_rresp,
    BYolo_GP1_rvalid,
    BYolo_GP1_wdata,
    BYolo_GP1_wid,
    BYolo_GP1_wlast,
    BYolo_GP1_wready,
    BYolo_GP1_wstrb,
    BYolo_GP1_wvalid,
    DDR_0_addr,
    DDR_0_ba,
    DDR_0_cas_n,
    DDR_0_ck_n,
    DDR_0_ck_p,
    DDR_0_cke,
    DDR_0_cs_n,
    DDR_0_dm,
    DDR_0_dq,
    DDR_0_dqs_n,
    DDR_0_dqs_p,
    DDR_0_odt,
    DDR_0_ras_n,
    DDR_0_reset_n,
    DDR_0_we_n,
    FCLK_CLK0_0,
    FCLK_RESET0_N_0,
    FIXED_IO_0_ddr_vrn,
    FIXED_IO_0_ddr_vrp,
    FIXED_IO_0_mio,
    FIXED_IO_0_ps_clk,
    FIXED_IO_0_ps_porb,
    FIXED_IO_0_ps_srstb,
    M_AI_HP_0_pl_araddr,
    M_AI_HP_0_pl_arinfo,
    M_AI_HP_0_pl_arlast,
    M_AI_HP_0_pl_arready,
    M_AI_HP_0_pl_arvalid,
    M_AI_HP_0_pl_awaddr,
    M_AI_HP_0_pl_awdata,
    M_AI_HP_0_pl_awen,
    M_AI_HP_0_pl_awinfo,
    M_AI_HP_0_pl_awlast,
    M_AI_HP_0_pl_awready,
    M_AI_HP_0_pl_awvalid,
    M_AI_HP_0_pl_bready,
    M_AI_HP_0_pl_bvalid,
    M_AI_HP_0_pl_rdata,
    M_AI_HP_0_pl_rlast,
    M_AI_HP_0_pl_rready,
    M_AI_HP_0_pl_rvalid,
    PJTAG_0_tck,
    PJTAG_0_tdi,
    PJTAG_0_tdo,
    PJTAG_0_tms,
    S_AI_GP_0_pl_ra_araddr,
    S_AI_GP_0_pl_ra_arready,
    S_AI_GP_0_pl_ra_arvalid,
    S_AI_GP_0_pl_ra_awaddr,
    S_AI_GP_0_pl_ra_awdata,
    S_AI_GP_0_pl_ra_awready,
    S_AI_GP_0_pl_ra_awvalid,
    S_AI_GP_0_pl_ra_rdata,
    S_AI_GP_0_pl_ra_rready,
    S_AI_GP_0_pl_ra_rvalid,
    S_AXI_HP0_0_araddr,
    S_AXI_HP0_0_arburst,
    S_AXI_HP0_0_arcache,
    S_AXI_HP0_0_arid,
    S_AXI_HP0_0_arlen,
    S_AXI_HP0_0_arlock,
    S_AXI_HP0_0_arprot,
    S_AXI_HP0_0_arqos,
    S_AXI_HP0_0_arready,
    S_AXI_HP0_0_arsize,
    S_AXI_HP0_0_arvalid,
    S_AXI_HP0_0_awaddr,
    S_AXI_HP0_0_awburst,
    S_AXI_HP0_0_awcache,
    S_AXI_HP0_0_awid,
    S_AXI_HP0_0_awlen,
    S_AXI_HP0_0_awlock,
    S_AXI_HP0_0_awprot,
    S_AXI_HP0_0_awqos,
    S_AXI_HP0_0_awready,
    S_AXI_HP0_0_awsize,
    S_AXI_HP0_0_awvalid,
    S_AXI_HP0_0_bid,
    S_AXI_HP0_0_bready,
    S_AXI_HP0_0_bresp,
    S_AXI_HP0_0_bvalid,
    S_AXI_HP0_0_rdata,
    S_AXI_HP0_0_rid,
    S_AXI_HP0_0_rlast,
    S_AXI_HP0_0_rready,
    S_AXI_HP0_0_rresp,
    S_AXI_HP0_0_rvalid,
    S_AXI_HP0_0_wdata,
    S_AXI_HP0_0_wid,
    S_AXI_HP0_0_wlast,
    S_AXI_HP0_0_wready,
    S_AXI_HP0_0_wstrb,
    S_AXI_HP0_0_wvalid,
    S_AXI_HP0_FIFO_CTRL_0_racount,
    S_AXI_HP0_FIFO_CTRL_0_rcount,
    S_AXI_HP0_FIFO_CTRL_0_rdissuecapen,
    S_AXI_HP0_FIFO_CTRL_0_wacount,
    S_AXI_HP0_FIFO_CTRL_0_wcount,
    S_AXI_HP0_FIFO_CTRL_0_wrissuecapen,
    S_AXI_HP1_0_araddr,
    S_AXI_HP1_0_arburst,
    S_AXI_HP1_0_arcache,
    S_AXI_HP1_0_arid,
    S_AXI_HP1_0_arlen,
    S_AXI_HP1_0_arlock,
    S_AXI_HP1_0_arprot,
    S_AXI_HP1_0_arqos,
    S_AXI_HP1_0_arready,
    S_AXI_HP1_0_arsize,
    S_AXI_HP1_0_arvalid,
    S_AXI_HP1_0_awaddr,
    S_AXI_HP1_0_awburst,
    S_AXI_HP1_0_awcache,
    S_AXI_HP1_0_awid,
    S_AXI_HP1_0_awlen,
    S_AXI_HP1_0_awlock,
    S_AXI_HP1_0_awprot,
    S_AXI_HP1_0_awqos,
    S_AXI_HP1_0_awready,
    S_AXI_HP1_0_awsize,
    S_AXI_HP1_0_awvalid,
    S_AXI_HP1_0_bid,
    S_AXI_HP1_0_bready,
    S_AXI_HP1_0_bresp,
    S_AXI_HP1_0_bvalid,
    S_AXI_HP1_0_rdata,
    S_AXI_HP1_0_rid,
    S_AXI_HP1_0_rlast,
    S_AXI_HP1_0_rready,
    S_AXI_HP1_0_rresp,
    S_AXI_HP1_0_rvalid,
    S_AXI_HP1_0_wdata,
    S_AXI_HP1_0_wid,
    S_AXI_HP1_0_wlast,
    S_AXI_HP1_0_wready,
    S_AXI_HP1_0_wstrb,
    S_AXI_HP1_0_wvalid,
    S_AXI_HP1_FIFO_CTRL_0_racount,
    S_AXI_HP1_FIFO_CTRL_0_rcount,
    S_AXI_HP1_FIFO_CTRL_0_rdissuecapen,
    S_AXI_HP1_FIFO_CTRL_0_wacount,
    S_AXI_HP1_FIFO_CTRL_0_wcount,
    S_AXI_HP1_FIFO_CTRL_0_wrissuecapen,
    S_AXI_HP2_0_araddr,
    S_AXI_HP2_0_arburst,
    S_AXI_HP2_0_arcache,
    S_AXI_HP2_0_arid,
    S_AXI_HP2_0_arlen,
    S_AXI_HP2_0_arlock,
    S_AXI_HP2_0_arprot,
    S_AXI_HP2_0_arqos,
    S_AXI_HP2_0_arready,
    S_AXI_HP2_0_arsize,
    S_AXI_HP2_0_arvalid,
    S_AXI_HP2_0_awaddr,
    S_AXI_HP2_0_awburst,
    S_AXI_HP2_0_awcache,
    S_AXI_HP2_0_awid,
    S_AXI_HP2_0_awlen,
    S_AXI_HP2_0_awlock,
    S_AXI_HP2_0_awprot,
    S_AXI_HP2_0_awqos,
    S_AXI_HP2_0_awready,
    S_AXI_HP2_0_awsize,
    S_AXI_HP2_0_awvalid,
    S_AXI_HP2_0_bid,
    S_AXI_HP2_0_bready,
    S_AXI_HP2_0_bresp,
    S_AXI_HP2_0_bvalid,
    S_AXI_HP2_0_rdata,
    S_AXI_HP2_0_rid,
    S_AXI_HP2_0_rlast,
    S_AXI_HP2_0_rready,
    S_AXI_HP2_0_rresp,
    S_AXI_HP2_0_rvalid,
    S_AXI_HP2_0_wdata,
    S_AXI_HP2_0_wid,
    S_AXI_HP2_0_wlast,
    S_AXI_HP2_0_wready,
    S_AXI_HP2_0_wstrb,
    S_AXI_HP2_0_wvalid,
    S_AXI_HP2_1_araddr,
    S_AXI_HP2_1_arburst,
    S_AXI_HP2_1_arcache,
    S_AXI_HP2_1_arid,
    S_AXI_HP2_1_arlen,
    S_AXI_HP2_1_arlock,
    S_AXI_HP2_1_arprot,
    S_AXI_HP2_1_arqos,
    S_AXI_HP2_1_arready,
    S_AXI_HP2_1_arsize,
    S_AXI_HP2_1_arvalid,
    S_AXI_HP2_1_awaddr,
    S_AXI_HP2_1_awburst,
    S_AXI_HP2_1_awcache,
    S_AXI_HP2_1_awid,
    S_AXI_HP2_1_awlen,
    S_AXI_HP2_1_awlock,
    S_AXI_HP2_1_awprot,
    S_AXI_HP2_1_awqos,
    S_AXI_HP2_1_awready,
    S_AXI_HP2_1_awsize,
    S_AXI_HP2_1_awvalid,
    S_AXI_HP2_1_bid,
    S_AXI_HP2_1_bready,
    S_AXI_HP2_1_bresp,
    S_AXI_HP2_1_bvalid,
    S_AXI_HP2_1_rdata,
    S_AXI_HP2_1_rid,
    S_AXI_HP2_1_rlast,
    S_AXI_HP2_1_rready,
    S_AXI_HP2_1_rresp,
    S_AXI_HP2_1_rvalid,
    S_AXI_HP2_1_wdata,
    S_AXI_HP2_1_wid,
    S_AXI_HP2_1_wlast,
    S_AXI_HP2_1_wready,
    S_AXI_HP2_1_wstrb,
    S_AXI_HP2_1_wvalid,
    S_AXI_HP2_FIFO_CTRL_0_racount,
    S_AXI_HP2_FIFO_CTRL_0_rcount,
    S_AXI_HP2_FIFO_CTRL_0_rdissuecapen,
    S_AXI_HP2_FIFO_CTRL_0_wacount,
    S_AXI_HP2_FIFO_CTRL_0_wcount,
    S_AXI_HP2_FIFO_CTRL_0_wrissuecapen,
    S_AXI_HP3_0_araddr,
    S_AXI_HP3_0_arburst,
    S_AXI_HP3_0_arcache,
    S_AXI_HP3_0_arid,
    S_AXI_HP3_0_arlen,
    S_AXI_HP3_0_arlock,
    S_AXI_HP3_0_arprot,
    S_AXI_HP3_0_arqos,
    S_AXI_HP3_0_arready,
    S_AXI_HP3_0_arsize,
    S_AXI_HP3_0_arvalid,
    S_AXI_HP3_0_awaddr,
    S_AXI_HP3_0_awburst,
    S_AXI_HP3_0_awcache,
    S_AXI_HP3_0_awid,
    S_AXI_HP3_0_awlen,
    S_AXI_HP3_0_awlock,
    S_AXI_HP3_0_awprot,
    S_AXI_HP3_0_awqos,
    S_AXI_HP3_0_awready,
    S_AXI_HP3_0_awsize,
    S_AXI_HP3_0_awvalid,
    S_AXI_HP3_0_bid,
    S_AXI_HP3_0_bready,
    S_AXI_HP3_0_bresp,
    S_AXI_HP3_0_bvalid,
    S_AXI_HP3_0_rdata,
    S_AXI_HP3_0_rid,
    S_AXI_HP3_0_rlast,
    S_AXI_HP3_0_rready,
    S_AXI_HP3_0_rresp,
    S_AXI_HP3_0_rvalid,
    S_AXI_HP3_0_wdata,
    S_AXI_HP3_0_wid,
    S_AXI_HP3_0_wlast,
    S_AXI_HP3_0_wready,
    S_AXI_HP3_0_wstrb,
    S_AXI_HP3_0_wvalid,
    S_AXI_HP3_FIFO_CTRL_0_racount,
    S_AXI_HP3_FIFO_CTRL_0_rcount,
    S_AXI_HP3_FIFO_CTRL_0_rdissuecapen,
    S_AXI_HP3_FIFO_CTRL_0_wacount,
    S_AXI_HP3_FIFO_CTRL_0_wcount,
    S_AXI_HP3_FIFO_CTRL_0_wrissuecapen,
    USBIND_0_0_port_indctl,
    USBIND_0_0_vbus_pwrfault,
    USBIND_0_0_vbus_pwrselect,
    User_GP0_araddr,
    User_GP0_arburst,
    User_GP0_arcache,
    User_GP0_arid,
    User_GP0_arlen,
    User_GP0_arlock,
    User_GP0_arprot,
    User_GP0_arqos,
    User_GP0_arready,
    User_GP0_arsize,
    User_GP0_arvalid,
    User_GP0_awaddr,
    User_GP0_awburst,
    User_GP0_awcache,
    User_GP0_awid,
    User_GP0_awlen,
    User_GP0_awlock,
    User_GP0_awprot,
    User_GP0_awqos,
    User_GP0_awready,
    User_GP0_awsize,
    User_GP0_awvalid,
    User_GP0_bid,
    User_GP0_bready,
    User_GP0_bresp,
    User_GP0_bvalid,
    User_GP0_rdata,
    User_GP0_rid,
    User_GP0_rlast,
    User_GP0_rready,
    User_GP0_rresp,
    User_GP0_rvalid,
    User_GP0_wdata,
    User_GP0_wid,
    User_GP0_wlast,
    User_GP0_wready,
    User_GP0_wstrb,
    User_GP0_wvalid,
    User_GP1_araddr,
    User_GP1_arburst,
    User_GP1_arcache,
    User_GP1_arid,
    User_GP1_arlen,
    User_GP1_arlock,
    User_GP1_arprot,
    User_GP1_arqos,
    User_GP1_arready,
    User_GP1_arsize,
    User_GP1_arvalid,
    User_GP1_awaddr,
    User_GP1_awburst,
    User_GP1_awcache,
    User_GP1_awid,
    User_GP1_awlen,
    User_GP1_awlock,
    User_GP1_awprot,
    User_GP1_awqos,
    User_GP1_awready,
    User_GP1_awsize,
    User_GP1_awvalid,
    User_GP1_bid,
    User_GP1_bready,
    User_GP1_bresp,
    User_GP1_bvalid,
    User_GP1_rdata,
    User_GP1_rid,
    User_GP1_rlast,
    User_GP1_rready,
    User_GP1_rresp,
    User_GP1_rvalid,
    User_GP1_wdata,
    User_GP1_wid,
    User_GP1_wlast,
    User_GP1_wready,
    User_GP1_wstrb,
    User_GP1_wvalid,
    ai_irq,
    customop_irq,
    gp_axi_aclk,
    hp_axi_aclk,
    pl_bist_clk_0,
    pl_bist_rstn_0,
    pl_clk_div_out_0,
    pl_clk_en_b_0,
    pl_itf_clk_0,
    pl_ra_clk_0,
    pl_rst_n_0,
    pl_scan_clk_0,
    pl_scan_rst_n_0,
    reset_n,
    soft_rst_n,
    test_irq);
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_BIST:2.0 AI_BIST_0 pl_bist_done" *) output AI_BIST_0_pl_bist_done;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_BIST:2.0 AI_BIST_0 pl_bist_en" *) input AI_BIST_0_pl_bist_en;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_BIST:2.0 AI_BIST_0 pl_bist_err" *) output AI_BIST_0_pl_bist_err;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_BIST:2.0 AI_BIST_0 pl_bist_err_inv" *) output AI_BIST_0_pl_bist_err_inv;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_BIST:2.0 AI_BIST_0 pl_repair_done" *) output AI_BIST_0_pl_repair_done;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_BIST:2.0 AI_BIST_0 pl_repair_fail" *) output AI_BIST_0_pl_repair_fail;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_IRQ:2.0 AI_IRQ_0 pl_int_info" *) output [17:0]AI_IRQ_0_pl_int_info;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_IRQ:2.0 AI_IRQ_0 pl_int_ready" *) input AI_IRQ_0_pl_int_ready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_IRQ:2.0 AI_IRQ_0 pl_int_valid" *) output AI_IRQ_0_pl_int_valid;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_compression_mode" *) input AI_SCAN_0_pl_scan_compression_mode;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_cs" *) input [7:0]AI_SCAN_0_pl_scan_cs;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_en" *) input AI_SCAN_0_pl_scan_en;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_in" *) input [63:0]AI_SCAN_0_pl_scan_in;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_mode_b" *) input AI_SCAN_0_pl_scan_mode_b;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_occ_bypass" *) input AI_SCAN_0_pl_scan_occ_bypass;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_occ_mode" *) input AI_SCAN_0_pl_scan_occ_mode;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_occ_reset" *) input AI_SCAN_0_pl_scan_occ_reset;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_out" *) output [63:0]AI_SCAN_0_pl_scan_out;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_wrp_mode" *) input AI_SCAN_0_pl_scan_wrp_mode;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_SCAN:2.0 AI_SCAN_0 pl_scan_wrp_shift" *) input AI_SCAN_0_pl_scan_wrp_shift;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME BYolo_GP0, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_gp_axi_aclk, DATA_WIDTH 32, FREQ_HZ 100000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 12, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 0, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) output [31:0]BYolo_GP0_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARBURST" *) output [1:0]BYolo_GP0_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARCACHE" *) output [3:0]BYolo_GP0_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARID" *) output [11:0]BYolo_GP0_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARLEN" *) output [3:0]BYolo_GP0_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARLOCK" *) output [1:0]BYolo_GP0_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARPROT" *) output [2:0]BYolo_GP0_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARQOS" *) output [3:0]BYolo_GP0_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARREADY" *) input [0:0]BYolo_GP0_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARSIZE" *) output [2:0]BYolo_GP0_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 ARVALID" *) output [0:0]BYolo_GP0_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWADDR" *) output [31:0]BYolo_GP0_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWBURST" *) output [1:0]BYolo_GP0_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWCACHE" *) output [3:0]BYolo_GP0_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWID" *) output [11:0]BYolo_GP0_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWLEN" *) output [3:0]BYolo_GP0_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWLOCK" *) output [1:0]BYolo_GP0_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWPROT" *) output [2:0]BYolo_GP0_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWQOS" *) output [3:0]BYolo_GP0_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWREADY" *) input [0:0]BYolo_GP0_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWSIZE" *) output [2:0]BYolo_GP0_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 AWVALID" *) output [0:0]BYolo_GP0_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 BID" *) input [11:0]BYolo_GP0_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 BREADY" *) output [0:0]BYolo_GP0_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 BRESP" *) input [1:0]BYolo_GP0_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 BVALID" *) input [0:0]BYolo_GP0_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 RDATA" *) input [31:0]BYolo_GP0_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 RID" *) input [11:0]BYolo_GP0_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 RLAST" *) input [0:0]BYolo_GP0_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 RREADY" *) output [0:0]BYolo_GP0_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 RRESP" *) input [1:0]BYolo_GP0_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 RVALID" *) input [0:0]BYolo_GP0_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 WDATA" *) output [31:0]BYolo_GP0_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 WID" *) output [11:0]BYolo_GP0_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 WLAST" *) output [0:0]BYolo_GP0_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 WREADY" *) input [0:0]BYolo_GP0_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 WSTRB" *) output [3:0]BYolo_GP0_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP0 WVALID" *) output [0:0]BYolo_GP0_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME BYolo_GP1, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_gp_axi_aclk, DATA_WIDTH 32, FREQ_HZ 100000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 12, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 0, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) output [31:0]BYolo_GP1_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARBURST" *) output [1:0]BYolo_GP1_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARCACHE" *) output [3:0]BYolo_GP1_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARID" *) output [11:0]BYolo_GP1_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARLEN" *) output [3:0]BYolo_GP1_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARLOCK" *) output [1:0]BYolo_GP1_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARPROT" *) output [2:0]BYolo_GP1_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARQOS" *) output [3:0]BYolo_GP1_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARREADY" *) input [0:0]BYolo_GP1_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARSIZE" *) output [2:0]BYolo_GP1_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 ARVALID" *) output [0:0]BYolo_GP1_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWADDR" *) output [31:0]BYolo_GP1_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWBURST" *) output [1:0]BYolo_GP1_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWCACHE" *) output [3:0]BYolo_GP1_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWID" *) output [11:0]BYolo_GP1_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWLEN" *) output [3:0]BYolo_GP1_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWLOCK" *) output [1:0]BYolo_GP1_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWPROT" *) output [2:0]BYolo_GP1_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWQOS" *) output [3:0]BYolo_GP1_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWREADY" *) input [0:0]BYolo_GP1_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWSIZE" *) output [2:0]BYolo_GP1_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 AWVALID" *) output [0:0]BYolo_GP1_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 BID" *) input [11:0]BYolo_GP1_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 BREADY" *) output [0:0]BYolo_GP1_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 BRESP" *) input [1:0]BYolo_GP1_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 BVALID" *) input [0:0]BYolo_GP1_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 RDATA" *) input [31:0]BYolo_GP1_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 RID" *) input [11:0]BYolo_GP1_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 RLAST" *) input [0:0]BYolo_GP1_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 RREADY" *) output [0:0]BYolo_GP1_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 RRESP" *) input [1:0]BYolo_GP1_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 RVALID" *) input [0:0]BYolo_GP1_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 WDATA" *) output [31:0]BYolo_GP1_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 WID" *) output [11:0]BYolo_GP1_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 WLAST" *) output [0:0]BYolo_GP1_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 WREADY" *) input [0:0]BYolo_GP1_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 WSTRB" *) output [3:0]BYolo_GP1_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 BYolo_GP1 WVALID" *) output [0:0]BYolo_GP1_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 ADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME DDR_0, AXI_ARBITRATION_SCHEME TDM, BURST_LENGTH 8, CAN_DEBUG false, CAS_LATENCY 11, CAS_WRITE_LATENCY 11, CS_ENABLED true, DATA_MASK_ENABLED true, DATA_WIDTH 8, MEMORY_TYPE COMPONENTS, MEM_ADDR_MAP ROW_COLUMN_BANK, SLOT Single, TIMEPERIOD_PS 1250" *) inout [14:0]DDR_0_addr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 BA" *) inout [2:0]DDR_0_ba;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 CAS_N" *) inout DDR_0_cas_n;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 CK_N" *) inout DDR_0_ck_n;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 CK_P" *) inout DDR_0_ck_p;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 CKE" *) inout DDR_0_cke;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 CS_N" *) inout DDR_0_cs_n;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 DM" *) inout [3:0]DDR_0_dm;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 DQ" *) inout [31:0]DDR_0_dq;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 DQS_N" *) inout [3:0]DDR_0_dqs_n;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 DQS_P" *) inout [3:0]DDR_0_dqs_p;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 ODT" *) inout DDR_0_odt;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 RAS_N" *) inout DDR_0_ras_n;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 RESET_N" *) inout DDR_0_reset_n;
  (* X_INTERFACE_INFO = "xilinx.com:interface:ddrx:1.0 DDR_0 WE_N" *) inout DDR_0_we_n;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK.FCLK_CLK0_0 CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME CLK.FCLK_CLK0_0, CLK_DOMAIN ps_ai_processing_system7_0_0_FCLK_CLK0, FREQ_HZ 50000000, INSERT_VIP 0, PHASE 0.000" *) output FCLK_CLK0_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 RST.FCLK_RESET0_N_0 RST" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME RST.FCLK_RESET0_N_0, INSERT_VIP 0, POLARITY ACTIVE_LOW" *) output FCLK_RESET0_N_0;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:fixedio:1.0 FIXED_IO_0 DDR_VRN" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME FIXED_IO_0, CAN_DEBUG false" *) inout FIXED_IO_0_ddr_vrn;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:fixedio:1.0 FIXED_IO_0 DDR_VRP" *) inout FIXED_IO_0_ddr_vrp;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:fixedio:1.0 FIXED_IO_0 MIO" *) inout [53:0]FIXED_IO_0_mio;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:fixedio:1.0 FIXED_IO_0 PS_CLK" *) inout FIXED_IO_0_ps_clk;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:fixedio:1.0 FIXED_IO_0 PS_PORB" *) inout FIXED_IO_0_ps_porb;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:fixedio:1.0 FIXED_IO_0 PS_SRSTB" *) inout FIXED_IO_0_ps_srstb;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_araddr" *) output [26:0]M_AI_HP_0_pl_araddr;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_arinfo" *) output [5:0]M_AI_HP_0_pl_arinfo;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_arlast" *) output M_AI_HP_0_pl_arlast;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_arready" *) input M_AI_HP_0_pl_arready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_arvalid" *) output M_AI_HP_0_pl_arvalid;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_awaddr" *) output [26:0]M_AI_HP_0_pl_awaddr;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_awdata" *) output [511:0]M_AI_HP_0_pl_awdata;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_awen" *) output [63:0]M_AI_HP_0_pl_awen;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_awinfo" *) output [5:0]M_AI_HP_0_pl_awinfo;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_awlast" *) output M_AI_HP_0_pl_awlast;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_awready" *) input M_AI_HP_0_pl_awready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_awvalid" *) output M_AI_HP_0_pl_awvalid;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_bready" *) output M_AI_HP_0_pl_bready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_bvalid" *) input M_AI_HP_0_pl_bvalid;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_rdata" *) input [511:0]M_AI_HP_0_pl_rdata;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_rlast" *) input M_AI_HP_0_pl_rlast;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_rready" *) output M_AI_HP_0_pl_rready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_HP:2.0 M_AI_HP_0 pl_rvalid" *) input M_AI_HP_0_pl_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:jtag:2.0 PJTAG_0 TCK" *) input PJTAG_0_tck;
  (* X_INTERFACE_INFO = "xilinx.com:interface:jtag:2.0 PJTAG_0 TDI" *) input PJTAG_0_tdi;
  (* X_INTERFACE_INFO = "xilinx.com:interface:jtag:2.0 PJTAG_0 TDO" *) output PJTAG_0_tdo;
  (* X_INTERFACE_INFO = "xilinx.com:interface:jtag:2.0 PJTAG_0 TMS" *) input PJTAG_0_tms;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_araddr" *) input [15:0]S_AI_GP_0_pl_ra_araddr;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_arready" *) output S_AI_GP_0_pl_ra_arready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_arvalid" *) input S_AI_GP_0_pl_ra_arvalid;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_awaddr" *) input [15:0]S_AI_GP_0_pl_ra_awaddr;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_awdata" *) input [31:0]S_AI_GP_0_pl_ra_awdata;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_awready" *) output S_AI_GP_0_pl_ra_awready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_awvalid" *) input S_AI_GP_0_pl_ra_awvalid;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_rdata" *) output [31:0]S_AI_GP_0_pl_ra_rdata;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_rready" *) input S_AI_GP_0_pl_ra_rready;
  (* X_INTERFACE_INFO = "fmsh.com:user:AI_GP:2.0 S_AI_GP_0 pl_ra_rvalid" *) output S_AI_GP_0_pl_ra_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXI_HP0_0, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_hp_axi_aclk, DATA_WIDTH 64, FREQ_HZ 200000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 6, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 1, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) input [31:0]S_AXI_HP0_0_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARBURST" *) input [1:0]S_AXI_HP0_0_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARCACHE" *) input [3:0]S_AXI_HP0_0_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARID" *) input [5:0]S_AXI_HP0_0_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARLEN" *) input [3:0]S_AXI_HP0_0_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARLOCK" *) input [1:0]S_AXI_HP0_0_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARPROT" *) input [2:0]S_AXI_HP0_0_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARQOS" *) input [3:0]S_AXI_HP0_0_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARREADY" *) output S_AXI_HP0_0_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARSIZE" *) input [2:0]S_AXI_HP0_0_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 ARVALID" *) input S_AXI_HP0_0_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWADDR" *) input [31:0]S_AXI_HP0_0_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWBURST" *) input [1:0]S_AXI_HP0_0_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWCACHE" *) input [3:0]S_AXI_HP0_0_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWID" *) input [5:0]S_AXI_HP0_0_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWLEN" *) input [3:0]S_AXI_HP0_0_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWLOCK" *) input [1:0]S_AXI_HP0_0_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWPROT" *) input [2:0]S_AXI_HP0_0_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWQOS" *) input [3:0]S_AXI_HP0_0_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWREADY" *) output S_AXI_HP0_0_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWSIZE" *) input [2:0]S_AXI_HP0_0_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 AWVALID" *) input S_AXI_HP0_0_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 BID" *) output [5:0]S_AXI_HP0_0_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 BREADY" *) input S_AXI_HP0_0_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 BRESP" *) output [1:0]S_AXI_HP0_0_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 BVALID" *) output S_AXI_HP0_0_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 RDATA" *) output [63:0]S_AXI_HP0_0_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 RID" *) output [5:0]S_AXI_HP0_0_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 RLAST" *) output S_AXI_HP0_0_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 RREADY" *) input S_AXI_HP0_0_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 RRESP" *) output [1:0]S_AXI_HP0_0_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 RVALID" *) output S_AXI_HP0_0_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 WDATA" *) input [63:0]S_AXI_HP0_0_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 WID" *) input [5:0]S_AXI_HP0_0_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 WLAST" *) input S_AXI_HP0_0_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 WREADY" *) output S_AXI_HP0_0_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 WSTRB" *) input [7:0]S_AXI_HP0_0_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP0_0 WVALID" *) input S_AXI_HP0_0_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP0_FIFO_CTRL_0 RACOUNT" *) output [2:0]S_AXI_HP0_FIFO_CTRL_0_racount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP0_FIFO_CTRL_0 RCOUNT" *) output [7:0]S_AXI_HP0_FIFO_CTRL_0_rcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP0_FIFO_CTRL_0 RDISSUECAPEN" *) input S_AXI_HP0_FIFO_CTRL_0_rdissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP0_FIFO_CTRL_0 WACOUNT" *) output [5:0]S_AXI_HP0_FIFO_CTRL_0_wacount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP0_FIFO_CTRL_0 WCOUNT" *) output [7:0]S_AXI_HP0_FIFO_CTRL_0_wcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP0_FIFO_CTRL_0 WRISSUECAPEN" *) input S_AXI_HP0_FIFO_CTRL_0_wrissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXI_HP1_0, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_hp_axi_aclk, DATA_WIDTH 64, FREQ_HZ 200000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 6, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 1, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) input [31:0]S_AXI_HP1_0_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARBURST" *) input [1:0]S_AXI_HP1_0_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARCACHE" *) input [3:0]S_AXI_HP1_0_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARID" *) input [5:0]S_AXI_HP1_0_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARLEN" *) input [3:0]S_AXI_HP1_0_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARLOCK" *) input [1:0]S_AXI_HP1_0_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARPROT" *) input [2:0]S_AXI_HP1_0_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARQOS" *) input [3:0]S_AXI_HP1_0_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARREADY" *) output S_AXI_HP1_0_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARSIZE" *) input [2:0]S_AXI_HP1_0_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 ARVALID" *) input S_AXI_HP1_0_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWADDR" *) input [31:0]S_AXI_HP1_0_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWBURST" *) input [1:0]S_AXI_HP1_0_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWCACHE" *) input [3:0]S_AXI_HP1_0_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWID" *) input [5:0]S_AXI_HP1_0_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWLEN" *) input [3:0]S_AXI_HP1_0_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWLOCK" *) input [1:0]S_AXI_HP1_0_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWPROT" *) input [2:0]S_AXI_HP1_0_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWQOS" *) input [3:0]S_AXI_HP1_0_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWREADY" *) output S_AXI_HP1_0_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWSIZE" *) input [2:0]S_AXI_HP1_0_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 AWVALID" *) input S_AXI_HP1_0_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 BID" *) output [5:0]S_AXI_HP1_0_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 BREADY" *) input S_AXI_HP1_0_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 BRESP" *) output [1:0]S_AXI_HP1_0_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 BVALID" *) output S_AXI_HP1_0_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 RDATA" *) output [63:0]S_AXI_HP1_0_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 RID" *) output [5:0]S_AXI_HP1_0_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 RLAST" *) output S_AXI_HP1_0_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 RREADY" *) input S_AXI_HP1_0_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 RRESP" *) output [1:0]S_AXI_HP1_0_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 RVALID" *) output S_AXI_HP1_0_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 WDATA" *) input [63:0]S_AXI_HP1_0_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 WID" *) input [5:0]S_AXI_HP1_0_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 WLAST" *) input S_AXI_HP1_0_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 WREADY" *) output S_AXI_HP1_0_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 WSTRB" *) input [7:0]S_AXI_HP1_0_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP1_0 WVALID" *) input S_AXI_HP1_0_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP1_FIFO_CTRL_0 RACOUNT" *) output [2:0]S_AXI_HP1_FIFO_CTRL_0_racount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP1_FIFO_CTRL_0 RCOUNT" *) output [7:0]S_AXI_HP1_FIFO_CTRL_0_rcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP1_FIFO_CTRL_0 RDISSUECAPEN" *) input S_AXI_HP1_FIFO_CTRL_0_rdissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP1_FIFO_CTRL_0 WACOUNT" *) output [5:0]S_AXI_HP1_FIFO_CTRL_0_wacount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP1_FIFO_CTRL_0 WCOUNT" *) output [7:0]S_AXI_HP1_FIFO_CTRL_0_wcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP1_FIFO_CTRL_0 WRISSUECAPEN" *) input S_AXI_HP1_FIFO_CTRL_0_wrissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXI_HP2_0, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_hp_axi_aclk, DATA_WIDTH 64, FREQ_HZ 200000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 5, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 1, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) input [31:0]S_AXI_HP2_0_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARBURST" *) input [1:0]S_AXI_HP2_0_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARCACHE" *) input [3:0]S_AXI_HP2_0_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARID" *) input [4:0]S_AXI_HP2_0_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARLEN" *) input [3:0]S_AXI_HP2_0_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARLOCK" *) input [1:0]S_AXI_HP2_0_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARPROT" *) input [2:0]S_AXI_HP2_0_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARQOS" *) input [3:0]S_AXI_HP2_0_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARREADY" *) output S_AXI_HP2_0_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARSIZE" *) input [2:0]S_AXI_HP2_0_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 ARVALID" *) input S_AXI_HP2_0_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWADDR" *) input [31:0]S_AXI_HP2_0_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWBURST" *) input [1:0]S_AXI_HP2_0_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWCACHE" *) input [3:0]S_AXI_HP2_0_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWID" *) input [4:0]S_AXI_HP2_0_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWLEN" *) input [3:0]S_AXI_HP2_0_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWLOCK" *) input [1:0]S_AXI_HP2_0_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWPROT" *) input [2:0]S_AXI_HP2_0_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWQOS" *) input [3:0]S_AXI_HP2_0_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWREADY" *) output S_AXI_HP2_0_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWSIZE" *) input [2:0]S_AXI_HP2_0_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 AWVALID" *) input S_AXI_HP2_0_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 BID" *) output [4:0]S_AXI_HP2_0_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 BREADY" *) input S_AXI_HP2_0_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 BRESP" *) output [1:0]S_AXI_HP2_0_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 BVALID" *) output S_AXI_HP2_0_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 RDATA" *) output [63:0]S_AXI_HP2_0_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 RID" *) output [4:0]S_AXI_HP2_0_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 RLAST" *) output S_AXI_HP2_0_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 RREADY" *) input S_AXI_HP2_0_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 RRESP" *) output [1:0]S_AXI_HP2_0_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 RVALID" *) output S_AXI_HP2_0_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 WDATA" *) input [63:0]S_AXI_HP2_0_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 WID" *) input [4:0]S_AXI_HP2_0_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 WLAST" *) input S_AXI_HP2_0_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 WREADY" *) output S_AXI_HP2_0_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 WSTRB" *) input [7:0]S_AXI_HP2_0_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_0 WVALID" *) input S_AXI_HP2_0_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXI_HP2_1, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_hp_axi_aclk, DATA_WIDTH 64, FREQ_HZ 200000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 5, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 1, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) input [31:0]S_AXI_HP2_1_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARBURST" *) input [1:0]S_AXI_HP2_1_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARCACHE" *) input [3:0]S_AXI_HP2_1_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARID" *) input [4:0]S_AXI_HP2_1_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARLEN" *) input [3:0]S_AXI_HP2_1_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARLOCK" *) input [1:0]S_AXI_HP2_1_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARPROT" *) input [2:0]S_AXI_HP2_1_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARQOS" *) input [3:0]S_AXI_HP2_1_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARREADY" *) output S_AXI_HP2_1_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARSIZE" *) input [2:0]S_AXI_HP2_1_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 ARVALID" *) input S_AXI_HP2_1_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWADDR" *) input [31:0]S_AXI_HP2_1_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWBURST" *) input [1:0]S_AXI_HP2_1_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWCACHE" *) input [3:0]S_AXI_HP2_1_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWID" *) input [4:0]S_AXI_HP2_1_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWLEN" *) input [3:0]S_AXI_HP2_1_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWLOCK" *) input [1:0]S_AXI_HP2_1_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWPROT" *) input [2:0]S_AXI_HP2_1_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWQOS" *) input [3:0]S_AXI_HP2_1_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWREADY" *) output S_AXI_HP2_1_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWSIZE" *) input [2:0]S_AXI_HP2_1_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 AWVALID" *) input S_AXI_HP2_1_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 BID" *) output [4:0]S_AXI_HP2_1_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 BREADY" *) input S_AXI_HP2_1_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 BRESP" *) output [1:0]S_AXI_HP2_1_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 BVALID" *) output S_AXI_HP2_1_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 RDATA" *) output [63:0]S_AXI_HP2_1_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 RID" *) output [4:0]S_AXI_HP2_1_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 RLAST" *) output S_AXI_HP2_1_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 RREADY" *) input S_AXI_HP2_1_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 RRESP" *) output [1:0]S_AXI_HP2_1_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 RVALID" *) output S_AXI_HP2_1_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 WDATA" *) input [63:0]S_AXI_HP2_1_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 WID" *) input [4:0]S_AXI_HP2_1_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 WLAST" *) input S_AXI_HP2_1_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 WREADY" *) output S_AXI_HP2_1_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 WSTRB" *) input [7:0]S_AXI_HP2_1_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP2_1 WVALID" *) input S_AXI_HP2_1_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP2_FIFO_CTRL_0 RACOUNT" *) output [2:0]S_AXI_HP2_FIFO_CTRL_0_racount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP2_FIFO_CTRL_0 RCOUNT" *) output [7:0]S_AXI_HP2_FIFO_CTRL_0_rcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP2_FIFO_CTRL_0 RDISSUECAPEN" *) input S_AXI_HP2_FIFO_CTRL_0_rdissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP2_FIFO_CTRL_0 WACOUNT" *) output [5:0]S_AXI_HP2_FIFO_CTRL_0_wacount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP2_FIFO_CTRL_0 WCOUNT" *) output [7:0]S_AXI_HP2_FIFO_CTRL_0_wcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP2_FIFO_CTRL_0 WRISSUECAPEN" *) input S_AXI_HP2_FIFO_CTRL_0_wrissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXI_HP3_0, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_hp_axi_aclk, DATA_WIDTH 64, FREQ_HZ 200000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 6, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 1, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) input [31:0]S_AXI_HP3_0_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARBURST" *) input [1:0]S_AXI_HP3_0_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARCACHE" *) input [3:0]S_AXI_HP3_0_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARID" *) input [5:0]S_AXI_HP3_0_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARLEN" *) input [3:0]S_AXI_HP3_0_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARLOCK" *) input [1:0]S_AXI_HP3_0_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARPROT" *) input [2:0]S_AXI_HP3_0_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARQOS" *) input [3:0]S_AXI_HP3_0_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARREADY" *) output S_AXI_HP3_0_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARSIZE" *) input [2:0]S_AXI_HP3_0_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 ARVALID" *) input S_AXI_HP3_0_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWADDR" *) input [31:0]S_AXI_HP3_0_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWBURST" *) input [1:0]S_AXI_HP3_0_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWCACHE" *) input [3:0]S_AXI_HP3_0_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWID" *) input [5:0]S_AXI_HP3_0_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWLEN" *) input [3:0]S_AXI_HP3_0_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWLOCK" *) input [1:0]S_AXI_HP3_0_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWPROT" *) input [2:0]S_AXI_HP3_0_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWQOS" *) input [3:0]S_AXI_HP3_0_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWREADY" *) output S_AXI_HP3_0_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWSIZE" *) input [2:0]S_AXI_HP3_0_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 AWVALID" *) input S_AXI_HP3_0_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 BID" *) output [5:0]S_AXI_HP3_0_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 BREADY" *) input S_AXI_HP3_0_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 BRESP" *) output [1:0]S_AXI_HP3_0_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 BVALID" *) output S_AXI_HP3_0_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 RDATA" *) output [63:0]S_AXI_HP3_0_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 RID" *) output [5:0]S_AXI_HP3_0_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 RLAST" *) output S_AXI_HP3_0_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 RREADY" *) input S_AXI_HP3_0_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 RRESP" *) output [1:0]S_AXI_HP3_0_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 RVALID" *) output S_AXI_HP3_0_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 WDATA" *) input [63:0]S_AXI_HP3_0_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 WID" *) input [5:0]S_AXI_HP3_0_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 WLAST" *) input S_AXI_HP3_0_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 WREADY" *) output S_AXI_HP3_0_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 WSTRB" *) input [7:0]S_AXI_HP3_0_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI_HP3_0 WVALID" *) input S_AXI_HP3_0_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP3_FIFO_CTRL_0 RACOUNT" *) output [2:0]S_AXI_HP3_FIFO_CTRL_0_racount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP3_FIFO_CTRL_0 RCOUNT" *) output [7:0]S_AXI_HP3_FIFO_CTRL_0_rcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP3_FIFO_CTRL_0 RDISSUECAPEN" *) input S_AXI_HP3_FIFO_CTRL_0_rdissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP3_FIFO_CTRL_0 WACOUNT" *) output [5:0]S_AXI_HP3_FIFO_CTRL_0_wacount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP3_FIFO_CTRL_0 WCOUNT" *) output [7:0]S_AXI_HP3_FIFO_CTRL_0_wcount;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:hpstatusctrl:1.0 S_AXI_HP3_FIFO_CTRL_0 WRISSUECAPEN" *) input S_AXI_HP3_FIFO_CTRL_0_wrissuecapen;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:usbctrl:1.0 USBIND_0_0 PORT_INDCTL" *) output [1:0]USBIND_0_0_port_indctl;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:usbctrl:1.0 USBIND_0_0 VBUS_PWRFAULT" *) input USBIND_0_0_vbus_pwrfault;
  (* X_INTERFACE_INFO = "xilinx.com:display_processing_system7:usbctrl:1.0 USBIND_0_0 VBUS_PWRSELECT" *) output USBIND_0_0_vbus_pwrselect;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME User_GP0, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_gp_axi_aclk, DATA_WIDTH 32, FREQ_HZ 100000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 12, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 0, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) output [31:0]User_GP0_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARBURST" *) output [1:0]User_GP0_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARCACHE" *) output [3:0]User_GP0_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARID" *) output [11:0]User_GP0_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARLEN" *) output [3:0]User_GP0_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARLOCK" *) output [1:0]User_GP0_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARPROT" *) output [2:0]User_GP0_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARQOS" *) output [3:0]User_GP0_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARREADY" *) input [0:0]User_GP0_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARSIZE" *) output [2:0]User_GP0_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 ARVALID" *) output [0:0]User_GP0_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWADDR" *) output [31:0]User_GP0_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWBURST" *) output [1:0]User_GP0_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWCACHE" *) output [3:0]User_GP0_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWID" *) output [11:0]User_GP0_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWLEN" *) output [3:0]User_GP0_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWLOCK" *) output [1:0]User_GP0_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWPROT" *) output [2:0]User_GP0_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWQOS" *) output [3:0]User_GP0_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWREADY" *) input [0:0]User_GP0_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWSIZE" *) output [2:0]User_GP0_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 AWVALID" *) output [0:0]User_GP0_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 BID" *) input [11:0]User_GP0_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 BREADY" *) output [0:0]User_GP0_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 BRESP" *) input [1:0]User_GP0_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 BVALID" *) input [0:0]User_GP0_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 RDATA" *) input [31:0]User_GP0_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 RID" *) input [11:0]User_GP0_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 RLAST" *) input [0:0]User_GP0_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 RREADY" *) output [0:0]User_GP0_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 RRESP" *) input [1:0]User_GP0_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 RVALID" *) input [0:0]User_GP0_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 WDATA" *) output [31:0]User_GP0_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 WID" *) output [11:0]User_GP0_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 WLAST" *) output [0:0]User_GP0_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 WREADY" *) input [0:0]User_GP0_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 WSTRB" *) output [3:0]User_GP0_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP0 WVALID" *) output [0:0]User_GP0_wvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARADDR" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME User_GP1, ADDR_WIDTH 32, ARUSER_WIDTH 0, AWUSER_WIDTH 0, BUSER_WIDTH 0, CLK_DOMAIN exdes_gp_axi_aclk, DATA_WIDTH 32, FREQ_HZ 100000000, HAS_BRESP 1, HAS_BURST 1, HAS_CACHE 1, HAS_LOCK 1, HAS_PROT 1, HAS_QOS 1, HAS_REGION 0, HAS_RRESP 1, HAS_WSTRB 1, ID_WIDTH 12, INSERT_VIP 0, MAX_BURST_LENGTH 16, NUM_READ_OUTSTANDING 8, NUM_READ_THREADS 1, NUM_WRITE_OUTSTANDING 8, NUM_WRITE_THREADS 1, PHASE 0.000, PROTOCOL AXI3, READ_WRITE_MODE READ_WRITE, RUSER_BITS_PER_BYTE 0, RUSER_WIDTH 0, SUPPORTS_NARROW_BURST 0, WUSER_BITS_PER_BYTE 0, WUSER_WIDTH 0" *) output [31:0]User_GP1_araddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARBURST" *) output [1:0]User_GP1_arburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARCACHE" *) output [3:0]User_GP1_arcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARID" *) output [11:0]User_GP1_arid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARLEN" *) output [3:0]User_GP1_arlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARLOCK" *) output [1:0]User_GP1_arlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARPROT" *) output [2:0]User_GP1_arprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARQOS" *) output [3:0]User_GP1_arqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARREADY" *) input [0:0]User_GP1_arready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARSIZE" *) output [2:0]User_GP1_arsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 ARVALID" *) output [0:0]User_GP1_arvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWADDR" *) output [31:0]User_GP1_awaddr;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWBURST" *) output [1:0]User_GP1_awburst;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWCACHE" *) output [3:0]User_GP1_awcache;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWID" *) output [11:0]User_GP1_awid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWLEN" *) output [3:0]User_GP1_awlen;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWLOCK" *) output [1:0]User_GP1_awlock;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWPROT" *) output [2:0]User_GP1_awprot;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWQOS" *) output [3:0]User_GP1_awqos;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWREADY" *) input [0:0]User_GP1_awready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWSIZE" *) output [2:0]User_GP1_awsize;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 AWVALID" *) output [0:0]User_GP1_awvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 BID" *) input [11:0]User_GP1_bid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 BREADY" *) output [0:0]User_GP1_bready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 BRESP" *) input [1:0]User_GP1_bresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 BVALID" *) input [0:0]User_GP1_bvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 RDATA" *) input [31:0]User_GP1_rdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 RID" *) input [11:0]User_GP1_rid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 RLAST" *) input [0:0]User_GP1_rlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 RREADY" *) output [0:0]User_GP1_rready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 RRESP" *) input [1:0]User_GP1_rresp;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 RVALID" *) input [0:0]User_GP1_rvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 WDATA" *) output [31:0]User_GP1_wdata;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 WID" *) output [11:0]User_GP1_wid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 WLAST" *) output [0:0]User_GP1_wlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 WREADY" *) input [0:0]User_GP1_wready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 WSTRB" *) output [3:0]User_GP1_wstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 User_GP1 WVALID" *) output [0:0]User_GP1_wvalid;
  input ai_irq;
  input customop_irq;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK.GP_AXI_ACLK CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME CLK.GP_AXI_ACLK, ASSOCIATED_BUSIF BYolo_GP0:BYolo_GP1:User_GP0:User_GP1:gp1_monitor:gp0_monitor:User_GP0, CLK_DOMAIN exdes_gp_axi_aclk, FREQ_HZ 100000000, INSERT_VIP 0, PHASE 0.000" *) input gp_axi_aclk;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK.HP_AXI_ACLK CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME CLK.HP_AXI_ACLK, ASSOCIATED_BUSIF S_AXI_HP0_0:S_AXI_HP1_0:S_AXI_HP2_0:S_AXI_HP3_0:S_AXI_HP2_1, CLK_DOMAIN exdes_hp_axi_aclk, FREQ_HZ 200000000, INSERT_VIP 0, PHASE 0.000" *) input hp_axi_aclk;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK.PL_BIST_CLK_0 CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME CLK.PL_BIST_CLK_0, ASSOCIATED_RESET pl_bist_rstn_0, CLK_DOMAIN ps_ai_pl_bist_clk_0, FREQ_HZ 100000000, INSERT_VIP 0, PHASE 0.000" *) input pl_bist_clk_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 RST.PL_BIST_RSTN_0 RST" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME RST.PL_BIST_RSTN_0, INSERT_VIP 0, POLARITY ACTIVE_LOW" *) input pl_bist_rstn_0;
  output pl_clk_div_out_0;
  input pl_clk_en_b_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK.PL_ITF_CLK_0 CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME CLK.PL_ITF_CLK_0, CLK_DOMAIN ps_ai_pl_itf_clk_0, FREQ_HZ 100000000, INSERT_VIP 0, PHASE 0.000" *) input pl_itf_clk_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK.PL_RA_CLK_0 CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME CLK.PL_RA_CLK_0, CLK_DOMAIN ps_ai_pl_ra_clk_0, FREQ_HZ 100000000, INSERT_VIP 0, PHASE 0.000" *) input pl_ra_clk_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 RST.PL_RST_N_0 RST" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME RST.PL_RST_N_0, INSERT_VIP 0, POLARITY ACTIVE_LOW" *) input pl_rst_n_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK.PL_SCAN_CLK_0 CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME CLK.PL_SCAN_CLK_0, CLK_DOMAIN ps_ai_pl_scan_clk_0, FREQ_HZ 100000000, INSERT_VIP 0, PHASE 0.000" *) input pl_scan_clk_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 RST.PL_SCAN_RST_N_0 RST" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME RST.PL_SCAN_RST_N_0, INSERT_VIP 0, POLARITY ACTIVE_LOW" *) input pl_scan_rst_n_0;
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 RST.RESET_N RST" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME RST.RESET_N, INSERT_VIP 0, POLARITY ACTIVE_LOW" *) input reset_n;
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 RST.SOFT_RST_N RST" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME RST.SOFT_RST_N, INSERT_VIP 0, POLARITY ACTIVE_LOW" *) input soft_rst_n;
  input test_irq;

  wire AI_BIST_0_1_pl_bist_done;
  wire AI_BIST_0_1_pl_bist_en;
  wire AI_BIST_0_1_pl_bist_err;
  wire AI_BIST_0_1_pl_bist_err_inv;
  wire AI_BIST_0_1_pl_repair_done;
  wire AI_BIST_0_1_pl_repair_fail;
  wire AI_SCAN_0_1_pl_scan_compression_mode;
  wire [7:0]AI_SCAN_0_1_pl_scan_cs;
  wire AI_SCAN_0_1_pl_scan_en;
  wire [63:0]AI_SCAN_0_1_pl_scan_in;
  wire AI_SCAN_0_1_pl_scan_mode_b;
  wire AI_SCAN_0_1_pl_scan_occ_bypass;
  wire AI_SCAN_0_1_pl_scan_occ_mode;
  wire AI_SCAN_0_1_pl_scan_occ_reset;
  wire [63:0]AI_SCAN_0_1_pl_scan_out;
  wire AI_SCAN_0_1_pl_scan_wrp_mode;
  wire AI_SCAN_0_1_pl_scan_wrp_shift;
  wire [0:0]ARESETN_1;
  wire [0:0]M00_ARESETN_1;
  wire PJTAG_0_1_TCK;
  wire PJTAG_0_1_TDI;
  wire PJTAG_0_1_TDO;
  wire PJTAG_0_1_TMS;
  wire [31:0]S00_AXI_1_ARADDR;
  wire [1:0]S00_AXI_1_ARBURST;
  wire [3:0]S00_AXI_1_ARCACHE;
  wire [11:0]S00_AXI_1_ARID;
  wire [3:0]S00_AXI_1_ARLEN;
  wire [1:0]S00_AXI_1_ARLOCK;
  wire [2:0]S00_AXI_1_ARPROT;
  wire [3:0]S00_AXI_1_ARQOS;
  wire S00_AXI_1_ARREADY;
  wire [2:0]S00_AXI_1_ARSIZE;
  wire S00_AXI_1_ARVALID;
  wire [31:0]S00_AXI_1_AWADDR;
  wire [1:0]S00_AXI_1_AWBURST;
  wire [3:0]S00_AXI_1_AWCACHE;
  wire [11:0]S00_AXI_1_AWID;
  wire [3:0]S00_AXI_1_AWLEN;
  wire [1:0]S00_AXI_1_AWLOCK;
  wire [2:0]S00_AXI_1_AWPROT;
  wire [3:0]S00_AXI_1_AWQOS;
  wire S00_AXI_1_AWREADY;
  wire [2:0]S00_AXI_1_AWSIZE;
  wire S00_AXI_1_AWVALID;
  wire [11:0]S00_AXI_1_BID;
  wire S00_AXI_1_BREADY;
  wire [1:0]S00_AXI_1_BRESP;
  wire S00_AXI_1_BVALID;
  wire [31:0]S00_AXI_1_RDATA;
  wire [11:0]S00_AXI_1_RID;
  wire S00_AXI_1_RLAST;
  wire S00_AXI_1_RREADY;
  wire [1:0]S00_AXI_1_RRESP;
  wire S00_AXI_1_RVALID;
  wire [31:0]S00_AXI_1_WDATA;
  wire [11:0]S00_AXI_1_WID;
  wire S00_AXI_1_WLAST;
  wire S00_AXI_1_WREADY;
  wire [3:0]S00_AXI_1_WSTRB;
  wire S00_AXI_1_WVALID;
  wire [31:0]S00_AXI_2_ARADDR;
  wire [1:0]S00_AXI_2_ARBURST;
  wire [3:0]S00_AXI_2_ARCACHE;
  wire [11:0]S00_AXI_2_ARID;
  wire [3:0]S00_AXI_2_ARLEN;
  wire [1:0]S00_AXI_2_ARLOCK;
  wire [2:0]S00_AXI_2_ARPROT;
  wire [3:0]S00_AXI_2_ARQOS;
  wire S00_AXI_2_ARREADY;
  wire [2:0]S00_AXI_2_ARSIZE;
  wire S00_AXI_2_ARVALID;
  wire [31:0]S00_AXI_2_AWADDR;
  wire [1:0]S00_AXI_2_AWBURST;
  wire [3:0]S00_AXI_2_AWCACHE;
  wire [11:0]S00_AXI_2_AWID;
  wire [3:0]S00_AXI_2_AWLEN;
  wire [1:0]S00_AXI_2_AWLOCK;
  wire [2:0]S00_AXI_2_AWPROT;
  wire [3:0]S00_AXI_2_AWQOS;
  wire S00_AXI_2_AWREADY;
  wire [2:0]S00_AXI_2_AWSIZE;
  wire S00_AXI_2_AWVALID;
  wire [11:0]S00_AXI_2_BID;
  wire S00_AXI_2_BREADY;
  wire [1:0]S00_AXI_2_BRESP;
  wire S00_AXI_2_BVALID;
  wire [31:0]S00_AXI_2_RDATA;
  wire [11:0]S00_AXI_2_RID;
  wire S00_AXI_2_RLAST;
  wire S00_AXI_2_RREADY;
  wire [1:0]S00_AXI_2_RRESP;
  wire S00_AXI_2_RVALID;
  wire [31:0]S00_AXI_2_WDATA;
  wire [11:0]S00_AXI_2_WID;
  wire S00_AXI_2_WLAST;
  wire S00_AXI_2_WREADY;
  wire [3:0]S00_AXI_2_WSTRB;
  wire S00_AXI_2_WVALID;
  wire [15:0]S_AI_GP_0_1_pl_ra_araddr;
  wire S_AI_GP_0_1_pl_ra_arready;
  wire S_AI_GP_0_1_pl_ra_arvalid;
  wire [15:0]S_AI_GP_0_1_pl_ra_awaddr;
  wire [31:0]S_AI_GP_0_1_pl_ra_awdata;
  wire S_AI_GP_0_1_pl_ra_awready;
  wire S_AI_GP_0_1_pl_ra_awvalid;
  wire [31:0]S_AI_GP_0_1_pl_ra_rdata;
  wire S_AI_GP_0_1_pl_ra_rready;
  wire S_AI_GP_0_1_pl_ra_rvalid;
  wire [31:0]S_AXI_HP0_0_1_ARADDR;
  wire [1:0]S_AXI_HP0_0_1_ARBURST;
  wire [3:0]S_AXI_HP0_0_1_ARCACHE;
  wire [5:0]S_AXI_HP0_0_1_ARID;
  wire [3:0]S_AXI_HP0_0_1_ARLEN;
  wire [1:0]S_AXI_HP0_0_1_ARLOCK;
  wire [2:0]S_AXI_HP0_0_1_ARPROT;
  wire [3:0]S_AXI_HP0_0_1_ARQOS;
  wire S_AXI_HP0_0_1_ARREADY;
  wire [2:0]S_AXI_HP0_0_1_ARSIZE;
  wire S_AXI_HP0_0_1_ARVALID;
  wire [31:0]S_AXI_HP0_0_1_AWADDR;
  wire [1:0]S_AXI_HP0_0_1_AWBURST;
  wire [3:0]S_AXI_HP0_0_1_AWCACHE;
  wire [5:0]S_AXI_HP0_0_1_AWID;
  wire [3:0]S_AXI_HP0_0_1_AWLEN;
  wire [1:0]S_AXI_HP0_0_1_AWLOCK;
  wire [2:0]S_AXI_HP0_0_1_AWPROT;
  wire [3:0]S_AXI_HP0_0_1_AWQOS;
  wire S_AXI_HP0_0_1_AWREADY;
  wire [2:0]S_AXI_HP0_0_1_AWSIZE;
  wire S_AXI_HP0_0_1_AWVALID;
  wire [5:0]S_AXI_HP0_0_1_BID;
  wire S_AXI_HP0_0_1_BREADY;
  wire [1:0]S_AXI_HP0_0_1_BRESP;
  wire S_AXI_HP0_0_1_BVALID;
  wire [63:0]S_AXI_HP0_0_1_RDATA;
  wire [5:0]S_AXI_HP0_0_1_RID;
  wire S_AXI_HP0_0_1_RLAST;
  wire S_AXI_HP0_0_1_RREADY;
  wire [1:0]S_AXI_HP0_0_1_RRESP;
  wire S_AXI_HP0_0_1_RVALID;
  wire [63:0]S_AXI_HP0_0_1_WDATA;
  wire [5:0]S_AXI_HP0_0_1_WID;
  wire S_AXI_HP0_0_1_WLAST;
  wire S_AXI_HP0_0_1_WREADY;
  wire [7:0]S_AXI_HP0_0_1_WSTRB;
  wire S_AXI_HP0_0_1_WVALID;
  wire [2:0]S_AXI_HP0_FIFO_CTRL_0_1_RACOUNT;
  wire [7:0]S_AXI_HP0_FIFO_CTRL_0_1_RCOUNT;
  wire S_AXI_HP0_FIFO_CTRL_0_1_RDISSUECAPEN;
  wire [5:0]S_AXI_HP0_FIFO_CTRL_0_1_WACOUNT;
  wire [7:0]S_AXI_HP0_FIFO_CTRL_0_1_WCOUNT;
  wire S_AXI_HP0_FIFO_CTRL_0_1_WRISSUECAPEN;
  wire [31:0]S_AXI_HP1_0_1_ARADDR;
  wire [1:0]S_AXI_HP1_0_1_ARBURST;
  wire [3:0]S_AXI_HP1_0_1_ARCACHE;
  wire [5:0]S_AXI_HP1_0_1_ARID;
  wire [3:0]S_AXI_HP1_0_1_ARLEN;
  wire [1:0]S_AXI_HP1_0_1_ARLOCK;
  wire [2:0]S_AXI_HP1_0_1_ARPROT;
  wire [3:0]S_AXI_HP1_0_1_ARQOS;
  wire S_AXI_HP1_0_1_ARREADY;
  wire [2:0]S_AXI_HP1_0_1_ARSIZE;
  wire S_AXI_HP1_0_1_ARVALID;
  wire [31:0]S_AXI_HP1_0_1_AWADDR;
  wire [1:0]S_AXI_HP1_0_1_AWBURST;
  wire [3:0]S_AXI_HP1_0_1_AWCACHE;
  wire [5:0]S_AXI_HP1_0_1_AWID;
  wire [3:0]S_AXI_HP1_0_1_AWLEN;
  wire [1:0]S_AXI_HP1_0_1_AWLOCK;
  wire [2:0]S_AXI_HP1_0_1_AWPROT;
  wire [3:0]S_AXI_HP1_0_1_AWQOS;
  wire S_AXI_HP1_0_1_AWREADY;
  wire [2:0]S_AXI_HP1_0_1_AWSIZE;
  wire S_AXI_HP1_0_1_AWVALID;
  wire [5:0]S_AXI_HP1_0_1_BID;
  wire S_AXI_HP1_0_1_BREADY;
  wire [1:0]S_AXI_HP1_0_1_BRESP;
  wire S_AXI_HP1_0_1_BVALID;
  wire [63:0]S_AXI_HP1_0_1_RDATA;
  wire [5:0]S_AXI_HP1_0_1_RID;
  wire S_AXI_HP1_0_1_RLAST;
  wire S_AXI_HP1_0_1_RREADY;
  wire [1:0]S_AXI_HP1_0_1_RRESP;
  wire S_AXI_HP1_0_1_RVALID;
  wire [63:0]S_AXI_HP1_0_1_WDATA;
  wire [5:0]S_AXI_HP1_0_1_WID;
  wire S_AXI_HP1_0_1_WLAST;
  wire S_AXI_HP1_0_1_WREADY;
  wire [7:0]S_AXI_HP1_0_1_WSTRB;
  wire S_AXI_HP1_0_1_WVALID;
  wire [2:0]S_AXI_HP1_FIFO_CTRL_0_1_RACOUNT;
  wire [7:0]S_AXI_HP1_FIFO_CTRL_0_1_RCOUNT;
  wire S_AXI_HP1_FIFO_CTRL_0_1_RDISSUECAPEN;
  wire [5:0]S_AXI_HP1_FIFO_CTRL_0_1_WACOUNT;
  wire [7:0]S_AXI_HP1_FIFO_CTRL_0_1_WCOUNT;
  wire S_AXI_HP1_FIFO_CTRL_0_1_WRISSUECAPEN;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [31:0]S_AXI_HP2_0_1_ARADDR;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_0_1_ARBURST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_0_1_ARCACHE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_0_1_ARID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_0_1_ARLEN;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_0_1_ARLOCK;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_0_1_ARPROT;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_0_1_ARQOS;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_ARREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_0_1_ARSIZE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_ARVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [31:0]S_AXI_HP2_0_1_AWADDR;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_0_1_AWBURST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_0_1_AWCACHE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_0_1_AWID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_0_1_AWLEN;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_0_1_AWLOCK;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_0_1_AWPROT;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_0_1_AWQOS;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_AWREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_0_1_AWSIZE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_AWVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_0_1_BID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_BREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_0_1_BRESP;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_BVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [63:0]S_AXI_HP2_0_1_RDATA;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_0_1_RID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_RLAST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_RREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_0_1_RRESP;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_RVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [63:0]S_AXI_HP2_0_1_WDATA;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_0_1_WID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_WLAST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_WREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [7:0]S_AXI_HP2_0_1_WSTRB;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_0_1_WVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [31:0]S_AXI_HP2_1_1_ARADDR;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_1_1_ARBURST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_1_1_ARCACHE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_1_1_ARID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_1_1_ARLEN;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_1_1_ARLOCK;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_1_1_ARPROT;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_1_1_ARQOS;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_ARREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_1_1_ARSIZE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_ARVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [31:0]S_AXI_HP2_1_1_AWADDR;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_1_1_AWBURST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_1_1_AWCACHE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_1_1_AWID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_1_1_AWLEN;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_1_1_AWLOCK;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_1_1_AWPROT;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]S_AXI_HP2_1_1_AWQOS;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_AWREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]S_AXI_HP2_1_1_AWSIZE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_AWVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_1_1_BID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_BREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_1_1_BRESP;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_BVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [63:0]S_AXI_HP2_1_1_RDATA;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_1_1_RID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_RLAST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_RREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]S_AXI_HP2_1_1_RRESP;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_RVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [63:0]S_AXI_HP2_1_1_WDATA;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [4:0]S_AXI_HP2_1_1_WID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_WLAST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_WREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [7:0]S_AXI_HP2_1_1_WSTRB;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire S_AXI_HP2_1_1_WVALID;
  wire [2:0]S_AXI_HP2_FIFO_CTRL_0_1_RACOUNT;
  wire [7:0]S_AXI_HP2_FIFO_CTRL_0_1_RCOUNT;
  wire S_AXI_HP2_FIFO_CTRL_0_1_RDISSUECAPEN;
  wire [5:0]S_AXI_HP2_FIFO_CTRL_0_1_WACOUNT;
  wire [7:0]S_AXI_HP2_FIFO_CTRL_0_1_WCOUNT;
  wire S_AXI_HP2_FIFO_CTRL_0_1_WRISSUECAPEN;
  wire [31:0]S_AXI_HP3_0_1_ARADDR;
  wire [1:0]S_AXI_HP3_0_1_ARBURST;
  wire [3:0]S_AXI_HP3_0_1_ARCACHE;
  wire [5:0]S_AXI_HP3_0_1_ARID;
  wire [3:0]S_AXI_HP3_0_1_ARLEN;
  wire [1:0]S_AXI_HP3_0_1_ARLOCK;
  wire [2:0]S_AXI_HP3_0_1_ARPROT;
  wire [3:0]S_AXI_HP3_0_1_ARQOS;
  wire S_AXI_HP3_0_1_ARREADY;
  wire [2:0]S_AXI_HP3_0_1_ARSIZE;
  wire S_AXI_HP3_0_1_ARVALID;
  wire [31:0]S_AXI_HP3_0_1_AWADDR;
  wire [1:0]S_AXI_HP3_0_1_AWBURST;
  wire [3:0]S_AXI_HP3_0_1_AWCACHE;
  wire [5:0]S_AXI_HP3_0_1_AWID;
  wire [3:0]S_AXI_HP3_0_1_AWLEN;
  wire [1:0]S_AXI_HP3_0_1_AWLOCK;
  wire [2:0]S_AXI_HP3_0_1_AWPROT;
  wire [3:0]S_AXI_HP3_0_1_AWQOS;
  wire S_AXI_HP3_0_1_AWREADY;
  wire [2:0]S_AXI_HP3_0_1_AWSIZE;
  wire S_AXI_HP3_0_1_AWVALID;
  wire [5:0]S_AXI_HP3_0_1_BID;
  wire S_AXI_HP3_0_1_BREADY;
  wire [1:0]S_AXI_HP3_0_1_BRESP;
  wire S_AXI_HP3_0_1_BVALID;
  wire [63:0]S_AXI_HP3_0_1_RDATA;
  wire [5:0]S_AXI_HP3_0_1_RID;
  wire S_AXI_HP3_0_1_RLAST;
  wire S_AXI_HP3_0_1_RREADY;
  wire [1:0]S_AXI_HP3_0_1_RRESP;
  wire S_AXI_HP3_0_1_RVALID;
  wire [63:0]S_AXI_HP3_0_1_WDATA;
  wire [5:0]S_AXI_HP3_0_1_WID;
  wire S_AXI_HP3_0_1_WLAST;
  wire S_AXI_HP3_0_1_WREADY;
  wire [7:0]S_AXI_HP3_0_1_WSTRB;
  wire S_AXI_HP3_0_1_WVALID;
  wire [2:0]S_AXI_HP3_FIFO_CTRL_0_1_RACOUNT;
  wire [7:0]S_AXI_HP3_FIFO_CTRL_0_1_RCOUNT;
  wire S_AXI_HP3_FIFO_CTRL_0_1_RDISSUECAPEN;
  wire [5:0]S_AXI_HP3_FIFO_CTRL_0_1_WACOUNT;
  wire [7:0]S_AXI_HP3_FIFO_CTRL_0_1_WCOUNT;
  wire S_AXI_HP3_FIFO_CTRL_0_1_WRISSUECAPEN;
  wire ai_irq_1;
  wire [31:0]axi_interconnect_0_M00_AXI_ARADDR;
  wire [1:0]axi_interconnect_0_M00_AXI_ARBURST;
  wire [3:0]axi_interconnect_0_M00_AXI_ARCACHE;
  wire [11:0]axi_interconnect_0_M00_AXI_ARID;
  wire [3:0]axi_interconnect_0_M00_AXI_ARLEN;
  wire [1:0]axi_interconnect_0_M00_AXI_ARLOCK;
  wire [2:0]axi_interconnect_0_M00_AXI_ARPROT;
  wire [3:0]axi_interconnect_0_M00_AXI_ARQOS;
  wire [0:0]axi_interconnect_0_M00_AXI_ARREADY;
  wire [2:0]axi_interconnect_0_M00_AXI_ARSIZE;
  wire [0:0]axi_interconnect_0_M00_AXI_ARVALID;
  wire [31:0]axi_interconnect_0_M00_AXI_AWADDR;
  wire [1:0]axi_interconnect_0_M00_AXI_AWBURST;
  wire [3:0]axi_interconnect_0_M00_AXI_AWCACHE;
  wire [11:0]axi_interconnect_0_M00_AXI_AWID;
  wire [3:0]axi_interconnect_0_M00_AXI_AWLEN;
  wire [1:0]axi_interconnect_0_M00_AXI_AWLOCK;
  wire [2:0]axi_interconnect_0_M00_AXI_AWPROT;
  wire [3:0]axi_interconnect_0_M00_AXI_AWQOS;
  wire [0:0]axi_interconnect_0_M00_AXI_AWREADY;
  wire [2:0]axi_interconnect_0_M00_AXI_AWSIZE;
  wire [0:0]axi_interconnect_0_M00_AXI_AWVALID;
  wire [11:0]axi_interconnect_0_M00_AXI_BID;
  wire [0:0]axi_interconnect_0_M00_AXI_BREADY;
  wire [1:0]axi_interconnect_0_M00_AXI_BRESP;
  wire [0:0]axi_interconnect_0_M00_AXI_BVALID;
  wire [31:0]axi_interconnect_0_M00_AXI_RDATA;
  wire [11:0]axi_interconnect_0_M00_AXI_RID;
  wire [0:0]axi_interconnect_0_M00_AXI_RLAST;
  wire [0:0]axi_interconnect_0_M00_AXI_RREADY;
  wire [1:0]axi_interconnect_0_M00_AXI_RRESP;
  wire [0:0]axi_interconnect_0_M00_AXI_RVALID;
  wire [31:0]axi_interconnect_0_M00_AXI_WDATA;
  wire [11:0]axi_interconnect_0_M00_AXI_WID;
  wire [0:0]axi_interconnect_0_M00_AXI_WLAST;
  wire [0:0]axi_interconnect_0_M00_AXI_WREADY;
  wire [3:0]axi_interconnect_0_M00_AXI_WSTRB;
  wire [0:0]axi_interconnect_0_M00_AXI_WVALID;
  wire [31:0]axi_interconnect_0_M01_AXI_ARADDR;
  wire [1:0]axi_interconnect_0_M01_AXI_ARBURST;
  wire [3:0]axi_interconnect_0_M01_AXI_ARCACHE;
  wire [11:0]axi_interconnect_0_M01_AXI_ARID;
  wire [3:0]axi_interconnect_0_M01_AXI_ARLEN;
  wire [1:0]axi_interconnect_0_M01_AXI_ARLOCK;
  wire [2:0]axi_interconnect_0_M01_AXI_ARPROT;
  wire [3:0]axi_interconnect_0_M01_AXI_ARQOS;
  wire [0:0]axi_interconnect_0_M01_AXI_ARREADY;
  wire [2:0]axi_interconnect_0_M01_AXI_ARSIZE;
  wire [0:0]axi_interconnect_0_M01_AXI_ARVALID;
  wire [31:0]axi_interconnect_0_M01_AXI_AWADDR;
  wire [1:0]axi_interconnect_0_M01_AXI_AWBURST;
  wire [3:0]axi_interconnect_0_M01_AXI_AWCACHE;
  wire [11:0]axi_interconnect_0_M01_AXI_AWID;
  wire [3:0]axi_interconnect_0_M01_AXI_AWLEN;
  wire [1:0]axi_interconnect_0_M01_AXI_AWLOCK;
  wire [2:0]axi_interconnect_0_M01_AXI_AWPROT;
  wire [3:0]axi_interconnect_0_M01_AXI_AWQOS;
  wire [0:0]axi_interconnect_0_M01_AXI_AWREADY;
  wire [2:0]axi_interconnect_0_M01_AXI_AWSIZE;
  wire [0:0]axi_interconnect_0_M01_AXI_AWVALID;
  wire [11:0]axi_interconnect_0_M01_AXI_BID;
  wire [0:0]axi_interconnect_0_M01_AXI_BREADY;
  wire [1:0]axi_interconnect_0_M01_AXI_BRESP;
  wire [0:0]axi_interconnect_0_M01_AXI_BVALID;
  wire [31:0]axi_interconnect_0_M01_AXI_RDATA;
  wire [11:0]axi_interconnect_0_M01_AXI_RID;
  wire [0:0]axi_interconnect_0_M01_AXI_RLAST;
  wire [0:0]axi_interconnect_0_M01_AXI_RREADY;
  wire [1:0]axi_interconnect_0_M01_AXI_RRESP;
  wire [0:0]axi_interconnect_0_M01_AXI_RVALID;
  wire [31:0]axi_interconnect_0_M01_AXI_WDATA;
  wire [11:0]axi_interconnect_0_M01_AXI_WID;
  wire [0:0]axi_interconnect_0_M01_AXI_WLAST;
  wire [0:0]axi_interconnect_0_M01_AXI_WREADY;
  wire [3:0]axi_interconnect_0_M01_AXI_WSTRB;
  wire [0:0]axi_interconnect_0_M01_AXI_WVALID;
  wire [31:0]axi_interconnect_1_M00_AXI_ARADDR;
  wire [1:0]axi_interconnect_1_M00_AXI_ARBURST;
  wire [3:0]axi_interconnect_1_M00_AXI_ARCACHE;
  wire [11:0]axi_interconnect_1_M00_AXI_ARID;
  wire [3:0]axi_interconnect_1_M00_AXI_ARLEN;
  wire [1:0]axi_interconnect_1_M00_AXI_ARLOCK;
  wire [2:0]axi_interconnect_1_M00_AXI_ARPROT;
  wire [3:0]axi_interconnect_1_M00_AXI_ARQOS;
  wire [0:0]axi_interconnect_1_M00_AXI_ARREADY;
  wire [2:0]axi_interconnect_1_M00_AXI_ARSIZE;
  wire [0:0]axi_interconnect_1_M00_AXI_ARVALID;
  wire [31:0]axi_interconnect_1_M00_AXI_AWADDR;
  wire [1:0]axi_interconnect_1_M00_AXI_AWBURST;
  wire [3:0]axi_interconnect_1_M00_AXI_AWCACHE;
  wire [11:0]axi_interconnect_1_M00_AXI_AWID;
  wire [3:0]axi_interconnect_1_M00_AXI_AWLEN;
  wire [1:0]axi_interconnect_1_M00_AXI_AWLOCK;
  wire [2:0]axi_interconnect_1_M00_AXI_AWPROT;
  wire [3:0]axi_interconnect_1_M00_AXI_AWQOS;
  wire [0:0]axi_interconnect_1_M00_AXI_AWREADY;
  wire [2:0]axi_interconnect_1_M00_AXI_AWSIZE;
  wire [0:0]axi_interconnect_1_M00_AXI_AWVALID;
  wire [11:0]axi_interconnect_1_M00_AXI_BID;
  wire [0:0]axi_interconnect_1_M00_AXI_BREADY;
  wire [1:0]axi_interconnect_1_M00_AXI_BRESP;
  wire [0:0]axi_interconnect_1_M00_AXI_BVALID;
  wire [31:0]axi_interconnect_1_M00_AXI_RDATA;
  wire [11:0]axi_interconnect_1_M00_AXI_RID;
  wire [0:0]axi_interconnect_1_M00_AXI_RLAST;
  wire [0:0]axi_interconnect_1_M00_AXI_RREADY;
  wire [1:0]axi_interconnect_1_M00_AXI_RRESP;
  wire [0:0]axi_interconnect_1_M00_AXI_RVALID;
  wire [31:0]axi_interconnect_1_M00_AXI_WDATA;
  wire [11:0]axi_interconnect_1_M00_AXI_WID;
  wire [0:0]axi_interconnect_1_M00_AXI_WLAST;
  wire [0:0]axi_interconnect_1_M00_AXI_WREADY;
  wire [3:0]axi_interconnect_1_M00_AXI_WSTRB;
  wire [0:0]axi_interconnect_1_M00_AXI_WVALID;
  wire [31:0]axi_interconnect_1_M01_AXI_ARADDR;
  wire [1:0]axi_interconnect_1_M01_AXI_ARBURST;
  wire [3:0]axi_interconnect_1_M01_AXI_ARCACHE;
  wire [11:0]axi_interconnect_1_M01_AXI_ARID;
  wire [3:0]axi_interconnect_1_M01_AXI_ARLEN;
  wire [1:0]axi_interconnect_1_M01_AXI_ARLOCK;
  wire [2:0]axi_interconnect_1_M01_AXI_ARPROT;
  wire [3:0]axi_interconnect_1_M01_AXI_ARQOS;
  wire [0:0]axi_interconnect_1_M01_AXI_ARREADY;
  wire [2:0]axi_interconnect_1_M01_AXI_ARSIZE;
  wire [0:0]axi_interconnect_1_M01_AXI_ARVALID;
  wire [31:0]axi_interconnect_1_M01_AXI_AWADDR;
  wire [1:0]axi_interconnect_1_M01_AXI_AWBURST;
  wire [3:0]axi_interconnect_1_M01_AXI_AWCACHE;
  wire [11:0]axi_interconnect_1_M01_AXI_AWID;
  wire [3:0]axi_interconnect_1_M01_AXI_AWLEN;
  wire [1:0]axi_interconnect_1_M01_AXI_AWLOCK;
  wire [2:0]axi_interconnect_1_M01_AXI_AWPROT;
  wire [3:0]axi_interconnect_1_M01_AXI_AWQOS;
  wire [0:0]axi_interconnect_1_M01_AXI_AWREADY;
  wire [2:0]axi_interconnect_1_M01_AXI_AWSIZE;
  wire [0:0]axi_interconnect_1_M01_AXI_AWVALID;
  wire [11:0]axi_interconnect_1_M01_AXI_BID;
  wire [0:0]axi_interconnect_1_M01_AXI_BREADY;
  wire [1:0]axi_interconnect_1_M01_AXI_BRESP;
  wire [0:0]axi_interconnect_1_M01_AXI_BVALID;
  wire [31:0]axi_interconnect_1_M01_AXI_RDATA;
  wire [11:0]axi_interconnect_1_M01_AXI_RID;
  wire [0:0]axi_interconnect_1_M01_AXI_RLAST;
  wire [0:0]axi_interconnect_1_M01_AXI_RREADY;
  wire [1:0]axi_interconnect_1_M01_AXI_RRESP;
  wire [0:0]axi_interconnect_1_M01_AXI_RVALID;
  wire [31:0]axi_interconnect_1_M01_AXI_WDATA;
  wire [11:0]axi_interconnect_1_M01_AXI_WID;
  wire [0:0]axi_interconnect_1_M01_AXI_WLAST;
  wire [0:0]axi_interconnect_1_M01_AXI_WREADY;
  wire [3:0]axi_interconnect_1_M01_AXI_WSTRB;
  wire [0:0]axi_interconnect_1_M01_AXI_WVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [31:0]axi_interconnect_4_M00_AXI_ARADDR;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]axi_interconnect_4_M00_AXI_ARBURST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]axi_interconnect_4_M00_AXI_ARCACHE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [5:0]axi_interconnect_4_M00_AXI_ARID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]axi_interconnect_4_M00_AXI_ARLEN;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]axi_interconnect_4_M00_AXI_ARLOCK;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]axi_interconnect_4_M00_AXI_ARPROT;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]axi_interconnect_4_M00_AXI_ARQOS;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_ARREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]axi_interconnect_4_M00_AXI_ARSIZE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_ARVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [31:0]axi_interconnect_4_M00_AXI_AWADDR;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]axi_interconnect_4_M00_AXI_AWBURST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]axi_interconnect_4_M00_AXI_AWCACHE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [5:0]axi_interconnect_4_M00_AXI_AWID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]axi_interconnect_4_M00_AXI_AWLEN;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]axi_interconnect_4_M00_AXI_AWLOCK;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]axi_interconnect_4_M00_AXI_AWPROT;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [3:0]axi_interconnect_4_M00_AXI_AWQOS;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_AWREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [2:0]axi_interconnect_4_M00_AXI_AWSIZE;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_AWVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [5:0]axi_interconnect_4_M00_AXI_BID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_BREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]axi_interconnect_4_M00_AXI_BRESP;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_BVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [63:0]axi_interconnect_4_M00_AXI_RDATA;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [5:0]axi_interconnect_4_M00_AXI_RID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_RLAST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_RREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [1:0]axi_interconnect_4_M00_AXI_RRESP;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_RVALID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [63:0]axi_interconnect_4_M00_AXI_WDATA;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [5:0]axi_interconnect_4_M00_AXI_WID;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_WLAST;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_WREADY;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [7:0]axi_interconnect_4_M00_AXI_WSTRB;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire axi_interconnect_4_M00_AXI_WVALID;
  wire customop_irq_1;
  wire hp_axi_aclk_1;
  wire pl_bist_clk_0_1;
  wire pl_bist_rstn_0_1;
  wire pl_clk_en_b_0_1;
  wire pl_itf_clk_0_1;
  wire pl_ra_clk_0_1;
  wire pl_rst_n_0_1;
  wire pl_scan_clk_0_1;
  wire pl_scan_rst_n_0_1;
  (* DEBUG = "true" *) (* MARK_DEBUG *) wire [0:0]proc_sys_reset_1_peripheral_aresetn;
  wire [17:0]processing_system7_0_AI_IRQ_pl_int_info;
  wire processing_system7_0_AI_IRQ_pl_int_ready;
  wire processing_system7_0_AI_IRQ_pl_int_valid;
  wire [14:0]processing_system7_0_DDR_ADDR;
  wire [2:0]processing_system7_0_DDR_BA;
  wire processing_system7_0_DDR_CAS_N;
  wire processing_system7_0_DDR_CKE;
  wire processing_system7_0_DDR_CK_N;
  wire processing_system7_0_DDR_CK_P;
  wire processing_system7_0_DDR_CS_N;
  wire [3:0]processing_system7_0_DDR_DM;
  wire [31:0]processing_system7_0_DDR_DQ;
  wire [3:0]processing_system7_0_DDR_DQS_N;
  wire [3:0]processing_system7_0_DDR_DQS_P;
  wire processing_system7_0_DDR_ODT;
  wire processing_system7_0_DDR_RAS_N;
  wire processing_system7_0_DDR_RESET_N;
  wire processing_system7_0_DDR_WE_N;
  wire processing_system7_0_FCLK_CLK0;
  wire processing_system7_0_FCLK_RESET0_N;
  wire processing_system7_0_FIXED_IO_DDR_VRN;
  wire processing_system7_0_FIXED_IO_DDR_VRP;
  wire [53:0]processing_system7_0_FIXED_IO_MIO;
  wire processing_system7_0_FIXED_IO_PS_CLK;
  wire processing_system7_0_FIXED_IO_PS_PORB;
  wire processing_system7_0_FIXED_IO_PS_SRSTB;
  wire [26:0]processing_system7_0_M_AI_HP_pl_araddr;
  wire [5:0]processing_system7_0_M_AI_HP_pl_arinfo;
  wire processing_system7_0_M_AI_HP_pl_arlast;
  wire processing_system7_0_M_AI_HP_pl_arready;
  wire processing_system7_0_M_AI_HP_pl_arvalid;
  wire [26:0]processing_system7_0_M_AI_HP_pl_awaddr;
  wire [511:0]processing_system7_0_M_AI_HP_pl_awdata;
  wire [63:0]processing_system7_0_M_AI_HP_pl_awen;
  wire [5:0]processing_system7_0_M_AI_HP_pl_awinfo;
  wire processing_system7_0_M_AI_HP_pl_awlast;
  wire processing_system7_0_M_AI_HP_pl_awready;
  wire processing_system7_0_M_AI_HP_pl_awvalid;
  wire processing_system7_0_M_AI_HP_pl_bready;
  wire processing_system7_0_M_AI_HP_pl_bvalid;
  wire [511:0]processing_system7_0_M_AI_HP_pl_rdata;
  wire processing_system7_0_M_AI_HP_pl_rlast;
  wire processing_system7_0_M_AI_HP_pl_rready;
  wire processing_system7_0_M_AI_HP_pl_rvalid;
  wire [1:0]processing_system7_0_USBIND_0_PORT_INDCTL;
  wire processing_system7_0_USBIND_0_VBUS_PWRFAULT;
  wire processing_system7_0_USBIND_0_VBUS_PWRSELECT;
  wire processing_system7_0_pl_clk_div_out;
  wire processing_system7_1_FCLK_CLK0;
  wire reset_n_1;
  wire soft_rst_n_1;
  wire test_irq_1;
  wire [0:0]util_vector_logic_0_Res;
  wire [2:0]xlconcat_0_dout;

  assign AI_BIST_0_1_pl_bist_en = AI_BIST_0_pl_bist_en;
  assign AI_BIST_0_pl_bist_done = AI_BIST_0_1_pl_bist_done;
  assign AI_BIST_0_pl_bist_err = AI_BIST_0_1_pl_bist_err;
  assign AI_BIST_0_pl_bist_err_inv = AI_BIST_0_1_pl_bist_err_inv;
  assign AI_BIST_0_pl_repair_done = AI_BIST_0_1_pl_repair_done;
  assign AI_BIST_0_pl_repair_fail = AI_BIST_0_1_pl_repair_fail;
  assign AI_IRQ_0_pl_int_info[17:0] = processing_system7_0_AI_IRQ_pl_int_info;
  assign AI_IRQ_0_pl_int_valid = processing_system7_0_AI_IRQ_pl_int_valid;
  assign AI_SCAN_0_1_pl_scan_compression_mode = AI_SCAN_0_pl_scan_compression_mode;
  assign AI_SCAN_0_1_pl_scan_cs = AI_SCAN_0_pl_scan_cs[7:0];
  assign AI_SCAN_0_1_pl_scan_en = AI_SCAN_0_pl_scan_en;
  assign AI_SCAN_0_1_pl_scan_in = AI_SCAN_0_pl_scan_in[63:0];
  assign AI_SCAN_0_1_pl_scan_mode_b = AI_SCAN_0_pl_scan_mode_b;
  assign AI_SCAN_0_1_pl_scan_occ_bypass = AI_SCAN_0_pl_scan_occ_bypass;
  assign AI_SCAN_0_1_pl_scan_occ_mode = AI_SCAN_0_pl_scan_occ_mode;
  assign AI_SCAN_0_1_pl_scan_occ_reset = AI_SCAN_0_pl_scan_occ_reset;
  assign AI_SCAN_0_1_pl_scan_wrp_mode = AI_SCAN_0_pl_scan_wrp_mode;
  assign AI_SCAN_0_1_pl_scan_wrp_shift = AI_SCAN_0_pl_scan_wrp_shift;
  assign AI_SCAN_0_pl_scan_out[63:0] = AI_SCAN_0_1_pl_scan_out;
  assign BYolo_GP0_araddr[31:0] = axi_interconnect_0_M00_AXI_ARADDR;
  assign BYolo_GP0_arburst[1:0] = axi_interconnect_0_M00_AXI_ARBURST;
  assign BYolo_GP0_arcache[3:0] = axi_interconnect_0_M00_AXI_ARCACHE;
  assign BYolo_GP0_arid[11:0] = axi_interconnect_0_M00_AXI_ARID;
  assign BYolo_GP0_arlen[3:0] = axi_interconnect_0_M00_AXI_ARLEN;
  assign BYolo_GP0_arlock[1:0] = axi_interconnect_0_M00_AXI_ARLOCK;
  assign BYolo_GP0_arprot[2:0] = axi_interconnect_0_M00_AXI_ARPROT;
  assign BYolo_GP0_arqos[3:0] = axi_interconnect_0_M00_AXI_ARQOS;
  assign BYolo_GP0_arsize[2:0] = axi_interconnect_0_M00_AXI_ARSIZE;
  assign BYolo_GP0_arvalid[0] = axi_interconnect_0_M00_AXI_ARVALID;
  assign BYolo_GP0_awaddr[31:0] = axi_interconnect_0_M00_AXI_AWADDR;
  assign BYolo_GP0_awburst[1:0] = axi_interconnect_0_M00_AXI_AWBURST;
  assign BYolo_GP0_awcache[3:0] = axi_interconnect_0_M00_AXI_AWCACHE;
  assign BYolo_GP0_awid[11:0] = axi_interconnect_0_M00_AXI_AWID;
  assign BYolo_GP0_awlen[3:0] = axi_interconnect_0_M00_AXI_AWLEN;
  assign BYolo_GP0_awlock[1:0] = axi_interconnect_0_M00_AXI_AWLOCK;
  assign BYolo_GP0_awprot[2:0] = axi_interconnect_0_M00_AXI_AWPROT;
  assign BYolo_GP0_awqos[3:0] = axi_interconnect_0_M00_AXI_AWQOS;
  assign BYolo_GP0_awsize[2:0] = axi_interconnect_0_M00_AXI_AWSIZE;
  assign BYolo_GP0_awvalid[0] = axi_interconnect_0_M00_AXI_AWVALID;
  assign BYolo_GP0_bready[0] = axi_interconnect_0_M00_AXI_BREADY;
  assign BYolo_GP0_rready[0] = axi_interconnect_0_M00_AXI_RREADY;
  assign BYolo_GP0_wdata[31:0] = axi_interconnect_0_M00_AXI_WDATA;
  assign BYolo_GP0_wid[11:0] = axi_interconnect_0_M00_AXI_WID;
  assign BYolo_GP0_wlast[0] = axi_interconnect_0_M00_AXI_WLAST;
  assign BYolo_GP0_wstrb[3:0] = axi_interconnect_0_M00_AXI_WSTRB;
  assign BYolo_GP0_wvalid[0] = axi_interconnect_0_M00_AXI_WVALID;
  assign BYolo_GP1_araddr[31:0] = axi_interconnect_1_M00_AXI_ARADDR;
  assign BYolo_GP1_arburst[1:0] = axi_interconnect_1_M00_AXI_ARBURST;
  assign BYolo_GP1_arcache[3:0] = axi_interconnect_1_M00_AXI_ARCACHE;
  assign BYolo_GP1_arid[11:0] = axi_interconnect_1_M00_AXI_ARID;
  assign BYolo_GP1_arlen[3:0] = axi_interconnect_1_M00_AXI_ARLEN;
  assign BYolo_GP1_arlock[1:0] = axi_interconnect_1_M00_AXI_ARLOCK;
  assign BYolo_GP1_arprot[2:0] = axi_interconnect_1_M00_AXI_ARPROT;
  assign BYolo_GP1_arqos[3:0] = axi_interconnect_1_M00_AXI_ARQOS;
  assign BYolo_GP1_arsize[2:0] = axi_interconnect_1_M00_AXI_ARSIZE;
  assign BYolo_GP1_arvalid[0] = axi_interconnect_1_M00_AXI_ARVALID;
  assign BYolo_GP1_awaddr[31:0] = axi_interconnect_1_M00_AXI_AWADDR;
  assign BYolo_GP1_awburst[1:0] = axi_interconnect_1_M00_AXI_AWBURST;
  assign BYolo_GP1_awcache[3:0] = axi_interconnect_1_M00_AXI_AWCACHE;
  assign BYolo_GP1_awid[11:0] = axi_interconnect_1_M00_AXI_AWID;
  assign BYolo_GP1_awlen[3:0] = axi_interconnect_1_M00_AXI_AWLEN;
  assign BYolo_GP1_awlock[1:0] = axi_interconnect_1_M00_AXI_AWLOCK;
  assign BYolo_GP1_awprot[2:0] = axi_interconnect_1_M00_AXI_AWPROT;
  assign BYolo_GP1_awqos[3:0] = axi_interconnect_1_M00_AXI_AWQOS;
  assign BYolo_GP1_awsize[2:0] = axi_interconnect_1_M00_AXI_AWSIZE;
  assign BYolo_GP1_awvalid[0] = axi_interconnect_1_M00_AXI_AWVALID;
  assign BYolo_GP1_bready[0] = axi_interconnect_1_M00_AXI_BREADY;
  assign BYolo_GP1_rready[0] = axi_interconnect_1_M00_AXI_RREADY;
  assign BYolo_GP1_wdata[31:0] = axi_interconnect_1_M00_AXI_WDATA;
  assign BYolo_GP1_wid[11:0] = axi_interconnect_1_M00_AXI_WID;
  assign BYolo_GP1_wlast[0] = axi_interconnect_1_M00_AXI_WLAST;
  assign BYolo_GP1_wstrb[3:0] = axi_interconnect_1_M00_AXI_WSTRB;
  assign BYolo_GP1_wvalid[0] = axi_interconnect_1_M00_AXI_WVALID;
  assign FCLK_CLK0_0 = processing_system7_0_FCLK_CLK0;
  assign FCLK_RESET0_N_0 = processing_system7_0_FCLK_RESET0_N;
  assign M_AI_HP_0_pl_araddr[26:0] = processing_system7_0_M_AI_HP_pl_araddr;
  assign M_AI_HP_0_pl_arinfo[5:0] = processing_system7_0_M_AI_HP_pl_arinfo;
  assign M_AI_HP_0_pl_arlast = processing_system7_0_M_AI_HP_pl_arlast;
  assign M_AI_HP_0_pl_arvalid = processing_system7_0_M_AI_HP_pl_arvalid;
  assign M_AI_HP_0_pl_awaddr[26:0] = processing_system7_0_M_AI_HP_pl_awaddr;
  assign M_AI_HP_0_pl_awdata[511:0] = processing_system7_0_M_AI_HP_pl_awdata;
  assign M_AI_HP_0_pl_awen[63:0] = processing_system7_0_M_AI_HP_pl_awen;
  assign M_AI_HP_0_pl_awinfo[5:0] = processing_system7_0_M_AI_HP_pl_awinfo;
  assign M_AI_HP_0_pl_awlast = processing_system7_0_M_AI_HP_pl_awlast;
  assign M_AI_HP_0_pl_awvalid = processing_system7_0_M_AI_HP_pl_awvalid;
  assign M_AI_HP_0_pl_bready = processing_system7_0_M_AI_HP_pl_bready;
  assign M_AI_HP_0_pl_rready = processing_system7_0_M_AI_HP_pl_rready;
  assign PJTAG_0_1_TCK = PJTAG_0_tck;
  assign PJTAG_0_1_TDI = PJTAG_0_tdi;
  assign PJTAG_0_1_TMS = PJTAG_0_tms;
  assign PJTAG_0_tdo = PJTAG_0_1_TDO;
  assign S_AI_GP_0_1_pl_ra_araddr = S_AI_GP_0_pl_ra_araddr[15:0];
  assign S_AI_GP_0_1_pl_ra_arvalid = S_AI_GP_0_pl_ra_arvalid;
  assign S_AI_GP_0_1_pl_ra_awaddr = S_AI_GP_0_pl_ra_awaddr[15:0];
  assign S_AI_GP_0_1_pl_ra_awdata = S_AI_GP_0_pl_ra_awdata[31:0];
  assign S_AI_GP_0_1_pl_ra_awvalid = S_AI_GP_0_pl_ra_awvalid;
  assign S_AI_GP_0_1_pl_ra_rready = S_AI_GP_0_pl_ra_rready;
  assign S_AI_GP_0_pl_ra_arready = S_AI_GP_0_1_pl_ra_arready;
  assign S_AI_GP_0_pl_ra_awready = S_AI_GP_0_1_pl_ra_awready;
  assign S_AI_GP_0_pl_ra_rdata[31:0] = S_AI_GP_0_1_pl_ra_rdata;
  assign S_AI_GP_0_pl_ra_rvalid = S_AI_GP_0_1_pl_ra_rvalid;
  assign S_AXI_HP0_0_1_ARADDR = S_AXI_HP0_0_araddr[31:0];
  assign S_AXI_HP0_0_1_ARBURST = S_AXI_HP0_0_arburst[1:0];
  assign S_AXI_HP0_0_1_ARCACHE = S_AXI_HP0_0_arcache[3:0];
  assign S_AXI_HP0_0_1_ARID = S_AXI_HP0_0_arid[5:0];
  assign S_AXI_HP0_0_1_ARLEN = S_AXI_HP0_0_arlen[3:0];
  assign S_AXI_HP0_0_1_ARLOCK = S_AXI_HP0_0_arlock[1:0];
  assign S_AXI_HP0_0_1_ARPROT = S_AXI_HP0_0_arprot[2:0];
  assign S_AXI_HP0_0_1_ARQOS = S_AXI_HP0_0_arqos[3:0];
  assign S_AXI_HP0_0_1_ARSIZE = S_AXI_HP0_0_arsize[2:0];
  assign S_AXI_HP0_0_1_ARVALID = S_AXI_HP0_0_arvalid;
  assign S_AXI_HP0_0_1_AWADDR = S_AXI_HP0_0_awaddr[31:0];
  assign S_AXI_HP0_0_1_AWBURST = S_AXI_HP0_0_awburst[1:0];
  assign S_AXI_HP0_0_1_AWCACHE = S_AXI_HP0_0_awcache[3:0];
  assign S_AXI_HP0_0_1_AWID = S_AXI_HP0_0_awid[5:0];
  assign S_AXI_HP0_0_1_AWLEN = S_AXI_HP0_0_awlen[3:0];
  assign S_AXI_HP0_0_1_AWLOCK = S_AXI_HP0_0_awlock[1:0];
  assign S_AXI_HP0_0_1_AWPROT = S_AXI_HP0_0_awprot[2:0];
  assign S_AXI_HP0_0_1_AWQOS = S_AXI_HP0_0_awqos[3:0];
  assign S_AXI_HP0_0_1_AWSIZE = S_AXI_HP0_0_awsize[2:0];
  assign S_AXI_HP0_0_1_AWVALID = S_AXI_HP0_0_awvalid;
  assign S_AXI_HP0_0_1_BREADY = S_AXI_HP0_0_bready;
  assign S_AXI_HP0_0_1_RREADY = S_AXI_HP0_0_rready;
  assign S_AXI_HP0_0_1_WDATA = S_AXI_HP0_0_wdata[63:0];
  assign S_AXI_HP0_0_1_WID = S_AXI_HP0_0_wid[5:0];
  assign S_AXI_HP0_0_1_WLAST = S_AXI_HP0_0_wlast;
  assign S_AXI_HP0_0_1_WSTRB = S_AXI_HP0_0_wstrb[7:0];
  assign S_AXI_HP0_0_1_WVALID = S_AXI_HP0_0_wvalid;
  assign S_AXI_HP0_0_arready = S_AXI_HP0_0_1_ARREADY;
  assign S_AXI_HP0_0_awready = S_AXI_HP0_0_1_AWREADY;
  assign S_AXI_HP0_0_bid[5:0] = S_AXI_HP0_0_1_BID;
  assign S_AXI_HP0_0_bresp[1:0] = S_AXI_HP0_0_1_BRESP;
  assign S_AXI_HP0_0_bvalid = S_AXI_HP0_0_1_BVALID;
  assign S_AXI_HP0_0_rdata[63:0] = S_AXI_HP0_0_1_RDATA;
  assign S_AXI_HP0_0_rid[5:0] = S_AXI_HP0_0_1_RID;
  assign S_AXI_HP0_0_rlast = S_AXI_HP0_0_1_RLAST;
  assign S_AXI_HP0_0_rresp[1:0] = S_AXI_HP0_0_1_RRESP;
  assign S_AXI_HP0_0_rvalid = S_AXI_HP0_0_1_RVALID;
  assign S_AXI_HP0_0_wready = S_AXI_HP0_0_1_WREADY;
  assign S_AXI_HP0_FIFO_CTRL_0_1_RDISSUECAPEN = S_AXI_HP0_FIFO_CTRL_0_rdissuecapen;
  assign S_AXI_HP0_FIFO_CTRL_0_1_WRISSUECAPEN = S_AXI_HP0_FIFO_CTRL_0_wrissuecapen;
  assign S_AXI_HP0_FIFO_CTRL_0_racount[2:0] = S_AXI_HP0_FIFO_CTRL_0_1_RACOUNT;
  assign S_AXI_HP0_FIFO_CTRL_0_rcount[7:0] = S_AXI_HP0_FIFO_CTRL_0_1_RCOUNT;
  assign S_AXI_HP0_FIFO_CTRL_0_wacount[5:0] = S_AXI_HP0_FIFO_CTRL_0_1_WACOUNT;
  assign S_AXI_HP0_FIFO_CTRL_0_wcount[7:0] = S_AXI_HP0_FIFO_CTRL_0_1_WCOUNT;
  assign S_AXI_HP1_0_1_ARADDR = S_AXI_HP1_0_araddr[31:0];
  assign S_AXI_HP1_0_1_ARBURST = S_AXI_HP1_0_arburst[1:0];
  assign S_AXI_HP1_0_1_ARCACHE = S_AXI_HP1_0_arcache[3:0];
  assign S_AXI_HP1_0_1_ARID = S_AXI_HP1_0_arid[5:0];
  assign S_AXI_HP1_0_1_ARLEN = S_AXI_HP1_0_arlen[3:0];
  assign S_AXI_HP1_0_1_ARLOCK = S_AXI_HP1_0_arlock[1:0];
  assign S_AXI_HP1_0_1_ARPROT = S_AXI_HP1_0_arprot[2:0];
  assign S_AXI_HP1_0_1_ARQOS = S_AXI_HP1_0_arqos[3:0];
  assign S_AXI_HP1_0_1_ARSIZE = S_AXI_HP1_0_arsize[2:0];
  assign S_AXI_HP1_0_1_ARVALID = S_AXI_HP1_0_arvalid;
  assign S_AXI_HP1_0_1_AWADDR = S_AXI_HP1_0_awaddr[31:0];
  assign S_AXI_HP1_0_1_AWBURST = S_AXI_HP1_0_awburst[1:0];
  assign S_AXI_HP1_0_1_AWCACHE = S_AXI_HP1_0_awcache[3:0];
  assign S_AXI_HP1_0_1_AWID = S_AXI_HP1_0_awid[5:0];
  assign S_AXI_HP1_0_1_AWLEN = S_AXI_HP1_0_awlen[3:0];
  assign S_AXI_HP1_0_1_AWLOCK = S_AXI_HP1_0_awlock[1:0];
  assign S_AXI_HP1_0_1_AWPROT = S_AXI_HP1_0_awprot[2:0];
  assign S_AXI_HP1_0_1_AWQOS = S_AXI_HP1_0_awqos[3:0];
  assign S_AXI_HP1_0_1_AWSIZE = S_AXI_HP1_0_awsize[2:0];
  assign S_AXI_HP1_0_1_AWVALID = S_AXI_HP1_0_awvalid;
  assign S_AXI_HP1_0_1_BREADY = S_AXI_HP1_0_bready;
  assign S_AXI_HP1_0_1_RREADY = S_AXI_HP1_0_rready;
  assign S_AXI_HP1_0_1_WDATA = S_AXI_HP1_0_wdata[63:0];
  assign S_AXI_HP1_0_1_WID = S_AXI_HP1_0_wid[5:0];
  assign S_AXI_HP1_0_1_WLAST = S_AXI_HP1_0_wlast;
  assign S_AXI_HP1_0_1_WSTRB = S_AXI_HP1_0_wstrb[7:0];
  assign S_AXI_HP1_0_1_WVALID = S_AXI_HP1_0_wvalid;
  assign S_AXI_HP1_0_arready = S_AXI_HP1_0_1_ARREADY;
  assign S_AXI_HP1_0_awready = S_AXI_HP1_0_1_AWREADY;
  assign S_AXI_HP1_0_bid[5:0] = S_AXI_HP1_0_1_BID;
  assign S_AXI_HP1_0_bresp[1:0] = S_AXI_HP1_0_1_BRESP;
  assign S_AXI_HP1_0_bvalid = S_AXI_HP1_0_1_BVALID;
  assign S_AXI_HP1_0_rdata[63:0] = S_AXI_HP1_0_1_RDATA;
  assign S_AXI_HP1_0_rid[5:0] = S_AXI_HP1_0_1_RID;
  assign S_AXI_HP1_0_rlast = S_AXI_HP1_0_1_RLAST;
  assign S_AXI_HP1_0_rresp[1:0] = S_AXI_HP1_0_1_RRESP;
  assign S_AXI_HP1_0_rvalid = S_AXI_HP1_0_1_RVALID;
  assign S_AXI_HP1_0_wready = S_AXI_HP1_0_1_WREADY;
  assign S_AXI_HP1_FIFO_CTRL_0_1_RDISSUECAPEN = S_AXI_HP1_FIFO_CTRL_0_rdissuecapen;
  assign S_AXI_HP1_FIFO_CTRL_0_1_WRISSUECAPEN = S_AXI_HP1_FIFO_CTRL_0_wrissuecapen;
  assign S_AXI_HP1_FIFO_CTRL_0_racount[2:0] = S_AXI_HP1_FIFO_CTRL_0_1_RACOUNT;
  assign S_AXI_HP1_FIFO_CTRL_0_rcount[7:0] = S_AXI_HP1_FIFO_CTRL_0_1_RCOUNT;
  assign S_AXI_HP1_FIFO_CTRL_0_wacount[5:0] = S_AXI_HP1_FIFO_CTRL_0_1_WACOUNT;
  assign S_AXI_HP1_FIFO_CTRL_0_wcount[7:0] = S_AXI_HP1_FIFO_CTRL_0_1_WCOUNT;
  assign S_AXI_HP2_0_1_ARADDR = S_AXI_HP2_0_araddr[31:0];
  assign S_AXI_HP2_0_1_ARBURST = S_AXI_HP2_0_arburst[1:0];
  assign S_AXI_HP2_0_1_ARCACHE = S_AXI_HP2_0_arcache[3:0];
  assign S_AXI_HP2_0_1_ARID = S_AXI_HP2_0_arid[4:0];
  assign S_AXI_HP2_0_1_ARLEN = S_AXI_HP2_0_arlen[3:0];
  assign S_AXI_HP2_0_1_ARLOCK = S_AXI_HP2_0_arlock[1:0];
  assign S_AXI_HP2_0_1_ARPROT = S_AXI_HP2_0_arprot[2:0];
  assign S_AXI_HP2_0_1_ARQOS = S_AXI_HP2_0_arqos[3:0];
  assign S_AXI_HP2_0_1_ARSIZE = S_AXI_HP2_0_arsize[2:0];
  assign S_AXI_HP2_0_1_ARVALID = S_AXI_HP2_0_arvalid;
  assign S_AXI_HP2_0_1_AWADDR = S_AXI_HP2_0_awaddr[31:0];
  assign S_AXI_HP2_0_1_AWBURST = S_AXI_HP2_0_awburst[1:0];
  assign S_AXI_HP2_0_1_AWCACHE = S_AXI_HP2_0_awcache[3:0];
  assign S_AXI_HP2_0_1_AWID = S_AXI_HP2_0_awid[4:0];
  assign S_AXI_HP2_0_1_AWLEN = S_AXI_HP2_0_awlen[3:0];
  assign S_AXI_HP2_0_1_AWLOCK = S_AXI_HP2_0_awlock[1:0];
  assign S_AXI_HP2_0_1_AWPROT = S_AXI_HP2_0_awprot[2:0];
  assign S_AXI_HP2_0_1_AWQOS = S_AXI_HP2_0_awqos[3:0];
  assign S_AXI_HP2_0_1_AWSIZE = S_AXI_HP2_0_awsize[2:0];
  assign S_AXI_HP2_0_1_AWVALID = S_AXI_HP2_0_awvalid;
  assign S_AXI_HP2_0_1_BREADY = S_AXI_HP2_0_bready;
  assign S_AXI_HP2_0_1_RREADY = S_AXI_HP2_0_rready;
  assign S_AXI_HP2_0_1_WDATA = S_AXI_HP2_0_wdata[63:0];
  assign S_AXI_HP2_0_1_WID = S_AXI_HP2_0_wid[4:0];
  assign S_AXI_HP2_0_1_WLAST = S_AXI_HP2_0_wlast;
  assign S_AXI_HP2_0_1_WSTRB = S_AXI_HP2_0_wstrb[7:0];
  assign S_AXI_HP2_0_1_WVALID = S_AXI_HP2_0_wvalid;
  assign S_AXI_HP2_0_arready = S_AXI_HP2_0_1_ARREADY;
  assign S_AXI_HP2_0_awready = S_AXI_HP2_0_1_AWREADY;
  assign S_AXI_HP2_0_bid[4:0] = S_AXI_HP2_0_1_BID;
  assign S_AXI_HP2_0_bresp[1:0] = S_AXI_HP2_0_1_BRESP;
  assign S_AXI_HP2_0_bvalid = S_AXI_HP2_0_1_BVALID;
  assign S_AXI_HP2_0_rdata[63:0] = S_AXI_HP2_0_1_RDATA;
  assign S_AXI_HP2_0_rid[4:0] = S_AXI_HP2_0_1_RID;
  assign S_AXI_HP2_0_rlast = S_AXI_HP2_0_1_RLAST;
  assign S_AXI_HP2_0_rresp[1:0] = S_AXI_HP2_0_1_RRESP;
  assign S_AXI_HP2_0_rvalid = S_AXI_HP2_0_1_RVALID;
  assign S_AXI_HP2_0_wready = S_AXI_HP2_0_1_WREADY;
  assign S_AXI_HP2_1_1_ARADDR = S_AXI_HP2_1_araddr[31:0];
  assign S_AXI_HP2_1_1_ARBURST = S_AXI_HP2_1_arburst[1:0];
  assign S_AXI_HP2_1_1_ARCACHE = S_AXI_HP2_1_arcache[3:0];
  assign S_AXI_HP2_1_1_ARID = S_AXI_HP2_1_arid[4:0];
  assign S_AXI_HP2_1_1_ARLEN = S_AXI_HP2_1_arlen[3:0];
  assign S_AXI_HP2_1_1_ARLOCK = S_AXI_HP2_1_arlock[1:0];
  assign S_AXI_HP2_1_1_ARPROT = S_AXI_HP2_1_arprot[2:0];
  assign S_AXI_HP2_1_1_ARQOS = S_AXI_HP2_1_arqos[3:0];
  assign S_AXI_HP2_1_1_ARSIZE = S_AXI_HP2_1_arsize[2:0];
  assign S_AXI_HP2_1_1_ARVALID = S_AXI_HP2_1_arvalid;
  assign S_AXI_HP2_1_1_AWADDR = S_AXI_HP2_1_awaddr[31:0];
  assign S_AXI_HP2_1_1_AWBURST = S_AXI_HP2_1_awburst[1:0];
  assign S_AXI_HP2_1_1_AWCACHE = S_AXI_HP2_1_awcache[3:0];
  assign S_AXI_HP2_1_1_AWID = S_AXI_HP2_1_awid[4:0];
  assign S_AXI_HP2_1_1_AWLEN = S_AXI_HP2_1_awlen[3:0];
  assign S_AXI_HP2_1_1_AWLOCK = S_AXI_HP2_1_awlock[1:0];
  assign S_AXI_HP2_1_1_AWPROT = S_AXI_HP2_1_awprot[2:0];
  assign S_AXI_HP2_1_1_AWQOS = S_AXI_HP2_1_awqos[3:0];
  assign S_AXI_HP2_1_1_AWSIZE = S_AXI_HP2_1_awsize[2:0];
  assign S_AXI_HP2_1_1_AWVALID = S_AXI_HP2_1_awvalid;
  assign S_AXI_HP2_1_1_BREADY = S_AXI_HP2_1_bready;
  assign S_AXI_HP2_1_1_RREADY = S_AXI_HP2_1_rready;
  assign S_AXI_HP2_1_1_WDATA = S_AXI_HP2_1_wdata[63:0];
  assign S_AXI_HP2_1_1_WID = S_AXI_HP2_1_wid[4:0];
  assign S_AXI_HP2_1_1_WLAST = S_AXI_HP2_1_wlast;
  assign S_AXI_HP2_1_1_WSTRB = S_AXI_HP2_1_wstrb[7:0];
  assign S_AXI_HP2_1_1_WVALID = S_AXI_HP2_1_wvalid;
  assign S_AXI_HP2_1_arready = S_AXI_HP2_1_1_ARREADY;
  assign S_AXI_HP2_1_awready = S_AXI_HP2_1_1_AWREADY;
  assign S_AXI_HP2_1_bid[4:0] = S_AXI_HP2_1_1_BID;
  assign S_AXI_HP2_1_bresp[1:0] = S_AXI_HP2_1_1_BRESP;
  assign S_AXI_HP2_1_bvalid = S_AXI_HP2_1_1_BVALID;
  assign S_AXI_HP2_1_rdata[63:0] = S_AXI_HP2_1_1_RDATA;
  assign S_AXI_HP2_1_rid[4:0] = S_AXI_HP2_1_1_RID;
  assign S_AXI_HP2_1_rlast = S_AXI_HP2_1_1_RLAST;
  assign S_AXI_HP2_1_rresp[1:0] = S_AXI_HP2_1_1_RRESP;
  assign S_AXI_HP2_1_rvalid = S_AXI_HP2_1_1_RVALID;
  assign S_AXI_HP2_1_wready = S_AXI_HP2_1_1_WREADY;
  assign S_AXI_HP2_FIFO_CTRL_0_1_RDISSUECAPEN = S_AXI_HP2_FIFO_CTRL_0_rdissuecapen;
  assign S_AXI_HP2_FIFO_CTRL_0_1_WRISSUECAPEN = S_AXI_HP2_FIFO_CTRL_0_wrissuecapen;
  assign S_AXI_HP2_FIFO_CTRL_0_racount[2:0] = S_AXI_HP2_FIFO_CTRL_0_1_RACOUNT;
  assign S_AXI_HP2_FIFO_CTRL_0_rcount[7:0] = S_AXI_HP2_FIFO_CTRL_0_1_RCOUNT;
  assign S_AXI_HP2_FIFO_CTRL_0_wacount[5:0] = S_AXI_HP2_FIFO_CTRL_0_1_WACOUNT;
  assign S_AXI_HP2_FIFO_CTRL_0_wcount[7:0] = S_AXI_HP2_FIFO_CTRL_0_1_WCOUNT;
  assign S_AXI_HP3_0_1_ARADDR = S_AXI_HP3_0_araddr[31:0];
  assign S_AXI_HP3_0_1_ARBURST = S_AXI_HP3_0_arburst[1:0];
  assign S_AXI_HP3_0_1_ARCACHE = S_AXI_HP3_0_arcache[3:0];
  assign S_AXI_HP3_0_1_ARID = S_AXI_HP3_0_arid[5:0];
  assign S_AXI_HP3_0_1_ARLEN = S_AXI_HP3_0_arlen[3:0];
  assign S_AXI_HP3_0_1_ARLOCK = S_AXI_HP3_0_arlock[1:0];
  assign S_AXI_HP3_0_1_ARPROT = S_AXI_HP3_0_arprot[2:0];
  assign S_AXI_HP3_0_1_ARQOS = S_AXI_HP3_0_arqos[3:0];
  assign S_AXI_HP3_0_1_ARSIZE = S_AXI_HP3_0_arsize[2:0];
  assign S_AXI_HP3_0_1_ARVALID = S_AXI_HP3_0_arvalid;
  assign S_AXI_HP3_0_1_AWADDR = S_AXI_HP3_0_awaddr[31:0];
  assign S_AXI_HP3_0_1_AWBURST = S_AXI_HP3_0_awburst[1:0];
  assign S_AXI_HP3_0_1_AWCACHE = S_AXI_HP3_0_awcache[3:0];
  assign S_AXI_HP3_0_1_AWID = S_AXI_HP3_0_awid[5:0];
  assign S_AXI_HP3_0_1_AWLEN = S_AXI_HP3_0_awlen[3:0];
  assign S_AXI_HP3_0_1_AWLOCK = S_AXI_HP3_0_awlock[1:0];
  assign S_AXI_HP3_0_1_AWPROT = S_AXI_HP3_0_awprot[2:0];
  assign S_AXI_HP3_0_1_AWQOS = S_AXI_HP3_0_awqos[3:0];
  assign S_AXI_HP3_0_1_AWSIZE = S_AXI_HP3_0_awsize[2:0];
  assign S_AXI_HP3_0_1_AWVALID = S_AXI_HP3_0_awvalid;
  assign S_AXI_HP3_0_1_BREADY = S_AXI_HP3_0_bready;
  assign S_AXI_HP3_0_1_RREADY = S_AXI_HP3_0_rready;
  assign S_AXI_HP3_0_1_WDATA = S_AXI_HP3_0_wdata[63:0];
  assign S_AXI_HP3_0_1_WID = S_AXI_HP3_0_wid[5:0];
  assign S_AXI_HP3_0_1_WLAST = S_AXI_HP3_0_wlast;
  assign S_AXI_HP3_0_1_WSTRB = S_AXI_HP3_0_wstrb[7:0];
  assign S_AXI_HP3_0_1_WVALID = S_AXI_HP3_0_wvalid;
  assign S_AXI_HP3_0_arready = S_AXI_HP3_0_1_ARREADY;
  assign S_AXI_HP3_0_awready = S_AXI_HP3_0_1_AWREADY;
  assign S_AXI_HP3_0_bid[5:0] = S_AXI_HP3_0_1_BID;
  assign S_AXI_HP3_0_bresp[1:0] = S_AXI_HP3_0_1_BRESP;
  assign S_AXI_HP3_0_bvalid = S_AXI_HP3_0_1_BVALID;
  assign S_AXI_HP3_0_rdata[63:0] = S_AXI_HP3_0_1_RDATA;
  assign S_AXI_HP3_0_rid[5:0] = S_AXI_HP3_0_1_RID;
  assign S_AXI_HP3_0_rlast = S_AXI_HP3_0_1_RLAST;
  assign S_AXI_HP3_0_rresp[1:0] = S_AXI_HP3_0_1_RRESP;
  assign S_AXI_HP3_0_rvalid = S_AXI_HP3_0_1_RVALID;
  assign S_AXI_HP3_0_wready = S_AXI_HP3_0_1_WREADY;
  assign S_AXI_HP3_FIFO_CTRL_0_1_RDISSUECAPEN = S_AXI_HP3_FIFO_CTRL_0_rdissuecapen;
  assign S_AXI_HP3_FIFO_CTRL_0_1_WRISSUECAPEN = S_AXI_HP3_FIFO_CTRL_0_wrissuecapen;
  assign S_AXI_HP3_FIFO_CTRL_0_racount[2:0] = S_AXI_HP3_FIFO_CTRL_0_1_RACOUNT;
  assign S_AXI_HP3_FIFO_CTRL_0_rcount[7:0] = S_AXI_HP3_FIFO_CTRL_0_1_RCOUNT;
  assign S_AXI_HP3_FIFO_CTRL_0_wacount[5:0] = S_AXI_HP3_FIFO_CTRL_0_1_WACOUNT;
  assign S_AXI_HP3_FIFO_CTRL_0_wcount[7:0] = S_AXI_HP3_FIFO_CTRL_0_1_WCOUNT;
  assign USBIND_0_0_port_indctl[1:0] = processing_system7_0_USBIND_0_PORT_INDCTL;
  assign USBIND_0_0_vbus_pwrselect = processing_system7_0_USBIND_0_VBUS_PWRSELECT;
  assign User_GP0_araddr[31:0] = axi_interconnect_0_M01_AXI_ARADDR;
  assign User_GP0_arburst[1:0] = axi_interconnect_0_M01_AXI_ARBURST;
  assign User_GP0_arcache[3:0] = axi_interconnect_0_M01_AXI_ARCACHE;
  assign User_GP0_arid[11:0] = axi_interconnect_0_M01_AXI_ARID;
  assign User_GP0_arlen[3:0] = axi_interconnect_0_M01_AXI_ARLEN;
  assign User_GP0_arlock[1:0] = axi_interconnect_0_M01_AXI_ARLOCK;
  assign User_GP0_arprot[2:0] = axi_interconnect_0_M01_AXI_ARPROT;
  assign User_GP0_arqos[3:0] = axi_interconnect_0_M01_AXI_ARQOS;
  assign User_GP0_arsize[2:0] = axi_interconnect_0_M01_AXI_ARSIZE;
  assign User_GP0_arvalid[0] = axi_interconnect_0_M01_AXI_ARVALID;
  assign User_GP0_awaddr[31:0] = axi_interconnect_0_M01_AXI_AWADDR;
  assign User_GP0_awburst[1:0] = axi_interconnect_0_M01_AXI_AWBURST;
  assign User_GP0_awcache[3:0] = axi_interconnect_0_M01_AXI_AWCACHE;
  assign User_GP0_awid[11:0] = axi_interconnect_0_M01_AXI_AWID;
  assign User_GP0_awlen[3:0] = axi_interconnect_0_M01_AXI_AWLEN;
  assign User_GP0_awlock[1:0] = axi_interconnect_0_M01_AXI_AWLOCK;
  assign User_GP0_awprot[2:0] = axi_interconnect_0_M01_AXI_AWPROT;
  assign User_GP0_awqos[3:0] = axi_interconnect_0_M01_AXI_AWQOS;
  assign User_GP0_awsize[2:0] = axi_interconnect_0_M01_AXI_AWSIZE;
  assign User_GP0_awvalid[0] = axi_interconnect_0_M01_AXI_AWVALID;
  assign User_GP0_bready[0] = axi_interconnect_0_M01_AXI_BREADY;
  assign User_GP0_rready[0] = axi_interconnect_0_M01_AXI_RREADY;
  assign User_GP0_wdata[31:0] = axi_interconnect_0_M01_AXI_WDATA;
  assign User_GP0_wid[11:0] = axi_interconnect_0_M01_AXI_WID;
  assign User_GP0_wlast[0] = axi_interconnect_0_M01_AXI_WLAST;
  assign User_GP0_wstrb[3:0] = axi_interconnect_0_M01_AXI_WSTRB;
  assign User_GP0_wvalid[0] = axi_interconnect_0_M01_AXI_WVALID;
  assign User_GP1_araddr[31:0] = axi_interconnect_1_M01_AXI_ARADDR;
  assign User_GP1_arburst[1:0] = axi_interconnect_1_M01_AXI_ARBURST;
  assign User_GP1_arcache[3:0] = axi_interconnect_1_M01_AXI_ARCACHE;
  assign User_GP1_arid[11:0] = axi_interconnect_1_M01_AXI_ARID;
  assign User_GP1_arlen[3:0] = axi_interconnect_1_M01_AXI_ARLEN;
  assign User_GP1_arlock[1:0] = axi_interconnect_1_M01_AXI_ARLOCK;
  assign User_GP1_arprot[2:0] = axi_interconnect_1_M01_AXI_ARPROT;
  assign User_GP1_arqos[3:0] = axi_interconnect_1_M01_AXI_ARQOS;
  assign User_GP1_arsize[2:0] = axi_interconnect_1_M01_AXI_ARSIZE;
  assign User_GP1_arvalid[0] = axi_interconnect_1_M01_AXI_ARVALID;
  assign User_GP1_awaddr[31:0] = axi_interconnect_1_M01_AXI_AWADDR;
  assign User_GP1_awburst[1:0] = axi_interconnect_1_M01_AXI_AWBURST;
  assign User_GP1_awcache[3:0] = axi_interconnect_1_M01_AXI_AWCACHE;
  assign User_GP1_awid[11:0] = axi_interconnect_1_M01_AXI_AWID;
  assign User_GP1_awlen[3:0] = axi_interconnect_1_M01_AXI_AWLEN;
  assign User_GP1_awlock[1:0] = axi_interconnect_1_M01_AXI_AWLOCK;
  assign User_GP1_awprot[2:0] = axi_interconnect_1_M01_AXI_AWPROT;
  assign User_GP1_awqos[3:0] = axi_interconnect_1_M01_AXI_AWQOS;
  assign User_GP1_awsize[2:0] = axi_interconnect_1_M01_AXI_AWSIZE;
  assign User_GP1_awvalid[0] = axi_interconnect_1_M01_AXI_AWVALID;
  assign User_GP1_bready[0] = axi_interconnect_1_M01_AXI_BREADY;
  assign User_GP1_rready[0] = axi_interconnect_1_M01_AXI_RREADY;
  assign User_GP1_wdata[31:0] = axi_interconnect_1_M01_AXI_WDATA;
  assign User_GP1_wid[11:0] = axi_interconnect_1_M01_AXI_WID;
  assign User_GP1_wlast[0] = axi_interconnect_1_M01_AXI_WLAST;
  assign User_GP1_wstrb[3:0] = axi_interconnect_1_M01_AXI_WSTRB;
  assign User_GP1_wvalid[0] = axi_interconnect_1_M01_AXI_WVALID;
  assign ai_irq_1 = ai_irq;
  assign axi_interconnect_0_M00_AXI_ARREADY = BYolo_GP0_arready[0];
  assign axi_interconnect_0_M00_AXI_AWREADY = BYolo_GP0_awready[0];
  assign axi_interconnect_0_M00_AXI_BID = BYolo_GP0_bid[11:0];
  assign axi_interconnect_0_M00_AXI_BRESP = BYolo_GP0_bresp[1:0];
  assign axi_interconnect_0_M00_AXI_BVALID = BYolo_GP0_bvalid[0];
  assign axi_interconnect_0_M00_AXI_RDATA = BYolo_GP0_rdata[31:0];
  assign axi_interconnect_0_M00_AXI_RID = BYolo_GP0_rid[11:0];
  assign axi_interconnect_0_M00_AXI_RLAST = BYolo_GP0_rlast[0];
  assign axi_interconnect_0_M00_AXI_RRESP = BYolo_GP0_rresp[1:0];
  assign axi_interconnect_0_M00_AXI_RVALID = BYolo_GP0_rvalid[0];
  assign axi_interconnect_0_M00_AXI_WREADY = BYolo_GP0_wready[0];
  assign axi_interconnect_0_M01_AXI_ARREADY = User_GP0_arready[0];
  assign axi_interconnect_0_M01_AXI_AWREADY = User_GP0_awready[0];
  assign axi_interconnect_0_M01_AXI_BID = User_GP0_bid[11:0];
  assign axi_interconnect_0_M01_AXI_BRESP = User_GP0_bresp[1:0];
  assign axi_interconnect_0_M01_AXI_BVALID = User_GP0_bvalid[0];
  assign axi_interconnect_0_M01_AXI_RDATA = User_GP0_rdata[31:0];
  assign axi_interconnect_0_M01_AXI_RID = User_GP0_rid[11:0];
  assign axi_interconnect_0_M01_AXI_RLAST = User_GP0_rlast[0];
  assign axi_interconnect_0_M01_AXI_RRESP = User_GP0_rresp[1:0];
  assign axi_interconnect_0_M01_AXI_RVALID = User_GP0_rvalid[0];
  assign axi_interconnect_0_M01_AXI_WREADY = User_GP0_wready[0];
  assign axi_interconnect_1_M00_AXI_ARREADY = BYolo_GP1_arready[0];
  assign axi_interconnect_1_M00_AXI_AWREADY = BYolo_GP1_awready[0];
  assign axi_interconnect_1_M00_AXI_BID = BYolo_GP1_bid[11:0];
  assign axi_interconnect_1_M00_AXI_BRESP = BYolo_GP1_bresp[1:0];
  assign axi_interconnect_1_M00_AXI_BVALID = BYolo_GP1_bvalid[0];
  assign axi_interconnect_1_M00_AXI_RDATA = BYolo_GP1_rdata[31:0];
  assign axi_interconnect_1_M00_AXI_RID = BYolo_GP1_rid[11:0];
  assign axi_interconnect_1_M00_AXI_RLAST = BYolo_GP1_rlast[0];
  assign axi_interconnect_1_M00_AXI_RRESP = BYolo_GP1_rresp[1:0];
  assign axi_interconnect_1_M00_AXI_RVALID = BYolo_GP1_rvalid[0];
  assign axi_interconnect_1_M00_AXI_WREADY = BYolo_GP1_wready[0];
  assign axi_interconnect_1_M01_AXI_ARREADY = User_GP1_arready[0];
  assign axi_interconnect_1_M01_AXI_AWREADY = User_GP1_awready[0];
  assign axi_interconnect_1_M01_AXI_BID = User_GP1_bid[11:0];
  assign axi_interconnect_1_M01_AXI_BRESP = User_GP1_bresp[1:0];
  assign axi_interconnect_1_M01_AXI_BVALID = User_GP1_bvalid[0];
  assign axi_interconnect_1_M01_AXI_RDATA = User_GP1_rdata[31:0];
  assign axi_interconnect_1_M01_AXI_RID = User_GP1_rid[11:0];
  assign axi_interconnect_1_M01_AXI_RLAST = User_GP1_rlast[0];
  assign axi_interconnect_1_M01_AXI_RRESP = User_GP1_rresp[1:0];
  assign axi_interconnect_1_M01_AXI_RVALID = User_GP1_rvalid[0];
  assign axi_interconnect_1_M01_AXI_WREADY = User_GP1_wready[0];
  assign customop_irq_1 = customop_irq;
  assign hp_axi_aclk_1 = hp_axi_aclk;
  assign pl_bist_clk_0_1 = pl_bist_clk_0;
  assign pl_bist_rstn_0_1 = pl_bist_rstn_0;
  assign pl_clk_div_out_0 = processing_system7_0_pl_clk_div_out;
  assign pl_clk_en_b_0_1 = pl_clk_en_b_0;
  assign pl_itf_clk_0_1 = pl_itf_clk_0;
  assign pl_ra_clk_0_1 = pl_ra_clk_0;
  assign pl_rst_n_0_1 = pl_rst_n_0;
  assign pl_scan_clk_0_1 = pl_scan_clk_0;
  assign pl_scan_rst_n_0_1 = pl_scan_rst_n_0;
  assign processing_system7_0_AI_IRQ_pl_int_ready = AI_IRQ_0_pl_int_ready;
  assign processing_system7_0_M_AI_HP_pl_arready = M_AI_HP_0_pl_arready;
  assign processing_system7_0_M_AI_HP_pl_awready = M_AI_HP_0_pl_awready;
  assign processing_system7_0_M_AI_HP_pl_bvalid = M_AI_HP_0_pl_bvalid;
  assign processing_system7_0_M_AI_HP_pl_rdata = M_AI_HP_0_pl_rdata[511:0];
  assign processing_system7_0_M_AI_HP_pl_rlast = M_AI_HP_0_pl_rlast;
  assign processing_system7_0_M_AI_HP_pl_rvalid = M_AI_HP_0_pl_rvalid;
  assign processing_system7_0_USBIND_0_VBUS_PWRFAULT = USBIND_0_0_vbus_pwrfault;
  assign processing_system7_1_FCLK_CLK0 = gp_axi_aclk;
  assign reset_n_1 = reset_n;
  assign soft_rst_n_1 = soft_rst_n;
  assign test_irq_1 = test_irq;
  ps_ai_axi_interconnect_0_0 axi_interconnect_0
       (.ACLK(processing_system7_1_FCLK_CLK0),
        .ARESETN(ARESETN_1),
        .M00_ACLK(processing_system7_1_FCLK_CLK0),
        .M00_ARESETN(M00_ARESETN_1),
        .M00_AXI_araddr(axi_interconnect_0_M00_AXI_ARADDR),
        .M00_AXI_arburst(axi_interconnect_0_M00_AXI_ARBURST),
        .M00_AXI_arcache(axi_interconnect_0_M00_AXI_ARCACHE),
        .M00_AXI_arid(axi_interconnect_0_M00_AXI_ARID),
        .M00_AXI_arlen(axi_interconnect_0_M00_AXI_ARLEN),
        .M00_AXI_arlock(axi_interconnect_0_M00_AXI_ARLOCK),
        .M00_AXI_arprot(axi_interconnect_0_M00_AXI_ARPROT),
        .M00_AXI_arqos(axi_interconnect_0_M00_AXI_ARQOS),
        .M00_AXI_arready(axi_interconnect_0_M00_AXI_ARREADY),
        .M00_AXI_arsize(axi_interconnect_0_M00_AXI_ARSIZE),
        .M00_AXI_arvalid(axi_interconnect_0_M00_AXI_ARVALID),
        .M00_AXI_awaddr(axi_interconnect_0_M00_AXI_AWADDR),
        .M00_AXI_awburst(axi_interconnect_0_M00_AXI_AWBURST),
        .M00_AXI_awcache(axi_interconnect_0_M00_AXI_AWCACHE),
        .M00_AXI_awid(axi_interconnect_0_M00_AXI_AWID),
        .M00_AXI_awlen(axi_interconnect_0_M00_AXI_AWLEN),
        .M00_AXI_awlock(axi_interconnect_0_M00_AXI_AWLOCK),
        .M00_AXI_awprot(axi_interconnect_0_M00_AXI_AWPROT),
        .M00_AXI_awqos(axi_interconnect_0_M00_AXI_AWQOS),
        .M00_AXI_awready(axi_interconnect_0_M00_AXI_AWREADY),
        .M00_AXI_awsize(axi_interconnect_0_M00_AXI_AWSIZE),
        .M00_AXI_awvalid(axi_interconnect_0_M00_AXI_AWVALID),
        .M00_AXI_bid(axi_interconnect_0_M00_AXI_BID),
        .M00_AXI_bready(axi_interconnect_0_M00_AXI_BREADY),
        .M00_AXI_bresp(axi_interconnect_0_M00_AXI_BRESP),
        .M00_AXI_bvalid(axi_interconnect_0_M00_AXI_BVALID),
        .M00_AXI_rdata(axi_interconnect_0_M00_AXI_RDATA),
        .M00_AXI_rid(axi_interconnect_0_M00_AXI_RID),
        .M00_AXI_rlast(axi_interconnect_0_M00_AXI_RLAST),
        .M00_AXI_rready(axi_interconnect_0_M00_AXI_RREADY),
        .M00_AXI_rresp(axi_interconnect_0_M00_AXI_RRESP),
        .M00_AXI_rvalid(axi_interconnect_0_M00_AXI_RVALID),
        .M00_AXI_wdata(axi_interconnect_0_M00_AXI_WDATA),
        .M00_AXI_wid(axi_interconnect_0_M00_AXI_WID),
        .M00_AXI_wlast(axi_interconnect_0_M00_AXI_WLAST),
        .M00_AXI_wready(axi_interconnect_0_M00_AXI_WREADY),
        .M00_AXI_wstrb(axi_interconnect_0_M00_AXI_WSTRB),
        .M00_AXI_wvalid(axi_interconnect_0_M00_AXI_WVALID),
        .M01_ACLK(processing_system7_1_FCLK_CLK0),
        .M01_ARESETN(M00_ARESETN_1),
        .M01_AXI_araddr(axi_interconnect_0_M01_AXI_ARADDR),
        .M01_AXI_arburst(axi_interconnect_0_M01_AXI_ARBURST),
        .M01_AXI_arcache(axi_interconnect_0_M01_AXI_ARCACHE),
        .M01_AXI_arid(axi_interconnect_0_M01_AXI_ARID),
        .M01_AXI_arlen(axi_interconnect_0_M01_AXI_ARLEN),
        .M01_AXI_arlock(axi_interconnect_0_M01_AXI_ARLOCK),
        .M01_AXI_arprot(axi_interconnect_0_M01_AXI_ARPROT),
        .M01_AXI_arqos(axi_interconnect_0_M01_AXI_ARQOS),
        .M01_AXI_arready(axi_interconnect_0_M01_AXI_ARREADY),
        .M01_AXI_arsize(axi_interconnect_0_M01_AXI_ARSIZE),
        .M01_AXI_arvalid(axi_interconnect_0_M01_AXI_ARVALID),
        .M01_AXI_awaddr(axi_interconnect_0_M01_AXI_AWADDR),
        .M01_AXI_awburst(axi_interconnect_0_M01_AXI_AWBURST),
        .M01_AXI_awcache(axi_interconnect_0_M01_AXI_AWCACHE),
        .M01_AXI_awid(axi_interconnect_0_M01_AXI_AWID),
        .M01_AXI_awlen(axi_interconnect_0_M01_AXI_AWLEN),
        .M01_AXI_awlock(axi_interconnect_0_M01_AXI_AWLOCK),
        .M01_AXI_awprot(axi_interconnect_0_M01_AXI_AWPROT),
        .M01_AXI_awqos(axi_interconnect_0_M01_AXI_AWQOS),
        .M01_AXI_awready(axi_interconnect_0_M01_AXI_AWREADY),
        .M01_AXI_awsize(axi_interconnect_0_M01_AXI_AWSIZE),
        .M01_AXI_awvalid(axi_interconnect_0_M01_AXI_AWVALID),
        .M01_AXI_bid(axi_interconnect_0_M01_AXI_BID),
        .M01_AXI_bready(axi_interconnect_0_M01_AXI_BREADY),
        .M01_AXI_bresp(axi_interconnect_0_M01_AXI_BRESP),
        .M01_AXI_bvalid(axi_interconnect_0_M01_AXI_BVALID),
        .M01_AXI_rdata(axi_interconnect_0_M01_AXI_RDATA),
        .M01_AXI_rid(axi_interconnect_0_M01_AXI_RID),
        .M01_AXI_rlast(axi_interconnect_0_M01_AXI_RLAST),
        .M01_AXI_rready(axi_interconnect_0_M01_AXI_RREADY),
        .M01_AXI_rresp(axi_interconnect_0_M01_AXI_RRESP),
        .M01_AXI_rvalid(axi_interconnect_0_M01_AXI_RVALID),
        .M01_AXI_wdata(axi_interconnect_0_M01_AXI_WDATA),
        .M01_AXI_wid(axi_interconnect_0_M01_AXI_WID),
        .M01_AXI_wlast(axi_interconnect_0_M01_AXI_WLAST),
        .M01_AXI_wready(axi_interconnect_0_M01_AXI_WREADY),
        .M01_AXI_wstrb(axi_interconnect_0_M01_AXI_WSTRB),
        .M01_AXI_wvalid(axi_interconnect_0_M01_AXI_WVALID),
        .S00_ACLK(processing_system7_1_FCLK_CLK0),
        .S00_ARESETN(M00_ARESETN_1),
        .S00_AXI_araddr(S00_AXI_1_ARADDR),
        .S00_AXI_arburst(S00_AXI_1_ARBURST),
        .S00_AXI_arcache(S00_AXI_1_ARCACHE),
        .S00_AXI_arid(S00_AXI_1_ARID),
        .S00_AXI_arlen(S00_AXI_1_ARLEN),
        .S00_AXI_arlock(S00_AXI_1_ARLOCK),
        .S00_AXI_arprot(S00_AXI_1_ARPROT),
        .S00_AXI_arqos(S00_AXI_1_ARQOS),
        .S00_AXI_arready(S00_AXI_1_ARREADY),
        .S00_AXI_arsize(S00_AXI_1_ARSIZE),
        .S00_AXI_arvalid(S00_AXI_1_ARVALID),
        .S00_AXI_awaddr(S00_AXI_1_AWADDR),
        .S00_AXI_awburst(S00_AXI_1_AWBURST),
        .S00_AXI_awcache(S00_AXI_1_AWCACHE),
        .S00_AXI_awid(S00_AXI_1_AWID),
        .S00_AXI_awlen(S00_AXI_1_AWLEN),
        .S00_AXI_awlock(S00_AXI_1_AWLOCK),
        .S00_AXI_awprot(S00_AXI_1_AWPROT),
        .S00_AXI_awqos(S00_AXI_1_AWQOS),
        .S00_AXI_awready(S00_AXI_1_AWREADY),
        .S00_AXI_awsize(S00_AXI_1_AWSIZE),
        .S00_AXI_awvalid(S00_AXI_1_AWVALID),
        .S00_AXI_bid(S00_AXI_1_BID),
        .S00_AXI_bready(S00_AXI_1_BREADY),
        .S00_AXI_bresp(S00_AXI_1_BRESP),
        .S00_AXI_bvalid(S00_AXI_1_BVALID),
        .S00_AXI_rdata(S00_AXI_1_RDATA),
        .S00_AXI_rid(S00_AXI_1_RID),
        .S00_AXI_rlast(S00_AXI_1_RLAST),
        .S00_AXI_rready(S00_AXI_1_RREADY),
        .S00_AXI_rresp(S00_AXI_1_RRESP),
        .S00_AXI_rvalid(S00_AXI_1_RVALID),
        .S00_AXI_wdata(S00_AXI_1_WDATA),
        .S00_AXI_wid(S00_AXI_1_WID),
        .S00_AXI_wlast(S00_AXI_1_WLAST),
        .S00_AXI_wready(S00_AXI_1_WREADY),
        .S00_AXI_wstrb(S00_AXI_1_WSTRB),
        .S00_AXI_wvalid(S00_AXI_1_WVALID));
  ps_ai_axi_interconnect_1_0 axi_interconnect_1
       (.ACLK(processing_system7_1_FCLK_CLK0),
        .ARESETN(ARESETN_1),
        .M00_ACLK(processing_system7_1_FCLK_CLK0),
        .M00_ARESETN(M00_ARESETN_1),
        .M00_AXI_araddr(axi_interconnect_1_M00_AXI_ARADDR),
        .M00_AXI_arburst(axi_interconnect_1_M00_AXI_ARBURST),
        .M00_AXI_arcache(axi_interconnect_1_M00_AXI_ARCACHE),
        .M00_AXI_arid(axi_interconnect_1_M00_AXI_ARID),
        .M00_AXI_arlen(axi_interconnect_1_M00_AXI_ARLEN),
        .M00_AXI_arlock(axi_interconnect_1_M00_AXI_ARLOCK),
        .M00_AXI_arprot(axi_interconnect_1_M00_AXI_ARPROT),
        .M00_AXI_arqos(axi_interconnect_1_M00_AXI_ARQOS),
        .M00_AXI_arready(axi_interconnect_1_M00_AXI_ARREADY),
        .M00_AXI_arsize(axi_interconnect_1_M00_AXI_ARSIZE),
        .M00_AXI_arvalid(axi_interconnect_1_M00_AXI_ARVALID),
        .M00_AXI_awaddr(axi_interconnect_1_M00_AXI_AWADDR),
        .M00_AXI_awburst(axi_interconnect_1_M00_AXI_AWBURST),
        .M00_AXI_awcache(axi_interconnect_1_M00_AXI_AWCACHE),
        .M00_AXI_awid(axi_interconnect_1_M00_AXI_AWID),
        .M00_AXI_awlen(axi_interconnect_1_M00_AXI_AWLEN),
        .M00_AXI_awlock(axi_interconnect_1_M00_AXI_AWLOCK),
        .M00_AXI_awprot(axi_interconnect_1_M00_AXI_AWPROT),
        .M00_AXI_awqos(axi_interconnect_1_M00_AXI_AWQOS),
        .M00_AXI_awready(axi_interconnect_1_M00_AXI_AWREADY),
        .M00_AXI_awsize(axi_interconnect_1_M00_AXI_AWSIZE),
        .M00_AXI_awvalid(axi_interconnect_1_M00_AXI_AWVALID),
        .M00_AXI_bid(axi_interconnect_1_M00_AXI_BID),
        .M00_AXI_bready(axi_interconnect_1_M00_AXI_BREADY),
        .M00_AXI_bresp(axi_interconnect_1_M00_AXI_BRESP),
        .M00_AXI_bvalid(axi_interconnect_1_M00_AXI_BVALID),
        .M00_AXI_rdata(axi_interconnect_1_M00_AXI_RDATA),
        .M00_AXI_rid(axi_interconnect_1_M00_AXI_RID),
        .M00_AXI_rlast(axi_interconnect_1_M00_AXI_RLAST),
        .M00_AXI_rready(axi_interconnect_1_M00_AXI_RREADY),
        .M00_AXI_rresp(axi_interconnect_1_M00_AXI_RRESP),
        .M00_AXI_rvalid(axi_interconnect_1_M00_AXI_RVALID),
        .M00_AXI_wdata(axi_interconnect_1_M00_AXI_WDATA),
        .M00_AXI_wid(axi_interconnect_1_M00_AXI_WID),
        .M00_AXI_wlast(axi_interconnect_1_M00_AXI_WLAST),
        .M00_AXI_wready(axi_interconnect_1_M00_AXI_WREADY),
        .M00_AXI_wstrb(axi_interconnect_1_M00_AXI_WSTRB),
        .M00_AXI_wvalid(axi_interconnect_1_M00_AXI_WVALID),
        .M01_ACLK(processing_system7_1_FCLK_CLK0),
        .M01_ARESETN(M00_ARESETN_1),
        .M01_AXI_araddr(axi_interconnect_1_M01_AXI_ARADDR),
        .M01_AXI_arburst(axi_interconnect_1_M01_AXI_ARBURST),
        .M01_AXI_arcache(axi_interconnect_1_M01_AXI_ARCACHE),
        .M01_AXI_arid(axi_interconnect_1_M01_AXI_ARID),
        .M01_AXI_arlen(axi_interconnect_1_M01_AXI_ARLEN),
        .M01_AXI_arlock(axi_interconnect_1_M01_AXI_ARLOCK),
        .M01_AXI_arprot(axi_interconnect_1_M01_AXI_ARPROT),
        .M01_AXI_arqos(axi_interconnect_1_M01_AXI_ARQOS),
        .M01_AXI_arready(axi_interconnect_1_M01_AXI_ARREADY),
        .M01_AXI_arsize(axi_interconnect_1_M01_AXI_ARSIZE),
        .M01_AXI_arvalid(axi_interconnect_1_M01_AXI_ARVALID),
        .M01_AXI_awaddr(axi_interconnect_1_M01_AXI_AWADDR),
        .M01_AXI_awburst(axi_interconnect_1_M01_AXI_AWBURST),
        .M01_AXI_awcache(axi_interconnect_1_M01_AXI_AWCACHE),
        .M01_AXI_awid(axi_interconnect_1_M01_AXI_AWID),
        .M01_AXI_awlen(axi_interconnect_1_M01_AXI_AWLEN),
        .M01_AXI_awlock(axi_interconnect_1_M01_AXI_AWLOCK),
        .M01_AXI_awprot(axi_interconnect_1_M01_AXI_AWPROT),
        .M01_AXI_awqos(axi_interconnect_1_M01_AXI_AWQOS),
        .M01_AXI_awready(axi_interconnect_1_M01_AXI_AWREADY),
        .M01_AXI_awsize(axi_interconnect_1_M01_AXI_AWSIZE),
        .M01_AXI_awvalid(axi_interconnect_1_M01_AXI_AWVALID),
        .M01_AXI_bid(axi_interconnect_1_M01_AXI_BID),
        .M01_AXI_bready(axi_interconnect_1_M01_AXI_BREADY),
        .M01_AXI_bresp(axi_interconnect_1_M01_AXI_BRESP),
        .M01_AXI_bvalid(axi_interconnect_1_M01_AXI_BVALID),
        .M01_AXI_rdata(axi_interconnect_1_M01_AXI_RDATA),
        .M01_AXI_rid(axi_interconnect_1_M01_AXI_RID),
        .M01_AXI_rlast(axi_interconnect_1_M01_AXI_RLAST),
        .M01_AXI_rready(axi_interconnect_1_M01_AXI_RREADY),
        .M01_AXI_rresp(axi_interconnect_1_M01_AXI_RRESP),
        .M01_AXI_rvalid(axi_interconnect_1_M01_AXI_RVALID),
        .M01_AXI_wdata(axi_interconnect_1_M01_AXI_WDATA),
        .M01_AXI_wid(axi_interconnect_1_M01_AXI_WID),
        .M01_AXI_wlast(axi_interconnect_1_M01_AXI_WLAST),
        .M01_AXI_wready(axi_interconnect_1_M01_AXI_WREADY),
        .M01_AXI_wstrb(axi_interconnect_1_M01_AXI_WSTRB),
        .M01_AXI_wvalid(axi_interconnect_1_M01_AXI_WVALID),
        .S00_ACLK(processing_system7_1_FCLK_CLK0),
        .S00_ARESETN(M00_ARESETN_1),
        .S00_AXI_araddr(S00_AXI_2_ARADDR),
        .S00_AXI_arburst(S00_AXI_2_ARBURST),
        .S00_AXI_arcache(S00_AXI_2_ARCACHE),
        .S00_AXI_arid(S00_AXI_2_ARID),
        .S00_AXI_arlen(S00_AXI_2_ARLEN),
        .S00_AXI_arlock(S00_AXI_2_ARLOCK),
        .S00_AXI_arprot(S00_AXI_2_ARPROT),
        .S00_AXI_arqos(S00_AXI_2_ARQOS),
        .S00_AXI_arready(S00_AXI_2_ARREADY),
        .S00_AXI_arsize(S00_AXI_2_ARSIZE),
        .S00_AXI_arvalid(S00_AXI_2_ARVALID),
        .S00_AXI_awaddr(S00_AXI_2_AWADDR),
        .S00_AXI_awburst(S00_AXI_2_AWBURST),
        .S00_AXI_awcache(S00_AXI_2_AWCACHE),
        .S00_AXI_awid(S00_AXI_2_AWID),
        .S00_AXI_awlen(S00_AXI_2_AWLEN),
        .S00_AXI_awlock(S00_AXI_2_AWLOCK),
        .S00_AXI_awprot(S00_AXI_2_AWPROT),
        .S00_AXI_awqos(S00_AXI_2_AWQOS),
        .S00_AXI_awready(S00_AXI_2_AWREADY),
        .S00_AXI_awsize(S00_AXI_2_AWSIZE),
        .S00_AXI_awvalid(S00_AXI_2_AWVALID),
        .S00_AXI_bid(S00_AXI_2_BID),
        .S00_AXI_bready(S00_AXI_2_BREADY),
        .S00_AXI_bresp(S00_AXI_2_BRESP),
        .S00_AXI_bvalid(S00_AXI_2_BVALID),
        .S00_AXI_rdata(S00_AXI_2_RDATA),
        .S00_AXI_rid(S00_AXI_2_RID),
        .S00_AXI_rlast(S00_AXI_2_RLAST),
        .S00_AXI_rready(S00_AXI_2_RREADY),
        .S00_AXI_rresp(S00_AXI_2_RRESP),
        .S00_AXI_rvalid(S00_AXI_2_RVALID),
        .S00_AXI_wdata(S00_AXI_2_WDATA),
        .S00_AXI_wid(S00_AXI_2_WID),
        .S00_AXI_wlast(S00_AXI_2_WLAST),
        .S00_AXI_wready(S00_AXI_2_WREADY),
        .S00_AXI_wstrb(S00_AXI_2_WSTRB),
        .S00_AXI_wvalid(S00_AXI_2_WVALID));
  ps_ai_axi_interconnect_3_0 axi_interconnect_4
       (.ACLK(hp_axi_aclk_1),
        .ARESETN(proc_sys_reset_1_peripheral_aresetn),
        .M00_ACLK(hp_axi_aclk_1),
        .M00_ARESETN(proc_sys_reset_1_peripheral_aresetn),
        .M00_AXI_araddr(axi_interconnect_4_M00_AXI_ARADDR),
        .M00_AXI_arburst(axi_interconnect_4_M00_AXI_ARBURST),
        .M00_AXI_arcache(axi_interconnect_4_M00_AXI_ARCACHE),
        .M00_AXI_arid(axi_interconnect_4_M00_AXI_ARID),
        .M00_AXI_arlen(axi_interconnect_4_M00_AXI_ARLEN),
        .M00_AXI_arlock(axi_interconnect_4_M00_AXI_ARLOCK),
        .M00_AXI_arprot(axi_interconnect_4_M00_AXI_ARPROT),
        .M00_AXI_arqos(axi_interconnect_4_M00_AXI_ARQOS),
        .M00_AXI_arready(axi_interconnect_4_M00_AXI_ARREADY),
        .M00_AXI_arsize(axi_interconnect_4_M00_AXI_ARSIZE),
        .M00_AXI_arvalid(axi_interconnect_4_M00_AXI_ARVALID),
        .M00_AXI_awaddr(axi_interconnect_4_M00_AXI_AWADDR),
        .M00_AXI_awburst(axi_interconnect_4_M00_AXI_AWBURST),
        .M00_AXI_awcache(axi_interconnect_4_M00_AXI_AWCACHE),
        .M00_AXI_awid(axi_interconnect_4_M00_AXI_AWID),
        .M00_AXI_awlen(axi_interconnect_4_M00_AXI_AWLEN),
        .M00_AXI_awlock(axi_interconnect_4_M00_AXI_AWLOCK),
        .M00_AXI_awprot(axi_interconnect_4_M00_AXI_AWPROT),
        .M00_AXI_awqos(axi_interconnect_4_M00_AXI_AWQOS),
        .M00_AXI_awready(axi_interconnect_4_M00_AXI_AWREADY),
        .M00_AXI_awsize(axi_interconnect_4_M00_AXI_AWSIZE),
        .M00_AXI_awvalid(axi_interconnect_4_M00_AXI_AWVALID),
        .M00_AXI_bid(axi_interconnect_4_M00_AXI_BID),
        .M00_AXI_bready(axi_interconnect_4_M00_AXI_BREADY),
        .M00_AXI_bresp(axi_interconnect_4_M00_AXI_BRESP),
        .M00_AXI_bvalid(axi_interconnect_4_M00_AXI_BVALID),
        .M00_AXI_rdata(axi_interconnect_4_M00_AXI_RDATA),
        .M00_AXI_rid(axi_interconnect_4_M00_AXI_RID),
        .M00_AXI_rlast(axi_interconnect_4_M00_AXI_RLAST),
        .M00_AXI_rready(axi_interconnect_4_M00_AXI_RREADY),
        .M00_AXI_rresp(axi_interconnect_4_M00_AXI_RRESP),
        .M00_AXI_rvalid(axi_interconnect_4_M00_AXI_RVALID),
        .M00_AXI_wdata(axi_interconnect_4_M00_AXI_WDATA),
        .M00_AXI_wid(axi_interconnect_4_M00_AXI_WID),
        .M00_AXI_wlast(axi_interconnect_4_M00_AXI_WLAST),
        .M00_AXI_wready(axi_interconnect_4_M00_AXI_WREADY),
        .M00_AXI_wstrb(axi_interconnect_4_M00_AXI_WSTRB),
        .M00_AXI_wvalid(axi_interconnect_4_M00_AXI_WVALID),
        .S00_ACLK(hp_axi_aclk_1),
        .S00_ARESETN(proc_sys_reset_1_peripheral_aresetn),
        .S00_AXI_araddr(S_AXI_HP2_0_1_ARADDR),
        .S00_AXI_arburst(S_AXI_HP2_0_1_ARBURST),
        .S00_AXI_arcache(S_AXI_HP2_0_1_ARCACHE),
        .S00_AXI_arid(S_AXI_HP2_0_1_ARID),
        .S00_AXI_arlen(S_AXI_HP2_0_1_ARLEN),
        .S00_AXI_arlock(S_AXI_HP2_0_1_ARLOCK),
        .S00_AXI_arprot(S_AXI_HP2_0_1_ARPROT),
        .S00_AXI_arqos(S_AXI_HP2_0_1_ARQOS),
        .S00_AXI_arready(S_AXI_HP2_0_1_ARREADY),
        .S00_AXI_arsize(S_AXI_HP2_0_1_ARSIZE),
        .S00_AXI_arvalid(S_AXI_HP2_0_1_ARVALID),
        .S00_AXI_awaddr(S_AXI_HP2_0_1_AWADDR),
        .S00_AXI_awburst(S_AXI_HP2_0_1_AWBURST),
        .S00_AXI_awcache(S_AXI_HP2_0_1_AWCACHE),
        .S00_AXI_awid(S_AXI_HP2_0_1_AWID),
        .S00_AXI_awlen(S_AXI_HP2_0_1_AWLEN),
        .S00_AXI_awlock(S_AXI_HP2_0_1_AWLOCK),
        .S00_AXI_awprot(S_AXI_HP2_0_1_AWPROT),
        .S00_AXI_awqos(S_AXI_HP2_0_1_AWQOS),
        .S00_AXI_awready(S_AXI_HP2_0_1_AWREADY),
        .S00_AXI_awsize(S_AXI_HP2_0_1_AWSIZE),
        .S00_AXI_awvalid(S_AXI_HP2_0_1_AWVALID),
        .S00_AXI_bid(S_AXI_HP2_0_1_BID),
        .S00_AXI_bready(S_AXI_HP2_0_1_BREADY),
        .S00_AXI_bresp(S_AXI_HP2_0_1_BRESP),
        .S00_AXI_bvalid(S_AXI_HP2_0_1_BVALID),
        .S00_AXI_rdata(S_AXI_HP2_0_1_RDATA),
        .S00_AXI_rid(S_AXI_HP2_0_1_RID),
        .S00_AXI_rlast(S_AXI_HP2_0_1_RLAST),
        .S00_AXI_rready(S_AXI_HP2_0_1_RREADY),
        .S00_AXI_rresp(S_AXI_HP2_0_1_RRESP),
        .S00_AXI_rvalid(S_AXI_HP2_0_1_RVALID),
        .S00_AXI_wdata(S_AXI_HP2_0_1_WDATA),
        .S00_AXI_wid(S_AXI_HP2_0_1_WID),
        .S00_AXI_wlast(S_AXI_HP2_0_1_WLAST),
        .S00_AXI_wready(S_AXI_HP2_0_1_WREADY),
        .S00_AXI_wstrb(S_AXI_HP2_0_1_WSTRB),
        .S00_AXI_wvalid(S_AXI_HP2_0_1_WVALID),
        .S01_ACLK(hp_axi_aclk_1),
        .S01_ARESETN(proc_sys_reset_1_peripheral_aresetn),
        .S01_AXI_araddr(S_AXI_HP2_1_1_ARADDR),
        .S01_AXI_arburst(S_AXI_HP2_1_1_ARBURST),
        .S01_AXI_arcache(S_AXI_HP2_1_1_ARCACHE),
        .S01_AXI_arid(S_AXI_HP2_1_1_ARID),
        .S01_AXI_arlen(S_AXI_HP2_1_1_ARLEN),
        .S01_AXI_arlock(S_AXI_HP2_1_1_ARLOCK),
        .S01_AXI_arprot(S_AXI_HP2_1_1_ARPROT),
        .S01_AXI_arqos(S_AXI_HP2_1_1_ARQOS),
        .S01_AXI_arready(S_AXI_HP2_1_1_ARREADY),
        .S01_AXI_arsize(S_AXI_HP2_1_1_ARSIZE),
        .S01_AXI_arvalid(S_AXI_HP2_1_1_ARVALID),
        .S01_AXI_awaddr(S_AXI_HP2_1_1_AWADDR),
        .S01_AXI_awburst(S_AXI_HP2_1_1_AWBURST),
        .S01_AXI_awcache(S_AXI_HP2_1_1_AWCACHE),
        .S01_AXI_awid(S_AXI_HP2_1_1_AWID),
        .S01_AXI_awlen(S_AXI_HP2_1_1_AWLEN),
        .S01_AXI_awlock(S_AXI_HP2_1_1_AWLOCK),
        .S01_AXI_awprot(S_AXI_HP2_1_1_AWPROT),
        .S01_AXI_awqos(S_AXI_HP2_1_1_AWQOS),
        .S01_AXI_awready(S_AXI_HP2_1_1_AWREADY),
        .S01_AXI_awsize(S_AXI_HP2_1_1_AWSIZE),
        .S01_AXI_awvalid(S_AXI_HP2_1_1_AWVALID),
        .S01_AXI_bid(S_AXI_HP2_1_1_BID),
        .S01_AXI_bready(S_AXI_HP2_1_1_BREADY),
        .S01_AXI_bresp(S_AXI_HP2_1_1_BRESP),
        .S01_AXI_bvalid(S_AXI_HP2_1_1_BVALID),
        .S01_AXI_rdata(S_AXI_HP2_1_1_RDATA),
        .S01_AXI_rid(S_AXI_HP2_1_1_RID),
        .S01_AXI_rlast(S_AXI_HP2_1_1_RLAST),
        .S01_AXI_rready(S_AXI_HP2_1_1_RREADY),
        .S01_AXI_rresp(S_AXI_HP2_1_1_RRESP),
        .S01_AXI_rvalid(S_AXI_HP2_1_1_RVALID),
        .S01_AXI_wdata(S_AXI_HP2_1_1_WDATA),
        .S01_AXI_wid(S_AXI_HP2_1_1_WID),
        .S01_AXI_wlast(S_AXI_HP2_1_1_WLAST),
        .S01_AXI_wready(S_AXI_HP2_1_1_WREADY),
        .S01_AXI_wstrb(S_AXI_HP2_1_1_WSTRB),
        .S01_AXI_wvalid(S_AXI_HP2_1_1_WVALID));
  ps_ai_proc_sys_reset_0_1 proc_sys_reset_0
       (.aux_reset_in(1'b1),
        .dcm_locked(1'b1),
        .ext_reset_in(util_vector_logic_0_Res),
        .interconnect_aresetn(ARESETN_1),
        .mb_debug_sys_rst(1'b0),
        .peripheral_aresetn(M00_ARESETN_1),
        .slowest_sync_clk(processing_system7_1_FCLK_CLK0));
  ps_ai_proc_sys_reset_0_0 proc_sys_reset_1
       (.aux_reset_in(1'b1),
        .dcm_locked(1'b1),
        .ext_reset_in(util_vector_logic_0_Res),
        .mb_debug_sys_rst(1'b0),
        .peripheral_aresetn(proc_sys_reset_1_peripheral_aresetn),
        .slowest_sync_clk(hp_axi_aclk_1));
  ps_ai_processing_system7_0_0 processing_system7_0
       (.DDR_Addr(DDR_0_addr[14:0]),
        .DDR_BankAddr(DDR_0_ba[2:0]),
        .DDR_CAS_n(DDR_0_cas_n),
        .DDR_CKE(DDR_0_cke),
        .DDR_CS_n(DDR_0_cs_n),
        .DDR_Clk(DDR_0_ck_p),
        .DDR_Clk_n(DDR_0_ck_n),
        .DDR_DM(DDR_0_dm[3:0]),
        .DDR_DQ(DDR_0_dq[31:0]),
        .DDR_DQS(DDR_0_dqs_p[3:0]),
        .DDR_DQS_n(DDR_0_dqs_n[3:0]),
        .DDR_DRSTB(DDR_0_reset_n),
        .DDR_ODT(DDR_0_odt),
        .DDR_RAS_n(DDR_0_ras_n),
        .DDR_VRN(FIXED_IO_0_ddr_vrn),
        .DDR_VRP(FIXED_IO_0_ddr_vrp),
        .DDR_WEB(DDR_0_we_n),
        .FCLK_CLK0(processing_system7_0_FCLK_CLK0),
        .FCLK_RESET0_N(processing_system7_0_FCLK_RESET0_N),
        .GPIO_I({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .I2C0_SCL_I(1'b0),
        .I2C0_SDA_I(1'b0),
        .I2C1_SCL_I(1'b0),
        .I2C1_SDA_I(1'b0),
        .IRQ_F2P(xlconcat_0_dout),
        .MIO(FIXED_IO_0_mio[53:0]),
        .M_AXI_GP0_ACLK(processing_system7_1_FCLK_CLK0),
        .M_AXI_GP0_ARADDR(S00_AXI_1_ARADDR),
        .M_AXI_GP0_ARBURST(S00_AXI_1_ARBURST),
        .M_AXI_GP0_ARCACHE(S00_AXI_1_ARCACHE),
        .M_AXI_GP0_ARID(S00_AXI_1_ARID),
        .M_AXI_GP0_ARLEN(S00_AXI_1_ARLEN),
        .M_AXI_GP0_ARLOCK(S00_AXI_1_ARLOCK),
        .M_AXI_GP0_ARPROT(S00_AXI_1_ARPROT),
        .M_AXI_GP0_ARQOS(S00_AXI_1_ARQOS),
        .M_AXI_GP0_ARREADY(S00_AXI_1_ARREADY),
        .M_AXI_GP0_ARSIZE(S00_AXI_1_ARSIZE),
        .M_AXI_GP0_ARVALID(S00_AXI_1_ARVALID),
        .M_AXI_GP0_AWADDR(S00_AXI_1_AWADDR),
        .M_AXI_GP0_AWBURST(S00_AXI_1_AWBURST),
        .M_AXI_GP0_AWCACHE(S00_AXI_1_AWCACHE),
        .M_AXI_GP0_AWID(S00_AXI_1_AWID),
        .M_AXI_GP0_AWLEN(S00_AXI_1_AWLEN),
        .M_AXI_GP0_AWLOCK(S00_AXI_1_AWLOCK),
        .M_AXI_GP0_AWPROT(S00_AXI_1_AWPROT),
        .M_AXI_GP0_AWQOS(S00_AXI_1_AWQOS),
        .M_AXI_GP0_AWREADY(S00_AXI_1_AWREADY),
        .M_AXI_GP0_AWSIZE(S00_AXI_1_AWSIZE),
        .M_AXI_GP0_AWVALID(S00_AXI_1_AWVALID),
        .M_AXI_GP0_BID(S00_AXI_1_BID),
        .M_AXI_GP0_BREADY(S00_AXI_1_BREADY),
        .M_AXI_GP0_BRESP(S00_AXI_1_BRESP),
        .M_AXI_GP0_BVALID(S00_AXI_1_BVALID),
        .M_AXI_GP0_RDATA(S00_AXI_1_RDATA),
        .M_AXI_GP0_RID(S00_AXI_1_RID),
        .M_AXI_GP0_RLAST(S00_AXI_1_RLAST),
        .M_AXI_GP0_RREADY(S00_AXI_1_RREADY),
        .M_AXI_GP0_RRESP(S00_AXI_1_RRESP),
        .M_AXI_GP0_RVALID(S00_AXI_1_RVALID),
        .M_AXI_GP0_WDATA(S00_AXI_1_WDATA),
        .M_AXI_GP0_WID(S00_AXI_1_WID),
        .M_AXI_GP0_WLAST(S00_AXI_1_WLAST),
        .M_AXI_GP0_WREADY(S00_AXI_1_WREADY),
        .M_AXI_GP0_WSTRB(S00_AXI_1_WSTRB),
        .M_AXI_GP0_WVALID(S00_AXI_1_WVALID),
        .M_AXI_GP1_ACLK(processing_system7_1_FCLK_CLK0),
        .M_AXI_GP1_ARADDR(S00_AXI_2_ARADDR),
        .M_AXI_GP1_ARBURST(S00_AXI_2_ARBURST),
        .M_AXI_GP1_ARCACHE(S00_AXI_2_ARCACHE),
        .M_AXI_GP1_ARID(S00_AXI_2_ARID),
        .M_AXI_GP1_ARLEN(S00_AXI_2_ARLEN),
        .M_AXI_GP1_ARLOCK(S00_AXI_2_ARLOCK),
        .M_AXI_GP1_ARPROT(S00_AXI_2_ARPROT),
        .M_AXI_GP1_ARQOS(S00_AXI_2_ARQOS),
        .M_AXI_GP1_ARREADY(S00_AXI_2_ARREADY),
        .M_AXI_GP1_ARSIZE(S00_AXI_2_ARSIZE),
        .M_AXI_GP1_ARVALID(S00_AXI_2_ARVALID),
        .M_AXI_GP1_AWADDR(S00_AXI_2_AWADDR),
        .M_AXI_GP1_AWBURST(S00_AXI_2_AWBURST),
        .M_AXI_GP1_AWCACHE(S00_AXI_2_AWCACHE),
        .M_AXI_GP1_AWID(S00_AXI_2_AWID),
        .M_AXI_GP1_AWLEN(S00_AXI_2_AWLEN),
        .M_AXI_GP1_AWLOCK(S00_AXI_2_AWLOCK),
        .M_AXI_GP1_AWPROT(S00_AXI_2_AWPROT),
        .M_AXI_GP1_AWQOS(S00_AXI_2_AWQOS),
        .M_AXI_GP1_AWREADY(S00_AXI_2_AWREADY),
        .M_AXI_GP1_AWSIZE(S00_AXI_2_AWSIZE),
        .M_AXI_GP1_AWVALID(S00_AXI_2_AWVALID),
        .M_AXI_GP1_BID(S00_AXI_2_BID),
        .M_AXI_GP1_BREADY(S00_AXI_2_BREADY),
        .M_AXI_GP1_BRESP(S00_AXI_2_BRESP),
        .M_AXI_GP1_BVALID(S00_AXI_2_BVALID),
        .M_AXI_GP1_RDATA(S00_AXI_2_RDATA),
        .M_AXI_GP1_RID(S00_AXI_2_RID),
        .M_AXI_GP1_RLAST(S00_AXI_2_RLAST),
        .M_AXI_GP1_RREADY(S00_AXI_2_RREADY),
        .M_AXI_GP1_RRESP(S00_AXI_2_RRESP),
        .M_AXI_GP1_RVALID(S00_AXI_2_RVALID),
        .M_AXI_GP1_WDATA(S00_AXI_2_WDATA),
        .M_AXI_GP1_WID(S00_AXI_2_WID),
        .M_AXI_GP1_WLAST(S00_AXI_2_WLAST),
        .M_AXI_GP1_WREADY(S00_AXI_2_WREADY),
        .M_AXI_GP1_WSTRB(S00_AXI_2_WSTRB),
        .M_AXI_GP1_WVALID(S00_AXI_2_WVALID),
        .PJTAG_TCK(PJTAG_0_1_TCK),
        .PJTAG_TDI(PJTAG_0_1_TDI),
        .PJTAG_TDO(PJTAG_0_1_TDO),
        .PJTAG_TMS(PJTAG_0_1_TMS),
        .PS_CLK(FIXED_IO_0_ps_clk),
        .PS_PORB(FIXED_IO_0_ps_porb),
        .PS_SRSTB(FIXED_IO_0_ps_srstb),
        .S_AXI_HP0_ACLK(hp_axi_aclk_1),
        .S_AXI_HP0_ARADDR(S_AXI_HP0_0_1_ARADDR),
        .S_AXI_HP0_ARBURST(S_AXI_HP0_0_1_ARBURST),
        .S_AXI_HP0_ARCACHE(S_AXI_HP0_0_1_ARCACHE),
        .S_AXI_HP0_ARID(S_AXI_HP0_0_1_ARID),
        .S_AXI_HP0_ARLEN(S_AXI_HP0_0_1_ARLEN),
        .S_AXI_HP0_ARLOCK(S_AXI_HP0_0_1_ARLOCK),
        .S_AXI_HP0_ARPROT(S_AXI_HP0_0_1_ARPROT),
        .S_AXI_HP0_ARQOS(S_AXI_HP0_0_1_ARQOS),
        .S_AXI_HP0_ARREADY(S_AXI_HP0_0_1_ARREADY),
        .S_AXI_HP0_ARSIZE(S_AXI_HP0_0_1_ARSIZE),
        .S_AXI_HP0_ARVALID(S_AXI_HP0_0_1_ARVALID),
        .S_AXI_HP0_AWADDR(S_AXI_HP0_0_1_AWADDR),
        .S_AXI_HP0_AWBURST(S_AXI_HP0_0_1_AWBURST),
        .S_AXI_HP0_AWCACHE(S_AXI_HP0_0_1_AWCACHE),
        .S_AXI_HP0_AWID(S_AXI_HP0_0_1_AWID),
        .S_AXI_HP0_AWLEN(S_AXI_HP0_0_1_AWLEN),
        .S_AXI_HP0_AWLOCK(S_AXI_HP0_0_1_AWLOCK),
        .S_AXI_HP0_AWPROT(S_AXI_HP0_0_1_AWPROT),
        .S_AXI_HP0_AWQOS(S_AXI_HP0_0_1_AWQOS),
        .S_AXI_HP0_AWREADY(S_AXI_HP0_0_1_AWREADY),
        .S_AXI_HP0_AWSIZE(S_AXI_HP0_0_1_AWSIZE),
        .S_AXI_HP0_AWVALID(S_AXI_HP0_0_1_AWVALID),
        .S_AXI_HP0_BID(S_AXI_HP0_0_1_BID),
        .S_AXI_HP0_BREADY(S_AXI_HP0_0_1_BREADY),
        .S_AXI_HP0_BRESP(S_AXI_HP0_0_1_BRESP),
        .S_AXI_HP0_BVALID(S_AXI_HP0_0_1_BVALID),
        .S_AXI_HP0_RACOUNT(S_AXI_HP0_FIFO_CTRL_0_1_RACOUNT),
        .S_AXI_HP0_RCOUNT(S_AXI_HP0_FIFO_CTRL_0_1_RCOUNT),
        .S_AXI_HP0_RDATA(S_AXI_HP0_0_1_RDATA),
        .S_AXI_HP0_RDISSUECAP1_EN(S_AXI_HP0_FIFO_CTRL_0_1_RDISSUECAPEN),
        .S_AXI_HP0_RID(S_AXI_HP0_0_1_RID),
        .S_AXI_HP0_RLAST(S_AXI_HP0_0_1_RLAST),
        .S_AXI_HP0_RREADY(S_AXI_HP0_0_1_RREADY),
        .S_AXI_HP0_RRESP(S_AXI_HP0_0_1_RRESP),
        .S_AXI_HP0_RVALID(S_AXI_HP0_0_1_RVALID),
        .S_AXI_HP0_WACOUNT(S_AXI_HP0_FIFO_CTRL_0_1_WACOUNT),
        .S_AXI_HP0_WCOUNT(S_AXI_HP0_FIFO_CTRL_0_1_WCOUNT),
        .S_AXI_HP0_WDATA(S_AXI_HP0_0_1_WDATA),
        .S_AXI_HP0_WID(S_AXI_HP0_0_1_WID),
        .S_AXI_HP0_WLAST(S_AXI_HP0_0_1_WLAST),
        .S_AXI_HP0_WREADY(S_AXI_HP0_0_1_WREADY),
        .S_AXI_HP0_WRISSUECAP1_EN(S_AXI_HP0_FIFO_CTRL_0_1_WRISSUECAPEN),
        .S_AXI_HP0_WSTRB(S_AXI_HP0_0_1_WSTRB),
        .S_AXI_HP0_WVALID(S_AXI_HP0_0_1_WVALID),
        .S_AXI_HP1_ACLK(hp_axi_aclk_1),
        .S_AXI_HP1_ARADDR(S_AXI_HP1_0_1_ARADDR),
        .S_AXI_HP1_ARBURST(S_AXI_HP1_0_1_ARBURST),
        .S_AXI_HP1_ARCACHE(S_AXI_HP1_0_1_ARCACHE),
        .S_AXI_HP1_ARID(S_AXI_HP1_0_1_ARID),
        .S_AXI_HP1_ARLEN(S_AXI_HP1_0_1_ARLEN),
        .S_AXI_HP1_ARLOCK(S_AXI_HP1_0_1_ARLOCK),
        .S_AXI_HP1_ARPROT(S_AXI_HP1_0_1_ARPROT),
        .S_AXI_HP1_ARQOS(S_AXI_HP1_0_1_ARQOS),
        .S_AXI_HP1_ARREADY(S_AXI_HP1_0_1_ARREADY),
        .S_AXI_HP1_ARSIZE(S_AXI_HP1_0_1_ARSIZE),
        .S_AXI_HP1_ARVALID(S_AXI_HP1_0_1_ARVALID),
        .S_AXI_HP1_AWADDR(S_AXI_HP1_0_1_AWADDR),
        .S_AXI_HP1_AWBURST(S_AXI_HP1_0_1_AWBURST),
        .S_AXI_HP1_AWCACHE(S_AXI_HP1_0_1_AWCACHE),
        .S_AXI_HP1_AWID(S_AXI_HP1_0_1_AWID),
        .S_AXI_HP1_AWLEN(S_AXI_HP1_0_1_AWLEN),
        .S_AXI_HP1_AWLOCK(S_AXI_HP1_0_1_AWLOCK),
        .S_AXI_HP1_AWPROT(S_AXI_HP1_0_1_AWPROT),
        .S_AXI_HP1_AWQOS(S_AXI_HP1_0_1_AWQOS),
        .S_AXI_HP1_AWREADY(S_AXI_HP1_0_1_AWREADY),
        .S_AXI_HP1_AWSIZE(S_AXI_HP1_0_1_AWSIZE),
        .S_AXI_HP1_AWVALID(S_AXI_HP1_0_1_AWVALID),
        .S_AXI_HP1_BID(S_AXI_HP1_0_1_BID),
        .S_AXI_HP1_BREADY(S_AXI_HP1_0_1_BREADY),
        .S_AXI_HP1_BRESP(S_AXI_HP1_0_1_BRESP),
        .S_AXI_HP1_BVALID(S_AXI_HP1_0_1_BVALID),
        .S_AXI_HP1_RACOUNT(S_AXI_HP1_FIFO_CTRL_0_1_RACOUNT),
        .S_AXI_HP1_RCOUNT(S_AXI_HP1_FIFO_CTRL_0_1_RCOUNT),
        .S_AXI_HP1_RDATA(S_AXI_HP1_0_1_RDATA),
        .S_AXI_HP1_RDISSUECAP1_EN(S_AXI_HP1_FIFO_CTRL_0_1_RDISSUECAPEN),
        .S_AXI_HP1_RID(S_AXI_HP1_0_1_RID),
        .S_AXI_HP1_RLAST(S_AXI_HP1_0_1_RLAST),
        .S_AXI_HP1_RREADY(S_AXI_HP1_0_1_RREADY),
        .S_AXI_HP1_RRESP(S_AXI_HP1_0_1_RRESP),
        .S_AXI_HP1_RVALID(S_AXI_HP1_0_1_RVALID),
        .S_AXI_HP1_WACOUNT(S_AXI_HP1_FIFO_CTRL_0_1_WACOUNT),
        .S_AXI_HP1_WCOUNT(S_AXI_HP1_FIFO_CTRL_0_1_WCOUNT),
        .S_AXI_HP1_WDATA(S_AXI_HP1_0_1_WDATA),
        .S_AXI_HP1_WID(S_AXI_HP1_0_1_WID),
        .S_AXI_HP1_WLAST(S_AXI_HP1_0_1_WLAST),
        .S_AXI_HP1_WREADY(S_AXI_HP1_0_1_WREADY),
        .S_AXI_HP1_WRISSUECAP1_EN(S_AXI_HP1_FIFO_CTRL_0_1_WRISSUECAPEN),
        .S_AXI_HP1_WSTRB(S_AXI_HP1_0_1_WSTRB),
        .S_AXI_HP1_WVALID(S_AXI_HP1_0_1_WVALID),
        .S_AXI_HP2_ACLK(hp_axi_aclk_1),
        .S_AXI_HP2_ARADDR(axi_interconnect_4_M00_AXI_ARADDR),
        .S_AXI_HP2_ARBURST(axi_interconnect_4_M00_AXI_ARBURST),
        .S_AXI_HP2_ARCACHE(axi_interconnect_4_M00_AXI_ARCACHE),
        .S_AXI_HP2_ARID(axi_interconnect_4_M00_AXI_ARID),
        .S_AXI_HP2_ARLEN(axi_interconnect_4_M00_AXI_ARLEN),
        .S_AXI_HP2_ARLOCK(axi_interconnect_4_M00_AXI_ARLOCK),
        .S_AXI_HP2_ARPROT(axi_interconnect_4_M00_AXI_ARPROT),
        .S_AXI_HP2_ARQOS(axi_interconnect_4_M00_AXI_ARQOS),
        .S_AXI_HP2_ARREADY(axi_interconnect_4_M00_AXI_ARREADY),
        .S_AXI_HP2_ARSIZE(axi_interconnect_4_M00_AXI_ARSIZE),
        .S_AXI_HP2_ARVALID(axi_interconnect_4_M00_AXI_ARVALID),
        .S_AXI_HP2_AWADDR(axi_interconnect_4_M00_AXI_AWADDR),
        .S_AXI_HP2_AWBURST(axi_interconnect_4_M00_AXI_AWBURST),
        .S_AXI_HP2_AWCACHE(axi_interconnect_4_M00_AXI_AWCACHE),
        .S_AXI_HP2_AWID(axi_interconnect_4_M00_AXI_AWID),
        .S_AXI_HP2_AWLEN(axi_interconnect_4_M00_AXI_AWLEN),
        .S_AXI_HP2_AWLOCK(axi_interconnect_4_M00_AXI_AWLOCK),
        .S_AXI_HP2_AWPROT(axi_interconnect_4_M00_AXI_AWPROT),
        .S_AXI_HP2_AWQOS(axi_interconnect_4_M00_AXI_AWQOS),
        .S_AXI_HP2_AWREADY(axi_interconnect_4_M00_AXI_AWREADY),
        .S_AXI_HP2_AWSIZE(axi_interconnect_4_M00_AXI_AWSIZE),
        .S_AXI_HP2_AWVALID(axi_interconnect_4_M00_AXI_AWVALID),
        .S_AXI_HP2_BID(axi_interconnect_4_M00_AXI_BID),
        .S_AXI_HP2_BREADY(axi_interconnect_4_M00_AXI_BREADY),
        .S_AXI_HP2_BRESP(axi_interconnect_4_M00_AXI_BRESP),
        .S_AXI_HP2_BVALID(axi_interconnect_4_M00_AXI_BVALID),
        .S_AXI_HP2_RACOUNT(S_AXI_HP2_FIFO_CTRL_0_1_RACOUNT),
        .S_AXI_HP2_RCOUNT(S_AXI_HP2_FIFO_CTRL_0_1_RCOUNT),
        .S_AXI_HP2_RDATA(axi_interconnect_4_M00_AXI_RDATA),
        .S_AXI_HP2_RDISSUECAP1_EN(S_AXI_HP2_FIFO_CTRL_0_1_RDISSUECAPEN),
        .S_AXI_HP2_RID(axi_interconnect_4_M00_AXI_RID),
        .S_AXI_HP2_RLAST(axi_interconnect_4_M00_AXI_RLAST),
        .S_AXI_HP2_RREADY(axi_interconnect_4_M00_AXI_RREADY),
        .S_AXI_HP2_RRESP(axi_interconnect_4_M00_AXI_RRESP),
        .S_AXI_HP2_RVALID(axi_interconnect_4_M00_AXI_RVALID),
        .S_AXI_HP2_WACOUNT(S_AXI_HP2_FIFO_CTRL_0_1_WACOUNT),
        .S_AXI_HP2_WCOUNT(S_AXI_HP2_FIFO_CTRL_0_1_WCOUNT),
        .S_AXI_HP2_WDATA(axi_interconnect_4_M00_AXI_WDATA),
        .S_AXI_HP2_WID(axi_interconnect_4_M00_AXI_WID),
        .S_AXI_HP2_WLAST(axi_interconnect_4_M00_AXI_WLAST),
        .S_AXI_HP2_WREADY(axi_interconnect_4_M00_AXI_WREADY),
        .S_AXI_HP2_WRISSUECAP1_EN(S_AXI_HP2_FIFO_CTRL_0_1_WRISSUECAPEN),
        .S_AXI_HP2_WSTRB(axi_interconnect_4_M00_AXI_WSTRB),
        .S_AXI_HP2_WVALID(axi_interconnect_4_M00_AXI_WVALID),
        .S_AXI_HP3_ACLK(hp_axi_aclk_1),
        .S_AXI_HP3_ARADDR(S_AXI_HP3_0_1_ARADDR),
        .S_AXI_HP3_ARBURST(S_AXI_HP3_0_1_ARBURST),
        .S_AXI_HP3_ARCACHE(S_AXI_HP3_0_1_ARCACHE),
        .S_AXI_HP3_ARID(S_AXI_HP3_0_1_ARID),
        .S_AXI_HP3_ARLEN(S_AXI_HP3_0_1_ARLEN),
        .S_AXI_HP3_ARLOCK(S_AXI_HP3_0_1_ARLOCK),
        .S_AXI_HP3_ARPROT(S_AXI_HP3_0_1_ARPROT),
        .S_AXI_HP3_ARQOS(S_AXI_HP3_0_1_ARQOS),
        .S_AXI_HP3_ARREADY(S_AXI_HP3_0_1_ARREADY),
        .S_AXI_HP3_ARSIZE(S_AXI_HP3_0_1_ARSIZE),
        .S_AXI_HP3_ARVALID(S_AXI_HP3_0_1_ARVALID),
        .S_AXI_HP3_AWADDR(S_AXI_HP3_0_1_AWADDR),
        .S_AXI_HP3_AWBURST(S_AXI_HP3_0_1_AWBURST),
        .S_AXI_HP3_AWCACHE(S_AXI_HP3_0_1_AWCACHE),
        .S_AXI_HP3_AWID(S_AXI_HP3_0_1_AWID),
        .S_AXI_HP3_AWLEN(S_AXI_HP3_0_1_AWLEN),
        .S_AXI_HP3_AWLOCK(S_AXI_HP3_0_1_AWLOCK),
        .S_AXI_HP3_AWPROT(S_AXI_HP3_0_1_AWPROT),
        .S_AXI_HP3_AWQOS(S_AXI_HP3_0_1_AWQOS),
        .S_AXI_HP3_AWREADY(S_AXI_HP3_0_1_AWREADY),
        .S_AXI_HP3_AWSIZE(S_AXI_HP3_0_1_AWSIZE),
        .S_AXI_HP3_AWVALID(S_AXI_HP3_0_1_AWVALID),
        .S_AXI_HP3_BID(S_AXI_HP3_0_1_BID),
        .S_AXI_HP3_BREADY(S_AXI_HP3_0_1_BREADY),
        .S_AXI_HP3_BRESP(S_AXI_HP3_0_1_BRESP),
        .S_AXI_HP3_BVALID(S_AXI_HP3_0_1_BVALID),
        .S_AXI_HP3_RACOUNT(S_AXI_HP3_FIFO_CTRL_0_1_RACOUNT),
        .S_AXI_HP3_RCOUNT(S_AXI_HP3_FIFO_CTRL_0_1_RCOUNT),
        .S_AXI_HP3_RDATA(S_AXI_HP3_0_1_RDATA),
        .S_AXI_HP3_RDISSUECAP1_EN(S_AXI_HP3_FIFO_CTRL_0_1_RDISSUECAPEN),
        .S_AXI_HP3_RID(S_AXI_HP3_0_1_RID),
        .S_AXI_HP3_RLAST(S_AXI_HP3_0_1_RLAST),
        .S_AXI_HP3_RREADY(S_AXI_HP3_0_1_RREADY),
        .S_AXI_HP3_RRESP(S_AXI_HP3_0_1_RRESP),
        .S_AXI_HP3_RVALID(S_AXI_HP3_0_1_RVALID),
        .S_AXI_HP3_WACOUNT(S_AXI_HP3_FIFO_CTRL_0_1_WACOUNT),
        .S_AXI_HP3_WCOUNT(S_AXI_HP3_FIFO_CTRL_0_1_WCOUNT),
        .S_AXI_HP3_WDATA(S_AXI_HP3_0_1_WDATA),
        .S_AXI_HP3_WID(S_AXI_HP3_0_1_WID),
        .S_AXI_HP3_WLAST(S_AXI_HP3_0_1_WLAST),
        .S_AXI_HP3_WREADY(S_AXI_HP3_0_1_WREADY),
        .S_AXI_HP3_WRISSUECAP1_EN(S_AXI_HP3_FIFO_CTRL_0_1_WRISSUECAPEN),
        .S_AXI_HP3_WSTRB(S_AXI_HP3_0_1_WSTRB),
        .S_AXI_HP3_WVALID(S_AXI_HP3_0_1_WVALID),
        .UART1_RX(1'b1),
        .USB0_PORT_INDCTL(processing_system7_0_USBIND_0_PORT_INDCTL),
        .USB0_VBUS_PWRFAULT(processing_system7_0_USBIND_0_VBUS_PWRFAULT),
        .USB0_VBUS_PWRSELECT(processing_system7_0_USBIND_0_VBUS_PWRSELECT),
        .pl_araddr(processing_system7_0_M_AI_HP_pl_araddr),
        .pl_arinfo(processing_system7_0_M_AI_HP_pl_arinfo),
        .pl_arlast(processing_system7_0_M_AI_HP_pl_arlast),
        .pl_arready(processing_system7_0_M_AI_HP_pl_arready),
        .pl_arvalid(processing_system7_0_M_AI_HP_pl_arvalid),
        .pl_awaddr(processing_system7_0_M_AI_HP_pl_awaddr),
        .pl_awdata(processing_system7_0_M_AI_HP_pl_awdata),
        .pl_awen(processing_system7_0_M_AI_HP_pl_awen),
        .pl_awinfo(processing_system7_0_M_AI_HP_pl_awinfo),
        .pl_awlast(processing_system7_0_M_AI_HP_pl_awlast),
        .pl_awready(processing_system7_0_M_AI_HP_pl_awready),
        .pl_awvalid(processing_system7_0_M_AI_HP_pl_awvalid),
        .pl_bist_clk(pl_bist_clk_0_1),
        .pl_bist_done(AI_BIST_0_1_pl_bist_done),
        .pl_bist_en(AI_BIST_0_1_pl_bist_en),
        .pl_bist_err(AI_BIST_0_1_pl_bist_err),
        .pl_bist_err_inv(AI_BIST_0_1_pl_bist_err_inv),
        .pl_bist_rstn(pl_bist_rstn_0_1),
        .pl_bready(processing_system7_0_M_AI_HP_pl_bready),
        .pl_bvalid(processing_system7_0_M_AI_HP_pl_bvalid),
        .pl_clk_div_out(processing_system7_0_pl_clk_div_out),
        .pl_clk_en_b(pl_clk_en_b_0_1),
        .pl_int_info(processing_system7_0_AI_IRQ_pl_int_info),
        .pl_int_ready(processing_system7_0_AI_IRQ_pl_int_ready),
        .pl_int_valid(processing_system7_0_AI_IRQ_pl_int_valid),
        .pl_itf_clk(pl_itf_clk_0_1),
        .pl_ra_araddr(S_AI_GP_0_1_pl_ra_araddr),
        .pl_ra_arready(S_AI_GP_0_1_pl_ra_arready),
        .pl_ra_arvalid(S_AI_GP_0_1_pl_ra_arvalid),
        .pl_ra_awaddr(S_AI_GP_0_1_pl_ra_awaddr),
        .pl_ra_awdata(S_AI_GP_0_1_pl_ra_awdata),
        .pl_ra_awready(S_AI_GP_0_1_pl_ra_awready),
        .pl_ra_awvalid(S_AI_GP_0_1_pl_ra_awvalid),
        .pl_ra_clk(pl_ra_clk_0_1),
        .pl_ra_rdata(S_AI_GP_0_1_pl_ra_rdata),
        .pl_ra_rready(S_AI_GP_0_1_pl_ra_rready),
        .pl_ra_rvalid(S_AI_GP_0_1_pl_ra_rvalid),
        .pl_rdata(processing_system7_0_M_AI_HP_pl_rdata),
        .pl_repair_done(AI_BIST_0_1_pl_repair_done),
        .pl_repair_fail(AI_BIST_0_1_pl_repair_fail),
        .pl_rlast(processing_system7_0_M_AI_HP_pl_rlast),
        .pl_rready(processing_system7_0_M_AI_HP_pl_rready),
        .pl_rst_n(pl_rst_n_0_1),
        .pl_rvalid(processing_system7_0_M_AI_HP_pl_rvalid),
        .pl_scan_clk(pl_scan_clk_0_1),
        .pl_scan_compression_mode(AI_SCAN_0_1_pl_scan_compression_mode),
        .pl_scan_cs(AI_SCAN_0_1_pl_scan_cs),
        .pl_scan_en(AI_SCAN_0_1_pl_scan_en),
        .pl_scan_in(AI_SCAN_0_1_pl_scan_in),
        .pl_scan_mode_b(AI_SCAN_0_1_pl_scan_mode_b),
        .pl_scan_occ_bypass(AI_SCAN_0_1_pl_scan_occ_bypass),
        .pl_scan_occ_mode(AI_SCAN_0_1_pl_scan_occ_mode),
        .pl_scan_occ_reset(AI_SCAN_0_1_pl_scan_occ_reset),
        .pl_scan_out(AI_SCAN_0_1_pl_scan_out),
        .pl_scan_rst_n(pl_scan_rst_n_0_1),
        .pl_scan_wrp_mode(AI_SCAN_0_1_pl_scan_wrp_mode),
        .pl_scan_wrp_shift(AI_SCAN_0_1_pl_scan_wrp_shift));
  ps_ai_util_vector_logic_0_0 util_vector_logic_0
       (.Op1(reset_n_1),
        .Op2(soft_rst_n_1),
        .Res(util_vector_logic_0_Res));
  ps_ai_xlconcat_0_0 xlconcat_0
       (.In0(test_irq_1),
        .In1(customop_irq_1),
        .In2(ai_irq_1),
        .dout(xlconcat_0_dout));
endmodule

module ps_ai_axi_interconnect_0_0
   (ACLK,
    ARESETN,
    M00_ACLK,
    M00_ARESETN,
    M00_AXI_araddr,
    M00_AXI_arburst,
    M00_AXI_arcache,
    M00_AXI_arid,
    M00_AXI_arlen,
    M00_AXI_arlock,
    M00_AXI_arprot,
    M00_AXI_arqos,
    M00_AXI_arready,
    M00_AXI_arsize,
    M00_AXI_arvalid,
    M00_AXI_awaddr,
    M00_AXI_awburst,
    M00_AXI_awcache,
    M00_AXI_awid,
    M00_AXI_awlen,
    M00_AXI_awlock,
    M00_AXI_awprot,
    M00_AXI_awqos,
    M00_AXI_awready,
    M00_AXI_awsize,
    M00_AXI_awvalid,
    M00_AXI_bid,
    M00_AXI_bready,
    M00_AXI_bresp,
    M00_AXI_bvalid,
    M00_AXI_rdata,
    M00_AXI_rid,
    M00_AXI_rlast,
    M00_AXI_rready,
    M00_AXI_rresp,
    M00_AXI_rvalid,
    M00_AXI_wdata,
    M00_AXI_wid,
    M00_AXI_wlast,
    M00_AXI_wready,
    M00_AXI_wstrb,
    M00_AXI_wvalid,
    M01_ACLK,
    M01_ARESETN,
    M01_AXI_araddr,
    M01_AXI_arburst,
    M01_AXI_arcache,
    M01_AXI_arid,
    M01_AXI_arlen,
    M01_AXI_arlock,
    M01_AXI_arprot,
    M01_AXI_arqos,
    M01_AXI_arready,
    M01_AXI_arsize,
    M01_AXI_arvalid,
    M01_AXI_awaddr,
    M01_AXI_awburst,
    M01_AXI_awcache,
    M01_AXI_awid,
    M01_AXI_awlen,
    M01_AXI_awlock,
    M01_AXI_awprot,
    M01_AXI_awqos,
    M01_AXI_awready,
    M01_AXI_awsize,
    M01_AXI_awvalid,
    M01_AXI_bid,
    M01_AXI_bready,
    M01_AXI_bresp,
    M01_AXI_bvalid,
    M01_AXI_rdata,
    M01_AXI_rid,
    M01_AXI_rlast,
    M01_AXI_rready,
    M01_AXI_rresp,
    M01_AXI_rvalid,
    M01_AXI_wdata,
    M01_AXI_wid,
    M01_AXI_wlast,
    M01_AXI_wready,
    M01_AXI_wstrb,
    M01_AXI_wvalid,
    S00_ACLK,
    S00_ARESETN,
    S00_AXI_araddr,
    S00_AXI_arburst,
    S00_AXI_arcache,
    S00_AXI_arid,
    S00_AXI_arlen,
    S00_AXI_arlock,
    S00_AXI_arprot,
    S00_AXI_arqos,
    S00_AXI_arready,
    S00_AXI_arsize,
    S00_AXI_arvalid,
    S00_AXI_awaddr,
    S00_AXI_awburst,
    S00_AXI_awcache,
    S00_AXI_awid,
    S00_AXI_awlen,
    S00_AXI_awlock,
    S00_AXI_awprot,
    S00_AXI_awqos,
    S00_AXI_awready,
    S00_AXI_awsize,
    S00_AXI_awvalid,
    S00_AXI_bid,
    S00_AXI_bready,
    S00_AXI_bresp,
    S00_AXI_bvalid,
    S00_AXI_rdata,
    S00_AXI_rid,
    S00_AXI_rlast,
    S00_AXI_rready,
    S00_AXI_rresp,
    S00_AXI_rvalid,
    S00_AXI_wdata,
    S00_AXI_wid,
    S00_AXI_wlast,
    S00_AXI_wready,
    S00_AXI_wstrb,
    S00_AXI_wvalid);
  input ACLK;
  input ARESETN;
  input M00_ACLK;
  input M00_ARESETN;
  output [31:0]M00_AXI_araddr;
  output [1:0]M00_AXI_arburst;
  output [3:0]M00_AXI_arcache;
  output [11:0]M00_AXI_arid;
  output [3:0]M00_AXI_arlen;
  output [1:0]M00_AXI_arlock;
  output [2:0]M00_AXI_arprot;
  output [3:0]M00_AXI_arqos;
  input [0:0]M00_AXI_arready;
  output [2:0]M00_AXI_arsize;
  output [0:0]M00_AXI_arvalid;
  output [31:0]M00_AXI_awaddr;
  output [1:0]M00_AXI_awburst;
  output [3:0]M00_AXI_awcache;
  output [11:0]M00_AXI_awid;
  output [3:0]M00_AXI_awlen;
  output [1:0]M00_AXI_awlock;
  output [2:0]M00_AXI_awprot;
  output [3:0]M00_AXI_awqos;
  input [0:0]M00_AXI_awready;
  output [2:0]M00_AXI_awsize;
  output [0:0]M00_AXI_awvalid;
  input [11:0]M00_AXI_bid;
  output [0:0]M00_AXI_bready;
  input [1:0]M00_AXI_bresp;
  input [0:0]M00_AXI_bvalid;
  input [31:0]M00_AXI_rdata;
  input [11:0]M00_AXI_rid;
  input [0:0]M00_AXI_rlast;
  output [0:0]M00_AXI_rready;
  input [1:0]M00_AXI_rresp;
  input [0:0]M00_AXI_rvalid;
  output [31:0]M00_AXI_wdata;
  output [11:0]M00_AXI_wid;
  output [0:0]M00_AXI_wlast;
  input [0:0]M00_AXI_wready;
  output [3:0]M00_AXI_wstrb;
  output [0:0]M00_AXI_wvalid;
  input M01_ACLK;
  input M01_ARESETN;
  output [31:0]M01_AXI_araddr;
  output [1:0]M01_AXI_arburst;
  output [3:0]M01_AXI_arcache;
  output [11:0]M01_AXI_arid;
  output [3:0]M01_AXI_arlen;
  output [1:0]M01_AXI_arlock;
  output [2:0]M01_AXI_arprot;
  output [3:0]M01_AXI_arqos;
  input [0:0]M01_AXI_arready;
  output [2:0]M01_AXI_arsize;
  output [0:0]M01_AXI_arvalid;
  output [31:0]M01_AXI_awaddr;
  output [1:0]M01_AXI_awburst;
  output [3:0]M01_AXI_awcache;
  output [11:0]M01_AXI_awid;
  output [3:0]M01_AXI_awlen;
  output [1:0]M01_AXI_awlock;
  output [2:0]M01_AXI_awprot;
  output [3:0]M01_AXI_awqos;
  input [0:0]M01_AXI_awready;
  output [2:0]M01_AXI_awsize;
  output [0:0]M01_AXI_awvalid;
  input [11:0]M01_AXI_bid;
  output [0:0]M01_AXI_bready;
  input [1:0]M01_AXI_bresp;
  input [0:0]M01_AXI_bvalid;
  input [31:0]M01_AXI_rdata;
  input [11:0]M01_AXI_rid;
  input [0:0]M01_AXI_rlast;
  output [0:0]M01_AXI_rready;
  input [1:0]M01_AXI_rresp;
  input [0:0]M01_AXI_rvalid;
  output [31:0]M01_AXI_wdata;
  output [11:0]M01_AXI_wid;
  output [0:0]M01_AXI_wlast;
  input [0:0]M01_AXI_wready;
  output [3:0]M01_AXI_wstrb;
  output [0:0]M01_AXI_wvalid;
  input S00_ACLK;
  input S00_ARESETN;
  input [31:0]S00_AXI_araddr;
  input [1:0]S00_AXI_arburst;
  input [3:0]S00_AXI_arcache;
  input [11:0]S00_AXI_arid;
  input [3:0]S00_AXI_arlen;
  input [1:0]S00_AXI_arlock;
  input [2:0]S00_AXI_arprot;
  input [3:0]S00_AXI_arqos;
  output S00_AXI_arready;
  input [2:0]S00_AXI_arsize;
  input S00_AXI_arvalid;
  input [31:0]S00_AXI_awaddr;
  input [1:0]S00_AXI_awburst;
  input [3:0]S00_AXI_awcache;
  input [11:0]S00_AXI_awid;
  input [3:0]S00_AXI_awlen;
  input [1:0]S00_AXI_awlock;
  input [2:0]S00_AXI_awprot;
  input [3:0]S00_AXI_awqos;
  output S00_AXI_awready;
  input [2:0]S00_AXI_awsize;
  input S00_AXI_awvalid;
  output [11:0]S00_AXI_bid;
  input S00_AXI_bready;
  output [1:0]S00_AXI_bresp;
  output S00_AXI_bvalid;
  output [31:0]S00_AXI_rdata;
  output [11:0]S00_AXI_rid;
  output S00_AXI_rlast;
  input S00_AXI_rready;
  output [1:0]S00_AXI_rresp;
  output S00_AXI_rvalid;
  input [31:0]S00_AXI_wdata;
  input [11:0]S00_AXI_wid;
  input S00_AXI_wlast;
  output S00_AXI_wready;
  input [3:0]S00_AXI_wstrb;
  input S00_AXI_wvalid;

  wire M00_ACLK_1;
  wire M00_ARESETN_1;
  wire M01_ACLK_1;
  wire M01_ARESETN_1;
  wire S00_ACLK_1;
  wire S00_ARESETN_1;
  wire axi_interconnect_0_ACLK_net;
  wire axi_interconnect_0_ARESETN_net;
  wire [31:0]axi_interconnect_0_to_s00_couplers_ARADDR;
  wire [1:0]axi_interconnect_0_to_s00_couplers_ARBURST;
  wire [3:0]axi_interconnect_0_to_s00_couplers_ARCACHE;
  wire [11:0]axi_interconnect_0_to_s00_couplers_ARID;
  wire [3:0]axi_interconnect_0_to_s00_couplers_ARLEN;
  wire [1:0]axi_interconnect_0_to_s00_couplers_ARLOCK;
  wire [2:0]axi_interconnect_0_to_s00_couplers_ARPROT;
  wire [3:0]axi_interconnect_0_to_s00_couplers_ARQOS;
  wire axi_interconnect_0_to_s00_couplers_ARREADY;
  wire [2:0]axi_interconnect_0_to_s00_couplers_ARSIZE;
  wire axi_interconnect_0_to_s00_couplers_ARVALID;
  wire [31:0]axi_interconnect_0_to_s00_couplers_AWADDR;
  wire [1:0]axi_interconnect_0_to_s00_couplers_AWBURST;
  wire [3:0]axi_interconnect_0_to_s00_couplers_AWCACHE;
  wire [11:0]axi_interconnect_0_to_s00_couplers_AWID;
  wire [3:0]axi_interconnect_0_to_s00_couplers_AWLEN;
  wire [1:0]axi_interconnect_0_to_s00_couplers_AWLOCK;
  wire [2:0]axi_interconnect_0_to_s00_couplers_AWPROT;
  wire [3:0]axi_interconnect_0_to_s00_couplers_AWQOS;
  wire axi_interconnect_0_to_s00_couplers_AWREADY;
  wire [2:0]axi_interconnect_0_to_s00_couplers_AWSIZE;
  wire axi_interconnect_0_to_s00_couplers_AWVALID;
  wire [11:0]axi_interconnect_0_to_s00_couplers_BID;
  wire axi_interconnect_0_to_s00_couplers_BREADY;
  wire [1:0]axi_interconnect_0_to_s00_couplers_BRESP;
  wire axi_interconnect_0_to_s00_couplers_BVALID;
  wire [31:0]axi_interconnect_0_to_s00_couplers_RDATA;
  wire [11:0]axi_interconnect_0_to_s00_couplers_RID;
  wire axi_interconnect_0_to_s00_couplers_RLAST;
  wire axi_interconnect_0_to_s00_couplers_RREADY;
  wire [1:0]axi_interconnect_0_to_s00_couplers_RRESP;
  wire axi_interconnect_0_to_s00_couplers_RVALID;
  wire [31:0]axi_interconnect_0_to_s00_couplers_WDATA;
  wire [11:0]axi_interconnect_0_to_s00_couplers_WID;
  wire axi_interconnect_0_to_s00_couplers_WLAST;
  wire axi_interconnect_0_to_s00_couplers_WREADY;
  wire [3:0]axi_interconnect_0_to_s00_couplers_WSTRB;
  wire axi_interconnect_0_to_s00_couplers_WVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_0_ARADDR;
  wire [1:0]m00_couplers_to_axi_interconnect_0_ARBURST;
  wire [3:0]m00_couplers_to_axi_interconnect_0_ARCACHE;
  wire [11:0]m00_couplers_to_axi_interconnect_0_ARID;
  wire [3:0]m00_couplers_to_axi_interconnect_0_ARLEN;
  wire [1:0]m00_couplers_to_axi_interconnect_0_ARLOCK;
  wire [2:0]m00_couplers_to_axi_interconnect_0_ARPROT;
  wire [3:0]m00_couplers_to_axi_interconnect_0_ARQOS;
  wire [0:0]m00_couplers_to_axi_interconnect_0_ARREADY;
  wire [2:0]m00_couplers_to_axi_interconnect_0_ARSIZE;
  wire [0:0]m00_couplers_to_axi_interconnect_0_ARVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_0_AWADDR;
  wire [1:0]m00_couplers_to_axi_interconnect_0_AWBURST;
  wire [3:0]m00_couplers_to_axi_interconnect_0_AWCACHE;
  wire [11:0]m00_couplers_to_axi_interconnect_0_AWID;
  wire [3:0]m00_couplers_to_axi_interconnect_0_AWLEN;
  wire [1:0]m00_couplers_to_axi_interconnect_0_AWLOCK;
  wire [2:0]m00_couplers_to_axi_interconnect_0_AWPROT;
  wire [3:0]m00_couplers_to_axi_interconnect_0_AWQOS;
  wire [0:0]m00_couplers_to_axi_interconnect_0_AWREADY;
  wire [2:0]m00_couplers_to_axi_interconnect_0_AWSIZE;
  wire [0:0]m00_couplers_to_axi_interconnect_0_AWVALID;
  wire [11:0]m00_couplers_to_axi_interconnect_0_BID;
  wire [0:0]m00_couplers_to_axi_interconnect_0_BREADY;
  wire [1:0]m00_couplers_to_axi_interconnect_0_BRESP;
  wire [0:0]m00_couplers_to_axi_interconnect_0_BVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_0_RDATA;
  wire [11:0]m00_couplers_to_axi_interconnect_0_RID;
  wire [0:0]m00_couplers_to_axi_interconnect_0_RLAST;
  wire [0:0]m00_couplers_to_axi_interconnect_0_RREADY;
  wire [1:0]m00_couplers_to_axi_interconnect_0_RRESP;
  wire [0:0]m00_couplers_to_axi_interconnect_0_RVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_0_WDATA;
  wire [11:0]m00_couplers_to_axi_interconnect_0_WID;
  wire [0:0]m00_couplers_to_axi_interconnect_0_WLAST;
  wire [0:0]m00_couplers_to_axi_interconnect_0_WREADY;
  wire [3:0]m00_couplers_to_axi_interconnect_0_WSTRB;
  wire [0:0]m00_couplers_to_axi_interconnect_0_WVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_0_ARADDR;
  wire [1:0]m01_couplers_to_axi_interconnect_0_ARBURST;
  wire [3:0]m01_couplers_to_axi_interconnect_0_ARCACHE;
  wire [11:0]m01_couplers_to_axi_interconnect_0_ARID;
  wire [3:0]m01_couplers_to_axi_interconnect_0_ARLEN;
  wire [1:0]m01_couplers_to_axi_interconnect_0_ARLOCK;
  wire [2:0]m01_couplers_to_axi_interconnect_0_ARPROT;
  wire [3:0]m01_couplers_to_axi_interconnect_0_ARQOS;
  wire [0:0]m01_couplers_to_axi_interconnect_0_ARREADY;
  wire [2:0]m01_couplers_to_axi_interconnect_0_ARSIZE;
  wire [0:0]m01_couplers_to_axi_interconnect_0_ARVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_0_AWADDR;
  wire [1:0]m01_couplers_to_axi_interconnect_0_AWBURST;
  wire [3:0]m01_couplers_to_axi_interconnect_0_AWCACHE;
  wire [11:0]m01_couplers_to_axi_interconnect_0_AWID;
  wire [3:0]m01_couplers_to_axi_interconnect_0_AWLEN;
  wire [1:0]m01_couplers_to_axi_interconnect_0_AWLOCK;
  wire [2:0]m01_couplers_to_axi_interconnect_0_AWPROT;
  wire [3:0]m01_couplers_to_axi_interconnect_0_AWQOS;
  wire [0:0]m01_couplers_to_axi_interconnect_0_AWREADY;
  wire [2:0]m01_couplers_to_axi_interconnect_0_AWSIZE;
  wire [0:0]m01_couplers_to_axi_interconnect_0_AWVALID;
  wire [11:0]m01_couplers_to_axi_interconnect_0_BID;
  wire [0:0]m01_couplers_to_axi_interconnect_0_BREADY;
  wire [1:0]m01_couplers_to_axi_interconnect_0_BRESP;
  wire [0:0]m01_couplers_to_axi_interconnect_0_BVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_0_RDATA;
  wire [11:0]m01_couplers_to_axi_interconnect_0_RID;
  wire [0:0]m01_couplers_to_axi_interconnect_0_RLAST;
  wire [0:0]m01_couplers_to_axi_interconnect_0_RREADY;
  wire [1:0]m01_couplers_to_axi_interconnect_0_RRESP;
  wire [0:0]m01_couplers_to_axi_interconnect_0_RVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_0_WDATA;
  wire [11:0]m01_couplers_to_axi_interconnect_0_WID;
  wire [0:0]m01_couplers_to_axi_interconnect_0_WLAST;
  wire [0:0]m01_couplers_to_axi_interconnect_0_WREADY;
  wire [3:0]m01_couplers_to_axi_interconnect_0_WSTRB;
  wire [0:0]m01_couplers_to_axi_interconnect_0_WVALID;
  wire [31:0]s00_couplers_to_xbar_ARADDR;
  wire [1:0]s00_couplers_to_xbar_ARBURST;
  wire [3:0]s00_couplers_to_xbar_ARCACHE;
  wire [11:0]s00_couplers_to_xbar_ARID;
  wire [3:0]s00_couplers_to_xbar_ARLEN;
  wire [1:0]s00_couplers_to_xbar_ARLOCK;
  wire [2:0]s00_couplers_to_xbar_ARPROT;
  wire [3:0]s00_couplers_to_xbar_ARQOS;
  wire [0:0]s00_couplers_to_xbar_ARREADY;
  wire [2:0]s00_couplers_to_xbar_ARSIZE;
  wire s00_couplers_to_xbar_ARVALID;
  wire [31:0]s00_couplers_to_xbar_AWADDR;
  wire [1:0]s00_couplers_to_xbar_AWBURST;
  wire [3:0]s00_couplers_to_xbar_AWCACHE;
  wire [11:0]s00_couplers_to_xbar_AWID;
  wire [3:0]s00_couplers_to_xbar_AWLEN;
  wire [1:0]s00_couplers_to_xbar_AWLOCK;
  wire [2:0]s00_couplers_to_xbar_AWPROT;
  wire [3:0]s00_couplers_to_xbar_AWQOS;
  wire [0:0]s00_couplers_to_xbar_AWREADY;
  wire [2:0]s00_couplers_to_xbar_AWSIZE;
  wire s00_couplers_to_xbar_AWVALID;
  wire [11:0]s00_couplers_to_xbar_BID;
  wire s00_couplers_to_xbar_BREADY;
  wire [1:0]s00_couplers_to_xbar_BRESP;
  wire [0:0]s00_couplers_to_xbar_BVALID;
  wire [31:0]s00_couplers_to_xbar_RDATA;
  wire [11:0]s00_couplers_to_xbar_RID;
  wire [0:0]s00_couplers_to_xbar_RLAST;
  wire s00_couplers_to_xbar_RREADY;
  wire [1:0]s00_couplers_to_xbar_RRESP;
  wire [0:0]s00_couplers_to_xbar_RVALID;
  wire [31:0]s00_couplers_to_xbar_WDATA;
  wire [11:0]s00_couplers_to_xbar_WID;
  wire s00_couplers_to_xbar_WLAST;
  wire [0:0]s00_couplers_to_xbar_WREADY;
  wire [3:0]s00_couplers_to_xbar_WSTRB;
  wire s00_couplers_to_xbar_WVALID;
  wire [31:0]xbar_to_m00_couplers_ARADDR;
  wire [1:0]xbar_to_m00_couplers_ARBURST;
  wire [3:0]xbar_to_m00_couplers_ARCACHE;
  wire [11:0]xbar_to_m00_couplers_ARID;
  wire [3:0]xbar_to_m00_couplers_ARLEN;
  wire [1:0]xbar_to_m00_couplers_ARLOCK;
  wire [2:0]xbar_to_m00_couplers_ARPROT;
  wire [3:0]xbar_to_m00_couplers_ARQOS;
  wire [0:0]xbar_to_m00_couplers_ARREADY;
  wire [2:0]xbar_to_m00_couplers_ARSIZE;
  wire [0:0]xbar_to_m00_couplers_ARVALID;
  wire [31:0]xbar_to_m00_couplers_AWADDR;
  wire [1:0]xbar_to_m00_couplers_AWBURST;
  wire [3:0]xbar_to_m00_couplers_AWCACHE;
  wire [11:0]xbar_to_m00_couplers_AWID;
  wire [3:0]xbar_to_m00_couplers_AWLEN;
  wire [1:0]xbar_to_m00_couplers_AWLOCK;
  wire [2:0]xbar_to_m00_couplers_AWPROT;
  wire [3:0]xbar_to_m00_couplers_AWQOS;
  wire [0:0]xbar_to_m00_couplers_AWREADY;
  wire [2:0]xbar_to_m00_couplers_AWSIZE;
  wire [0:0]xbar_to_m00_couplers_AWVALID;
  wire [11:0]xbar_to_m00_couplers_BID;
  wire [0:0]xbar_to_m00_couplers_BREADY;
  wire [1:0]xbar_to_m00_couplers_BRESP;
  wire [0:0]xbar_to_m00_couplers_BVALID;
  wire [31:0]xbar_to_m00_couplers_RDATA;
  wire [11:0]xbar_to_m00_couplers_RID;
  wire [0:0]xbar_to_m00_couplers_RLAST;
  wire [0:0]xbar_to_m00_couplers_RREADY;
  wire [1:0]xbar_to_m00_couplers_RRESP;
  wire [0:0]xbar_to_m00_couplers_RVALID;
  wire [31:0]xbar_to_m00_couplers_WDATA;
  wire [11:0]xbar_to_m00_couplers_WID;
  wire [0:0]xbar_to_m00_couplers_WLAST;
  wire [0:0]xbar_to_m00_couplers_WREADY;
  wire [3:0]xbar_to_m00_couplers_WSTRB;
  wire [0:0]xbar_to_m00_couplers_WVALID;
  wire [63:32]xbar_to_m01_couplers_ARADDR;
  wire [3:2]xbar_to_m01_couplers_ARBURST;
  wire [7:4]xbar_to_m01_couplers_ARCACHE;
  wire [23:12]xbar_to_m01_couplers_ARID;
  wire [7:4]xbar_to_m01_couplers_ARLEN;
  wire [3:2]xbar_to_m01_couplers_ARLOCK;
  wire [5:3]xbar_to_m01_couplers_ARPROT;
  wire [7:4]xbar_to_m01_couplers_ARQOS;
  wire [0:0]xbar_to_m01_couplers_ARREADY;
  wire [5:3]xbar_to_m01_couplers_ARSIZE;
  wire [1:1]xbar_to_m01_couplers_ARVALID;
  wire [63:32]xbar_to_m01_couplers_AWADDR;
  wire [3:2]xbar_to_m01_couplers_AWBURST;
  wire [7:4]xbar_to_m01_couplers_AWCACHE;
  wire [23:12]xbar_to_m01_couplers_AWID;
  wire [7:4]xbar_to_m01_couplers_AWLEN;
  wire [3:2]xbar_to_m01_couplers_AWLOCK;
  wire [5:3]xbar_to_m01_couplers_AWPROT;
  wire [7:4]xbar_to_m01_couplers_AWQOS;
  wire [0:0]xbar_to_m01_couplers_AWREADY;
  wire [5:3]xbar_to_m01_couplers_AWSIZE;
  wire [1:1]xbar_to_m01_couplers_AWVALID;
  wire [11:0]xbar_to_m01_couplers_BID;
  wire [1:1]xbar_to_m01_couplers_BREADY;
  wire [1:0]xbar_to_m01_couplers_BRESP;
  wire [0:0]xbar_to_m01_couplers_BVALID;
  wire [31:0]xbar_to_m01_couplers_RDATA;
  wire [11:0]xbar_to_m01_couplers_RID;
  wire [0:0]xbar_to_m01_couplers_RLAST;
  wire [1:1]xbar_to_m01_couplers_RREADY;
  wire [1:0]xbar_to_m01_couplers_RRESP;
  wire [0:0]xbar_to_m01_couplers_RVALID;
  wire [63:32]xbar_to_m01_couplers_WDATA;
  wire [23:12]xbar_to_m01_couplers_WID;
  wire [1:1]xbar_to_m01_couplers_WLAST;
  wire [0:0]xbar_to_m01_couplers_WREADY;
  wire [7:4]xbar_to_m01_couplers_WSTRB;
  wire [1:1]xbar_to_m01_couplers_WVALID;

  assign M00_ACLK_1 = M00_ACLK;
  assign M00_ARESETN_1 = M00_ARESETN;
  assign M00_AXI_araddr[31:0] = m00_couplers_to_axi_interconnect_0_ARADDR;
  assign M00_AXI_arburst[1:0] = m00_couplers_to_axi_interconnect_0_ARBURST;
  assign M00_AXI_arcache[3:0] = m00_couplers_to_axi_interconnect_0_ARCACHE;
  assign M00_AXI_arid[11:0] = m00_couplers_to_axi_interconnect_0_ARID;
  assign M00_AXI_arlen[3:0] = m00_couplers_to_axi_interconnect_0_ARLEN;
  assign M00_AXI_arlock[1:0] = m00_couplers_to_axi_interconnect_0_ARLOCK;
  assign M00_AXI_arprot[2:0] = m00_couplers_to_axi_interconnect_0_ARPROT;
  assign M00_AXI_arqos[3:0] = m00_couplers_to_axi_interconnect_0_ARQOS;
  assign M00_AXI_arsize[2:0] = m00_couplers_to_axi_interconnect_0_ARSIZE;
  assign M00_AXI_arvalid[0] = m00_couplers_to_axi_interconnect_0_ARVALID;
  assign M00_AXI_awaddr[31:0] = m00_couplers_to_axi_interconnect_0_AWADDR;
  assign M00_AXI_awburst[1:0] = m00_couplers_to_axi_interconnect_0_AWBURST;
  assign M00_AXI_awcache[3:0] = m00_couplers_to_axi_interconnect_0_AWCACHE;
  assign M00_AXI_awid[11:0] = m00_couplers_to_axi_interconnect_0_AWID;
  assign M00_AXI_awlen[3:0] = m00_couplers_to_axi_interconnect_0_AWLEN;
  assign M00_AXI_awlock[1:0] = m00_couplers_to_axi_interconnect_0_AWLOCK;
  assign M00_AXI_awprot[2:0] = m00_couplers_to_axi_interconnect_0_AWPROT;
  assign M00_AXI_awqos[3:0] = m00_couplers_to_axi_interconnect_0_AWQOS;
  assign M00_AXI_awsize[2:0] = m00_couplers_to_axi_interconnect_0_AWSIZE;
  assign M00_AXI_awvalid[0] = m00_couplers_to_axi_interconnect_0_AWVALID;
  assign M00_AXI_bready[0] = m00_couplers_to_axi_interconnect_0_BREADY;
  assign M00_AXI_rready[0] = m00_couplers_to_axi_interconnect_0_RREADY;
  assign M00_AXI_wdata[31:0] = m00_couplers_to_axi_interconnect_0_WDATA;
  assign M00_AXI_wid[11:0] = m00_couplers_to_axi_interconnect_0_WID;
  assign M00_AXI_wlast[0] = m00_couplers_to_axi_interconnect_0_WLAST;
  assign M00_AXI_wstrb[3:0] = m00_couplers_to_axi_interconnect_0_WSTRB;
  assign M00_AXI_wvalid[0] = m00_couplers_to_axi_interconnect_0_WVALID;
  assign M01_ACLK_1 = M01_ACLK;
  assign M01_ARESETN_1 = M01_ARESETN;
  assign M01_AXI_araddr[31:0] = m01_couplers_to_axi_interconnect_0_ARADDR;
  assign M01_AXI_arburst[1:0] = m01_couplers_to_axi_interconnect_0_ARBURST;
  assign M01_AXI_arcache[3:0] = m01_couplers_to_axi_interconnect_0_ARCACHE;
  assign M01_AXI_arid[11:0] = m01_couplers_to_axi_interconnect_0_ARID;
  assign M01_AXI_arlen[3:0] = m01_couplers_to_axi_interconnect_0_ARLEN;
  assign M01_AXI_arlock[1:0] = m01_couplers_to_axi_interconnect_0_ARLOCK;
  assign M01_AXI_arprot[2:0] = m01_couplers_to_axi_interconnect_0_ARPROT;
  assign M01_AXI_arqos[3:0] = m01_couplers_to_axi_interconnect_0_ARQOS;
  assign M01_AXI_arsize[2:0] = m01_couplers_to_axi_interconnect_0_ARSIZE;
  assign M01_AXI_arvalid[0] = m01_couplers_to_axi_interconnect_0_ARVALID;
  assign M01_AXI_awaddr[31:0] = m01_couplers_to_axi_interconnect_0_AWADDR;
  assign M01_AXI_awburst[1:0] = m01_couplers_to_axi_interconnect_0_AWBURST;
  assign M01_AXI_awcache[3:0] = m01_couplers_to_axi_interconnect_0_AWCACHE;
  assign M01_AXI_awid[11:0] = m01_couplers_to_axi_interconnect_0_AWID;
  assign M01_AXI_awlen[3:0] = m01_couplers_to_axi_interconnect_0_AWLEN;
  assign M01_AXI_awlock[1:0] = m01_couplers_to_axi_interconnect_0_AWLOCK;
  assign M01_AXI_awprot[2:0] = m01_couplers_to_axi_interconnect_0_AWPROT;
  assign M01_AXI_awqos[3:0] = m01_couplers_to_axi_interconnect_0_AWQOS;
  assign M01_AXI_awsize[2:0] = m01_couplers_to_axi_interconnect_0_AWSIZE;
  assign M01_AXI_awvalid[0] = m01_couplers_to_axi_interconnect_0_AWVALID;
  assign M01_AXI_bready[0] = m01_couplers_to_axi_interconnect_0_BREADY;
  assign M01_AXI_rready[0] = m01_couplers_to_axi_interconnect_0_RREADY;
  assign M01_AXI_wdata[31:0] = m01_couplers_to_axi_interconnect_0_WDATA;
  assign M01_AXI_wid[11:0] = m01_couplers_to_axi_interconnect_0_WID;
  assign M01_AXI_wlast[0] = m01_couplers_to_axi_interconnect_0_WLAST;
  assign M01_AXI_wstrb[3:0] = m01_couplers_to_axi_interconnect_0_WSTRB;
  assign M01_AXI_wvalid[0] = m01_couplers_to_axi_interconnect_0_WVALID;
  assign S00_ACLK_1 = S00_ACLK;
  assign S00_ARESETN_1 = S00_ARESETN;
  assign S00_AXI_arready = axi_interconnect_0_to_s00_couplers_ARREADY;
  assign S00_AXI_awready = axi_interconnect_0_to_s00_couplers_AWREADY;
  assign S00_AXI_bid[11:0] = axi_interconnect_0_to_s00_couplers_BID;
  assign S00_AXI_bresp[1:0] = axi_interconnect_0_to_s00_couplers_BRESP;
  assign S00_AXI_bvalid = axi_interconnect_0_to_s00_couplers_BVALID;
  assign S00_AXI_rdata[31:0] = axi_interconnect_0_to_s00_couplers_RDATA;
  assign S00_AXI_rid[11:0] = axi_interconnect_0_to_s00_couplers_RID;
  assign S00_AXI_rlast = axi_interconnect_0_to_s00_couplers_RLAST;
  assign S00_AXI_rresp[1:0] = axi_interconnect_0_to_s00_couplers_RRESP;
  assign S00_AXI_rvalid = axi_interconnect_0_to_s00_couplers_RVALID;
  assign S00_AXI_wready = axi_interconnect_0_to_s00_couplers_WREADY;
  assign axi_interconnect_0_ACLK_net = ACLK;
  assign axi_interconnect_0_ARESETN_net = ARESETN;
  assign axi_interconnect_0_to_s00_couplers_ARADDR = S00_AXI_araddr[31:0];
  assign axi_interconnect_0_to_s00_couplers_ARBURST = S00_AXI_arburst[1:0];
  assign axi_interconnect_0_to_s00_couplers_ARCACHE = S00_AXI_arcache[3:0];
  assign axi_interconnect_0_to_s00_couplers_ARID = S00_AXI_arid[11:0];
  assign axi_interconnect_0_to_s00_couplers_ARLEN = S00_AXI_arlen[3:0];
  assign axi_interconnect_0_to_s00_couplers_ARLOCK = S00_AXI_arlock[1:0];
  assign axi_interconnect_0_to_s00_couplers_ARPROT = S00_AXI_arprot[2:0];
  assign axi_interconnect_0_to_s00_couplers_ARQOS = S00_AXI_arqos[3:0];
  assign axi_interconnect_0_to_s00_couplers_ARSIZE = S00_AXI_arsize[2:0];
  assign axi_interconnect_0_to_s00_couplers_ARVALID = S00_AXI_arvalid;
  assign axi_interconnect_0_to_s00_couplers_AWADDR = S00_AXI_awaddr[31:0];
  assign axi_interconnect_0_to_s00_couplers_AWBURST = S00_AXI_awburst[1:0];
  assign axi_interconnect_0_to_s00_couplers_AWCACHE = S00_AXI_awcache[3:0];
  assign axi_interconnect_0_to_s00_couplers_AWID = S00_AXI_awid[11:0];
  assign axi_interconnect_0_to_s00_couplers_AWLEN = S00_AXI_awlen[3:0];
  assign axi_interconnect_0_to_s00_couplers_AWLOCK = S00_AXI_awlock[1:0];
  assign axi_interconnect_0_to_s00_couplers_AWPROT = S00_AXI_awprot[2:0];
  assign axi_interconnect_0_to_s00_couplers_AWQOS = S00_AXI_awqos[3:0];
  assign axi_interconnect_0_to_s00_couplers_AWSIZE = S00_AXI_awsize[2:0];
  assign axi_interconnect_0_to_s00_couplers_AWVALID = S00_AXI_awvalid;
  assign axi_interconnect_0_to_s00_couplers_BREADY = S00_AXI_bready;
  assign axi_interconnect_0_to_s00_couplers_RREADY = S00_AXI_rready;
  assign axi_interconnect_0_to_s00_couplers_WDATA = S00_AXI_wdata[31:0];
  assign axi_interconnect_0_to_s00_couplers_WID = S00_AXI_wid[11:0];
  assign axi_interconnect_0_to_s00_couplers_WLAST = S00_AXI_wlast;
  assign axi_interconnect_0_to_s00_couplers_WSTRB = S00_AXI_wstrb[3:0];
  assign axi_interconnect_0_to_s00_couplers_WVALID = S00_AXI_wvalid;
  assign m00_couplers_to_axi_interconnect_0_ARREADY = M00_AXI_arready[0];
  assign m00_couplers_to_axi_interconnect_0_AWREADY = M00_AXI_awready[0];
  assign m00_couplers_to_axi_interconnect_0_BID = M00_AXI_bid[11:0];
  assign m00_couplers_to_axi_interconnect_0_BRESP = M00_AXI_bresp[1:0];
  assign m00_couplers_to_axi_interconnect_0_BVALID = M00_AXI_bvalid[0];
  assign m00_couplers_to_axi_interconnect_0_RDATA = M00_AXI_rdata[31:0];
  assign m00_couplers_to_axi_interconnect_0_RID = M00_AXI_rid[11:0];
  assign m00_couplers_to_axi_interconnect_0_RLAST = M00_AXI_rlast[0];
  assign m00_couplers_to_axi_interconnect_0_RRESP = M00_AXI_rresp[1:0];
  assign m00_couplers_to_axi_interconnect_0_RVALID = M00_AXI_rvalid[0];
  assign m00_couplers_to_axi_interconnect_0_WREADY = M00_AXI_wready[0];
  assign m01_couplers_to_axi_interconnect_0_ARREADY = M01_AXI_arready[0];
  assign m01_couplers_to_axi_interconnect_0_AWREADY = M01_AXI_awready[0];
  assign m01_couplers_to_axi_interconnect_0_BID = M01_AXI_bid[11:0];
  assign m01_couplers_to_axi_interconnect_0_BRESP = M01_AXI_bresp[1:0];
  assign m01_couplers_to_axi_interconnect_0_BVALID = M01_AXI_bvalid[0];
  assign m01_couplers_to_axi_interconnect_0_RDATA = M01_AXI_rdata[31:0];
  assign m01_couplers_to_axi_interconnect_0_RID = M01_AXI_rid[11:0];
  assign m01_couplers_to_axi_interconnect_0_RLAST = M01_AXI_rlast[0];
  assign m01_couplers_to_axi_interconnect_0_RRESP = M01_AXI_rresp[1:0];
  assign m01_couplers_to_axi_interconnect_0_RVALID = M01_AXI_rvalid[0];
  assign m01_couplers_to_axi_interconnect_0_WREADY = M01_AXI_wready[0];
  m00_couplers_imp_1D6FAED m00_couplers
       (.M_ACLK(M00_ACLK_1),
        .M_ARESETN(M00_ARESETN_1),
        .M_AXI_araddr(m00_couplers_to_axi_interconnect_0_ARADDR),
        .M_AXI_arburst(m00_couplers_to_axi_interconnect_0_ARBURST),
        .M_AXI_arcache(m00_couplers_to_axi_interconnect_0_ARCACHE),
        .M_AXI_arid(m00_couplers_to_axi_interconnect_0_ARID),
        .M_AXI_arlen(m00_couplers_to_axi_interconnect_0_ARLEN),
        .M_AXI_arlock(m00_couplers_to_axi_interconnect_0_ARLOCK),
        .M_AXI_arprot(m00_couplers_to_axi_interconnect_0_ARPROT),
        .M_AXI_arqos(m00_couplers_to_axi_interconnect_0_ARQOS),
        .M_AXI_arready(m00_couplers_to_axi_interconnect_0_ARREADY),
        .M_AXI_arsize(m00_couplers_to_axi_interconnect_0_ARSIZE),
        .M_AXI_arvalid(m00_couplers_to_axi_interconnect_0_ARVALID),
        .M_AXI_awaddr(m00_couplers_to_axi_interconnect_0_AWADDR),
        .M_AXI_awburst(m00_couplers_to_axi_interconnect_0_AWBURST),
        .M_AXI_awcache(m00_couplers_to_axi_interconnect_0_AWCACHE),
        .M_AXI_awid(m00_couplers_to_axi_interconnect_0_AWID),
        .M_AXI_awlen(m00_couplers_to_axi_interconnect_0_AWLEN),
        .M_AXI_awlock(m00_couplers_to_axi_interconnect_0_AWLOCK),
        .M_AXI_awprot(m00_couplers_to_axi_interconnect_0_AWPROT),
        .M_AXI_awqos(m00_couplers_to_axi_interconnect_0_AWQOS),
        .M_AXI_awready(m00_couplers_to_axi_interconnect_0_AWREADY),
        .M_AXI_awsize(m00_couplers_to_axi_interconnect_0_AWSIZE),
        .M_AXI_awvalid(m00_couplers_to_axi_interconnect_0_AWVALID),
        .M_AXI_bid(m00_couplers_to_axi_interconnect_0_BID),
        .M_AXI_bready(m00_couplers_to_axi_interconnect_0_BREADY),
        .M_AXI_bresp(m00_couplers_to_axi_interconnect_0_BRESP),
        .M_AXI_bvalid(m00_couplers_to_axi_interconnect_0_BVALID),
        .M_AXI_rdata(m00_couplers_to_axi_interconnect_0_RDATA),
        .M_AXI_rid(m00_couplers_to_axi_interconnect_0_RID),
        .M_AXI_rlast(m00_couplers_to_axi_interconnect_0_RLAST),
        .M_AXI_rready(m00_couplers_to_axi_interconnect_0_RREADY),
        .M_AXI_rresp(m00_couplers_to_axi_interconnect_0_RRESP),
        .M_AXI_rvalid(m00_couplers_to_axi_interconnect_0_RVALID),
        .M_AXI_wdata(m00_couplers_to_axi_interconnect_0_WDATA),
        .M_AXI_wid(m00_couplers_to_axi_interconnect_0_WID),
        .M_AXI_wlast(m00_couplers_to_axi_interconnect_0_WLAST),
        .M_AXI_wready(m00_couplers_to_axi_interconnect_0_WREADY),
        .M_AXI_wstrb(m00_couplers_to_axi_interconnect_0_WSTRB),
        .M_AXI_wvalid(m00_couplers_to_axi_interconnect_0_WVALID),
        .S_ACLK(axi_interconnect_0_ACLK_net),
        .S_ARESETN(axi_interconnect_0_ARESETN_net),
        .S_AXI_araddr(xbar_to_m00_couplers_ARADDR),
        .S_AXI_arburst(xbar_to_m00_couplers_ARBURST),
        .S_AXI_arcache(xbar_to_m00_couplers_ARCACHE),
        .S_AXI_arid(xbar_to_m00_couplers_ARID),
        .S_AXI_arlen(xbar_to_m00_couplers_ARLEN),
        .S_AXI_arlock(xbar_to_m00_couplers_ARLOCK),
        .S_AXI_arprot(xbar_to_m00_couplers_ARPROT),
        .S_AXI_arqos(xbar_to_m00_couplers_ARQOS),
        .S_AXI_arready(xbar_to_m00_couplers_ARREADY),
        .S_AXI_arsize(xbar_to_m00_couplers_ARSIZE),
        .S_AXI_arvalid(xbar_to_m00_couplers_ARVALID),
        .S_AXI_awaddr(xbar_to_m00_couplers_AWADDR),
        .S_AXI_awburst(xbar_to_m00_couplers_AWBURST),
        .S_AXI_awcache(xbar_to_m00_couplers_AWCACHE),
        .S_AXI_awid(xbar_to_m00_couplers_AWID),
        .S_AXI_awlen(xbar_to_m00_couplers_AWLEN),
        .S_AXI_awlock(xbar_to_m00_couplers_AWLOCK),
        .S_AXI_awprot(xbar_to_m00_couplers_AWPROT),
        .S_AXI_awqos(xbar_to_m00_couplers_AWQOS),
        .S_AXI_awready(xbar_to_m00_couplers_AWREADY),
        .S_AXI_awsize(xbar_to_m00_couplers_AWSIZE),
        .S_AXI_awvalid(xbar_to_m00_couplers_AWVALID),
        .S_AXI_bid(xbar_to_m00_couplers_BID),
        .S_AXI_bready(xbar_to_m00_couplers_BREADY),
        .S_AXI_bresp(xbar_to_m00_couplers_BRESP),
        .S_AXI_bvalid(xbar_to_m00_couplers_BVALID),
        .S_AXI_rdata(xbar_to_m00_couplers_RDATA),
        .S_AXI_rid(xbar_to_m00_couplers_RID),
        .S_AXI_rlast(xbar_to_m00_couplers_RLAST),
        .S_AXI_rready(xbar_to_m00_couplers_RREADY),
        .S_AXI_rresp(xbar_to_m00_couplers_RRESP),
        .S_AXI_rvalid(xbar_to_m00_couplers_RVALID),
        .S_AXI_wdata(xbar_to_m00_couplers_WDATA),
        .S_AXI_wid(xbar_to_m00_couplers_WID),
        .S_AXI_wlast(xbar_to_m00_couplers_WLAST),
        .S_AXI_wready(xbar_to_m00_couplers_WREADY),
        .S_AXI_wstrb(xbar_to_m00_couplers_WSTRB),
        .S_AXI_wvalid(xbar_to_m00_couplers_WVALID));
  m01_couplers_imp_2FMNIL m01_couplers
       (.M_ACLK(M01_ACLK_1),
        .M_ARESETN(M01_ARESETN_1),
        .M_AXI_araddr(m01_couplers_to_axi_interconnect_0_ARADDR),
        .M_AXI_arburst(m01_couplers_to_axi_interconnect_0_ARBURST),
        .M_AXI_arcache(m01_couplers_to_axi_interconnect_0_ARCACHE),
        .M_AXI_arid(m01_couplers_to_axi_interconnect_0_ARID),
        .M_AXI_arlen(m01_couplers_to_axi_interconnect_0_ARLEN),
        .M_AXI_arlock(m01_couplers_to_axi_interconnect_0_ARLOCK),
        .M_AXI_arprot(m01_couplers_to_axi_interconnect_0_ARPROT),
        .M_AXI_arqos(m01_couplers_to_axi_interconnect_0_ARQOS),
        .M_AXI_arready(m01_couplers_to_axi_interconnect_0_ARREADY),
        .M_AXI_arsize(m01_couplers_to_axi_interconnect_0_ARSIZE),
        .M_AXI_arvalid(m01_couplers_to_axi_interconnect_0_ARVALID),
        .M_AXI_awaddr(m01_couplers_to_axi_interconnect_0_AWADDR),
        .M_AXI_awburst(m01_couplers_to_axi_interconnect_0_AWBURST),
        .M_AXI_awcache(m01_couplers_to_axi_interconnect_0_AWCACHE),
        .M_AXI_awid(m01_couplers_to_axi_interconnect_0_AWID),
        .M_AXI_awlen(m01_couplers_to_axi_interconnect_0_AWLEN),
        .M_AXI_awlock(m01_couplers_to_axi_interconnect_0_AWLOCK),
        .M_AXI_awprot(m01_couplers_to_axi_interconnect_0_AWPROT),
        .M_AXI_awqos(m01_couplers_to_axi_interconnect_0_AWQOS),
        .M_AXI_awready(m01_couplers_to_axi_interconnect_0_AWREADY),
        .M_AXI_awsize(m01_couplers_to_axi_interconnect_0_AWSIZE),
        .M_AXI_awvalid(m01_couplers_to_axi_interconnect_0_AWVALID),
        .M_AXI_bid(m01_couplers_to_axi_interconnect_0_BID),
        .M_AXI_bready(m01_couplers_to_axi_interconnect_0_BREADY),
        .M_AXI_bresp(m01_couplers_to_axi_interconnect_0_BRESP),
        .M_AXI_bvalid(m01_couplers_to_axi_interconnect_0_BVALID),
        .M_AXI_rdata(m01_couplers_to_axi_interconnect_0_RDATA),
        .M_AXI_rid(m01_couplers_to_axi_interconnect_0_RID),
        .M_AXI_rlast(m01_couplers_to_axi_interconnect_0_RLAST),
        .M_AXI_rready(m01_couplers_to_axi_interconnect_0_RREADY),
        .M_AXI_rresp(m01_couplers_to_axi_interconnect_0_RRESP),
        .M_AXI_rvalid(m01_couplers_to_axi_interconnect_0_RVALID),
        .M_AXI_wdata(m01_couplers_to_axi_interconnect_0_WDATA),
        .M_AXI_wid(m01_couplers_to_axi_interconnect_0_WID),
        .M_AXI_wlast(m01_couplers_to_axi_interconnect_0_WLAST),
        .M_AXI_wready(m01_couplers_to_axi_interconnect_0_WREADY),
        .M_AXI_wstrb(m01_couplers_to_axi_interconnect_0_WSTRB),
        .M_AXI_wvalid(m01_couplers_to_axi_interconnect_0_WVALID),
        .S_ACLK(axi_interconnect_0_ACLK_net),
        .S_ARESETN(axi_interconnect_0_ARESETN_net),
        .S_AXI_araddr(xbar_to_m01_couplers_ARADDR),
        .S_AXI_arburst(xbar_to_m01_couplers_ARBURST),
        .S_AXI_arcache(xbar_to_m01_couplers_ARCACHE),
        .S_AXI_arid(xbar_to_m01_couplers_ARID),
        .S_AXI_arlen(xbar_to_m01_couplers_ARLEN),
        .S_AXI_arlock(xbar_to_m01_couplers_ARLOCK),
        .S_AXI_arprot(xbar_to_m01_couplers_ARPROT),
        .S_AXI_arqos(xbar_to_m01_couplers_ARQOS),
        .S_AXI_arready(xbar_to_m01_couplers_ARREADY),
        .S_AXI_arsize(xbar_to_m01_couplers_ARSIZE),
        .S_AXI_arvalid(xbar_to_m01_couplers_ARVALID),
        .S_AXI_awaddr(xbar_to_m01_couplers_AWADDR),
        .S_AXI_awburst(xbar_to_m01_couplers_AWBURST),
        .S_AXI_awcache(xbar_to_m01_couplers_AWCACHE),
        .S_AXI_awid(xbar_to_m01_couplers_AWID),
        .S_AXI_awlen(xbar_to_m01_couplers_AWLEN),
        .S_AXI_awlock(xbar_to_m01_couplers_AWLOCK),
        .S_AXI_awprot(xbar_to_m01_couplers_AWPROT),
        .S_AXI_awqos(xbar_to_m01_couplers_AWQOS),
        .S_AXI_awready(xbar_to_m01_couplers_AWREADY),
        .S_AXI_awsize(xbar_to_m01_couplers_AWSIZE),
        .S_AXI_awvalid(xbar_to_m01_couplers_AWVALID),
        .S_AXI_bid(xbar_to_m01_couplers_BID),
        .S_AXI_bready(xbar_to_m01_couplers_BREADY),
        .S_AXI_bresp(xbar_to_m01_couplers_BRESP),
        .S_AXI_bvalid(xbar_to_m01_couplers_BVALID),
        .S_AXI_rdata(xbar_to_m01_couplers_RDATA),
        .S_AXI_rid(xbar_to_m01_couplers_RID),
        .S_AXI_rlast(xbar_to_m01_couplers_RLAST),
        .S_AXI_rready(xbar_to_m01_couplers_RREADY),
        .S_AXI_rresp(xbar_to_m01_couplers_RRESP),
        .S_AXI_rvalid(xbar_to_m01_couplers_RVALID),
        .S_AXI_wdata(xbar_to_m01_couplers_WDATA),
        .S_AXI_wid(xbar_to_m01_couplers_WID),
        .S_AXI_wlast(xbar_to_m01_couplers_WLAST),
        .S_AXI_wready(xbar_to_m01_couplers_WREADY),
        .S_AXI_wstrb(xbar_to_m01_couplers_WSTRB),
        .S_AXI_wvalid(xbar_to_m01_couplers_WVALID));
  s00_couplers_imp_1S6C5N2 s00_couplers
       (.M_ACLK(axi_interconnect_0_ACLK_net),
        .M_ARESETN(axi_interconnect_0_ARESETN_net),
        .M_AXI_araddr(s00_couplers_to_xbar_ARADDR),
        .M_AXI_arburst(s00_couplers_to_xbar_ARBURST),
        .M_AXI_arcache(s00_couplers_to_xbar_ARCACHE),
        .M_AXI_arid(s00_couplers_to_xbar_ARID),
        .M_AXI_arlen(s00_couplers_to_xbar_ARLEN),
        .M_AXI_arlock(s00_couplers_to_xbar_ARLOCK),
        .M_AXI_arprot(s00_couplers_to_xbar_ARPROT),
        .M_AXI_arqos(s00_couplers_to_xbar_ARQOS),
        .M_AXI_arready(s00_couplers_to_xbar_ARREADY),
        .M_AXI_arsize(s00_couplers_to_xbar_ARSIZE),
        .M_AXI_arvalid(s00_couplers_to_xbar_ARVALID),
        .M_AXI_awaddr(s00_couplers_to_xbar_AWADDR),
        .M_AXI_awburst(s00_couplers_to_xbar_AWBURST),
        .M_AXI_awcache(s00_couplers_to_xbar_AWCACHE),
        .M_AXI_awid(s00_couplers_to_xbar_AWID),
        .M_AXI_awlen(s00_couplers_to_xbar_AWLEN),
        .M_AXI_awlock(s00_couplers_to_xbar_AWLOCK),
        .M_AXI_awprot(s00_couplers_to_xbar_AWPROT),
        .M_AXI_awqos(s00_couplers_to_xbar_AWQOS),
        .M_AXI_awready(s00_couplers_to_xbar_AWREADY),
        .M_AXI_awsize(s00_couplers_to_xbar_AWSIZE),
        .M_AXI_awvalid(s00_couplers_to_xbar_AWVALID),
        .M_AXI_bid(s00_couplers_to_xbar_BID),
        .M_AXI_bready(s00_couplers_to_xbar_BREADY),
        .M_AXI_bresp(s00_couplers_to_xbar_BRESP),
        .M_AXI_bvalid(s00_couplers_to_xbar_BVALID),
        .M_AXI_rdata(s00_couplers_to_xbar_RDATA),
        .M_AXI_rid(s00_couplers_to_xbar_RID),
        .M_AXI_rlast(s00_couplers_to_xbar_RLAST),
        .M_AXI_rready(s00_couplers_to_xbar_RREADY),
        .M_AXI_rresp(s00_couplers_to_xbar_RRESP),
        .M_AXI_rvalid(s00_couplers_to_xbar_RVALID),
        .M_AXI_wdata(s00_couplers_to_xbar_WDATA),
        .M_AXI_wid(s00_couplers_to_xbar_WID),
        .M_AXI_wlast(s00_couplers_to_xbar_WLAST),
        .M_AXI_wready(s00_couplers_to_xbar_WREADY),
        .M_AXI_wstrb(s00_couplers_to_xbar_WSTRB),
        .M_AXI_wvalid(s00_couplers_to_xbar_WVALID),
        .S_ACLK(S00_ACLK_1),
        .S_ARESETN(S00_ARESETN_1),
        .S_AXI_araddr(axi_interconnect_0_to_s00_couplers_ARADDR),
        .S_AXI_arburst(axi_interconnect_0_to_s00_couplers_ARBURST),
        .S_AXI_arcache(axi_interconnect_0_to_s00_couplers_ARCACHE),
        .S_AXI_arid(axi_interconnect_0_to_s00_couplers_ARID),
        .S_AXI_arlen(axi_interconnect_0_to_s00_couplers_ARLEN),
        .S_AXI_arlock(axi_interconnect_0_to_s00_couplers_ARLOCK),
        .S_AXI_arprot(axi_interconnect_0_to_s00_couplers_ARPROT),
        .S_AXI_arqos(axi_interconnect_0_to_s00_couplers_ARQOS),
        .S_AXI_arready(axi_interconnect_0_to_s00_couplers_ARREADY),
        .S_AXI_arsize(axi_interconnect_0_to_s00_couplers_ARSIZE),
        .S_AXI_arvalid(axi_interconnect_0_to_s00_couplers_ARVALID),
        .S_AXI_awaddr(axi_interconnect_0_to_s00_couplers_AWADDR),
        .S_AXI_awburst(axi_interconnect_0_to_s00_couplers_AWBURST),
        .S_AXI_awcache(axi_interconnect_0_to_s00_couplers_AWCACHE),
        .S_AXI_awid(axi_interconnect_0_to_s00_couplers_AWID),
        .S_AXI_awlen(axi_interconnect_0_to_s00_couplers_AWLEN),
        .S_AXI_awlock(axi_interconnect_0_to_s00_couplers_AWLOCK),
        .S_AXI_awprot(axi_interconnect_0_to_s00_couplers_AWPROT),
        .S_AXI_awqos(axi_interconnect_0_to_s00_couplers_AWQOS),
        .S_AXI_awready(axi_interconnect_0_to_s00_couplers_AWREADY),
        .S_AXI_awsize(axi_interconnect_0_to_s00_couplers_AWSIZE),
        .S_AXI_awvalid(axi_interconnect_0_to_s00_couplers_AWVALID),
        .S_AXI_bid(axi_interconnect_0_to_s00_couplers_BID),
        .S_AXI_bready(axi_interconnect_0_to_s00_couplers_BREADY),
        .S_AXI_bresp(axi_interconnect_0_to_s00_couplers_BRESP),
        .S_AXI_bvalid(axi_interconnect_0_to_s00_couplers_BVALID),
        .S_AXI_rdata(axi_interconnect_0_to_s00_couplers_RDATA),
        .S_AXI_rid(axi_interconnect_0_to_s00_couplers_RID),
        .S_AXI_rlast(axi_interconnect_0_to_s00_couplers_RLAST),
        .S_AXI_rready(axi_interconnect_0_to_s00_couplers_RREADY),
        .S_AXI_rresp(axi_interconnect_0_to_s00_couplers_RRESP),
        .S_AXI_rvalid(axi_interconnect_0_to_s00_couplers_RVALID),
        .S_AXI_wdata(axi_interconnect_0_to_s00_couplers_WDATA),
        .S_AXI_wid(axi_interconnect_0_to_s00_couplers_WID),
        .S_AXI_wlast(axi_interconnect_0_to_s00_couplers_WLAST),
        .S_AXI_wready(axi_interconnect_0_to_s00_couplers_WREADY),
        .S_AXI_wstrb(axi_interconnect_0_to_s00_couplers_WSTRB),
        .S_AXI_wvalid(axi_interconnect_0_to_s00_couplers_WVALID));
  ps_ai_xbar_0 xbar
       (.aclk(axi_interconnect_0_ACLK_net),
        .aresetn(axi_interconnect_0_ARESETN_net),
        .m_axi_araddr({xbar_to_m01_couplers_ARADDR,xbar_to_m00_couplers_ARADDR}),
        .m_axi_arburst({xbar_to_m01_couplers_ARBURST,xbar_to_m00_couplers_ARBURST}),
        .m_axi_arcache({xbar_to_m01_couplers_ARCACHE,xbar_to_m00_couplers_ARCACHE}),
        .m_axi_arid({xbar_to_m01_couplers_ARID,xbar_to_m00_couplers_ARID}),
        .m_axi_arlen({xbar_to_m01_couplers_ARLEN,xbar_to_m00_couplers_ARLEN}),
        .m_axi_arlock({xbar_to_m01_couplers_ARLOCK,xbar_to_m00_couplers_ARLOCK}),
        .m_axi_arprot({xbar_to_m01_couplers_ARPROT,xbar_to_m00_couplers_ARPROT}),
        .m_axi_arqos({xbar_to_m01_couplers_ARQOS,xbar_to_m00_couplers_ARQOS}),
        .m_axi_arready({xbar_to_m01_couplers_ARREADY,xbar_to_m00_couplers_ARREADY}),
        .m_axi_arsize({xbar_to_m01_couplers_ARSIZE,xbar_to_m00_couplers_ARSIZE}),
        .m_axi_arvalid({xbar_to_m01_couplers_ARVALID,xbar_to_m00_couplers_ARVALID}),
        .m_axi_awaddr({xbar_to_m01_couplers_AWADDR,xbar_to_m00_couplers_AWADDR}),
        .m_axi_awburst({xbar_to_m01_couplers_AWBURST,xbar_to_m00_couplers_AWBURST}),
        .m_axi_awcache({xbar_to_m01_couplers_AWCACHE,xbar_to_m00_couplers_AWCACHE}),
        .m_axi_awid({xbar_to_m01_couplers_AWID,xbar_to_m00_couplers_AWID}),
        .m_axi_awlen({xbar_to_m01_couplers_AWLEN,xbar_to_m00_couplers_AWLEN}),
        .m_axi_awlock({xbar_to_m01_couplers_AWLOCK,xbar_to_m00_couplers_AWLOCK}),
        .m_axi_awprot({xbar_to_m01_couplers_AWPROT,xbar_to_m00_couplers_AWPROT}),
        .m_axi_awqos({xbar_to_m01_couplers_AWQOS,xbar_to_m00_couplers_AWQOS}),
        .m_axi_awready({xbar_to_m01_couplers_AWREADY,xbar_to_m00_couplers_AWREADY}),
        .m_axi_awsize({xbar_to_m01_couplers_AWSIZE,xbar_to_m00_couplers_AWSIZE}),
        .m_axi_awvalid({xbar_to_m01_couplers_AWVALID,xbar_to_m00_couplers_AWVALID}),
        .m_axi_bid({xbar_to_m01_couplers_BID,xbar_to_m00_couplers_BID}),
        .m_axi_bready({xbar_to_m01_couplers_BREADY,xbar_to_m00_couplers_BREADY}),
        .m_axi_bresp({xbar_to_m01_couplers_BRESP,xbar_to_m00_couplers_BRESP}),
        .m_axi_bvalid({xbar_to_m01_couplers_BVALID,xbar_to_m00_couplers_BVALID}),
        .m_axi_rdata({xbar_to_m01_couplers_RDATA,xbar_to_m00_couplers_RDATA}),
        .m_axi_rid({xbar_to_m01_couplers_RID,xbar_to_m00_couplers_RID}),
        .m_axi_rlast({xbar_to_m01_couplers_RLAST,xbar_to_m00_couplers_RLAST}),
        .m_axi_rready({xbar_to_m01_couplers_RREADY,xbar_to_m00_couplers_RREADY}),
        .m_axi_rresp({xbar_to_m01_couplers_RRESP,xbar_to_m00_couplers_RRESP}),
        .m_axi_rvalid({xbar_to_m01_couplers_RVALID,xbar_to_m00_couplers_RVALID}),
        .m_axi_wdata({xbar_to_m01_couplers_WDATA,xbar_to_m00_couplers_WDATA}),
        .m_axi_wid({xbar_to_m01_couplers_WID,xbar_to_m00_couplers_WID}),
        .m_axi_wlast({xbar_to_m01_couplers_WLAST,xbar_to_m00_couplers_WLAST}),
        .m_axi_wready({xbar_to_m01_couplers_WREADY,xbar_to_m00_couplers_WREADY}),
        .m_axi_wstrb({xbar_to_m01_couplers_WSTRB,xbar_to_m00_couplers_WSTRB}),
        .m_axi_wvalid({xbar_to_m01_couplers_WVALID,xbar_to_m00_couplers_WVALID}),
        .s_axi_araddr(s00_couplers_to_xbar_ARADDR),
        .s_axi_arburst(s00_couplers_to_xbar_ARBURST),
        .s_axi_arcache(s00_couplers_to_xbar_ARCACHE),
        .s_axi_arid(s00_couplers_to_xbar_ARID),
        .s_axi_arlen(s00_couplers_to_xbar_ARLEN),
        .s_axi_arlock(s00_couplers_to_xbar_ARLOCK),
        .s_axi_arprot(s00_couplers_to_xbar_ARPROT),
        .s_axi_arqos(s00_couplers_to_xbar_ARQOS),
        .s_axi_arready(s00_couplers_to_xbar_ARREADY),
        .s_axi_arsize(s00_couplers_to_xbar_ARSIZE),
        .s_axi_arvalid(s00_couplers_to_xbar_ARVALID),
        .s_axi_awaddr(s00_couplers_to_xbar_AWADDR),
        .s_axi_awburst(s00_couplers_to_xbar_AWBURST),
        .s_axi_awcache(s00_couplers_to_xbar_AWCACHE),
        .s_axi_awid(s00_couplers_to_xbar_AWID),
        .s_axi_awlen(s00_couplers_to_xbar_AWLEN),
        .s_axi_awlock(s00_couplers_to_xbar_AWLOCK),
        .s_axi_awprot(s00_couplers_to_xbar_AWPROT),
        .s_axi_awqos(s00_couplers_to_xbar_AWQOS),
        .s_axi_awready(s00_couplers_to_xbar_AWREADY),
        .s_axi_awsize(s00_couplers_to_xbar_AWSIZE),
        .s_axi_awvalid(s00_couplers_to_xbar_AWVALID),
        .s_axi_bid(s00_couplers_to_xbar_BID),
        .s_axi_bready(s00_couplers_to_xbar_BREADY),
        .s_axi_bresp(s00_couplers_to_xbar_BRESP),
        .s_axi_bvalid(s00_couplers_to_xbar_BVALID),
        .s_axi_rdata(s00_couplers_to_xbar_RDATA),
        .s_axi_rid(s00_couplers_to_xbar_RID),
        .s_axi_rlast(s00_couplers_to_xbar_RLAST),
        .s_axi_rready(s00_couplers_to_xbar_RREADY),
        .s_axi_rresp(s00_couplers_to_xbar_RRESP),
        .s_axi_rvalid(s00_couplers_to_xbar_RVALID),
        .s_axi_wdata(s00_couplers_to_xbar_WDATA),
        .s_axi_wid(s00_couplers_to_xbar_WID),
        .s_axi_wlast(s00_couplers_to_xbar_WLAST),
        .s_axi_wready(s00_couplers_to_xbar_WREADY),
        .s_axi_wstrb(s00_couplers_to_xbar_WSTRB),
        .s_axi_wvalid(s00_couplers_to_xbar_WVALID));
endmodule

module ps_ai_axi_interconnect_1_0
   (ACLK,
    ARESETN,
    M00_ACLK,
    M00_ARESETN,
    M00_AXI_araddr,
    M00_AXI_arburst,
    M00_AXI_arcache,
    M00_AXI_arid,
    M00_AXI_arlen,
    M00_AXI_arlock,
    M00_AXI_arprot,
    M00_AXI_arqos,
    M00_AXI_arready,
    M00_AXI_arsize,
    M00_AXI_arvalid,
    M00_AXI_awaddr,
    M00_AXI_awburst,
    M00_AXI_awcache,
    M00_AXI_awid,
    M00_AXI_awlen,
    M00_AXI_awlock,
    M00_AXI_awprot,
    M00_AXI_awqos,
    M00_AXI_awready,
    M00_AXI_awsize,
    M00_AXI_awvalid,
    M00_AXI_bid,
    M00_AXI_bready,
    M00_AXI_bresp,
    M00_AXI_bvalid,
    M00_AXI_rdata,
    M00_AXI_rid,
    M00_AXI_rlast,
    M00_AXI_rready,
    M00_AXI_rresp,
    M00_AXI_rvalid,
    M00_AXI_wdata,
    M00_AXI_wid,
    M00_AXI_wlast,
    M00_AXI_wready,
    M00_AXI_wstrb,
    M00_AXI_wvalid,
    M01_ACLK,
    M01_ARESETN,
    M01_AXI_araddr,
    M01_AXI_arburst,
    M01_AXI_arcache,
    M01_AXI_arid,
    M01_AXI_arlen,
    M01_AXI_arlock,
    M01_AXI_arprot,
    M01_AXI_arqos,
    M01_AXI_arready,
    M01_AXI_arsize,
    M01_AXI_arvalid,
    M01_AXI_awaddr,
    M01_AXI_awburst,
    M01_AXI_awcache,
    M01_AXI_awid,
    M01_AXI_awlen,
    M01_AXI_awlock,
    M01_AXI_awprot,
    M01_AXI_awqos,
    M01_AXI_awready,
    M01_AXI_awsize,
    M01_AXI_awvalid,
    M01_AXI_bid,
    M01_AXI_bready,
    M01_AXI_bresp,
    M01_AXI_bvalid,
    M01_AXI_rdata,
    M01_AXI_rid,
    M01_AXI_rlast,
    M01_AXI_rready,
    M01_AXI_rresp,
    M01_AXI_rvalid,
    M01_AXI_wdata,
    M01_AXI_wid,
    M01_AXI_wlast,
    M01_AXI_wready,
    M01_AXI_wstrb,
    M01_AXI_wvalid,
    S00_ACLK,
    S00_ARESETN,
    S00_AXI_araddr,
    S00_AXI_arburst,
    S00_AXI_arcache,
    S00_AXI_arid,
    S00_AXI_arlen,
    S00_AXI_arlock,
    S00_AXI_arprot,
    S00_AXI_arqos,
    S00_AXI_arready,
    S00_AXI_arsize,
    S00_AXI_arvalid,
    S00_AXI_awaddr,
    S00_AXI_awburst,
    S00_AXI_awcache,
    S00_AXI_awid,
    S00_AXI_awlen,
    S00_AXI_awlock,
    S00_AXI_awprot,
    S00_AXI_awqos,
    S00_AXI_awready,
    S00_AXI_awsize,
    S00_AXI_awvalid,
    S00_AXI_bid,
    S00_AXI_bready,
    S00_AXI_bresp,
    S00_AXI_bvalid,
    S00_AXI_rdata,
    S00_AXI_rid,
    S00_AXI_rlast,
    S00_AXI_rready,
    S00_AXI_rresp,
    S00_AXI_rvalid,
    S00_AXI_wdata,
    S00_AXI_wid,
    S00_AXI_wlast,
    S00_AXI_wready,
    S00_AXI_wstrb,
    S00_AXI_wvalid);
  input ACLK;
  input ARESETN;
  input M00_ACLK;
  input M00_ARESETN;
  output [31:0]M00_AXI_araddr;
  output [1:0]M00_AXI_arburst;
  output [3:0]M00_AXI_arcache;
  output [11:0]M00_AXI_arid;
  output [3:0]M00_AXI_arlen;
  output [1:0]M00_AXI_arlock;
  output [2:0]M00_AXI_arprot;
  output [3:0]M00_AXI_arqos;
  input [0:0]M00_AXI_arready;
  output [2:0]M00_AXI_arsize;
  output [0:0]M00_AXI_arvalid;
  output [31:0]M00_AXI_awaddr;
  output [1:0]M00_AXI_awburst;
  output [3:0]M00_AXI_awcache;
  output [11:0]M00_AXI_awid;
  output [3:0]M00_AXI_awlen;
  output [1:0]M00_AXI_awlock;
  output [2:0]M00_AXI_awprot;
  output [3:0]M00_AXI_awqos;
  input [0:0]M00_AXI_awready;
  output [2:0]M00_AXI_awsize;
  output [0:0]M00_AXI_awvalid;
  input [11:0]M00_AXI_bid;
  output [0:0]M00_AXI_bready;
  input [1:0]M00_AXI_bresp;
  input [0:0]M00_AXI_bvalid;
  input [31:0]M00_AXI_rdata;
  input [11:0]M00_AXI_rid;
  input [0:0]M00_AXI_rlast;
  output [0:0]M00_AXI_rready;
  input [1:0]M00_AXI_rresp;
  input [0:0]M00_AXI_rvalid;
  output [31:0]M00_AXI_wdata;
  output [11:0]M00_AXI_wid;
  output [0:0]M00_AXI_wlast;
  input [0:0]M00_AXI_wready;
  output [3:0]M00_AXI_wstrb;
  output [0:0]M00_AXI_wvalid;
  input M01_ACLK;
  input M01_ARESETN;
  output [31:0]M01_AXI_araddr;
  output [1:0]M01_AXI_arburst;
  output [3:0]M01_AXI_arcache;
  output [11:0]M01_AXI_arid;
  output [3:0]M01_AXI_arlen;
  output [1:0]M01_AXI_arlock;
  output [2:0]M01_AXI_arprot;
  output [3:0]M01_AXI_arqos;
  input [0:0]M01_AXI_arready;
  output [2:0]M01_AXI_arsize;
  output [0:0]M01_AXI_arvalid;
  output [31:0]M01_AXI_awaddr;
  output [1:0]M01_AXI_awburst;
  output [3:0]M01_AXI_awcache;
  output [11:0]M01_AXI_awid;
  output [3:0]M01_AXI_awlen;
  output [1:0]M01_AXI_awlock;
  output [2:0]M01_AXI_awprot;
  output [3:0]M01_AXI_awqos;
  input [0:0]M01_AXI_awready;
  output [2:0]M01_AXI_awsize;
  output [0:0]M01_AXI_awvalid;
  input [11:0]M01_AXI_bid;
  output [0:0]M01_AXI_bready;
  input [1:0]M01_AXI_bresp;
  input [0:0]M01_AXI_bvalid;
  input [31:0]M01_AXI_rdata;
  input [11:0]M01_AXI_rid;
  input [0:0]M01_AXI_rlast;
  output [0:0]M01_AXI_rready;
  input [1:0]M01_AXI_rresp;
  input [0:0]M01_AXI_rvalid;
  output [31:0]M01_AXI_wdata;
  output [11:0]M01_AXI_wid;
  output [0:0]M01_AXI_wlast;
  input [0:0]M01_AXI_wready;
  output [3:0]M01_AXI_wstrb;
  output [0:0]M01_AXI_wvalid;
  input S00_ACLK;
  input S00_ARESETN;
  input [31:0]S00_AXI_araddr;
  input [1:0]S00_AXI_arburst;
  input [3:0]S00_AXI_arcache;
  input [11:0]S00_AXI_arid;
  input [3:0]S00_AXI_arlen;
  input [1:0]S00_AXI_arlock;
  input [2:0]S00_AXI_arprot;
  input [3:0]S00_AXI_arqos;
  output S00_AXI_arready;
  input [2:0]S00_AXI_arsize;
  input S00_AXI_arvalid;
  input [31:0]S00_AXI_awaddr;
  input [1:0]S00_AXI_awburst;
  input [3:0]S00_AXI_awcache;
  input [11:0]S00_AXI_awid;
  input [3:0]S00_AXI_awlen;
  input [1:0]S00_AXI_awlock;
  input [2:0]S00_AXI_awprot;
  input [3:0]S00_AXI_awqos;
  output S00_AXI_awready;
  input [2:0]S00_AXI_awsize;
  input S00_AXI_awvalid;
  output [11:0]S00_AXI_bid;
  input S00_AXI_bready;
  output [1:0]S00_AXI_bresp;
  output S00_AXI_bvalid;
  output [31:0]S00_AXI_rdata;
  output [11:0]S00_AXI_rid;
  output S00_AXI_rlast;
  input S00_AXI_rready;
  output [1:0]S00_AXI_rresp;
  output S00_AXI_rvalid;
  input [31:0]S00_AXI_wdata;
  input [11:0]S00_AXI_wid;
  input S00_AXI_wlast;
  output S00_AXI_wready;
  input [3:0]S00_AXI_wstrb;
  input S00_AXI_wvalid;

  wire M00_ACLK_1;
  wire M00_ARESETN_1;
  wire M01_ACLK_1;
  wire M01_ARESETN_1;
  wire S00_ACLK_1;
  wire S00_ARESETN_1;
  wire axi_interconnect_1_ACLK_net;
  wire axi_interconnect_1_ARESETN_net;
  wire [31:0]axi_interconnect_1_to_s00_couplers_ARADDR;
  wire [1:0]axi_interconnect_1_to_s00_couplers_ARBURST;
  wire [3:0]axi_interconnect_1_to_s00_couplers_ARCACHE;
  wire [11:0]axi_interconnect_1_to_s00_couplers_ARID;
  wire [3:0]axi_interconnect_1_to_s00_couplers_ARLEN;
  wire [1:0]axi_interconnect_1_to_s00_couplers_ARLOCK;
  wire [2:0]axi_interconnect_1_to_s00_couplers_ARPROT;
  wire [3:0]axi_interconnect_1_to_s00_couplers_ARQOS;
  wire axi_interconnect_1_to_s00_couplers_ARREADY;
  wire [2:0]axi_interconnect_1_to_s00_couplers_ARSIZE;
  wire axi_interconnect_1_to_s00_couplers_ARVALID;
  wire [31:0]axi_interconnect_1_to_s00_couplers_AWADDR;
  wire [1:0]axi_interconnect_1_to_s00_couplers_AWBURST;
  wire [3:0]axi_interconnect_1_to_s00_couplers_AWCACHE;
  wire [11:0]axi_interconnect_1_to_s00_couplers_AWID;
  wire [3:0]axi_interconnect_1_to_s00_couplers_AWLEN;
  wire [1:0]axi_interconnect_1_to_s00_couplers_AWLOCK;
  wire [2:0]axi_interconnect_1_to_s00_couplers_AWPROT;
  wire [3:0]axi_interconnect_1_to_s00_couplers_AWQOS;
  wire axi_interconnect_1_to_s00_couplers_AWREADY;
  wire [2:0]axi_interconnect_1_to_s00_couplers_AWSIZE;
  wire axi_interconnect_1_to_s00_couplers_AWVALID;
  wire [11:0]axi_interconnect_1_to_s00_couplers_BID;
  wire axi_interconnect_1_to_s00_couplers_BREADY;
  wire [1:0]axi_interconnect_1_to_s00_couplers_BRESP;
  wire axi_interconnect_1_to_s00_couplers_BVALID;
  wire [31:0]axi_interconnect_1_to_s00_couplers_RDATA;
  wire [11:0]axi_interconnect_1_to_s00_couplers_RID;
  wire axi_interconnect_1_to_s00_couplers_RLAST;
  wire axi_interconnect_1_to_s00_couplers_RREADY;
  wire [1:0]axi_interconnect_1_to_s00_couplers_RRESP;
  wire axi_interconnect_1_to_s00_couplers_RVALID;
  wire [31:0]axi_interconnect_1_to_s00_couplers_WDATA;
  wire [11:0]axi_interconnect_1_to_s00_couplers_WID;
  wire axi_interconnect_1_to_s00_couplers_WLAST;
  wire axi_interconnect_1_to_s00_couplers_WREADY;
  wire [3:0]axi_interconnect_1_to_s00_couplers_WSTRB;
  wire axi_interconnect_1_to_s00_couplers_WVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_1_ARADDR;
  wire [1:0]m00_couplers_to_axi_interconnect_1_ARBURST;
  wire [3:0]m00_couplers_to_axi_interconnect_1_ARCACHE;
  wire [11:0]m00_couplers_to_axi_interconnect_1_ARID;
  wire [3:0]m00_couplers_to_axi_interconnect_1_ARLEN;
  wire [1:0]m00_couplers_to_axi_interconnect_1_ARLOCK;
  wire [2:0]m00_couplers_to_axi_interconnect_1_ARPROT;
  wire [3:0]m00_couplers_to_axi_interconnect_1_ARQOS;
  wire [0:0]m00_couplers_to_axi_interconnect_1_ARREADY;
  wire [2:0]m00_couplers_to_axi_interconnect_1_ARSIZE;
  wire [0:0]m00_couplers_to_axi_interconnect_1_ARVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_1_AWADDR;
  wire [1:0]m00_couplers_to_axi_interconnect_1_AWBURST;
  wire [3:0]m00_couplers_to_axi_interconnect_1_AWCACHE;
  wire [11:0]m00_couplers_to_axi_interconnect_1_AWID;
  wire [3:0]m00_couplers_to_axi_interconnect_1_AWLEN;
  wire [1:0]m00_couplers_to_axi_interconnect_1_AWLOCK;
  wire [2:0]m00_couplers_to_axi_interconnect_1_AWPROT;
  wire [3:0]m00_couplers_to_axi_interconnect_1_AWQOS;
  wire [0:0]m00_couplers_to_axi_interconnect_1_AWREADY;
  wire [2:0]m00_couplers_to_axi_interconnect_1_AWSIZE;
  wire [0:0]m00_couplers_to_axi_interconnect_1_AWVALID;
  wire [11:0]m00_couplers_to_axi_interconnect_1_BID;
  wire [0:0]m00_couplers_to_axi_interconnect_1_BREADY;
  wire [1:0]m00_couplers_to_axi_interconnect_1_BRESP;
  wire [0:0]m00_couplers_to_axi_interconnect_1_BVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_1_RDATA;
  wire [11:0]m00_couplers_to_axi_interconnect_1_RID;
  wire [0:0]m00_couplers_to_axi_interconnect_1_RLAST;
  wire [0:0]m00_couplers_to_axi_interconnect_1_RREADY;
  wire [1:0]m00_couplers_to_axi_interconnect_1_RRESP;
  wire [0:0]m00_couplers_to_axi_interconnect_1_RVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_1_WDATA;
  wire [11:0]m00_couplers_to_axi_interconnect_1_WID;
  wire [0:0]m00_couplers_to_axi_interconnect_1_WLAST;
  wire [0:0]m00_couplers_to_axi_interconnect_1_WREADY;
  wire [3:0]m00_couplers_to_axi_interconnect_1_WSTRB;
  wire [0:0]m00_couplers_to_axi_interconnect_1_WVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_1_ARADDR;
  wire [1:0]m01_couplers_to_axi_interconnect_1_ARBURST;
  wire [3:0]m01_couplers_to_axi_interconnect_1_ARCACHE;
  wire [11:0]m01_couplers_to_axi_interconnect_1_ARID;
  wire [3:0]m01_couplers_to_axi_interconnect_1_ARLEN;
  wire [1:0]m01_couplers_to_axi_interconnect_1_ARLOCK;
  wire [2:0]m01_couplers_to_axi_interconnect_1_ARPROT;
  wire [3:0]m01_couplers_to_axi_interconnect_1_ARQOS;
  wire [0:0]m01_couplers_to_axi_interconnect_1_ARREADY;
  wire [2:0]m01_couplers_to_axi_interconnect_1_ARSIZE;
  wire [0:0]m01_couplers_to_axi_interconnect_1_ARVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_1_AWADDR;
  wire [1:0]m01_couplers_to_axi_interconnect_1_AWBURST;
  wire [3:0]m01_couplers_to_axi_interconnect_1_AWCACHE;
  wire [11:0]m01_couplers_to_axi_interconnect_1_AWID;
  wire [3:0]m01_couplers_to_axi_interconnect_1_AWLEN;
  wire [1:0]m01_couplers_to_axi_interconnect_1_AWLOCK;
  wire [2:0]m01_couplers_to_axi_interconnect_1_AWPROT;
  wire [3:0]m01_couplers_to_axi_interconnect_1_AWQOS;
  wire [0:0]m01_couplers_to_axi_interconnect_1_AWREADY;
  wire [2:0]m01_couplers_to_axi_interconnect_1_AWSIZE;
  wire [0:0]m01_couplers_to_axi_interconnect_1_AWVALID;
  wire [11:0]m01_couplers_to_axi_interconnect_1_BID;
  wire [0:0]m01_couplers_to_axi_interconnect_1_BREADY;
  wire [1:0]m01_couplers_to_axi_interconnect_1_BRESP;
  wire [0:0]m01_couplers_to_axi_interconnect_1_BVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_1_RDATA;
  wire [11:0]m01_couplers_to_axi_interconnect_1_RID;
  wire [0:0]m01_couplers_to_axi_interconnect_1_RLAST;
  wire [0:0]m01_couplers_to_axi_interconnect_1_RREADY;
  wire [1:0]m01_couplers_to_axi_interconnect_1_RRESP;
  wire [0:0]m01_couplers_to_axi_interconnect_1_RVALID;
  wire [31:0]m01_couplers_to_axi_interconnect_1_WDATA;
  wire [11:0]m01_couplers_to_axi_interconnect_1_WID;
  wire [0:0]m01_couplers_to_axi_interconnect_1_WLAST;
  wire [0:0]m01_couplers_to_axi_interconnect_1_WREADY;
  wire [3:0]m01_couplers_to_axi_interconnect_1_WSTRB;
  wire [0:0]m01_couplers_to_axi_interconnect_1_WVALID;
  wire [31:0]s00_couplers_to_xbar_ARADDR;
  wire [1:0]s00_couplers_to_xbar_ARBURST;
  wire [3:0]s00_couplers_to_xbar_ARCACHE;
  wire [11:0]s00_couplers_to_xbar_ARID;
  wire [3:0]s00_couplers_to_xbar_ARLEN;
  wire [1:0]s00_couplers_to_xbar_ARLOCK;
  wire [2:0]s00_couplers_to_xbar_ARPROT;
  wire [3:0]s00_couplers_to_xbar_ARQOS;
  wire [0:0]s00_couplers_to_xbar_ARREADY;
  wire [2:0]s00_couplers_to_xbar_ARSIZE;
  wire s00_couplers_to_xbar_ARVALID;
  wire [31:0]s00_couplers_to_xbar_AWADDR;
  wire [1:0]s00_couplers_to_xbar_AWBURST;
  wire [3:0]s00_couplers_to_xbar_AWCACHE;
  wire [11:0]s00_couplers_to_xbar_AWID;
  wire [3:0]s00_couplers_to_xbar_AWLEN;
  wire [1:0]s00_couplers_to_xbar_AWLOCK;
  wire [2:0]s00_couplers_to_xbar_AWPROT;
  wire [3:0]s00_couplers_to_xbar_AWQOS;
  wire [0:0]s00_couplers_to_xbar_AWREADY;
  wire [2:0]s00_couplers_to_xbar_AWSIZE;
  wire s00_couplers_to_xbar_AWVALID;
  wire [11:0]s00_couplers_to_xbar_BID;
  wire s00_couplers_to_xbar_BREADY;
  wire [1:0]s00_couplers_to_xbar_BRESP;
  wire [0:0]s00_couplers_to_xbar_BVALID;
  wire [31:0]s00_couplers_to_xbar_RDATA;
  wire [11:0]s00_couplers_to_xbar_RID;
  wire [0:0]s00_couplers_to_xbar_RLAST;
  wire s00_couplers_to_xbar_RREADY;
  wire [1:0]s00_couplers_to_xbar_RRESP;
  wire [0:0]s00_couplers_to_xbar_RVALID;
  wire [31:0]s00_couplers_to_xbar_WDATA;
  wire [11:0]s00_couplers_to_xbar_WID;
  wire s00_couplers_to_xbar_WLAST;
  wire [0:0]s00_couplers_to_xbar_WREADY;
  wire [3:0]s00_couplers_to_xbar_WSTRB;
  wire s00_couplers_to_xbar_WVALID;
  wire [31:0]xbar_to_m00_couplers_ARADDR;
  wire [1:0]xbar_to_m00_couplers_ARBURST;
  wire [3:0]xbar_to_m00_couplers_ARCACHE;
  wire [11:0]xbar_to_m00_couplers_ARID;
  wire [3:0]xbar_to_m00_couplers_ARLEN;
  wire [1:0]xbar_to_m00_couplers_ARLOCK;
  wire [2:0]xbar_to_m00_couplers_ARPROT;
  wire [3:0]xbar_to_m00_couplers_ARQOS;
  wire [0:0]xbar_to_m00_couplers_ARREADY;
  wire [2:0]xbar_to_m00_couplers_ARSIZE;
  wire [0:0]xbar_to_m00_couplers_ARVALID;
  wire [31:0]xbar_to_m00_couplers_AWADDR;
  wire [1:0]xbar_to_m00_couplers_AWBURST;
  wire [3:0]xbar_to_m00_couplers_AWCACHE;
  wire [11:0]xbar_to_m00_couplers_AWID;
  wire [3:0]xbar_to_m00_couplers_AWLEN;
  wire [1:0]xbar_to_m00_couplers_AWLOCK;
  wire [2:0]xbar_to_m00_couplers_AWPROT;
  wire [3:0]xbar_to_m00_couplers_AWQOS;
  wire [0:0]xbar_to_m00_couplers_AWREADY;
  wire [2:0]xbar_to_m00_couplers_AWSIZE;
  wire [0:0]xbar_to_m00_couplers_AWVALID;
  wire [11:0]xbar_to_m00_couplers_BID;
  wire [0:0]xbar_to_m00_couplers_BREADY;
  wire [1:0]xbar_to_m00_couplers_BRESP;
  wire [0:0]xbar_to_m00_couplers_BVALID;
  wire [31:0]xbar_to_m00_couplers_RDATA;
  wire [11:0]xbar_to_m00_couplers_RID;
  wire [0:0]xbar_to_m00_couplers_RLAST;
  wire [0:0]xbar_to_m00_couplers_RREADY;
  wire [1:0]xbar_to_m00_couplers_RRESP;
  wire [0:0]xbar_to_m00_couplers_RVALID;
  wire [31:0]xbar_to_m00_couplers_WDATA;
  wire [11:0]xbar_to_m00_couplers_WID;
  wire [0:0]xbar_to_m00_couplers_WLAST;
  wire [0:0]xbar_to_m00_couplers_WREADY;
  wire [3:0]xbar_to_m00_couplers_WSTRB;
  wire [0:0]xbar_to_m00_couplers_WVALID;
  wire [63:32]xbar_to_m01_couplers_ARADDR;
  wire [3:2]xbar_to_m01_couplers_ARBURST;
  wire [7:4]xbar_to_m01_couplers_ARCACHE;
  wire [23:12]xbar_to_m01_couplers_ARID;
  wire [7:4]xbar_to_m01_couplers_ARLEN;
  wire [3:2]xbar_to_m01_couplers_ARLOCK;
  wire [5:3]xbar_to_m01_couplers_ARPROT;
  wire [7:4]xbar_to_m01_couplers_ARQOS;
  wire [0:0]xbar_to_m01_couplers_ARREADY;
  wire [5:3]xbar_to_m01_couplers_ARSIZE;
  wire [1:1]xbar_to_m01_couplers_ARVALID;
  wire [63:32]xbar_to_m01_couplers_AWADDR;
  wire [3:2]xbar_to_m01_couplers_AWBURST;
  wire [7:4]xbar_to_m01_couplers_AWCACHE;
  wire [23:12]xbar_to_m01_couplers_AWID;
  wire [7:4]xbar_to_m01_couplers_AWLEN;
  wire [3:2]xbar_to_m01_couplers_AWLOCK;
  wire [5:3]xbar_to_m01_couplers_AWPROT;
  wire [7:4]xbar_to_m01_couplers_AWQOS;
  wire [0:0]xbar_to_m01_couplers_AWREADY;
  wire [5:3]xbar_to_m01_couplers_AWSIZE;
  wire [1:1]xbar_to_m01_couplers_AWVALID;
  wire [11:0]xbar_to_m01_couplers_BID;
  wire [1:1]xbar_to_m01_couplers_BREADY;
  wire [1:0]xbar_to_m01_couplers_BRESP;
  wire [0:0]xbar_to_m01_couplers_BVALID;
  wire [31:0]xbar_to_m01_couplers_RDATA;
  wire [11:0]xbar_to_m01_couplers_RID;
  wire [0:0]xbar_to_m01_couplers_RLAST;
  wire [1:1]xbar_to_m01_couplers_RREADY;
  wire [1:0]xbar_to_m01_couplers_RRESP;
  wire [0:0]xbar_to_m01_couplers_RVALID;
  wire [63:32]xbar_to_m01_couplers_WDATA;
  wire [23:12]xbar_to_m01_couplers_WID;
  wire [1:1]xbar_to_m01_couplers_WLAST;
  wire [0:0]xbar_to_m01_couplers_WREADY;
  wire [7:4]xbar_to_m01_couplers_WSTRB;
  wire [1:1]xbar_to_m01_couplers_WVALID;

  assign M00_ACLK_1 = M00_ACLK;
  assign M00_ARESETN_1 = M00_ARESETN;
  assign M00_AXI_araddr[31:0] = m00_couplers_to_axi_interconnect_1_ARADDR;
  assign M00_AXI_arburst[1:0] = m00_couplers_to_axi_interconnect_1_ARBURST;
  assign M00_AXI_arcache[3:0] = m00_couplers_to_axi_interconnect_1_ARCACHE;
  assign M00_AXI_arid[11:0] = m00_couplers_to_axi_interconnect_1_ARID;
  assign M00_AXI_arlen[3:0] = m00_couplers_to_axi_interconnect_1_ARLEN;
  assign M00_AXI_arlock[1:0] = m00_couplers_to_axi_interconnect_1_ARLOCK;
  assign M00_AXI_arprot[2:0] = m00_couplers_to_axi_interconnect_1_ARPROT;
  assign M00_AXI_arqos[3:0] = m00_couplers_to_axi_interconnect_1_ARQOS;
  assign M00_AXI_arsize[2:0] = m00_couplers_to_axi_interconnect_1_ARSIZE;
  assign M00_AXI_arvalid[0] = m00_couplers_to_axi_interconnect_1_ARVALID;
  assign M00_AXI_awaddr[31:0] = m00_couplers_to_axi_interconnect_1_AWADDR;
  assign M00_AXI_awburst[1:0] = m00_couplers_to_axi_interconnect_1_AWBURST;
  assign M00_AXI_awcache[3:0] = m00_couplers_to_axi_interconnect_1_AWCACHE;
  assign M00_AXI_awid[11:0] = m00_couplers_to_axi_interconnect_1_AWID;
  assign M00_AXI_awlen[3:0] = m00_couplers_to_axi_interconnect_1_AWLEN;
  assign M00_AXI_awlock[1:0] = m00_couplers_to_axi_interconnect_1_AWLOCK;
  assign M00_AXI_awprot[2:0] = m00_couplers_to_axi_interconnect_1_AWPROT;
  assign M00_AXI_awqos[3:0] = m00_couplers_to_axi_interconnect_1_AWQOS;
  assign M00_AXI_awsize[2:0] = m00_couplers_to_axi_interconnect_1_AWSIZE;
  assign M00_AXI_awvalid[0] = m00_couplers_to_axi_interconnect_1_AWVALID;
  assign M00_AXI_bready[0] = m00_couplers_to_axi_interconnect_1_BREADY;
  assign M00_AXI_rready[0] = m00_couplers_to_axi_interconnect_1_RREADY;
  assign M00_AXI_wdata[31:0] = m00_couplers_to_axi_interconnect_1_WDATA;
  assign M00_AXI_wid[11:0] = m00_couplers_to_axi_interconnect_1_WID;
  assign M00_AXI_wlast[0] = m00_couplers_to_axi_interconnect_1_WLAST;
  assign M00_AXI_wstrb[3:0] = m00_couplers_to_axi_interconnect_1_WSTRB;
  assign M00_AXI_wvalid[0] = m00_couplers_to_axi_interconnect_1_WVALID;
  assign M01_ACLK_1 = M01_ACLK;
  assign M01_ARESETN_1 = M01_ARESETN;
  assign M01_AXI_araddr[31:0] = m01_couplers_to_axi_interconnect_1_ARADDR;
  assign M01_AXI_arburst[1:0] = m01_couplers_to_axi_interconnect_1_ARBURST;
  assign M01_AXI_arcache[3:0] = m01_couplers_to_axi_interconnect_1_ARCACHE;
  assign M01_AXI_arid[11:0] = m01_couplers_to_axi_interconnect_1_ARID;
  assign M01_AXI_arlen[3:0] = m01_couplers_to_axi_interconnect_1_ARLEN;
  assign M01_AXI_arlock[1:0] = m01_couplers_to_axi_interconnect_1_ARLOCK;
  assign M01_AXI_arprot[2:0] = m01_couplers_to_axi_interconnect_1_ARPROT;
  assign M01_AXI_arqos[3:0] = m01_couplers_to_axi_interconnect_1_ARQOS;
  assign M01_AXI_arsize[2:0] = m01_couplers_to_axi_interconnect_1_ARSIZE;
  assign M01_AXI_arvalid[0] = m01_couplers_to_axi_interconnect_1_ARVALID;
  assign M01_AXI_awaddr[31:0] = m01_couplers_to_axi_interconnect_1_AWADDR;
  assign M01_AXI_awburst[1:0] = m01_couplers_to_axi_interconnect_1_AWBURST;
  assign M01_AXI_awcache[3:0] = m01_couplers_to_axi_interconnect_1_AWCACHE;
  assign M01_AXI_awid[11:0] = m01_couplers_to_axi_interconnect_1_AWID;
  assign M01_AXI_awlen[3:0] = m01_couplers_to_axi_interconnect_1_AWLEN;
  assign M01_AXI_awlock[1:0] = m01_couplers_to_axi_interconnect_1_AWLOCK;
  assign M01_AXI_awprot[2:0] = m01_couplers_to_axi_interconnect_1_AWPROT;
  assign M01_AXI_awqos[3:0] = m01_couplers_to_axi_interconnect_1_AWQOS;
  assign M01_AXI_awsize[2:0] = m01_couplers_to_axi_interconnect_1_AWSIZE;
  assign M01_AXI_awvalid[0] = m01_couplers_to_axi_interconnect_1_AWVALID;
  assign M01_AXI_bready[0] = m01_couplers_to_axi_interconnect_1_BREADY;
  assign M01_AXI_rready[0] = m01_couplers_to_axi_interconnect_1_RREADY;
  assign M01_AXI_wdata[31:0] = m01_couplers_to_axi_interconnect_1_WDATA;
  assign M01_AXI_wid[11:0] = m01_couplers_to_axi_interconnect_1_WID;
  assign M01_AXI_wlast[0] = m01_couplers_to_axi_interconnect_1_WLAST;
  assign M01_AXI_wstrb[3:0] = m01_couplers_to_axi_interconnect_1_WSTRB;
  assign M01_AXI_wvalid[0] = m01_couplers_to_axi_interconnect_1_WVALID;
  assign S00_ACLK_1 = S00_ACLK;
  assign S00_ARESETN_1 = S00_ARESETN;
  assign S00_AXI_arready = axi_interconnect_1_to_s00_couplers_ARREADY;
  assign S00_AXI_awready = axi_interconnect_1_to_s00_couplers_AWREADY;
  assign S00_AXI_bid[11:0] = axi_interconnect_1_to_s00_couplers_BID;
  assign S00_AXI_bresp[1:0] = axi_interconnect_1_to_s00_couplers_BRESP;
  assign S00_AXI_bvalid = axi_interconnect_1_to_s00_couplers_BVALID;
  assign S00_AXI_rdata[31:0] = axi_interconnect_1_to_s00_couplers_RDATA;
  assign S00_AXI_rid[11:0] = axi_interconnect_1_to_s00_couplers_RID;
  assign S00_AXI_rlast = axi_interconnect_1_to_s00_couplers_RLAST;
  assign S00_AXI_rresp[1:0] = axi_interconnect_1_to_s00_couplers_RRESP;
  assign S00_AXI_rvalid = axi_interconnect_1_to_s00_couplers_RVALID;
  assign S00_AXI_wready = axi_interconnect_1_to_s00_couplers_WREADY;
  assign axi_interconnect_1_ACLK_net = ACLK;
  assign axi_interconnect_1_ARESETN_net = ARESETN;
  assign axi_interconnect_1_to_s00_couplers_ARADDR = S00_AXI_araddr[31:0];
  assign axi_interconnect_1_to_s00_couplers_ARBURST = S00_AXI_arburst[1:0];
  assign axi_interconnect_1_to_s00_couplers_ARCACHE = S00_AXI_arcache[3:0];
  assign axi_interconnect_1_to_s00_couplers_ARID = S00_AXI_arid[11:0];
  assign axi_interconnect_1_to_s00_couplers_ARLEN = S00_AXI_arlen[3:0];
  assign axi_interconnect_1_to_s00_couplers_ARLOCK = S00_AXI_arlock[1:0];
  assign axi_interconnect_1_to_s00_couplers_ARPROT = S00_AXI_arprot[2:0];
  assign axi_interconnect_1_to_s00_couplers_ARQOS = S00_AXI_arqos[3:0];
  assign axi_interconnect_1_to_s00_couplers_ARSIZE = S00_AXI_arsize[2:0];
  assign axi_interconnect_1_to_s00_couplers_ARVALID = S00_AXI_arvalid;
  assign axi_interconnect_1_to_s00_couplers_AWADDR = S00_AXI_awaddr[31:0];
  assign axi_interconnect_1_to_s00_couplers_AWBURST = S00_AXI_awburst[1:0];
  assign axi_interconnect_1_to_s00_couplers_AWCACHE = S00_AXI_awcache[3:0];
  assign axi_interconnect_1_to_s00_couplers_AWID = S00_AXI_awid[11:0];
  assign axi_interconnect_1_to_s00_couplers_AWLEN = S00_AXI_awlen[3:0];
  assign axi_interconnect_1_to_s00_couplers_AWLOCK = S00_AXI_awlock[1:0];
  assign axi_interconnect_1_to_s00_couplers_AWPROT = S00_AXI_awprot[2:0];
  assign axi_interconnect_1_to_s00_couplers_AWQOS = S00_AXI_awqos[3:0];
  assign axi_interconnect_1_to_s00_couplers_AWSIZE = S00_AXI_awsize[2:0];
  assign axi_interconnect_1_to_s00_couplers_AWVALID = S00_AXI_awvalid;
  assign axi_interconnect_1_to_s00_couplers_BREADY = S00_AXI_bready;
  assign axi_interconnect_1_to_s00_couplers_RREADY = S00_AXI_rready;
  assign axi_interconnect_1_to_s00_couplers_WDATA = S00_AXI_wdata[31:0];
  assign axi_interconnect_1_to_s00_couplers_WID = S00_AXI_wid[11:0];
  assign axi_interconnect_1_to_s00_couplers_WLAST = S00_AXI_wlast;
  assign axi_interconnect_1_to_s00_couplers_WSTRB = S00_AXI_wstrb[3:0];
  assign axi_interconnect_1_to_s00_couplers_WVALID = S00_AXI_wvalid;
  assign m00_couplers_to_axi_interconnect_1_ARREADY = M00_AXI_arready[0];
  assign m00_couplers_to_axi_interconnect_1_AWREADY = M00_AXI_awready[0];
  assign m00_couplers_to_axi_interconnect_1_BID = M00_AXI_bid[11:0];
  assign m00_couplers_to_axi_interconnect_1_BRESP = M00_AXI_bresp[1:0];
  assign m00_couplers_to_axi_interconnect_1_BVALID = M00_AXI_bvalid[0];
  assign m00_couplers_to_axi_interconnect_1_RDATA = M00_AXI_rdata[31:0];
  assign m00_couplers_to_axi_interconnect_1_RID = M00_AXI_rid[11:0];
  assign m00_couplers_to_axi_interconnect_1_RLAST = M00_AXI_rlast[0];
  assign m00_couplers_to_axi_interconnect_1_RRESP = M00_AXI_rresp[1:0];
  assign m00_couplers_to_axi_interconnect_1_RVALID = M00_AXI_rvalid[0];
  assign m00_couplers_to_axi_interconnect_1_WREADY = M00_AXI_wready[0];
  assign m01_couplers_to_axi_interconnect_1_ARREADY = M01_AXI_arready[0];
  assign m01_couplers_to_axi_interconnect_1_AWREADY = M01_AXI_awready[0];
  assign m01_couplers_to_axi_interconnect_1_BID = M01_AXI_bid[11:0];
  assign m01_couplers_to_axi_interconnect_1_BRESP = M01_AXI_bresp[1:0];
  assign m01_couplers_to_axi_interconnect_1_BVALID = M01_AXI_bvalid[0];
  assign m01_couplers_to_axi_interconnect_1_RDATA = M01_AXI_rdata[31:0];
  assign m01_couplers_to_axi_interconnect_1_RID = M01_AXI_rid[11:0];
  assign m01_couplers_to_axi_interconnect_1_RLAST = M01_AXI_rlast[0];
  assign m01_couplers_to_axi_interconnect_1_RRESP = M01_AXI_rresp[1:0];
  assign m01_couplers_to_axi_interconnect_1_RVALID = M01_AXI_rvalid[0];
  assign m01_couplers_to_axi_interconnect_1_WREADY = M01_AXI_wready[0];
  m00_couplers_imp_SJGDOD m00_couplers
       (.M_ACLK(M00_ACLK_1),
        .M_ARESETN(M00_ARESETN_1),
        .M_AXI_araddr(m00_couplers_to_axi_interconnect_1_ARADDR),
        .M_AXI_arburst(m00_couplers_to_axi_interconnect_1_ARBURST),
        .M_AXI_arcache(m00_couplers_to_axi_interconnect_1_ARCACHE),
        .M_AXI_arid(m00_couplers_to_axi_interconnect_1_ARID),
        .M_AXI_arlen(m00_couplers_to_axi_interconnect_1_ARLEN),
        .M_AXI_arlock(m00_couplers_to_axi_interconnect_1_ARLOCK),
        .M_AXI_arprot(m00_couplers_to_axi_interconnect_1_ARPROT),
        .M_AXI_arqos(m00_couplers_to_axi_interconnect_1_ARQOS),
        .M_AXI_arready(m00_couplers_to_axi_interconnect_1_ARREADY),
        .M_AXI_arsize(m00_couplers_to_axi_interconnect_1_ARSIZE),
        .M_AXI_arvalid(m00_couplers_to_axi_interconnect_1_ARVALID),
        .M_AXI_awaddr(m00_couplers_to_axi_interconnect_1_AWADDR),
        .M_AXI_awburst(m00_couplers_to_axi_interconnect_1_AWBURST),
        .M_AXI_awcache(m00_couplers_to_axi_interconnect_1_AWCACHE),
        .M_AXI_awid(m00_couplers_to_axi_interconnect_1_AWID),
        .M_AXI_awlen(m00_couplers_to_axi_interconnect_1_AWLEN),
        .M_AXI_awlock(m00_couplers_to_axi_interconnect_1_AWLOCK),
        .M_AXI_awprot(m00_couplers_to_axi_interconnect_1_AWPROT),
        .M_AXI_awqos(m00_couplers_to_axi_interconnect_1_AWQOS),
        .M_AXI_awready(m00_couplers_to_axi_interconnect_1_AWREADY),
        .M_AXI_awsize(m00_couplers_to_axi_interconnect_1_AWSIZE),
        .M_AXI_awvalid(m00_couplers_to_axi_interconnect_1_AWVALID),
        .M_AXI_bid(m00_couplers_to_axi_interconnect_1_BID),
        .M_AXI_bready(m00_couplers_to_axi_interconnect_1_BREADY),
        .M_AXI_bresp(m00_couplers_to_axi_interconnect_1_BRESP),
        .M_AXI_bvalid(m00_couplers_to_axi_interconnect_1_BVALID),
        .M_AXI_rdata(m00_couplers_to_axi_interconnect_1_RDATA),
        .M_AXI_rid(m00_couplers_to_axi_interconnect_1_RID),
        .M_AXI_rlast(m00_couplers_to_axi_interconnect_1_RLAST),
        .M_AXI_rready(m00_couplers_to_axi_interconnect_1_RREADY),
        .M_AXI_rresp(m00_couplers_to_axi_interconnect_1_RRESP),
        .M_AXI_rvalid(m00_couplers_to_axi_interconnect_1_RVALID),
        .M_AXI_wdata(m00_couplers_to_axi_interconnect_1_WDATA),
        .M_AXI_wid(m00_couplers_to_axi_interconnect_1_WID),
        .M_AXI_wlast(m00_couplers_to_axi_interconnect_1_WLAST),
        .M_AXI_wready(m00_couplers_to_axi_interconnect_1_WREADY),
        .M_AXI_wstrb(m00_couplers_to_axi_interconnect_1_WSTRB),
        .M_AXI_wvalid(m00_couplers_to_axi_interconnect_1_WVALID),
        .S_ACLK(axi_interconnect_1_ACLK_net),
        .S_ARESETN(axi_interconnect_1_ARESETN_net),
        .S_AXI_araddr(xbar_to_m00_couplers_ARADDR),
        .S_AXI_arburst(xbar_to_m00_couplers_ARBURST),
        .S_AXI_arcache(xbar_to_m00_couplers_ARCACHE),
        .S_AXI_arid(xbar_to_m00_couplers_ARID),
        .S_AXI_arlen(xbar_to_m00_couplers_ARLEN),
        .S_AXI_arlock(xbar_to_m00_couplers_ARLOCK),
        .S_AXI_arprot(xbar_to_m00_couplers_ARPROT),
        .S_AXI_arqos(xbar_to_m00_couplers_ARQOS),
        .S_AXI_arready(xbar_to_m00_couplers_ARREADY),
        .S_AXI_arsize(xbar_to_m00_couplers_ARSIZE),
        .S_AXI_arvalid(xbar_to_m00_couplers_ARVALID),
        .S_AXI_awaddr(xbar_to_m00_couplers_AWADDR),
        .S_AXI_awburst(xbar_to_m00_couplers_AWBURST),
        .S_AXI_awcache(xbar_to_m00_couplers_AWCACHE),
        .S_AXI_awid(xbar_to_m00_couplers_AWID),
        .S_AXI_awlen(xbar_to_m00_couplers_AWLEN),
        .S_AXI_awlock(xbar_to_m00_couplers_AWLOCK),
        .S_AXI_awprot(xbar_to_m00_couplers_AWPROT),
        .S_AXI_awqos(xbar_to_m00_couplers_AWQOS),
        .S_AXI_awready(xbar_to_m00_couplers_AWREADY),
        .S_AXI_awsize(xbar_to_m00_couplers_AWSIZE),
        .S_AXI_awvalid(xbar_to_m00_couplers_AWVALID),
        .S_AXI_bid(xbar_to_m00_couplers_BID),
        .S_AXI_bready(xbar_to_m00_couplers_BREADY),
        .S_AXI_bresp(xbar_to_m00_couplers_BRESP),
        .S_AXI_bvalid(xbar_to_m00_couplers_BVALID),
        .S_AXI_rdata(xbar_to_m00_couplers_RDATA),
        .S_AXI_rid(xbar_to_m00_couplers_RID),
        .S_AXI_rlast(xbar_to_m00_couplers_RLAST),
        .S_AXI_rready(xbar_to_m00_couplers_RREADY),
        .S_AXI_rresp(xbar_to_m00_couplers_RRESP),
        .S_AXI_rvalid(xbar_to_m00_couplers_RVALID),
        .S_AXI_wdata(xbar_to_m00_couplers_WDATA),
        .S_AXI_wid(xbar_to_m00_couplers_WID),
        .S_AXI_wlast(xbar_to_m00_couplers_WLAST),
        .S_AXI_wready(xbar_to_m00_couplers_WREADY),
        .S_AXI_wstrb(xbar_to_m00_couplers_WSTRB),
        .S_AXI_wvalid(xbar_to_m00_couplers_WVALID));
  m01_couplers_imp_1PX0PUD m01_couplers
       (.M_ACLK(M01_ACLK_1),
        .M_ARESETN(M01_ARESETN_1),
        .M_AXI_araddr(m01_couplers_to_axi_interconnect_1_ARADDR),
        .M_AXI_arburst(m01_couplers_to_axi_interconnect_1_ARBURST),
        .M_AXI_arcache(m01_couplers_to_axi_interconnect_1_ARCACHE),
        .M_AXI_arid(m01_couplers_to_axi_interconnect_1_ARID),
        .M_AXI_arlen(m01_couplers_to_axi_interconnect_1_ARLEN),
        .M_AXI_arlock(m01_couplers_to_axi_interconnect_1_ARLOCK),
        .M_AXI_arprot(m01_couplers_to_axi_interconnect_1_ARPROT),
        .M_AXI_arqos(m01_couplers_to_axi_interconnect_1_ARQOS),
        .M_AXI_arready(m01_couplers_to_axi_interconnect_1_ARREADY),
        .M_AXI_arsize(m01_couplers_to_axi_interconnect_1_ARSIZE),
        .M_AXI_arvalid(m01_couplers_to_axi_interconnect_1_ARVALID),
        .M_AXI_awaddr(m01_couplers_to_axi_interconnect_1_AWADDR),
        .M_AXI_awburst(m01_couplers_to_axi_interconnect_1_AWBURST),
        .M_AXI_awcache(m01_couplers_to_axi_interconnect_1_AWCACHE),
        .M_AXI_awid(m01_couplers_to_axi_interconnect_1_AWID),
        .M_AXI_awlen(m01_couplers_to_axi_interconnect_1_AWLEN),
        .M_AXI_awlock(m01_couplers_to_axi_interconnect_1_AWLOCK),
        .M_AXI_awprot(m01_couplers_to_axi_interconnect_1_AWPROT),
        .M_AXI_awqos(m01_couplers_to_axi_interconnect_1_AWQOS),
        .M_AXI_awready(m01_couplers_to_axi_interconnect_1_AWREADY),
        .M_AXI_awsize(m01_couplers_to_axi_interconnect_1_AWSIZE),
        .M_AXI_awvalid(m01_couplers_to_axi_interconnect_1_AWVALID),
        .M_AXI_bid(m01_couplers_to_axi_interconnect_1_BID),
        .M_AXI_bready(m01_couplers_to_axi_interconnect_1_BREADY),
        .M_AXI_bresp(m01_couplers_to_axi_interconnect_1_BRESP),
        .M_AXI_bvalid(m01_couplers_to_axi_interconnect_1_BVALID),
        .M_AXI_rdata(m01_couplers_to_axi_interconnect_1_RDATA),
        .M_AXI_rid(m01_couplers_to_axi_interconnect_1_RID),
        .M_AXI_rlast(m01_couplers_to_axi_interconnect_1_RLAST),
        .M_AXI_rready(m01_couplers_to_axi_interconnect_1_RREADY),
        .M_AXI_rresp(m01_couplers_to_axi_interconnect_1_RRESP),
        .M_AXI_rvalid(m01_couplers_to_axi_interconnect_1_RVALID),
        .M_AXI_wdata(m01_couplers_to_axi_interconnect_1_WDATA),
        .M_AXI_wid(m01_couplers_to_axi_interconnect_1_WID),
        .M_AXI_wlast(m01_couplers_to_axi_interconnect_1_WLAST),
        .M_AXI_wready(m01_couplers_to_axi_interconnect_1_WREADY),
        .M_AXI_wstrb(m01_couplers_to_axi_interconnect_1_WSTRB),
        .M_AXI_wvalid(m01_couplers_to_axi_interconnect_1_WVALID),
        .S_ACLK(axi_interconnect_1_ACLK_net),
        .S_ARESETN(axi_interconnect_1_ARESETN_net),
        .S_AXI_araddr(xbar_to_m01_couplers_ARADDR),
        .S_AXI_arburst(xbar_to_m01_couplers_ARBURST),
        .S_AXI_arcache(xbar_to_m01_couplers_ARCACHE),
        .S_AXI_arid(xbar_to_m01_couplers_ARID),
        .S_AXI_arlen(xbar_to_m01_couplers_ARLEN),
        .S_AXI_arlock(xbar_to_m01_couplers_ARLOCK),
        .S_AXI_arprot(xbar_to_m01_couplers_ARPROT),
        .S_AXI_arqos(xbar_to_m01_couplers_ARQOS),
        .S_AXI_arready(xbar_to_m01_couplers_ARREADY),
        .S_AXI_arsize(xbar_to_m01_couplers_ARSIZE),
        .S_AXI_arvalid(xbar_to_m01_couplers_ARVALID),
        .S_AXI_awaddr(xbar_to_m01_couplers_AWADDR),
        .S_AXI_awburst(xbar_to_m01_couplers_AWBURST),
        .S_AXI_awcache(xbar_to_m01_couplers_AWCACHE),
        .S_AXI_awid(xbar_to_m01_couplers_AWID),
        .S_AXI_awlen(xbar_to_m01_couplers_AWLEN),
        .S_AXI_awlock(xbar_to_m01_couplers_AWLOCK),
        .S_AXI_awprot(xbar_to_m01_couplers_AWPROT),
        .S_AXI_awqos(xbar_to_m01_couplers_AWQOS),
        .S_AXI_awready(xbar_to_m01_couplers_AWREADY),
        .S_AXI_awsize(xbar_to_m01_couplers_AWSIZE),
        .S_AXI_awvalid(xbar_to_m01_couplers_AWVALID),
        .S_AXI_bid(xbar_to_m01_couplers_BID),
        .S_AXI_bready(xbar_to_m01_couplers_BREADY),
        .S_AXI_bresp(xbar_to_m01_couplers_BRESP),
        .S_AXI_bvalid(xbar_to_m01_couplers_BVALID),
        .S_AXI_rdata(xbar_to_m01_couplers_RDATA),
        .S_AXI_rid(xbar_to_m01_couplers_RID),
        .S_AXI_rlast(xbar_to_m01_couplers_RLAST),
        .S_AXI_rready(xbar_to_m01_couplers_RREADY),
        .S_AXI_rresp(xbar_to_m01_couplers_RRESP),
        .S_AXI_rvalid(xbar_to_m01_couplers_RVALID),
        .S_AXI_wdata(xbar_to_m01_couplers_WDATA),
        .S_AXI_wid(xbar_to_m01_couplers_WID),
        .S_AXI_wlast(xbar_to_m01_couplers_WLAST),
        .S_AXI_wready(xbar_to_m01_couplers_WREADY),
        .S_AXI_wstrb(xbar_to_m01_couplers_WSTRB),
        .S_AXI_wvalid(xbar_to_m01_couplers_WVALID));
  s00_couplers_imp_DI37BQ s00_couplers
       (.M_ACLK(axi_interconnect_1_ACLK_net),
        .M_ARESETN(axi_interconnect_1_ARESETN_net),
        .M_AXI_araddr(s00_couplers_to_xbar_ARADDR),
        .M_AXI_arburst(s00_couplers_to_xbar_ARBURST),
        .M_AXI_arcache(s00_couplers_to_xbar_ARCACHE),
        .M_AXI_arid(s00_couplers_to_xbar_ARID),
        .M_AXI_arlen(s00_couplers_to_xbar_ARLEN),
        .M_AXI_arlock(s00_couplers_to_xbar_ARLOCK),
        .M_AXI_arprot(s00_couplers_to_xbar_ARPROT),
        .M_AXI_arqos(s00_couplers_to_xbar_ARQOS),
        .M_AXI_arready(s00_couplers_to_xbar_ARREADY),
        .M_AXI_arsize(s00_couplers_to_xbar_ARSIZE),
        .M_AXI_arvalid(s00_couplers_to_xbar_ARVALID),
        .M_AXI_awaddr(s00_couplers_to_xbar_AWADDR),
        .M_AXI_awburst(s00_couplers_to_xbar_AWBURST),
        .M_AXI_awcache(s00_couplers_to_xbar_AWCACHE),
        .M_AXI_awid(s00_couplers_to_xbar_AWID),
        .M_AXI_awlen(s00_couplers_to_xbar_AWLEN),
        .M_AXI_awlock(s00_couplers_to_xbar_AWLOCK),
        .M_AXI_awprot(s00_couplers_to_xbar_AWPROT),
        .M_AXI_awqos(s00_couplers_to_xbar_AWQOS),
        .M_AXI_awready(s00_couplers_to_xbar_AWREADY),
        .M_AXI_awsize(s00_couplers_to_xbar_AWSIZE),
        .M_AXI_awvalid(s00_couplers_to_xbar_AWVALID),
        .M_AXI_bid(s00_couplers_to_xbar_BID),
        .M_AXI_bready(s00_couplers_to_xbar_BREADY),
        .M_AXI_bresp(s00_couplers_to_xbar_BRESP),
        .M_AXI_bvalid(s00_couplers_to_xbar_BVALID),
        .M_AXI_rdata(s00_couplers_to_xbar_RDATA),
        .M_AXI_rid(s00_couplers_to_xbar_RID),
        .M_AXI_rlast(s00_couplers_to_xbar_RLAST),
        .M_AXI_rready(s00_couplers_to_xbar_RREADY),
        .M_AXI_rresp(s00_couplers_to_xbar_RRESP),
        .M_AXI_rvalid(s00_couplers_to_xbar_RVALID),
        .M_AXI_wdata(s00_couplers_to_xbar_WDATA),
        .M_AXI_wid(s00_couplers_to_xbar_WID),
        .M_AXI_wlast(s00_couplers_to_xbar_WLAST),
        .M_AXI_wready(s00_couplers_to_xbar_WREADY),
        .M_AXI_wstrb(s00_couplers_to_xbar_WSTRB),
        .M_AXI_wvalid(s00_couplers_to_xbar_WVALID),
        .S_ACLK(S00_ACLK_1),
        .S_ARESETN(S00_ARESETN_1),
        .S_AXI_araddr(axi_interconnect_1_to_s00_couplers_ARADDR),
        .S_AXI_arburst(axi_interconnect_1_to_s00_couplers_ARBURST),
        .S_AXI_arcache(axi_interconnect_1_to_s00_couplers_ARCACHE),
        .S_AXI_arid(axi_interconnect_1_to_s00_couplers_ARID),
        .S_AXI_arlen(axi_interconnect_1_to_s00_couplers_ARLEN),
        .S_AXI_arlock(axi_interconnect_1_to_s00_couplers_ARLOCK),
        .S_AXI_arprot(axi_interconnect_1_to_s00_couplers_ARPROT),
        .S_AXI_arqos(axi_interconnect_1_to_s00_couplers_ARQOS),
        .S_AXI_arready(axi_interconnect_1_to_s00_couplers_ARREADY),
        .S_AXI_arsize(axi_interconnect_1_to_s00_couplers_ARSIZE),
        .S_AXI_arvalid(axi_interconnect_1_to_s00_couplers_ARVALID),
        .S_AXI_awaddr(axi_interconnect_1_to_s00_couplers_AWADDR),
        .S_AXI_awburst(axi_interconnect_1_to_s00_couplers_AWBURST),
        .S_AXI_awcache(axi_interconnect_1_to_s00_couplers_AWCACHE),
        .S_AXI_awid(axi_interconnect_1_to_s00_couplers_AWID),
        .S_AXI_awlen(axi_interconnect_1_to_s00_couplers_AWLEN),
        .S_AXI_awlock(axi_interconnect_1_to_s00_couplers_AWLOCK),
        .S_AXI_awprot(axi_interconnect_1_to_s00_couplers_AWPROT),
        .S_AXI_awqos(axi_interconnect_1_to_s00_couplers_AWQOS),
        .S_AXI_awready(axi_interconnect_1_to_s00_couplers_AWREADY),
        .S_AXI_awsize(axi_interconnect_1_to_s00_couplers_AWSIZE),
        .S_AXI_awvalid(axi_interconnect_1_to_s00_couplers_AWVALID),
        .S_AXI_bid(axi_interconnect_1_to_s00_couplers_BID),
        .S_AXI_bready(axi_interconnect_1_to_s00_couplers_BREADY),
        .S_AXI_bresp(axi_interconnect_1_to_s00_couplers_BRESP),
        .S_AXI_bvalid(axi_interconnect_1_to_s00_couplers_BVALID),
        .S_AXI_rdata(axi_interconnect_1_to_s00_couplers_RDATA),
        .S_AXI_rid(axi_interconnect_1_to_s00_couplers_RID),
        .S_AXI_rlast(axi_interconnect_1_to_s00_couplers_RLAST),
        .S_AXI_rready(axi_interconnect_1_to_s00_couplers_RREADY),
        .S_AXI_rresp(axi_interconnect_1_to_s00_couplers_RRESP),
        .S_AXI_rvalid(axi_interconnect_1_to_s00_couplers_RVALID),
        .S_AXI_wdata(axi_interconnect_1_to_s00_couplers_WDATA),
        .S_AXI_wid(axi_interconnect_1_to_s00_couplers_WID),
        .S_AXI_wlast(axi_interconnect_1_to_s00_couplers_WLAST),
        .S_AXI_wready(axi_interconnect_1_to_s00_couplers_WREADY),
        .S_AXI_wstrb(axi_interconnect_1_to_s00_couplers_WSTRB),
        .S_AXI_wvalid(axi_interconnect_1_to_s00_couplers_WVALID));
  ps_ai_xbar_1 xbar
       (.aclk(axi_interconnect_1_ACLK_net),
        .aresetn(axi_interconnect_1_ARESETN_net),
        .m_axi_araddr({xbar_to_m01_couplers_ARADDR,xbar_to_m00_couplers_ARADDR}),
        .m_axi_arburst({xbar_to_m01_couplers_ARBURST,xbar_to_m00_couplers_ARBURST}),
        .m_axi_arcache({xbar_to_m01_couplers_ARCACHE,xbar_to_m00_couplers_ARCACHE}),
        .m_axi_arid({xbar_to_m01_couplers_ARID,xbar_to_m00_couplers_ARID}),
        .m_axi_arlen({xbar_to_m01_couplers_ARLEN,xbar_to_m00_couplers_ARLEN}),
        .m_axi_arlock({xbar_to_m01_couplers_ARLOCK,xbar_to_m00_couplers_ARLOCK}),
        .m_axi_arprot({xbar_to_m01_couplers_ARPROT,xbar_to_m00_couplers_ARPROT}),
        .m_axi_arqos({xbar_to_m01_couplers_ARQOS,xbar_to_m00_couplers_ARQOS}),
        .m_axi_arready({xbar_to_m01_couplers_ARREADY,xbar_to_m00_couplers_ARREADY}),
        .m_axi_arsize({xbar_to_m01_couplers_ARSIZE,xbar_to_m00_couplers_ARSIZE}),
        .m_axi_arvalid({xbar_to_m01_couplers_ARVALID,xbar_to_m00_couplers_ARVALID}),
        .m_axi_awaddr({xbar_to_m01_couplers_AWADDR,xbar_to_m00_couplers_AWADDR}),
        .m_axi_awburst({xbar_to_m01_couplers_AWBURST,xbar_to_m00_couplers_AWBURST}),
        .m_axi_awcache({xbar_to_m01_couplers_AWCACHE,xbar_to_m00_couplers_AWCACHE}),
        .m_axi_awid({xbar_to_m01_couplers_AWID,xbar_to_m00_couplers_AWID}),
        .m_axi_awlen({xbar_to_m01_couplers_AWLEN,xbar_to_m00_couplers_AWLEN}),
        .m_axi_awlock({xbar_to_m01_couplers_AWLOCK,xbar_to_m00_couplers_AWLOCK}),
        .m_axi_awprot({xbar_to_m01_couplers_AWPROT,xbar_to_m00_couplers_AWPROT}),
        .m_axi_awqos({xbar_to_m01_couplers_AWQOS,xbar_to_m00_couplers_AWQOS}),
        .m_axi_awready({xbar_to_m01_couplers_AWREADY,xbar_to_m00_couplers_AWREADY}),
        .m_axi_awsize({xbar_to_m01_couplers_AWSIZE,xbar_to_m00_couplers_AWSIZE}),
        .m_axi_awvalid({xbar_to_m01_couplers_AWVALID,xbar_to_m00_couplers_AWVALID}),
        .m_axi_bid({xbar_to_m01_couplers_BID,xbar_to_m00_couplers_BID}),
        .m_axi_bready({xbar_to_m01_couplers_BREADY,xbar_to_m00_couplers_BREADY}),
        .m_axi_bresp({xbar_to_m01_couplers_BRESP,xbar_to_m00_couplers_BRESP}),
        .m_axi_bvalid({xbar_to_m01_couplers_BVALID,xbar_to_m00_couplers_BVALID}),
        .m_axi_rdata({xbar_to_m01_couplers_RDATA,xbar_to_m00_couplers_RDATA}),
        .m_axi_rid({xbar_to_m01_couplers_RID,xbar_to_m00_couplers_RID}),
        .m_axi_rlast({xbar_to_m01_couplers_RLAST,xbar_to_m00_couplers_RLAST}),
        .m_axi_rready({xbar_to_m01_couplers_RREADY,xbar_to_m00_couplers_RREADY}),
        .m_axi_rresp({xbar_to_m01_couplers_RRESP,xbar_to_m00_couplers_RRESP}),
        .m_axi_rvalid({xbar_to_m01_couplers_RVALID,xbar_to_m00_couplers_RVALID}),
        .m_axi_wdata({xbar_to_m01_couplers_WDATA,xbar_to_m00_couplers_WDATA}),
        .m_axi_wid({xbar_to_m01_couplers_WID,xbar_to_m00_couplers_WID}),
        .m_axi_wlast({xbar_to_m01_couplers_WLAST,xbar_to_m00_couplers_WLAST}),
        .m_axi_wready({xbar_to_m01_couplers_WREADY,xbar_to_m00_couplers_WREADY}),
        .m_axi_wstrb({xbar_to_m01_couplers_WSTRB,xbar_to_m00_couplers_WSTRB}),
        .m_axi_wvalid({xbar_to_m01_couplers_WVALID,xbar_to_m00_couplers_WVALID}),
        .s_axi_araddr(s00_couplers_to_xbar_ARADDR),
        .s_axi_arburst(s00_couplers_to_xbar_ARBURST),
        .s_axi_arcache(s00_couplers_to_xbar_ARCACHE),
        .s_axi_arid(s00_couplers_to_xbar_ARID),
        .s_axi_arlen(s00_couplers_to_xbar_ARLEN),
        .s_axi_arlock(s00_couplers_to_xbar_ARLOCK),
        .s_axi_arprot(s00_couplers_to_xbar_ARPROT),
        .s_axi_arqos(s00_couplers_to_xbar_ARQOS),
        .s_axi_arready(s00_couplers_to_xbar_ARREADY),
        .s_axi_arsize(s00_couplers_to_xbar_ARSIZE),
        .s_axi_arvalid(s00_couplers_to_xbar_ARVALID),
        .s_axi_awaddr(s00_couplers_to_xbar_AWADDR),
        .s_axi_awburst(s00_couplers_to_xbar_AWBURST),
        .s_axi_awcache(s00_couplers_to_xbar_AWCACHE),
        .s_axi_awid(s00_couplers_to_xbar_AWID),
        .s_axi_awlen(s00_couplers_to_xbar_AWLEN),
        .s_axi_awlock(s00_couplers_to_xbar_AWLOCK),
        .s_axi_awprot(s00_couplers_to_xbar_AWPROT),
        .s_axi_awqos(s00_couplers_to_xbar_AWQOS),
        .s_axi_awready(s00_couplers_to_xbar_AWREADY),
        .s_axi_awsize(s00_couplers_to_xbar_AWSIZE),
        .s_axi_awvalid(s00_couplers_to_xbar_AWVALID),
        .s_axi_bid(s00_couplers_to_xbar_BID),
        .s_axi_bready(s00_couplers_to_xbar_BREADY),
        .s_axi_bresp(s00_couplers_to_xbar_BRESP),
        .s_axi_bvalid(s00_couplers_to_xbar_BVALID),
        .s_axi_rdata(s00_couplers_to_xbar_RDATA),
        .s_axi_rid(s00_couplers_to_xbar_RID),
        .s_axi_rlast(s00_couplers_to_xbar_RLAST),
        .s_axi_rready(s00_couplers_to_xbar_RREADY),
        .s_axi_rresp(s00_couplers_to_xbar_RRESP),
        .s_axi_rvalid(s00_couplers_to_xbar_RVALID),
        .s_axi_wdata(s00_couplers_to_xbar_WDATA),
        .s_axi_wid(s00_couplers_to_xbar_WID),
        .s_axi_wlast(s00_couplers_to_xbar_WLAST),
        .s_axi_wready(s00_couplers_to_xbar_WREADY),
        .s_axi_wstrb(s00_couplers_to_xbar_WSTRB),
        .s_axi_wvalid(s00_couplers_to_xbar_WVALID));
endmodule

module ps_ai_axi_interconnect_3_0
   (ACLK,
    ARESETN,
    M00_ACLK,
    M00_ARESETN,
    M00_AXI_araddr,
    M00_AXI_arburst,
    M00_AXI_arcache,
    M00_AXI_arid,
    M00_AXI_arlen,
    M00_AXI_arlock,
    M00_AXI_arprot,
    M00_AXI_arqos,
    M00_AXI_arready,
    M00_AXI_arsize,
    M00_AXI_arvalid,
    M00_AXI_awaddr,
    M00_AXI_awburst,
    M00_AXI_awcache,
    M00_AXI_awid,
    M00_AXI_awlen,
    M00_AXI_awlock,
    M00_AXI_awprot,
    M00_AXI_awqos,
    M00_AXI_awready,
    M00_AXI_awsize,
    M00_AXI_awvalid,
    M00_AXI_bid,
    M00_AXI_bready,
    M00_AXI_bresp,
    M00_AXI_bvalid,
    M00_AXI_rdata,
    M00_AXI_rid,
    M00_AXI_rlast,
    M00_AXI_rready,
    M00_AXI_rresp,
    M00_AXI_rvalid,
    M00_AXI_wdata,
    M00_AXI_wid,
    M00_AXI_wlast,
    M00_AXI_wready,
    M00_AXI_wstrb,
    M00_AXI_wvalid,
    S00_ACLK,
    S00_ARESETN,
    S00_AXI_araddr,
    S00_AXI_arburst,
    S00_AXI_arcache,
    S00_AXI_arid,
    S00_AXI_arlen,
    S00_AXI_arlock,
    S00_AXI_arprot,
    S00_AXI_arqos,
    S00_AXI_arready,
    S00_AXI_arsize,
    S00_AXI_arvalid,
    S00_AXI_awaddr,
    S00_AXI_awburst,
    S00_AXI_awcache,
    S00_AXI_awid,
    S00_AXI_awlen,
    S00_AXI_awlock,
    S00_AXI_awprot,
    S00_AXI_awqos,
    S00_AXI_awready,
    S00_AXI_awsize,
    S00_AXI_awvalid,
    S00_AXI_bid,
    S00_AXI_bready,
    S00_AXI_bresp,
    S00_AXI_bvalid,
    S00_AXI_rdata,
    S00_AXI_rid,
    S00_AXI_rlast,
    S00_AXI_rready,
    S00_AXI_rresp,
    S00_AXI_rvalid,
    S00_AXI_wdata,
    S00_AXI_wid,
    S00_AXI_wlast,
    S00_AXI_wready,
    S00_AXI_wstrb,
    S00_AXI_wvalid,
    S01_ACLK,
    S01_ARESETN,
    S01_AXI_araddr,
    S01_AXI_arburst,
    S01_AXI_arcache,
    S01_AXI_arid,
    S01_AXI_arlen,
    S01_AXI_arlock,
    S01_AXI_arprot,
    S01_AXI_arqos,
    S01_AXI_arready,
    S01_AXI_arsize,
    S01_AXI_arvalid,
    S01_AXI_awaddr,
    S01_AXI_awburst,
    S01_AXI_awcache,
    S01_AXI_awid,
    S01_AXI_awlen,
    S01_AXI_awlock,
    S01_AXI_awprot,
    S01_AXI_awqos,
    S01_AXI_awready,
    S01_AXI_awsize,
    S01_AXI_awvalid,
    S01_AXI_bid,
    S01_AXI_bready,
    S01_AXI_bresp,
    S01_AXI_bvalid,
    S01_AXI_rdata,
    S01_AXI_rid,
    S01_AXI_rlast,
    S01_AXI_rready,
    S01_AXI_rresp,
    S01_AXI_rvalid,
    S01_AXI_wdata,
    S01_AXI_wid,
    S01_AXI_wlast,
    S01_AXI_wready,
    S01_AXI_wstrb,
    S01_AXI_wvalid);
  input ACLK;
  input ARESETN;
  input M00_ACLK;
  input M00_ARESETN;
  output [31:0]M00_AXI_araddr;
  output [1:0]M00_AXI_arburst;
  output [3:0]M00_AXI_arcache;
  output [5:0]M00_AXI_arid;
  output [3:0]M00_AXI_arlen;
  output [1:0]M00_AXI_arlock;
  output [2:0]M00_AXI_arprot;
  output [3:0]M00_AXI_arqos;
  input M00_AXI_arready;
  output [2:0]M00_AXI_arsize;
  output M00_AXI_arvalid;
  output [31:0]M00_AXI_awaddr;
  output [1:0]M00_AXI_awburst;
  output [3:0]M00_AXI_awcache;
  output [5:0]M00_AXI_awid;
  output [3:0]M00_AXI_awlen;
  output [1:0]M00_AXI_awlock;
  output [2:0]M00_AXI_awprot;
  output [3:0]M00_AXI_awqos;
  input M00_AXI_awready;
  output [2:0]M00_AXI_awsize;
  output M00_AXI_awvalid;
  input [5:0]M00_AXI_bid;
  output M00_AXI_bready;
  input [1:0]M00_AXI_bresp;
  input M00_AXI_bvalid;
  input [63:0]M00_AXI_rdata;
  input [5:0]M00_AXI_rid;
  input M00_AXI_rlast;
  output M00_AXI_rready;
  input [1:0]M00_AXI_rresp;
  input M00_AXI_rvalid;
  output [63:0]M00_AXI_wdata;
  output [5:0]M00_AXI_wid;
  output M00_AXI_wlast;
  input M00_AXI_wready;
  output [7:0]M00_AXI_wstrb;
  output M00_AXI_wvalid;
  input S00_ACLK;
  input S00_ARESETN;
  input [31:0]S00_AXI_araddr;
  input [1:0]S00_AXI_arburst;
  input [3:0]S00_AXI_arcache;
  input [4:0]S00_AXI_arid;
  input [3:0]S00_AXI_arlen;
  input [1:0]S00_AXI_arlock;
  input [2:0]S00_AXI_arprot;
  input [3:0]S00_AXI_arqos;
  output S00_AXI_arready;
  input [2:0]S00_AXI_arsize;
  input S00_AXI_arvalid;
  input [31:0]S00_AXI_awaddr;
  input [1:0]S00_AXI_awburst;
  input [3:0]S00_AXI_awcache;
  input [4:0]S00_AXI_awid;
  input [3:0]S00_AXI_awlen;
  input [1:0]S00_AXI_awlock;
  input [2:0]S00_AXI_awprot;
  input [3:0]S00_AXI_awqos;
  output S00_AXI_awready;
  input [2:0]S00_AXI_awsize;
  input S00_AXI_awvalid;
  output [4:0]S00_AXI_bid;
  input S00_AXI_bready;
  output [1:0]S00_AXI_bresp;
  output S00_AXI_bvalid;
  output [63:0]S00_AXI_rdata;
  output [4:0]S00_AXI_rid;
  output S00_AXI_rlast;
  input S00_AXI_rready;
  output [1:0]S00_AXI_rresp;
  output S00_AXI_rvalid;
  input [63:0]S00_AXI_wdata;
  input [4:0]S00_AXI_wid;
  input S00_AXI_wlast;
  output S00_AXI_wready;
  input [7:0]S00_AXI_wstrb;
  input S00_AXI_wvalid;
  input S01_ACLK;
  input S01_ARESETN;
  input [31:0]S01_AXI_araddr;
  input [1:0]S01_AXI_arburst;
  input [3:0]S01_AXI_arcache;
  input [4:0]S01_AXI_arid;
  input [3:0]S01_AXI_arlen;
  input [1:0]S01_AXI_arlock;
  input [2:0]S01_AXI_arprot;
  input [3:0]S01_AXI_arqos;
  output S01_AXI_arready;
  input [2:0]S01_AXI_arsize;
  input S01_AXI_arvalid;
  input [31:0]S01_AXI_awaddr;
  input [1:0]S01_AXI_awburst;
  input [3:0]S01_AXI_awcache;
  input [4:0]S01_AXI_awid;
  input [3:0]S01_AXI_awlen;
  input [1:0]S01_AXI_awlock;
  input [2:0]S01_AXI_awprot;
  input [3:0]S01_AXI_awqos;
  output S01_AXI_awready;
  input [2:0]S01_AXI_awsize;
  input S01_AXI_awvalid;
  output [4:0]S01_AXI_bid;
  input S01_AXI_bready;
  output [1:0]S01_AXI_bresp;
  output S01_AXI_bvalid;
  output [63:0]S01_AXI_rdata;
  output [4:0]S01_AXI_rid;
  output S01_AXI_rlast;
  input S01_AXI_rready;
  output [1:0]S01_AXI_rresp;
  output S01_AXI_rvalid;
  input [63:0]S01_AXI_wdata;
  input [4:0]S01_AXI_wid;
  input S01_AXI_wlast;
  output S01_AXI_wready;
  input [7:0]S01_AXI_wstrb;
  input S01_AXI_wvalid;

  wire axi_interconnect_4_ACLK_net;
  wire axi_interconnect_4_ARESETN_net;
  wire [31:0]axi_interconnect_4_to_s00_couplers_ARADDR;
  wire [1:0]axi_interconnect_4_to_s00_couplers_ARBURST;
  wire [3:0]axi_interconnect_4_to_s00_couplers_ARCACHE;
  wire [4:0]axi_interconnect_4_to_s00_couplers_ARID;
  wire [3:0]axi_interconnect_4_to_s00_couplers_ARLEN;
  wire [1:0]axi_interconnect_4_to_s00_couplers_ARLOCK;
  wire [2:0]axi_interconnect_4_to_s00_couplers_ARPROT;
  wire [3:0]axi_interconnect_4_to_s00_couplers_ARQOS;
  wire axi_interconnect_4_to_s00_couplers_ARREADY;
  wire [2:0]axi_interconnect_4_to_s00_couplers_ARSIZE;
  wire axi_interconnect_4_to_s00_couplers_ARVALID;
  wire [31:0]axi_interconnect_4_to_s00_couplers_AWADDR;
  wire [1:0]axi_interconnect_4_to_s00_couplers_AWBURST;
  wire [3:0]axi_interconnect_4_to_s00_couplers_AWCACHE;
  wire [4:0]axi_interconnect_4_to_s00_couplers_AWID;
  wire [3:0]axi_interconnect_4_to_s00_couplers_AWLEN;
  wire [1:0]axi_interconnect_4_to_s00_couplers_AWLOCK;
  wire [2:0]axi_interconnect_4_to_s00_couplers_AWPROT;
  wire [3:0]axi_interconnect_4_to_s00_couplers_AWQOS;
  wire axi_interconnect_4_to_s00_couplers_AWREADY;
  wire [2:0]axi_interconnect_4_to_s00_couplers_AWSIZE;
  wire axi_interconnect_4_to_s00_couplers_AWVALID;
  wire [4:0]axi_interconnect_4_to_s00_couplers_BID;
  wire axi_interconnect_4_to_s00_couplers_BREADY;
  wire [1:0]axi_interconnect_4_to_s00_couplers_BRESP;
  wire axi_interconnect_4_to_s00_couplers_BVALID;
  wire [63:0]axi_interconnect_4_to_s00_couplers_RDATA;
  wire [4:0]axi_interconnect_4_to_s00_couplers_RID;
  wire axi_interconnect_4_to_s00_couplers_RLAST;
  wire axi_interconnect_4_to_s00_couplers_RREADY;
  wire [1:0]axi_interconnect_4_to_s00_couplers_RRESP;
  wire axi_interconnect_4_to_s00_couplers_RVALID;
  wire [63:0]axi_interconnect_4_to_s00_couplers_WDATA;
  wire [4:0]axi_interconnect_4_to_s00_couplers_WID;
  wire axi_interconnect_4_to_s00_couplers_WLAST;
  wire axi_interconnect_4_to_s00_couplers_WREADY;
  wire [7:0]axi_interconnect_4_to_s00_couplers_WSTRB;
  wire axi_interconnect_4_to_s00_couplers_WVALID;
  wire [31:0]axi_interconnect_4_to_s01_couplers_ARADDR;
  wire [1:0]axi_interconnect_4_to_s01_couplers_ARBURST;
  wire [3:0]axi_interconnect_4_to_s01_couplers_ARCACHE;
  wire [4:0]axi_interconnect_4_to_s01_couplers_ARID;
  wire [3:0]axi_interconnect_4_to_s01_couplers_ARLEN;
  wire [1:0]axi_interconnect_4_to_s01_couplers_ARLOCK;
  wire [2:0]axi_interconnect_4_to_s01_couplers_ARPROT;
  wire [3:0]axi_interconnect_4_to_s01_couplers_ARQOS;
  wire axi_interconnect_4_to_s01_couplers_ARREADY;
  wire [2:0]axi_interconnect_4_to_s01_couplers_ARSIZE;
  wire axi_interconnect_4_to_s01_couplers_ARVALID;
  wire [31:0]axi_interconnect_4_to_s01_couplers_AWADDR;
  wire [1:0]axi_interconnect_4_to_s01_couplers_AWBURST;
  wire [3:0]axi_interconnect_4_to_s01_couplers_AWCACHE;
  wire [4:0]axi_interconnect_4_to_s01_couplers_AWID;
  wire [3:0]axi_interconnect_4_to_s01_couplers_AWLEN;
  wire [1:0]axi_interconnect_4_to_s01_couplers_AWLOCK;
  wire [2:0]axi_interconnect_4_to_s01_couplers_AWPROT;
  wire [3:0]axi_interconnect_4_to_s01_couplers_AWQOS;
  wire axi_interconnect_4_to_s01_couplers_AWREADY;
  wire [2:0]axi_interconnect_4_to_s01_couplers_AWSIZE;
  wire axi_interconnect_4_to_s01_couplers_AWVALID;
  wire [4:0]axi_interconnect_4_to_s01_couplers_BID;
  wire axi_interconnect_4_to_s01_couplers_BREADY;
  wire [1:0]axi_interconnect_4_to_s01_couplers_BRESP;
  wire axi_interconnect_4_to_s01_couplers_BVALID;
  wire [63:0]axi_interconnect_4_to_s01_couplers_RDATA;
  wire [4:0]axi_interconnect_4_to_s01_couplers_RID;
  wire axi_interconnect_4_to_s01_couplers_RLAST;
  wire axi_interconnect_4_to_s01_couplers_RREADY;
  wire [1:0]axi_interconnect_4_to_s01_couplers_RRESP;
  wire axi_interconnect_4_to_s01_couplers_RVALID;
  wire [63:0]axi_interconnect_4_to_s01_couplers_WDATA;
  wire [4:0]axi_interconnect_4_to_s01_couplers_WID;
  wire axi_interconnect_4_to_s01_couplers_WLAST;
  wire axi_interconnect_4_to_s01_couplers_WREADY;
  wire [7:0]axi_interconnect_4_to_s01_couplers_WSTRB;
  wire axi_interconnect_4_to_s01_couplers_WVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_4_ARADDR;
  wire [1:0]m00_couplers_to_axi_interconnect_4_ARBURST;
  wire [3:0]m00_couplers_to_axi_interconnect_4_ARCACHE;
  wire [5:0]m00_couplers_to_axi_interconnect_4_ARID;
  wire [3:0]m00_couplers_to_axi_interconnect_4_ARLEN;
  wire [1:0]m00_couplers_to_axi_interconnect_4_ARLOCK;
  wire [2:0]m00_couplers_to_axi_interconnect_4_ARPROT;
  wire [3:0]m00_couplers_to_axi_interconnect_4_ARQOS;
  wire m00_couplers_to_axi_interconnect_4_ARREADY;
  wire [2:0]m00_couplers_to_axi_interconnect_4_ARSIZE;
  wire m00_couplers_to_axi_interconnect_4_ARVALID;
  wire [31:0]m00_couplers_to_axi_interconnect_4_AWADDR;
  wire [1:0]m00_couplers_to_axi_interconnect_4_AWBURST;
  wire [3:0]m00_couplers_to_axi_interconnect_4_AWCACHE;
  wire [5:0]m00_couplers_to_axi_interconnect_4_AWID;
  wire [3:0]m00_couplers_to_axi_interconnect_4_AWLEN;
  wire [1:0]m00_couplers_to_axi_interconnect_4_AWLOCK;
  wire [2:0]m00_couplers_to_axi_interconnect_4_AWPROT;
  wire [3:0]m00_couplers_to_axi_interconnect_4_AWQOS;
  wire m00_couplers_to_axi_interconnect_4_AWREADY;
  wire [2:0]m00_couplers_to_axi_interconnect_4_AWSIZE;
  wire m00_couplers_to_axi_interconnect_4_AWVALID;
  wire [5:0]m00_couplers_to_axi_interconnect_4_BID;
  wire m00_couplers_to_axi_interconnect_4_BREADY;
  wire [1:0]m00_couplers_to_axi_interconnect_4_BRESP;
  wire m00_couplers_to_axi_interconnect_4_BVALID;
  wire [63:0]m00_couplers_to_axi_interconnect_4_RDATA;
  wire [5:0]m00_couplers_to_axi_interconnect_4_RID;
  wire m00_couplers_to_axi_interconnect_4_RLAST;
  wire m00_couplers_to_axi_interconnect_4_RREADY;
  wire [1:0]m00_couplers_to_axi_interconnect_4_RRESP;
  wire m00_couplers_to_axi_interconnect_4_RVALID;
  wire [63:0]m00_couplers_to_axi_interconnect_4_WDATA;
  wire [5:0]m00_couplers_to_axi_interconnect_4_WID;
  wire m00_couplers_to_axi_interconnect_4_WLAST;
  wire m00_couplers_to_axi_interconnect_4_WREADY;
  wire [7:0]m00_couplers_to_axi_interconnect_4_WSTRB;
  wire m00_couplers_to_axi_interconnect_4_WVALID;
  wire [31:0]s00_couplers_to_xbar_ARADDR;
  wire [1:0]s00_couplers_to_xbar_ARBURST;
  wire [3:0]s00_couplers_to_xbar_ARCACHE;
  wire [4:0]s00_couplers_to_xbar_ARID;
  wire [3:0]s00_couplers_to_xbar_ARLEN;
  wire [1:0]s00_couplers_to_xbar_ARLOCK;
  wire [2:0]s00_couplers_to_xbar_ARPROT;
  wire [3:0]s00_couplers_to_xbar_ARQOS;
  wire [0:0]s00_couplers_to_xbar_ARREADY;
  wire [2:0]s00_couplers_to_xbar_ARSIZE;
  wire s00_couplers_to_xbar_ARVALID;
  wire [31:0]s00_couplers_to_xbar_AWADDR;
  wire [1:0]s00_couplers_to_xbar_AWBURST;
  wire [3:0]s00_couplers_to_xbar_AWCACHE;
  wire [4:0]s00_couplers_to_xbar_AWID;
  wire [3:0]s00_couplers_to_xbar_AWLEN;
  wire [1:0]s00_couplers_to_xbar_AWLOCK;
  wire [2:0]s00_couplers_to_xbar_AWPROT;
  wire [3:0]s00_couplers_to_xbar_AWQOS;
  wire [0:0]s00_couplers_to_xbar_AWREADY;
  wire [2:0]s00_couplers_to_xbar_AWSIZE;
  wire s00_couplers_to_xbar_AWVALID;
  wire [5:0]s00_couplers_to_xbar_BID;
  wire s00_couplers_to_xbar_BREADY;
  wire [1:0]s00_couplers_to_xbar_BRESP;
  wire [0:0]s00_couplers_to_xbar_BVALID;
  wire [63:0]s00_couplers_to_xbar_RDATA;
  wire [5:0]s00_couplers_to_xbar_RID;
  wire [0:0]s00_couplers_to_xbar_RLAST;
  wire s00_couplers_to_xbar_RREADY;
  wire [1:0]s00_couplers_to_xbar_RRESP;
  wire [0:0]s00_couplers_to_xbar_RVALID;
  wire [63:0]s00_couplers_to_xbar_WDATA;
  wire [4:0]s00_couplers_to_xbar_WID;
  wire s00_couplers_to_xbar_WLAST;
  wire [0:0]s00_couplers_to_xbar_WREADY;
  wire [7:0]s00_couplers_to_xbar_WSTRB;
  wire s00_couplers_to_xbar_WVALID;
  wire [31:0]s01_couplers_to_xbar_ARADDR;
  wire [1:0]s01_couplers_to_xbar_ARBURST;
  wire [3:0]s01_couplers_to_xbar_ARCACHE;
  wire [4:0]s01_couplers_to_xbar_ARID;
  wire [3:0]s01_couplers_to_xbar_ARLEN;
  wire [1:0]s01_couplers_to_xbar_ARLOCK;
  wire [2:0]s01_couplers_to_xbar_ARPROT;
  wire [3:0]s01_couplers_to_xbar_ARQOS;
  wire [1:1]s01_couplers_to_xbar_ARREADY;
  wire [2:0]s01_couplers_to_xbar_ARSIZE;
  wire s01_couplers_to_xbar_ARVALID;
  wire [31:0]s01_couplers_to_xbar_AWADDR;
  wire [1:0]s01_couplers_to_xbar_AWBURST;
  wire [3:0]s01_couplers_to_xbar_AWCACHE;
  wire [4:0]s01_couplers_to_xbar_AWID;
  wire [3:0]s01_couplers_to_xbar_AWLEN;
  wire [1:0]s01_couplers_to_xbar_AWLOCK;
  wire [2:0]s01_couplers_to_xbar_AWPROT;
  wire [3:0]s01_couplers_to_xbar_AWQOS;
  wire [1:1]s01_couplers_to_xbar_AWREADY;
  wire [2:0]s01_couplers_to_xbar_AWSIZE;
  wire s01_couplers_to_xbar_AWVALID;
  wire [11:6]s01_couplers_to_xbar_BID;
  wire s01_couplers_to_xbar_BREADY;
  wire [3:2]s01_couplers_to_xbar_BRESP;
  wire [1:1]s01_couplers_to_xbar_BVALID;
  wire [127:64]s01_couplers_to_xbar_RDATA;
  wire [11:6]s01_couplers_to_xbar_RID;
  wire [1:1]s01_couplers_to_xbar_RLAST;
  wire s01_couplers_to_xbar_RREADY;
  wire [3:2]s01_couplers_to_xbar_RRESP;
  wire [1:1]s01_couplers_to_xbar_RVALID;
  wire [63:0]s01_couplers_to_xbar_WDATA;
  wire [4:0]s01_couplers_to_xbar_WID;
  wire s01_couplers_to_xbar_WLAST;
  wire [1:1]s01_couplers_to_xbar_WREADY;
  wire [7:0]s01_couplers_to_xbar_WSTRB;
  wire s01_couplers_to_xbar_WVALID;
  wire [31:0]xbar_to_m00_couplers_ARADDR;
  wire [1:0]xbar_to_m00_couplers_ARBURST;
  wire [3:0]xbar_to_m00_couplers_ARCACHE;
  wire [5:0]xbar_to_m00_couplers_ARID;
  wire [3:0]xbar_to_m00_couplers_ARLEN;
  wire [1:0]xbar_to_m00_couplers_ARLOCK;
  wire [2:0]xbar_to_m00_couplers_ARPROT;
  wire [3:0]xbar_to_m00_couplers_ARQOS;
  wire xbar_to_m00_couplers_ARREADY;
  wire [2:0]xbar_to_m00_couplers_ARSIZE;
  wire [0:0]xbar_to_m00_couplers_ARVALID;
  wire [31:0]xbar_to_m00_couplers_AWADDR;
  wire [1:0]xbar_to_m00_couplers_AWBURST;
  wire [3:0]xbar_to_m00_couplers_AWCACHE;
  wire [5:0]xbar_to_m00_couplers_AWID;
  wire [3:0]xbar_to_m00_couplers_AWLEN;
  wire [1:0]xbar_to_m00_couplers_AWLOCK;
  wire [2:0]xbar_to_m00_couplers_AWPROT;
  wire [3:0]xbar_to_m00_couplers_AWQOS;
  wire xbar_to_m00_couplers_AWREADY;
  wire [2:0]xbar_to_m00_couplers_AWSIZE;
  wire [0:0]xbar_to_m00_couplers_AWVALID;
  wire [5:0]xbar_to_m00_couplers_BID;
  wire [0:0]xbar_to_m00_couplers_BREADY;
  wire [1:0]xbar_to_m00_couplers_BRESP;
  wire xbar_to_m00_couplers_BVALID;
  wire [63:0]xbar_to_m00_couplers_RDATA;
  wire [5:0]xbar_to_m00_couplers_RID;
  wire xbar_to_m00_couplers_RLAST;
  wire [0:0]xbar_to_m00_couplers_RREADY;
  wire [1:0]xbar_to_m00_couplers_RRESP;
  wire xbar_to_m00_couplers_RVALID;
  wire [63:0]xbar_to_m00_couplers_WDATA;
  wire [5:0]xbar_to_m00_couplers_WID;
  wire [0:0]xbar_to_m00_couplers_WLAST;
  wire xbar_to_m00_couplers_WREADY;
  wire [7:0]xbar_to_m00_couplers_WSTRB;
  wire [0:0]xbar_to_m00_couplers_WVALID;

  assign M00_AXI_araddr[31:0] = m00_couplers_to_axi_interconnect_4_ARADDR;
  assign M00_AXI_arburst[1:0] = m00_couplers_to_axi_interconnect_4_ARBURST;
  assign M00_AXI_arcache[3:0] = m00_couplers_to_axi_interconnect_4_ARCACHE;
  assign M00_AXI_arid[5:0] = m00_couplers_to_axi_interconnect_4_ARID;
  assign M00_AXI_arlen[3:0] = m00_couplers_to_axi_interconnect_4_ARLEN;
  assign M00_AXI_arlock[1:0] = m00_couplers_to_axi_interconnect_4_ARLOCK;
  assign M00_AXI_arprot[2:0] = m00_couplers_to_axi_interconnect_4_ARPROT;
  assign M00_AXI_arqos[3:0] = m00_couplers_to_axi_interconnect_4_ARQOS;
  assign M00_AXI_arsize[2:0] = m00_couplers_to_axi_interconnect_4_ARSIZE;
  assign M00_AXI_arvalid = m00_couplers_to_axi_interconnect_4_ARVALID;
  assign M00_AXI_awaddr[31:0] = m00_couplers_to_axi_interconnect_4_AWADDR;
  assign M00_AXI_awburst[1:0] = m00_couplers_to_axi_interconnect_4_AWBURST;
  assign M00_AXI_awcache[3:0] = m00_couplers_to_axi_interconnect_4_AWCACHE;
  assign M00_AXI_awid[5:0] = m00_couplers_to_axi_interconnect_4_AWID;
  assign M00_AXI_awlen[3:0] = m00_couplers_to_axi_interconnect_4_AWLEN;
  assign M00_AXI_awlock[1:0] = m00_couplers_to_axi_interconnect_4_AWLOCK;
  assign M00_AXI_awprot[2:0] = m00_couplers_to_axi_interconnect_4_AWPROT;
  assign M00_AXI_awqos[3:0] = m00_couplers_to_axi_interconnect_4_AWQOS;
  assign M00_AXI_awsize[2:0] = m00_couplers_to_axi_interconnect_4_AWSIZE;
  assign M00_AXI_awvalid = m00_couplers_to_axi_interconnect_4_AWVALID;
  assign M00_AXI_bready = m00_couplers_to_axi_interconnect_4_BREADY;
  assign M00_AXI_rready = m00_couplers_to_axi_interconnect_4_RREADY;
  assign M00_AXI_wdata[63:0] = m00_couplers_to_axi_interconnect_4_WDATA;
  assign M00_AXI_wid[5:0] = m00_couplers_to_axi_interconnect_4_WID;
  assign M00_AXI_wlast = m00_couplers_to_axi_interconnect_4_WLAST;
  assign M00_AXI_wstrb[7:0] = m00_couplers_to_axi_interconnect_4_WSTRB;
  assign M00_AXI_wvalid = m00_couplers_to_axi_interconnect_4_WVALID;
  assign S00_AXI_arready = axi_interconnect_4_to_s00_couplers_ARREADY;
  assign S00_AXI_awready = axi_interconnect_4_to_s00_couplers_AWREADY;
  assign S00_AXI_bid[4:0] = axi_interconnect_4_to_s00_couplers_BID;
  assign S00_AXI_bresp[1:0] = axi_interconnect_4_to_s00_couplers_BRESP;
  assign S00_AXI_bvalid = axi_interconnect_4_to_s00_couplers_BVALID;
  assign S00_AXI_rdata[63:0] = axi_interconnect_4_to_s00_couplers_RDATA;
  assign S00_AXI_rid[4:0] = axi_interconnect_4_to_s00_couplers_RID;
  assign S00_AXI_rlast = axi_interconnect_4_to_s00_couplers_RLAST;
  assign S00_AXI_rresp[1:0] = axi_interconnect_4_to_s00_couplers_RRESP;
  assign S00_AXI_rvalid = axi_interconnect_4_to_s00_couplers_RVALID;
  assign S00_AXI_wready = axi_interconnect_4_to_s00_couplers_WREADY;
  assign S01_AXI_arready = axi_interconnect_4_to_s01_couplers_ARREADY;
  assign S01_AXI_awready = axi_interconnect_4_to_s01_couplers_AWREADY;
  assign S01_AXI_bid[4:0] = axi_interconnect_4_to_s01_couplers_BID;
  assign S01_AXI_bresp[1:0] = axi_interconnect_4_to_s01_couplers_BRESP;
  assign S01_AXI_bvalid = axi_interconnect_4_to_s01_couplers_BVALID;
  assign S01_AXI_rdata[63:0] = axi_interconnect_4_to_s01_couplers_RDATA;
  assign S01_AXI_rid[4:0] = axi_interconnect_4_to_s01_couplers_RID;
  assign S01_AXI_rlast = axi_interconnect_4_to_s01_couplers_RLAST;
  assign S01_AXI_rresp[1:0] = axi_interconnect_4_to_s01_couplers_RRESP;
  assign S01_AXI_rvalid = axi_interconnect_4_to_s01_couplers_RVALID;
  assign S01_AXI_wready = axi_interconnect_4_to_s01_couplers_WREADY;
  assign axi_interconnect_4_ACLK_net = ACLK;
  assign axi_interconnect_4_ARESETN_net = ARESETN;
  assign axi_interconnect_4_to_s00_couplers_ARADDR = S00_AXI_araddr[31:0];
  assign axi_interconnect_4_to_s00_couplers_ARBURST = S00_AXI_arburst[1:0];
  assign axi_interconnect_4_to_s00_couplers_ARCACHE = S00_AXI_arcache[3:0];
  assign axi_interconnect_4_to_s00_couplers_ARID = S00_AXI_arid[4:0];
  assign axi_interconnect_4_to_s00_couplers_ARLEN = S00_AXI_arlen[3:0];
  assign axi_interconnect_4_to_s00_couplers_ARLOCK = S00_AXI_arlock[1:0];
  assign axi_interconnect_4_to_s00_couplers_ARPROT = S00_AXI_arprot[2:0];
  assign axi_interconnect_4_to_s00_couplers_ARQOS = S00_AXI_arqos[3:0];
  assign axi_interconnect_4_to_s00_couplers_ARSIZE = S00_AXI_arsize[2:0];
  assign axi_interconnect_4_to_s00_couplers_ARVALID = S00_AXI_arvalid;
  assign axi_interconnect_4_to_s00_couplers_AWADDR = S00_AXI_awaddr[31:0];
  assign axi_interconnect_4_to_s00_couplers_AWBURST = S00_AXI_awburst[1:0];
  assign axi_interconnect_4_to_s00_couplers_AWCACHE = S00_AXI_awcache[3:0];
  assign axi_interconnect_4_to_s00_couplers_AWID = S00_AXI_awid[4:0];
  assign axi_interconnect_4_to_s00_couplers_AWLEN = S00_AXI_awlen[3:0];
  assign axi_interconnect_4_to_s00_couplers_AWLOCK = S00_AXI_awlock[1:0];
  assign axi_interconnect_4_to_s00_couplers_AWPROT = S00_AXI_awprot[2:0];
  assign axi_interconnect_4_to_s00_couplers_AWQOS = S00_AXI_awqos[3:0];
  assign axi_interconnect_4_to_s00_couplers_AWSIZE = S00_AXI_awsize[2:0];
  assign axi_interconnect_4_to_s00_couplers_AWVALID = S00_AXI_awvalid;
  assign axi_interconnect_4_to_s00_couplers_BREADY = S00_AXI_bready;
  assign axi_interconnect_4_to_s00_couplers_RREADY = S00_AXI_rready;
  assign axi_interconnect_4_to_s00_couplers_WDATA = S00_AXI_wdata[63:0];
  assign axi_interconnect_4_to_s00_couplers_WID = S00_AXI_wid[4:0];
  assign axi_interconnect_4_to_s00_couplers_WLAST = S00_AXI_wlast;
  assign axi_interconnect_4_to_s00_couplers_WSTRB = S00_AXI_wstrb[7:0];
  assign axi_interconnect_4_to_s00_couplers_WVALID = S00_AXI_wvalid;
  assign axi_interconnect_4_to_s01_couplers_ARADDR = S01_AXI_araddr[31:0];
  assign axi_interconnect_4_to_s01_couplers_ARBURST = S01_AXI_arburst[1:0];
  assign axi_interconnect_4_to_s01_couplers_ARCACHE = S01_AXI_arcache[3:0];
  assign axi_interconnect_4_to_s01_couplers_ARID = S01_AXI_arid[4:0];
  assign axi_interconnect_4_to_s01_couplers_ARLEN = S01_AXI_arlen[3:0];
  assign axi_interconnect_4_to_s01_couplers_ARLOCK = S01_AXI_arlock[1:0];
  assign axi_interconnect_4_to_s01_couplers_ARPROT = S01_AXI_arprot[2:0];
  assign axi_interconnect_4_to_s01_couplers_ARQOS = S01_AXI_arqos[3:0];
  assign axi_interconnect_4_to_s01_couplers_ARSIZE = S01_AXI_arsize[2:0];
  assign axi_interconnect_4_to_s01_couplers_ARVALID = S01_AXI_arvalid;
  assign axi_interconnect_4_to_s01_couplers_AWADDR = S01_AXI_awaddr[31:0];
  assign axi_interconnect_4_to_s01_couplers_AWBURST = S01_AXI_awburst[1:0];
  assign axi_interconnect_4_to_s01_couplers_AWCACHE = S01_AXI_awcache[3:0];
  assign axi_interconnect_4_to_s01_couplers_AWID = S01_AXI_awid[4:0];
  assign axi_interconnect_4_to_s01_couplers_AWLEN = S01_AXI_awlen[3:0];
  assign axi_interconnect_4_to_s01_couplers_AWLOCK = S01_AXI_awlock[1:0];
  assign axi_interconnect_4_to_s01_couplers_AWPROT = S01_AXI_awprot[2:0];
  assign axi_interconnect_4_to_s01_couplers_AWQOS = S01_AXI_awqos[3:0];
  assign axi_interconnect_4_to_s01_couplers_AWSIZE = S01_AXI_awsize[2:0];
  assign axi_interconnect_4_to_s01_couplers_AWVALID = S01_AXI_awvalid;
  assign axi_interconnect_4_to_s01_couplers_BREADY = S01_AXI_bready;
  assign axi_interconnect_4_to_s01_couplers_RREADY = S01_AXI_rready;
  assign axi_interconnect_4_to_s01_couplers_WDATA = S01_AXI_wdata[63:0];
  assign axi_interconnect_4_to_s01_couplers_WID = S01_AXI_wid[4:0];
  assign axi_interconnect_4_to_s01_couplers_WLAST = S01_AXI_wlast;
  assign axi_interconnect_4_to_s01_couplers_WSTRB = S01_AXI_wstrb[7:0];
  assign axi_interconnect_4_to_s01_couplers_WVALID = S01_AXI_wvalid;
  assign m00_couplers_to_axi_interconnect_4_ARREADY = M00_AXI_arready;
  assign m00_couplers_to_axi_interconnect_4_AWREADY = M00_AXI_awready;
  assign m00_couplers_to_axi_interconnect_4_BID = M00_AXI_bid[5:0];
  assign m00_couplers_to_axi_interconnect_4_BRESP = M00_AXI_bresp[1:0];
  assign m00_couplers_to_axi_interconnect_4_BVALID = M00_AXI_bvalid;
  assign m00_couplers_to_axi_interconnect_4_RDATA = M00_AXI_rdata[63:0];
  assign m00_couplers_to_axi_interconnect_4_RID = M00_AXI_rid[5:0];
  assign m00_couplers_to_axi_interconnect_4_RLAST = M00_AXI_rlast;
  assign m00_couplers_to_axi_interconnect_4_RRESP = M00_AXI_rresp[1:0];
  assign m00_couplers_to_axi_interconnect_4_RVALID = M00_AXI_rvalid;
  assign m00_couplers_to_axi_interconnect_4_WREADY = M00_AXI_wready;
  m00_couplers_imp_OID2TJ m00_couplers
       (.M_ACLK(axi_interconnect_4_ACLK_net),
        .M_ARESETN(axi_interconnect_4_ARESETN_net),
        .M_AXI_araddr(m00_couplers_to_axi_interconnect_4_ARADDR),
        .M_AXI_arburst(m00_couplers_to_axi_interconnect_4_ARBURST),
        .M_AXI_arcache(m00_couplers_to_axi_interconnect_4_ARCACHE),
        .M_AXI_arid(m00_couplers_to_axi_interconnect_4_ARID),
        .M_AXI_arlen(m00_couplers_to_axi_interconnect_4_ARLEN),
        .M_AXI_arlock(m00_couplers_to_axi_interconnect_4_ARLOCK),
        .M_AXI_arprot(m00_couplers_to_axi_interconnect_4_ARPROT),
        .M_AXI_arqos(m00_couplers_to_axi_interconnect_4_ARQOS),
        .M_AXI_arready(m00_couplers_to_axi_interconnect_4_ARREADY),
        .M_AXI_arsize(m00_couplers_to_axi_interconnect_4_ARSIZE),
        .M_AXI_arvalid(m00_couplers_to_axi_interconnect_4_ARVALID),
        .M_AXI_awaddr(m00_couplers_to_axi_interconnect_4_AWADDR),
        .M_AXI_awburst(m00_couplers_to_axi_interconnect_4_AWBURST),
        .M_AXI_awcache(m00_couplers_to_axi_interconnect_4_AWCACHE),
        .M_AXI_awid(m00_couplers_to_axi_interconnect_4_AWID),
        .M_AXI_awlen(m00_couplers_to_axi_interconnect_4_AWLEN),
        .M_AXI_awlock(m00_couplers_to_axi_interconnect_4_AWLOCK),
        .M_AXI_awprot(m00_couplers_to_axi_interconnect_4_AWPROT),
        .M_AXI_awqos(m00_couplers_to_axi_interconnect_4_AWQOS),
        .M_AXI_awready(m00_couplers_to_axi_interconnect_4_AWREADY),
        .M_AXI_awsize(m00_couplers_to_axi_interconnect_4_AWSIZE),
        .M_AXI_awvalid(m00_couplers_to_axi_interconnect_4_AWVALID),
        .M_AXI_bid(m00_couplers_to_axi_interconnect_4_BID),
        .M_AXI_bready(m00_couplers_to_axi_interconnect_4_BREADY),
        .M_AXI_bresp(m00_couplers_to_axi_interconnect_4_BRESP),
        .M_AXI_bvalid(m00_couplers_to_axi_interconnect_4_BVALID),
        .M_AXI_rdata(m00_couplers_to_axi_interconnect_4_RDATA),
        .M_AXI_rid(m00_couplers_to_axi_interconnect_4_RID),
        .M_AXI_rlast(m00_couplers_to_axi_interconnect_4_RLAST),
        .M_AXI_rready(m00_couplers_to_axi_interconnect_4_RREADY),
        .M_AXI_rresp(m00_couplers_to_axi_interconnect_4_RRESP),
        .M_AXI_rvalid(m00_couplers_to_axi_interconnect_4_RVALID),
        .M_AXI_wdata(m00_couplers_to_axi_interconnect_4_WDATA),
        .M_AXI_wid(m00_couplers_to_axi_interconnect_4_WID),
        .M_AXI_wlast(m00_couplers_to_axi_interconnect_4_WLAST),
        .M_AXI_wready(m00_couplers_to_axi_interconnect_4_WREADY),
        .M_AXI_wstrb(m00_couplers_to_axi_interconnect_4_WSTRB),
        .M_AXI_wvalid(m00_couplers_to_axi_interconnect_4_WVALID),
        .S_ACLK(axi_interconnect_4_ACLK_net),
        .S_ARESETN(axi_interconnect_4_ARESETN_net),
        .S_AXI_araddr(xbar_to_m00_couplers_ARADDR),
        .S_AXI_arburst(xbar_to_m00_couplers_ARBURST),
        .S_AXI_arcache(xbar_to_m00_couplers_ARCACHE),
        .S_AXI_arid(xbar_to_m00_couplers_ARID),
        .S_AXI_arlen(xbar_to_m00_couplers_ARLEN),
        .S_AXI_arlock(xbar_to_m00_couplers_ARLOCK),
        .S_AXI_arprot(xbar_to_m00_couplers_ARPROT),
        .S_AXI_arqos(xbar_to_m00_couplers_ARQOS),
        .S_AXI_arready(xbar_to_m00_couplers_ARREADY),
        .S_AXI_arsize(xbar_to_m00_couplers_ARSIZE),
        .S_AXI_arvalid(xbar_to_m00_couplers_ARVALID),
        .S_AXI_awaddr(xbar_to_m00_couplers_AWADDR),
        .S_AXI_awburst(xbar_to_m00_couplers_AWBURST),
        .S_AXI_awcache(xbar_to_m00_couplers_AWCACHE),
        .S_AXI_awid(xbar_to_m00_couplers_AWID),
        .S_AXI_awlen(xbar_to_m00_couplers_AWLEN),
        .S_AXI_awlock(xbar_to_m00_couplers_AWLOCK),
        .S_AXI_awprot(xbar_to_m00_couplers_AWPROT),
        .S_AXI_awqos(xbar_to_m00_couplers_AWQOS),
        .S_AXI_awready(xbar_to_m00_couplers_AWREADY),
        .S_AXI_awsize(xbar_to_m00_couplers_AWSIZE),
        .S_AXI_awvalid(xbar_to_m00_couplers_AWVALID),
        .S_AXI_bid(xbar_to_m00_couplers_BID),
        .S_AXI_bready(xbar_to_m00_couplers_BREADY),
        .S_AXI_bresp(xbar_to_m00_couplers_BRESP),
        .S_AXI_bvalid(xbar_to_m00_couplers_BVALID),
        .S_AXI_rdata(xbar_to_m00_couplers_RDATA),
        .S_AXI_rid(xbar_to_m00_couplers_RID),
        .S_AXI_rlast(xbar_to_m00_couplers_RLAST),
        .S_AXI_rready(xbar_to_m00_couplers_RREADY),
        .S_AXI_rresp(xbar_to_m00_couplers_RRESP),
        .S_AXI_rvalid(xbar_to_m00_couplers_RVALID),
        .S_AXI_wdata(xbar_to_m00_couplers_WDATA),
        .S_AXI_wid(xbar_to_m00_couplers_WID),
        .S_AXI_wlast(xbar_to_m00_couplers_WLAST),
        .S_AXI_wready(xbar_to_m00_couplers_WREADY),
        .S_AXI_wstrb(xbar_to_m00_couplers_WSTRB),
        .S_AXI_wvalid(xbar_to_m00_couplers_WVALID));
  s00_couplers_imp_3X80A4 s00_couplers
       (.M_ACLK(axi_interconnect_4_ACLK_net),
        .M_ARESETN(axi_interconnect_4_ARESETN_net),
        .M_AXI_araddr(s00_couplers_to_xbar_ARADDR),
        .M_AXI_arburst(s00_couplers_to_xbar_ARBURST),
        .M_AXI_arcache(s00_couplers_to_xbar_ARCACHE),
        .M_AXI_arid(s00_couplers_to_xbar_ARID),
        .M_AXI_arlen(s00_couplers_to_xbar_ARLEN),
        .M_AXI_arlock(s00_couplers_to_xbar_ARLOCK),
        .M_AXI_arprot(s00_couplers_to_xbar_ARPROT),
        .M_AXI_arqos(s00_couplers_to_xbar_ARQOS),
        .M_AXI_arready(s00_couplers_to_xbar_ARREADY),
        .M_AXI_arsize(s00_couplers_to_xbar_ARSIZE),
        .M_AXI_arvalid(s00_couplers_to_xbar_ARVALID),
        .M_AXI_awaddr(s00_couplers_to_xbar_AWADDR),
        .M_AXI_awburst(s00_couplers_to_xbar_AWBURST),
        .M_AXI_awcache(s00_couplers_to_xbar_AWCACHE),
        .M_AXI_awid(s00_couplers_to_xbar_AWID),
        .M_AXI_awlen(s00_couplers_to_xbar_AWLEN),
        .M_AXI_awlock(s00_couplers_to_xbar_AWLOCK),
        .M_AXI_awprot(s00_couplers_to_xbar_AWPROT),
        .M_AXI_awqos(s00_couplers_to_xbar_AWQOS),
        .M_AXI_awready(s00_couplers_to_xbar_AWREADY),
        .M_AXI_awsize(s00_couplers_to_xbar_AWSIZE),
        .M_AXI_awvalid(s00_couplers_to_xbar_AWVALID),
        .M_AXI_bid(s00_couplers_to_xbar_BID),
        .M_AXI_bready(s00_couplers_to_xbar_BREADY),
        .M_AXI_bresp(s00_couplers_to_xbar_BRESP),
        .M_AXI_bvalid(s00_couplers_to_xbar_BVALID),
        .M_AXI_rdata(s00_couplers_to_xbar_RDATA),
        .M_AXI_rid(s00_couplers_to_xbar_RID),
        .M_AXI_rlast(s00_couplers_to_xbar_RLAST),
        .M_AXI_rready(s00_couplers_to_xbar_RREADY),
        .M_AXI_rresp(s00_couplers_to_xbar_RRESP),
        .M_AXI_rvalid(s00_couplers_to_xbar_RVALID),
        .M_AXI_wdata(s00_couplers_to_xbar_WDATA),
        .M_AXI_wid(s00_couplers_to_xbar_WID),
        .M_AXI_wlast(s00_couplers_to_xbar_WLAST),
        .M_AXI_wready(s00_couplers_to_xbar_WREADY),
        .M_AXI_wstrb(s00_couplers_to_xbar_WSTRB),
        .M_AXI_wvalid(s00_couplers_to_xbar_WVALID),
        .S_ACLK(axi_interconnect_4_ACLK_net),
        .S_ARESETN(axi_interconnect_4_ARESETN_net),
        .S_AXI_araddr(axi_interconnect_4_to_s00_couplers_ARADDR),
        .S_AXI_arburst(axi_interconnect_4_to_s00_couplers_ARBURST),
        .S_AXI_arcache(axi_interconnect_4_to_s00_couplers_ARCACHE),
        .S_AXI_arid(axi_interconnect_4_to_s00_couplers_ARID),
        .S_AXI_arlen(axi_interconnect_4_to_s00_couplers_ARLEN),
        .S_AXI_arlock(axi_interconnect_4_to_s00_couplers_ARLOCK),
        .S_AXI_arprot(axi_interconnect_4_to_s00_couplers_ARPROT),
        .S_AXI_arqos(axi_interconnect_4_to_s00_couplers_ARQOS),
        .S_AXI_arready(axi_interconnect_4_to_s00_couplers_ARREADY),
        .S_AXI_arsize(axi_interconnect_4_to_s00_couplers_ARSIZE),
        .S_AXI_arvalid(axi_interconnect_4_to_s00_couplers_ARVALID),
        .S_AXI_awaddr(axi_interconnect_4_to_s00_couplers_AWADDR),
        .S_AXI_awburst(axi_interconnect_4_to_s00_couplers_AWBURST),
        .S_AXI_awcache(axi_interconnect_4_to_s00_couplers_AWCACHE),
        .S_AXI_awid(axi_interconnect_4_to_s00_couplers_AWID),
        .S_AXI_awlen(axi_interconnect_4_to_s00_couplers_AWLEN),
        .S_AXI_awlock(axi_interconnect_4_to_s00_couplers_AWLOCK),
        .S_AXI_awprot(axi_interconnect_4_to_s00_couplers_AWPROT),
        .S_AXI_awqos(axi_interconnect_4_to_s00_couplers_AWQOS),
        .S_AXI_awready(axi_interconnect_4_to_s00_couplers_AWREADY),
        .S_AXI_awsize(axi_interconnect_4_to_s00_couplers_AWSIZE),
        .S_AXI_awvalid(axi_interconnect_4_to_s00_couplers_AWVALID),
        .S_AXI_bid(axi_interconnect_4_to_s00_couplers_BID),
        .S_AXI_bready(axi_interconnect_4_to_s00_couplers_BREADY),
        .S_AXI_bresp(axi_interconnect_4_to_s00_couplers_BRESP),
        .S_AXI_bvalid(axi_interconnect_4_to_s00_couplers_BVALID),
        .S_AXI_rdata(axi_interconnect_4_to_s00_couplers_RDATA),
        .S_AXI_rid(axi_interconnect_4_to_s00_couplers_RID),
        .S_AXI_rlast(axi_interconnect_4_to_s00_couplers_RLAST),
        .S_AXI_rready(axi_interconnect_4_to_s00_couplers_RREADY),
        .S_AXI_rresp(axi_interconnect_4_to_s00_couplers_RRESP),
        .S_AXI_rvalid(axi_interconnect_4_to_s00_couplers_RVALID),
        .S_AXI_wdata(axi_interconnect_4_to_s00_couplers_WDATA),
        .S_AXI_wid(axi_interconnect_4_to_s00_couplers_WID),
        .S_AXI_wlast(axi_interconnect_4_to_s00_couplers_WLAST),
        .S_AXI_wready(axi_interconnect_4_to_s00_couplers_WREADY),
        .S_AXI_wstrb(axi_interconnect_4_to_s00_couplers_WSTRB),
        .S_AXI_wvalid(axi_interconnect_4_to_s00_couplers_WVALID));
  s01_couplers_imp_1F0E4QS s01_couplers
       (.M_ACLK(axi_interconnect_4_ACLK_net),
        .M_ARESETN(axi_interconnect_4_ARESETN_net),
        .M_AXI_araddr(s01_couplers_to_xbar_ARADDR),
        .M_AXI_arburst(s01_couplers_to_xbar_ARBURST),
        .M_AXI_arcache(s01_couplers_to_xbar_ARCACHE),
        .M_AXI_arid(s01_couplers_to_xbar_ARID),
        .M_AXI_arlen(s01_couplers_to_xbar_ARLEN),
        .M_AXI_arlock(s01_couplers_to_xbar_ARLOCK),
        .M_AXI_arprot(s01_couplers_to_xbar_ARPROT),
        .M_AXI_arqos(s01_couplers_to_xbar_ARQOS),
        .M_AXI_arready(s01_couplers_to_xbar_ARREADY),
        .M_AXI_arsize(s01_couplers_to_xbar_ARSIZE),
        .M_AXI_arvalid(s01_couplers_to_xbar_ARVALID),
        .M_AXI_awaddr(s01_couplers_to_xbar_AWADDR),
        .M_AXI_awburst(s01_couplers_to_xbar_AWBURST),
        .M_AXI_awcache(s01_couplers_to_xbar_AWCACHE),
        .M_AXI_awid(s01_couplers_to_xbar_AWID),
        .M_AXI_awlen(s01_couplers_to_xbar_AWLEN),
        .M_AXI_awlock(s01_couplers_to_xbar_AWLOCK),
        .M_AXI_awprot(s01_couplers_to_xbar_AWPROT),
        .M_AXI_awqos(s01_couplers_to_xbar_AWQOS),
        .M_AXI_awready(s01_couplers_to_xbar_AWREADY),
        .M_AXI_awsize(s01_couplers_to_xbar_AWSIZE),
        .M_AXI_awvalid(s01_couplers_to_xbar_AWVALID),
        .M_AXI_bid(s01_couplers_to_xbar_BID),
        .M_AXI_bready(s01_couplers_to_xbar_BREADY),
        .M_AXI_bresp(s01_couplers_to_xbar_BRESP),
        .M_AXI_bvalid(s01_couplers_to_xbar_BVALID),
        .M_AXI_rdata(s01_couplers_to_xbar_RDATA),
        .M_AXI_rid(s01_couplers_to_xbar_RID),
        .M_AXI_rlast(s01_couplers_to_xbar_RLAST),
        .M_AXI_rready(s01_couplers_to_xbar_RREADY),
        .M_AXI_rresp(s01_couplers_to_xbar_RRESP),
        .M_AXI_rvalid(s01_couplers_to_xbar_RVALID),
        .M_AXI_wdata(s01_couplers_to_xbar_WDATA),
        .M_AXI_wid(s01_couplers_to_xbar_WID),
        .M_AXI_wlast(s01_couplers_to_xbar_WLAST),
        .M_AXI_wready(s01_couplers_to_xbar_WREADY),
        .M_AXI_wstrb(s01_couplers_to_xbar_WSTRB),
        .M_AXI_wvalid(s01_couplers_to_xbar_WVALID),
        .S_ACLK(axi_interconnect_4_ACLK_net),
        .S_ARESETN(axi_interconnect_4_ARESETN_net),
        .S_AXI_araddr(axi_interconnect_4_to_s01_couplers_ARADDR),
        .S_AXI_arburst(axi_interconnect_4_to_s01_couplers_ARBURST),
        .S_AXI_arcache(axi_interconnect_4_to_s01_couplers_ARCACHE),
        .S_AXI_arid(axi_interconnect_4_to_s01_couplers_ARID),
        .S_AXI_arlen(axi_interconnect_4_to_s01_couplers_ARLEN),
        .S_AXI_arlock(axi_interconnect_4_to_s01_couplers_ARLOCK),
        .S_AXI_arprot(axi_interconnect_4_to_s01_couplers_ARPROT),
        .S_AXI_arqos(axi_interconnect_4_to_s01_couplers_ARQOS),
        .S_AXI_arready(axi_interconnect_4_to_s01_couplers_ARREADY),
        .S_AXI_arsize(axi_interconnect_4_to_s01_couplers_ARSIZE),
        .S_AXI_arvalid(axi_interconnect_4_to_s01_couplers_ARVALID),
        .S_AXI_awaddr(axi_interconnect_4_to_s01_couplers_AWADDR),
        .S_AXI_awburst(axi_interconnect_4_to_s01_couplers_AWBURST),
        .S_AXI_awcache(axi_interconnect_4_to_s01_couplers_AWCACHE),
        .S_AXI_awid(axi_interconnect_4_to_s01_couplers_AWID),
        .S_AXI_awlen(axi_interconnect_4_to_s01_couplers_AWLEN),
        .S_AXI_awlock(axi_interconnect_4_to_s01_couplers_AWLOCK),
        .S_AXI_awprot(axi_interconnect_4_to_s01_couplers_AWPROT),
        .S_AXI_awqos(axi_interconnect_4_to_s01_couplers_AWQOS),
        .S_AXI_awready(axi_interconnect_4_to_s01_couplers_AWREADY),
        .S_AXI_awsize(axi_interconnect_4_to_s01_couplers_AWSIZE),
        .S_AXI_awvalid(axi_interconnect_4_to_s01_couplers_AWVALID),
        .S_AXI_bid(axi_interconnect_4_to_s01_couplers_BID),
        .S_AXI_bready(axi_interconnect_4_to_s01_couplers_BREADY),
        .S_AXI_bresp(axi_interconnect_4_to_s01_couplers_BRESP),
        .S_AXI_bvalid(axi_interconnect_4_to_s01_couplers_BVALID),
        .S_AXI_rdata(axi_interconnect_4_to_s01_couplers_RDATA),
        .S_AXI_rid(axi_interconnect_4_to_s01_couplers_RID),
        .S_AXI_rlast(axi_interconnect_4_to_s01_couplers_RLAST),
        .S_AXI_rready(axi_interconnect_4_to_s01_couplers_RREADY),
        .S_AXI_rresp(axi_interconnect_4_to_s01_couplers_RRESP),
        .S_AXI_rvalid(axi_interconnect_4_to_s01_couplers_RVALID),
        .S_AXI_wdata(axi_interconnect_4_to_s01_couplers_WDATA),
        .S_AXI_wid(axi_interconnect_4_to_s01_couplers_WID),
        .S_AXI_wlast(axi_interconnect_4_to_s01_couplers_WLAST),
        .S_AXI_wready(axi_interconnect_4_to_s01_couplers_WREADY),
        .S_AXI_wstrb(axi_interconnect_4_to_s01_couplers_WSTRB),
        .S_AXI_wvalid(axi_interconnect_4_to_s01_couplers_WVALID));
  ps_ai_xbar_4 xbar
       (.aclk(axi_interconnect_4_ACLK_net),
        .aresetn(axi_interconnect_4_ARESETN_net),
        .m_axi_araddr(xbar_to_m00_couplers_ARADDR),
        .m_axi_arburst(xbar_to_m00_couplers_ARBURST),
        .m_axi_arcache(xbar_to_m00_couplers_ARCACHE),
        .m_axi_arid(xbar_to_m00_couplers_ARID),
        .m_axi_arlen(xbar_to_m00_couplers_ARLEN),
        .m_axi_arlock(xbar_to_m00_couplers_ARLOCK),
        .m_axi_arprot(xbar_to_m00_couplers_ARPROT),
        .m_axi_arqos(xbar_to_m00_couplers_ARQOS),
        .m_axi_arready(xbar_to_m00_couplers_ARREADY),
        .m_axi_arsize(xbar_to_m00_couplers_ARSIZE),
        .m_axi_arvalid(xbar_to_m00_couplers_ARVALID),
        .m_axi_awaddr(xbar_to_m00_couplers_AWADDR),
        .m_axi_awburst(xbar_to_m00_couplers_AWBURST),
        .m_axi_awcache(xbar_to_m00_couplers_AWCACHE),
        .m_axi_awid(xbar_to_m00_couplers_AWID),
        .m_axi_awlen(xbar_to_m00_couplers_AWLEN),
        .m_axi_awlock(xbar_to_m00_couplers_AWLOCK),
        .m_axi_awprot(xbar_to_m00_couplers_AWPROT),
        .m_axi_awqos(xbar_to_m00_couplers_AWQOS),
        .m_axi_awready(xbar_to_m00_couplers_AWREADY),
        .m_axi_awsize(xbar_to_m00_couplers_AWSIZE),
        .m_axi_awvalid(xbar_to_m00_couplers_AWVALID),
        .m_axi_bid(xbar_to_m00_couplers_BID),
        .m_axi_bready(xbar_to_m00_couplers_BREADY),
        .m_axi_bresp(xbar_to_m00_couplers_BRESP),
        .m_axi_bvalid(xbar_to_m00_couplers_BVALID),
        .m_axi_rdata(xbar_to_m00_couplers_RDATA),
        .m_axi_rid(xbar_to_m00_couplers_RID),
        .m_axi_rlast(xbar_to_m00_couplers_RLAST),
        .m_axi_rready(xbar_to_m00_couplers_RREADY),
        .m_axi_rresp(xbar_to_m00_couplers_RRESP),
        .m_axi_rvalid(xbar_to_m00_couplers_RVALID),
        .m_axi_wdata(xbar_to_m00_couplers_WDATA),
        .m_axi_wid(xbar_to_m00_couplers_WID),
        .m_axi_wlast(xbar_to_m00_couplers_WLAST),
        .m_axi_wready(xbar_to_m00_couplers_WREADY),
        .m_axi_wstrb(xbar_to_m00_couplers_WSTRB),
        .m_axi_wvalid(xbar_to_m00_couplers_WVALID),
        .s_axi_araddr({s01_couplers_to_xbar_ARADDR,s00_couplers_to_xbar_ARADDR}),
        .s_axi_arburst({s01_couplers_to_xbar_ARBURST,s00_couplers_to_xbar_ARBURST}),
        .s_axi_arcache({s01_couplers_to_xbar_ARCACHE,s00_couplers_to_xbar_ARCACHE}),
        .s_axi_arid({1'b0,s01_couplers_to_xbar_ARID,1'b0,s00_couplers_to_xbar_ARID}),
        .s_axi_arlen({s01_couplers_to_xbar_ARLEN,s00_couplers_to_xbar_ARLEN}),
        .s_axi_arlock({s01_couplers_to_xbar_ARLOCK,s00_couplers_to_xbar_ARLOCK}),
        .s_axi_arprot({s01_couplers_to_xbar_ARPROT,s00_couplers_to_xbar_ARPROT}),
        .s_axi_arqos({s01_couplers_to_xbar_ARQOS,s00_couplers_to_xbar_ARQOS}),
        .s_axi_arready({s01_couplers_to_xbar_ARREADY,s00_couplers_to_xbar_ARREADY}),
        .s_axi_arsize({s01_couplers_to_xbar_ARSIZE,s00_couplers_to_xbar_ARSIZE}),
        .s_axi_arvalid({s01_couplers_to_xbar_ARVALID,s00_couplers_to_xbar_ARVALID}),
        .s_axi_awaddr({s01_couplers_to_xbar_AWADDR,s00_couplers_to_xbar_AWADDR}),
        .s_axi_awburst({s01_couplers_to_xbar_AWBURST,s00_couplers_to_xbar_AWBURST}),
        .s_axi_awcache({s01_couplers_to_xbar_AWCACHE,s00_couplers_to_xbar_AWCACHE}),
        .s_axi_awid({1'b0,s01_couplers_to_xbar_AWID,1'b0,s00_couplers_to_xbar_AWID}),
        .s_axi_awlen({s01_couplers_to_xbar_AWLEN,s00_couplers_to_xbar_AWLEN}),
        .s_axi_awlock({s01_couplers_to_xbar_AWLOCK,s00_couplers_to_xbar_AWLOCK}),
        .s_axi_awprot({s01_couplers_to_xbar_AWPROT,s00_couplers_to_xbar_AWPROT}),
        .s_axi_awqos({s01_couplers_to_xbar_AWQOS,s00_couplers_to_xbar_AWQOS}),
        .s_axi_awready({s01_couplers_to_xbar_AWREADY,s00_couplers_to_xbar_AWREADY}),
        .s_axi_awsize({s01_couplers_to_xbar_AWSIZE,s00_couplers_to_xbar_AWSIZE}),
        .s_axi_awvalid({s01_couplers_to_xbar_AWVALID,s00_couplers_to_xbar_AWVALID}),
        .s_axi_bid({s01_couplers_to_xbar_BID,s00_couplers_to_xbar_BID}),
        .s_axi_bready({s01_couplers_to_xbar_BREADY,s00_couplers_to_xbar_BREADY}),
        .s_axi_bresp({s01_couplers_to_xbar_BRESP,s00_couplers_to_xbar_BRESP}),
        .s_axi_bvalid({s01_couplers_to_xbar_BVALID,s00_couplers_to_xbar_BVALID}),
        .s_axi_rdata({s01_couplers_to_xbar_RDATA,s00_couplers_to_xbar_RDATA}),
        .s_axi_rid({s01_couplers_to_xbar_RID,s00_couplers_to_xbar_RID}),
        .s_axi_rlast({s01_couplers_to_xbar_RLAST,s00_couplers_to_xbar_RLAST}),
        .s_axi_rready({s01_couplers_to_xbar_RREADY,s00_couplers_to_xbar_RREADY}),
        .s_axi_rresp({s01_couplers_to_xbar_RRESP,s00_couplers_to_xbar_RRESP}),
        .s_axi_rvalid({s01_couplers_to_xbar_RVALID,s00_couplers_to_xbar_RVALID}),
        .s_axi_wdata({s01_couplers_to_xbar_WDATA,s00_couplers_to_xbar_WDATA}),
        .s_axi_wid({1'b0,s01_couplers_to_xbar_WID,1'b0,s00_couplers_to_xbar_WID}),
        .s_axi_wlast({s01_couplers_to_xbar_WLAST,s00_couplers_to_xbar_WLAST}),
        .s_axi_wready({s01_couplers_to_xbar_WREADY,s00_couplers_to_xbar_WREADY}),
        .s_axi_wstrb({s01_couplers_to_xbar_WSTRB,s00_couplers_to_xbar_WSTRB}),
        .s_axi_wvalid({s01_couplers_to_xbar_WVALID,s00_couplers_to_xbar_WVALID}));
endmodule

module s00_couplers_imp_1S6C5N2
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [11:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [11:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output M_AXI_awvalid;
  input [11:0]M_AXI_bid;
  output M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input M_AXI_bvalid;
  input [31:0]M_AXI_rdata;
  input [11:0]M_AXI_rid;
  input M_AXI_rlast;
  output M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input M_AXI_rvalid;
  output [31:0]M_AXI_wdata;
  output [11:0]M_AXI_wid;
  output M_AXI_wlast;
  input M_AXI_wready;
  output [3:0]M_AXI_wstrb;
  output M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [11:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [11:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input S_AXI_awvalid;
  output [11:0]S_AXI_bid;
  input S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output S_AXI_bvalid;
  output [31:0]S_AXI_rdata;
  output [11:0]S_AXI_rid;
  output S_AXI_rlast;
  input S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output S_AXI_rvalid;
  input [31:0]S_AXI_wdata;
  input [11:0]S_AXI_wid;
  input S_AXI_wlast;
  output S_AXI_wready;
  input [3:0]S_AXI_wstrb;
  input S_AXI_wvalid;

  wire S_ACLK_1;
  wire S_ARESETN_1;
  wire [31:0]s00_couplers_to_s00_regslice_ARADDR;
  wire [1:0]s00_couplers_to_s00_regslice_ARBURST;
  wire [3:0]s00_couplers_to_s00_regslice_ARCACHE;
  wire [11:0]s00_couplers_to_s00_regslice_ARID;
  wire [3:0]s00_couplers_to_s00_regslice_ARLEN;
  wire [1:0]s00_couplers_to_s00_regslice_ARLOCK;
  wire [2:0]s00_couplers_to_s00_regslice_ARPROT;
  wire [3:0]s00_couplers_to_s00_regslice_ARQOS;
  wire s00_couplers_to_s00_regslice_ARREADY;
  wire [2:0]s00_couplers_to_s00_regslice_ARSIZE;
  wire s00_couplers_to_s00_regslice_ARVALID;
  wire [31:0]s00_couplers_to_s00_regslice_AWADDR;
  wire [1:0]s00_couplers_to_s00_regslice_AWBURST;
  wire [3:0]s00_couplers_to_s00_regslice_AWCACHE;
  wire [11:0]s00_couplers_to_s00_regslice_AWID;
  wire [3:0]s00_couplers_to_s00_regslice_AWLEN;
  wire [1:0]s00_couplers_to_s00_regslice_AWLOCK;
  wire [2:0]s00_couplers_to_s00_regslice_AWPROT;
  wire [3:0]s00_couplers_to_s00_regslice_AWQOS;
  wire s00_couplers_to_s00_regslice_AWREADY;
  wire [2:0]s00_couplers_to_s00_regslice_AWSIZE;
  wire s00_couplers_to_s00_regslice_AWVALID;
  wire [11:0]s00_couplers_to_s00_regslice_BID;
  wire s00_couplers_to_s00_regslice_BREADY;
  wire [1:0]s00_couplers_to_s00_regslice_BRESP;
  wire s00_couplers_to_s00_regslice_BVALID;
  wire [31:0]s00_couplers_to_s00_regslice_RDATA;
  wire [11:0]s00_couplers_to_s00_regslice_RID;
  wire s00_couplers_to_s00_regslice_RLAST;
  wire s00_couplers_to_s00_regslice_RREADY;
  wire [1:0]s00_couplers_to_s00_regslice_RRESP;
  wire s00_couplers_to_s00_regslice_RVALID;
  wire [31:0]s00_couplers_to_s00_regslice_WDATA;
  wire [11:0]s00_couplers_to_s00_regslice_WID;
  wire s00_couplers_to_s00_regslice_WLAST;
  wire s00_couplers_to_s00_regslice_WREADY;
  wire [3:0]s00_couplers_to_s00_regslice_WSTRB;
  wire s00_couplers_to_s00_regslice_WVALID;
  wire [31:0]s00_regslice_to_s00_couplers_ARADDR;
  wire [1:0]s00_regslice_to_s00_couplers_ARBURST;
  wire [3:0]s00_regslice_to_s00_couplers_ARCACHE;
  wire [11:0]s00_regslice_to_s00_couplers_ARID;
  wire [3:0]s00_regslice_to_s00_couplers_ARLEN;
  wire [1:0]s00_regslice_to_s00_couplers_ARLOCK;
  wire [2:0]s00_regslice_to_s00_couplers_ARPROT;
  wire [3:0]s00_regslice_to_s00_couplers_ARQOS;
  wire s00_regslice_to_s00_couplers_ARREADY;
  wire [2:0]s00_regslice_to_s00_couplers_ARSIZE;
  wire s00_regslice_to_s00_couplers_ARVALID;
  wire [31:0]s00_regslice_to_s00_couplers_AWADDR;
  wire [1:0]s00_regslice_to_s00_couplers_AWBURST;
  wire [3:0]s00_regslice_to_s00_couplers_AWCACHE;
  wire [11:0]s00_regslice_to_s00_couplers_AWID;
  wire [3:0]s00_regslice_to_s00_couplers_AWLEN;
  wire [1:0]s00_regslice_to_s00_couplers_AWLOCK;
  wire [2:0]s00_regslice_to_s00_couplers_AWPROT;
  wire [3:0]s00_regslice_to_s00_couplers_AWQOS;
  wire s00_regslice_to_s00_couplers_AWREADY;
  wire [2:0]s00_regslice_to_s00_couplers_AWSIZE;
  wire s00_regslice_to_s00_couplers_AWVALID;
  wire [11:0]s00_regslice_to_s00_couplers_BID;
  wire s00_regslice_to_s00_couplers_BREADY;
  wire [1:0]s00_regslice_to_s00_couplers_BRESP;
  wire s00_regslice_to_s00_couplers_BVALID;
  wire [31:0]s00_regslice_to_s00_couplers_RDATA;
  wire [11:0]s00_regslice_to_s00_couplers_RID;
  wire s00_regslice_to_s00_couplers_RLAST;
  wire s00_regslice_to_s00_couplers_RREADY;
  wire [1:0]s00_regslice_to_s00_couplers_RRESP;
  wire s00_regslice_to_s00_couplers_RVALID;
  wire [31:0]s00_regslice_to_s00_couplers_WDATA;
  wire [11:0]s00_regslice_to_s00_couplers_WID;
  wire s00_regslice_to_s00_couplers_WLAST;
  wire s00_regslice_to_s00_couplers_WREADY;
  wire [3:0]s00_regslice_to_s00_couplers_WSTRB;
  wire s00_regslice_to_s00_couplers_WVALID;

  assign M_AXI_araddr[31:0] = s00_regslice_to_s00_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = s00_regslice_to_s00_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = s00_regslice_to_s00_couplers_ARCACHE;
  assign M_AXI_arid[11:0] = s00_regslice_to_s00_couplers_ARID;
  assign M_AXI_arlen[3:0] = s00_regslice_to_s00_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = s00_regslice_to_s00_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = s00_regslice_to_s00_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = s00_regslice_to_s00_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = s00_regslice_to_s00_couplers_ARSIZE;
  assign M_AXI_arvalid = s00_regslice_to_s00_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = s00_regslice_to_s00_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = s00_regslice_to_s00_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = s00_regslice_to_s00_couplers_AWCACHE;
  assign M_AXI_awid[11:0] = s00_regslice_to_s00_couplers_AWID;
  assign M_AXI_awlen[3:0] = s00_regslice_to_s00_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = s00_regslice_to_s00_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = s00_regslice_to_s00_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = s00_regslice_to_s00_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = s00_regslice_to_s00_couplers_AWSIZE;
  assign M_AXI_awvalid = s00_regslice_to_s00_couplers_AWVALID;
  assign M_AXI_bready = s00_regslice_to_s00_couplers_BREADY;
  assign M_AXI_rready = s00_regslice_to_s00_couplers_RREADY;
  assign M_AXI_wdata[31:0] = s00_regslice_to_s00_couplers_WDATA;
  assign M_AXI_wid[11:0] = s00_regslice_to_s00_couplers_WID;
  assign M_AXI_wlast = s00_regslice_to_s00_couplers_WLAST;
  assign M_AXI_wstrb[3:0] = s00_regslice_to_s00_couplers_WSTRB;
  assign M_AXI_wvalid = s00_regslice_to_s00_couplers_WVALID;
  assign S_ACLK_1 = S_ACLK;
  assign S_ARESETN_1 = S_ARESETN;
  assign S_AXI_arready = s00_couplers_to_s00_regslice_ARREADY;
  assign S_AXI_awready = s00_couplers_to_s00_regslice_AWREADY;
  assign S_AXI_bid[11:0] = s00_couplers_to_s00_regslice_BID;
  assign S_AXI_bresp[1:0] = s00_couplers_to_s00_regslice_BRESP;
  assign S_AXI_bvalid = s00_couplers_to_s00_regslice_BVALID;
  assign S_AXI_rdata[31:0] = s00_couplers_to_s00_regslice_RDATA;
  assign S_AXI_rid[11:0] = s00_couplers_to_s00_regslice_RID;
  assign S_AXI_rlast = s00_couplers_to_s00_regslice_RLAST;
  assign S_AXI_rresp[1:0] = s00_couplers_to_s00_regslice_RRESP;
  assign S_AXI_rvalid = s00_couplers_to_s00_regslice_RVALID;
  assign S_AXI_wready = s00_couplers_to_s00_regslice_WREADY;
  assign s00_couplers_to_s00_regslice_ARADDR = S_AXI_araddr[31:0];
  assign s00_couplers_to_s00_regslice_ARBURST = S_AXI_arburst[1:0];
  assign s00_couplers_to_s00_regslice_ARCACHE = S_AXI_arcache[3:0];
  assign s00_couplers_to_s00_regslice_ARID = S_AXI_arid[11:0];
  assign s00_couplers_to_s00_regslice_ARLEN = S_AXI_arlen[3:0];
  assign s00_couplers_to_s00_regslice_ARLOCK = S_AXI_arlock[1:0];
  assign s00_couplers_to_s00_regslice_ARPROT = S_AXI_arprot[2:0];
  assign s00_couplers_to_s00_regslice_ARQOS = S_AXI_arqos[3:0];
  assign s00_couplers_to_s00_regslice_ARSIZE = S_AXI_arsize[2:0];
  assign s00_couplers_to_s00_regslice_ARVALID = S_AXI_arvalid;
  assign s00_couplers_to_s00_regslice_AWADDR = S_AXI_awaddr[31:0];
  assign s00_couplers_to_s00_regslice_AWBURST = S_AXI_awburst[1:0];
  assign s00_couplers_to_s00_regslice_AWCACHE = S_AXI_awcache[3:0];
  assign s00_couplers_to_s00_regslice_AWID = S_AXI_awid[11:0];
  assign s00_couplers_to_s00_regslice_AWLEN = S_AXI_awlen[3:0];
  assign s00_couplers_to_s00_regslice_AWLOCK = S_AXI_awlock[1:0];
  assign s00_couplers_to_s00_regslice_AWPROT = S_AXI_awprot[2:0];
  assign s00_couplers_to_s00_regslice_AWQOS = S_AXI_awqos[3:0];
  assign s00_couplers_to_s00_regslice_AWSIZE = S_AXI_awsize[2:0];
  assign s00_couplers_to_s00_regslice_AWVALID = S_AXI_awvalid;
  assign s00_couplers_to_s00_regslice_BREADY = S_AXI_bready;
  assign s00_couplers_to_s00_regslice_RREADY = S_AXI_rready;
  assign s00_couplers_to_s00_regslice_WDATA = S_AXI_wdata[31:0];
  assign s00_couplers_to_s00_regslice_WID = S_AXI_wid[11:0];
  assign s00_couplers_to_s00_regslice_WLAST = S_AXI_wlast;
  assign s00_couplers_to_s00_regslice_WSTRB = S_AXI_wstrb[3:0];
  assign s00_couplers_to_s00_regslice_WVALID = S_AXI_wvalid;
  assign s00_regslice_to_s00_couplers_ARREADY = M_AXI_arready;
  assign s00_regslice_to_s00_couplers_AWREADY = M_AXI_awready;
  assign s00_regslice_to_s00_couplers_BID = M_AXI_bid[11:0];
  assign s00_regslice_to_s00_couplers_BRESP = M_AXI_bresp[1:0];
  assign s00_regslice_to_s00_couplers_BVALID = M_AXI_bvalid;
  assign s00_regslice_to_s00_couplers_RDATA = M_AXI_rdata[31:0];
  assign s00_regslice_to_s00_couplers_RID = M_AXI_rid[11:0];
  assign s00_regslice_to_s00_couplers_RLAST = M_AXI_rlast;
  assign s00_regslice_to_s00_couplers_RRESP = M_AXI_rresp[1:0];
  assign s00_regslice_to_s00_couplers_RVALID = M_AXI_rvalid;
  assign s00_regslice_to_s00_couplers_WREADY = M_AXI_wready;
  ps_ai_s00_regslice_0 s00_regslice
       (.aclk(S_ACLK_1),
        .aresetn(S_ARESETN_1),
        .m_axi_araddr(s00_regslice_to_s00_couplers_ARADDR),
        .m_axi_arburst(s00_regslice_to_s00_couplers_ARBURST),
        .m_axi_arcache(s00_regslice_to_s00_couplers_ARCACHE),
        .m_axi_arid(s00_regslice_to_s00_couplers_ARID),
        .m_axi_arlen(s00_regslice_to_s00_couplers_ARLEN),
        .m_axi_arlock(s00_regslice_to_s00_couplers_ARLOCK),
        .m_axi_arprot(s00_regslice_to_s00_couplers_ARPROT),
        .m_axi_arqos(s00_regslice_to_s00_couplers_ARQOS),
        .m_axi_arready(s00_regslice_to_s00_couplers_ARREADY),
        .m_axi_arsize(s00_regslice_to_s00_couplers_ARSIZE),
        .m_axi_arvalid(s00_regslice_to_s00_couplers_ARVALID),
        .m_axi_awaddr(s00_regslice_to_s00_couplers_AWADDR),
        .m_axi_awburst(s00_regslice_to_s00_couplers_AWBURST),
        .m_axi_awcache(s00_regslice_to_s00_couplers_AWCACHE),
        .m_axi_awid(s00_regslice_to_s00_couplers_AWID),
        .m_axi_awlen(s00_regslice_to_s00_couplers_AWLEN),
        .m_axi_awlock(s00_regslice_to_s00_couplers_AWLOCK),
        .m_axi_awprot(s00_regslice_to_s00_couplers_AWPROT),
        .m_axi_awqos(s00_regslice_to_s00_couplers_AWQOS),
        .m_axi_awready(s00_regslice_to_s00_couplers_AWREADY),
        .m_axi_awsize(s00_regslice_to_s00_couplers_AWSIZE),
        .m_axi_awvalid(s00_regslice_to_s00_couplers_AWVALID),
        .m_axi_bid(s00_regslice_to_s00_couplers_BID),
        .m_axi_bready(s00_regslice_to_s00_couplers_BREADY),
        .m_axi_bresp(s00_regslice_to_s00_couplers_BRESP),
        .m_axi_bvalid(s00_regslice_to_s00_couplers_BVALID),
        .m_axi_rdata(s00_regslice_to_s00_couplers_RDATA),
        .m_axi_rid(s00_regslice_to_s00_couplers_RID),
        .m_axi_rlast(s00_regslice_to_s00_couplers_RLAST),
        .m_axi_rready(s00_regslice_to_s00_couplers_RREADY),
        .m_axi_rresp(s00_regslice_to_s00_couplers_RRESP),
        .m_axi_rvalid(s00_regslice_to_s00_couplers_RVALID),
        .m_axi_wdata(s00_regslice_to_s00_couplers_WDATA),
        .m_axi_wid(s00_regslice_to_s00_couplers_WID),
        .m_axi_wlast(s00_regslice_to_s00_couplers_WLAST),
        .m_axi_wready(s00_regslice_to_s00_couplers_WREADY),
        .m_axi_wstrb(s00_regslice_to_s00_couplers_WSTRB),
        .m_axi_wvalid(s00_regslice_to_s00_couplers_WVALID),
        .s_axi_araddr(s00_couplers_to_s00_regslice_ARADDR),
        .s_axi_arburst(s00_couplers_to_s00_regslice_ARBURST),
        .s_axi_arcache(s00_couplers_to_s00_regslice_ARCACHE),
        .s_axi_arid(s00_couplers_to_s00_regslice_ARID),
        .s_axi_arlen(s00_couplers_to_s00_regslice_ARLEN),
        .s_axi_arlock(s00_couplers_to_s00_regslice_ARLOCK),
        .s_axi_arprot(s00_couplers_to_s00_regslice_ARPROT),
        .s_axi_arqos(s00_couplers_to_s00_regslice_ARQOS),
        .s_axi_arready(s00_couplers_to_s00_regslice_ARREADY),
        .s_axi_arsize(s00_couplers_to_s00_regslice_ARSIZE),
        .s_axi_arvalid(s00_couplers_to_s00_regslice_ARVALID),
        .s_axi_awaddr(s00_couplers_to_s00_regslice_AWADDR),
        .s_axi_awburst(s00_couplers_to_s00_regslice_AWBURST),
        .s_axi_awcache(s00_couplers_to_s00_regslice_AWCACHE),
        .s_axi_awid(s00_couplers_to_s00_regslice_AWID),
        .s_axi_awlen(s00_couplers_to_s00_regslice_AWLEN),
        .s_axi_awlock(s00_couplers_to_s00_regslice_AWLOCK),
        .s_axi_awprot(s00_couplers_to_s00_regslice_AWPROT),
        .s_axi_awqos(s00_couplers_to_s00_regslice_AWQOS),
        .s_axi_awready(s00_couplers_to_s00_regslice_AWREADY),
        .s_axi_awsize(s00_couplers_to_s00_regslice_AWSIZE),
        .s_axi_awvalid(s00_couplers_to_s00_regslice_AWVALID),
        .s_axi_bid(s00_couplers_to_s00_regslice_BID),
        .s_axi_bready(s00_couplers_to_s00_regslice_BREADY),
        .s_axi_bresp(s00_couplers_to_s00_regslice_BRESP),
        .s_axi_bvalid(s00_couplers_to_s00_regslice_BVALID),
        .s_axi_rdata(s00_couplers_to_s00_regslice_RDATA),
        .s_axi_rid(s00_couplers_to_s00_regslice_RID),
        .s_axi_rlast(s00_couplers_to_s00_regslice_RLAST),
        .s_axi_rready(s00_couplers_to_s00_regslice_RREADY),
        .s_axi_rresp(s00_couplers_to_s00_regslice_RRESP),
        .s_axi_rvalid(s00_couplers_to_s00_regslice_RVALID),
        .s_axi_wdata(s00_couplers_to_s00_regslice_WDATA),
        .s_axi_wid(s00_couplers_to_s00_regslice_WID),
        .s_axi_wlast(s00_couplers_to_s00_regslice_WLAST),
        .s_axi_wready(s00_couplers_to_s00_regslice_WREADY),
        .s_axi_wstrb(s00_couplers_to_s00_regslice_WSTRB),
        .s_axi_wvalid(s00_couplers_to_s00_regslice_WVALID));
endmodule

module s00_couplers_imp_3X80A4
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [4:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [4:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output M_AXI_awvalid;
  input [5:0]M_AXI_bid;
  output M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input M_AXI_bvalid;
  input [63:0]M_AXI_rdata;
  input [5:0]M_AXI_rid;
  input M_AXI_rlast;
  output M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input M_AXI_rvalid;
  output [63:0]M_AXI_wdata;
  output [4:0]M_AXI_wid;
  output M_AXI_wlast;
  input M_AXI_wready;
  output [7:0]M_AXI_wstrb;
  output M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [4:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [4:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input S_AXI_awvalid;
  output [4:0]S_AXI_bid;
  input S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output S_AXI_bvalid;
  output [63:0]S_AXI_rdata;
  output [4:0]S_AXI_rid;
  output S_AXI_rlast;
  input S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output S_AXI_rvalid;
  input [63:0]S_AXI_wdata;
  input [4:0]S_AXI_wid;
  input S_AXI_wlast;
  output S_AXI_wready;
  input [7:0]S_AXI_wstrb;
  input S_AXI_wvalid;

  wire S_ACLK_1;
  wire S_ARESETN_1;
  wire [31:0]s00_couplers_to_s00_regslice_ARADDR;
  wire [1:0]s00_couplers_to_s00_regslice_ARBURST;
  wire [3:0]s00_couplers_to_s00_regslice_ARCACHE;
  wire [4:0]s00_couplers_to_s00_regslice_ARID;
  wire [3:0]s00_couplers_to_s00_regslice_ARLEN;
  wire [1:0]s00_couplers_to_s00_regslice_ARLOCK;
  wire [2:0]s00_couplers_to_s00_regslice_ARPROT;
  wire [3:0]s00_couplers_to_s00_regslice_ARQOS;
  wire s00_couplers_to_s00_regslice_ARREADY;
  wire [2:0]s00_couplers_to_s00_regslice_ARSIZE;
  wire s00_couplers_to_s00_regslice_ARVALID;
  wire [31:0]s00_couplers_to_s00_regslice_AWADDR;
  wire [1:0]s00_couplers_to_s00_regslice_AWBURST;
  wire [3:0]s00_couplers_to_s00_regslice_AWCACHE;
  wire [4:0]s00_couplers_to_s00_regslice_AWID;
  wire [3:0]s00_couplers_to_s00_regslice_AWLEN;
  wire [1:0]s00_couplers_to_s00_regslice_AWLOCK;
  wire [2:0]s00_couplers_to_s00_regslice_AWPROT;
  wire [3:0]s00_couplers_to_s00_regslice_AWQOS;
  wire s00_couplers_to_s00_regslice_AWREADY;
  wire [2:0]s00_couplers_to_s00_regslice_AWSIZE;
  wire s00_couplers_to_s00_regslice_AWVALID;
  wire [4:0]s00_couplers_to_s00_regslice_BID;
  wire s00_couplers_to_s00_regslice_BREADY;
  wire [1:0]s00_couplers_to_s00_regslice_BRESP;
  wire s00_couplers_to_s00_regslice_BVALID;
  wire [63:0]s00_couplers_to_s00_regslice_RDATA;
  wire [4:0]s00_couplers_to_s00_regslice_RID;
  wire s00_couplers_to_s00_regslice_RLAST;
  wire s00_couplers_to_s00_regslice_RREADY;
  wire [1:0]s00_couplers_to_s00_regslice_RRESP;
  wire s00_couplers_to_s00_regslice_RVALID;
  wire [63:0]s00_couplers_to_s00_regslice_WDATA;
  wire [4:0]s00_couplers_to_s00_regslice_WID;
  wire s00_couplers_to_s00_regslice_WLAST;
  wire s00_couplers_to_s00_regslice_WREADY;
  wire [7:0]s00_couplers_to_s00_regslice_WSTRB;
  wire s00_couplers_to_s00_regslice_WVALID;
  wire [31:0]s00_regslice_to_s00_couplers_ARADDR;
  wire [1:0]s00_regslice_to_s00_couplers_ARBURST;
  wire [3:0]s00_regslice_to_s00_couplers_ARCACHE;
  wire [4:0]s00_regslice_to_s00_couplers_ARID;
  wire [3:0]s00_regslice_to_s00_couplers_ARLEN;
  wire [1:0]s00_regslice_to_s00_couplers_ARLOCK;
  wire [2:0]s00_regslice_to_s00_couplers_ARPROT;
  wire [3:0]s00_regslice_to_s00_couplers_ARQOS;
  wire s00_regslice_to_s00_couplers_ARREADY;
  wire [2:0]s00_regslice_to_s00_couplers_ARSIZE;
  wire s00_regslice_to_s00_couplers_ARVALID;
  wire [31:0]s00_regslice_to_s00_couplers_AWADDR;
  wire [1:0]s00_regslice_to_s00_couplers_AWBURST;
  wire [3:0]s00_regslice_to_s00_couplers_AWCACHE;
  wire [4:0]s00_regslice_to_s00_couplers_AWID;
  wire [3:0]s00_regslice_to_s00_couplers_AWLEN;
  wire [1:0]s00_regslice_to_s00_couplers_AWLOCK;
  wire [2:0]s00_regslice_to_s00_couplers_AWPROT;
  wire [3:0]s00_regslice_to_s00_couplers_AWQOS;
  wire s00_regslice_to_s00_couplers_AWREADY;
  wire [2:0]s00_regslice_to_s00_couplers_AWSIZE;
  wire s00_regslice_to_s00_couplers_AWVALID;
  wire [5:0]s00_regslice_to_s00_couplers_BID;
  wire s00_regslice_to_s00_couplers_BREADY;
  wire [1:0]s00_regslice_to_s00_couplers_BRESP;
  wire s00_regslice_to_s00_couplers_BVALID;
  wire [63:0]s00_regslice_to_s00_couplers_RDATA;
  wire [5:0]s00_regslice_to_s00_couplers_RID;
  wire s00_regslice_to_s00_couplers_RLAST;
  wire s00_regslice_to_s00_couplers_RREADY;
  wire [1:0]s00_regslice_to_s00_couplers_RRESP;
  wire s00_regslice_to_s00_couplers_RVALID;
  wire [63:0]s00_regslice_to_s00_couplers_WDATA;
  wire [4:0]s00_regslice_to_s00_couplers_WID;
  wire s00_regslice_to_s00_couplers_WLAST;
  wire s00_regslice_to_s00_couplers_WREADY;
  wire [7:0]s00_regslice_to_s00_couplers_WSTRB;
  wire s00_regslice_to_s00_couplers_WVALID;

  assign M_AXI_araddr[31:0] = s00_regslice_to_s00_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = s00_regslice_to_s00_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = s00_regslice_to_s00_couplers_ARCACHE;
  assign M_AXI_arid[4:0] = s00_regslice_to_s00_couplers_ARID;
  assign M_AXI_arlen[3:0] = s00_regslice_to_s00_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = s00_regslice_to_s00_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = s00_regslice_to_s00_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = s00_regslice_to_s00_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = s00_regslice_to_s00_couplers_ARSIZE;
  assign M_AXI_arvalid = s00_regslice_to_s00_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = s00_regslice_to_s00_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = s00_regslice_to_s00_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = s00_regslice_to_s00_couplers_AWCACHE;
  assign M_AXI_awid[4:0] = s00_regslice_to_s00_couplers_AWID;
  assign M_AXI_awlen[3:0] = s00_regslice_to_s00_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = s00_regslice_to_s00_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = s00_regslice_to_s00_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = s00_regslice_to_s00_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = s00_regslice_to_s00_couplers_AWSIZE;
  assign M_AXI_awvalid = s00_regslice_to_s00_couplers_AWVALID;
  assign M_AXI_bready = s00_regslice_to_s00_couplers_BREADY;
  assign M_AXI_rready = s00_regslice_to_s00_couplers_RREADY;
  assign M_AXI_wdata[63:0] = s00_regslice_to_s00_couplers_WDATA;
  assign M_AXI_wid[4:0] = s00_regslice_to_s00_couplers_WID;
  assign M_AXI_wlast = s00_regslice_to_s00_couplers_WLAST;
  assign M_AXI_wstrb[7:0] = s00_regslice_to_s00_couplers_WSTRB;
  assign M_AXI_wvalid = s00_regslice_to_s00_couplers_WVALID;
  assign S_ACLK_1 = S_ACLK;
  assign S_ARESETN_1 = S_ARESETN;
  assign S_AXI_arready = s00_couplers_to_s00_regslice_ARREADY;
  assign S_AXI_awready = s00_couplers_to_s00_regslice_AWREADY;
  assign S_AXI_bid[4:0] = s00_couplers_to_s00_regslice_BID;
  assign S_AXI_bresp[1:0] = s00_couplers_to_s00_regslice_BRESP;
  assign S_AXI_bvalid = s00_couplers_to_s00_regslice_BVALID;
  assign S_AXI_rdata[63:0] = s00_couplers_to_s00_regslice_RDATA;
  assign S_AXI_rid[4:0] = s00_couplers_to_s00_regslice_RID;
  assign S_AXI_rlast = s00_couplers_to_s00_regslice_RLAST;
  assign S_AXI_rresp[1:0] = s00_couplers_to_s00_regslice_RRESP;
  assign S_AXI_rvalid = s00_couplers_to_s00_regslice_RVALID;
  assign S_AXI_wready = s00_couplers_to_s00_regslice_WREADY;
  assign s00_couplers_to_s00_regslice_ARADDR = S_AXI_araddr[31:0];
  assign s00_couplers_to_s00_regslice_ARBURST = S_AXI_arburst[1:0];
  assign s00_couplers_to_s00_regslice_ARCACHE = S_AXI_arcache[3:0];
  assign s00_couplers_to_s00_regslice_ARID = S_AXI_arid[4:0];
  assign s00_couplers_to_s00_regslice_ARLEN = S_AXI_arlen[3:0];
  assign s00_couplers_to_s00_regslice_ARLOCK = S_AXI_arlock[1:0];
  assign s00_couplers_to_s00_regslice_ARPROT = S_AXI_arprot[2:0];
  assign s00_couplers_to_s00_regslice_ARQOS = S_AXI_arqos[3:0];
  assign s00_couplers_to_s00_regslice_ARSIZE = S_AXI_arsize[2:0];
  assign s00_couplers_to_s00_regslice_ARVALID = S_AXI_arvalid;
  assign s00_couplers_to_s00_regslice_AWADDR = S_AXI_awaddr[31:0];
  assign s00_couplers_to_s00_regslice_AWBURST = S_AXI_awburst[1:0];
  assign s00_couplers_to_s00_regslice_AWCACHE = S_AXI_awcache[3:0];
  assign s00_couplers_to_s00_regslice_AWID = S_AXI_awid[4:0];
  assign s00_couplers_to_s00_regslice_AWLEN = S_AXI_awlen[3:0];
  assign s00_couplers_to_s00_regslice_AWLOCK = S_AXI_awlock[1:0];
  assign s00_couplers_to_s00_regslice_AWPROT = S_AXI_awprot[2:0];
  assign s00_couplers_to_s00_regslice_AWQOS = S_AXI_awqos[3:0];
  assign s00_couplers_to_s00_regslice_AWSIZE = S_AXI_awsize[2:0];
  assign s00_couplers_to_s00_regslice_AWVALID = S_AXI_awvalid;
  assign s00_couplers_to_s00_regslice_BREADY = S_AXI_bready;
  assign s00_couplers_to_s00_regslice_RREADY = S_AXI_rready;
  assign s00_couplers_to_s00_regslice_WDATA = S_AXI_wdata[63:0];
  assign s00_couplers_to_s00_regslice_WID = S_AXI_wid[4:0];
  assign s00_couplers_to_s00_regslice_WLAST = S_AXI_wlast;
  assign s00_couplers_to_s00_regslice_WSTRB = S_AXI_wstrb[7:0];
  assign s00_couplers_to_s00_regslice_WVALID = S_AXI_wvalid;
  assign s00_regslice_to_s00_couplers_ARREADY = M_AXI_arready;
  assign s00_regslice_to_s00_couplers_AWREADY = M_AXI_awready;
  assign s00_regslice_to_s00_couplers_BID = M_AXI_bid[5:0];
  assign s00_regslice_to_s00_couplers_BRESP = M_AXI_bresp[1:0];
  assign s00_regslice_to_s00_couplers_BVALID = M_AXI_bvalid;
  assign s00_regslice_to_s00_couplers_RDATA = M_AXI_rdata[63:0];
  assign s00_regslice_to_s00_couplers_RID = M_AXI_rid[5:0];
  assign s00_regslice_to_s00_couplers_RLAST = M_AXI_rlast;
  assign s00_regslice_to_s00_couplers_RRESP = M_AXI_rresp[1:0];
  assign s00_regslice_to_s00_couplers_RVALID = M_AXI_rvalid;
  assign s00_regslice_to_s00_couplers_WREADY = M_AXI_wready;
  ps_ai_s00_regslice_1 s00_regslice
       (.aclk(S_ACLK_1),
        .aresetn(S_ARESETN_1),
        .m_axi_araddr(s00_regslice_to_s00_couplers_ARADDR),
        .m_axi_arburst(s00_regslice_to_s00_couplers_ARBURST),
        .m_axi_arcache(s00_regslice_to_s00_couplers_ARCACHE),
        .m_axi_arid(s00_regslice_to_s00_couplers_ARID),
        .m_axi_arlen(s00_regslice_to_s00_couplers_ARLEN),
        .m_axi_arlock(s00_regslice_to_s00_couplers_ARLOCK),
        .m_axi_arprot(s00_regslice_to_s00_couplers_ARPROT),
        .m_axi_arqos(s00_regslice_to_s00_couplers_ARQOS),
        .m_axi_arready(s00_regslice_to_s00_couplers_ARREADY),
        .m_axi_arsize(s00_regslice_to_s00_couplers_ARSIZE),
        .m_axi_arvalid(s00_regslice_to_s00_couplers_ARVALID),
        .m_axi_awaddr(s00_regslice_to_s00_couplers_AWADDR),
        .m_axi_awburst(s00_regslice_to_s00_couplers_AWBURST),
        .m_axi_awcache(s00_regslice_to_s00_couplers_AWCACHE),
        .m_axi_awid(s00_regslice_to_s00_couplers_AWID),
        .m_axi_awlen(s00_regslice_to_s00_couplers_AWLEN),
        .m_axi_awlock(s00_regslice_to_s00_couplers_AWLOCK),
        .m_axi_awprot(s00_regslice_to_s00_couplers_AWPROT),
        .m_axi_awqos(s00_regslice_to_s00_couplers_AWQOS),
        .m_axi_awready(s00_regslice_to_s00_couplers_AWREADY),
        .m_axi_awsize(s00_regslice_to_s00_couplers_AWSIZE),
        .m_axi_awvalid(s00_regslice_to_s00_couplers_AWVALID),
        .m_axi_bid(s00_regslice_to_s00_couplers_BID[4:0]),
        .m_axi_bready(s00_regslice_to_s00_couplers_BREADY),
        .m_axi_bresp(s00_regslice_to_s00_couplers_BRESP),
        .m_axi_bvalid(s00_regslice_to_s00_couplers_BVALID),
        .m_axi_rdata(s00_regslice_to_s00_couplers_RDATA),
        .m_axi_rid(s00_regslice_to_s00_couplers_RID[4:0]),
        .m_axi_rlast(s00_regslice_to_s00_couplers_RLAST),
        .m_axi_rready(s00_regslice_to_s00_couplers_RREADY),
        .m_axi_rresp(s00_regslice_to_s00_couplers_RRESP),
        .m_axi_rvalid(s00_regslice_to_s00_couplers_RVALID),
        .m_axi_wdata(s00_regslice_to_s00_couplers_WDATA),
        .m_axi_wid(s00_regslice_to_s00_couplers_WID),
        .m_axi_wlast(s00_regslice_to_s00_couplers_WLAST),
        .m_axi_wready(s00_regslice_to_s00_couplers_WREADY),
        .m_axi_wstrb(s00_regslice_to_s00_couplers_WSTRB),
        .m_axi_wvalid(s00_regslice_to_s00_couplers_WVALID),
        .s_axi_araddr(s00_couplers_to_s00_regslice_ARADDR),
        .s_axi_arburst(s00_couplers_to_s00_regslice_ARBURST),
        .s_axi_arcache(s00_couplers_to_s00_regslice_ARCACHE),
        .s_axi_arid(s00_couplers_to_s00_regslice_ARID),
        .s_axi_arlen(s00_couplers_to_s00_regslice_ARLEN),
        .s_axi_arlock(s00_couplers_to_s00_regslice_ARLOCK),
        .s_axi_arprot(s00_couplers_to_s00_regslice_ARPROT),
        .s_axi_arqos(s00_couplers_to_s00_regslice_ARQOS),
        .s_axi_arready(s00_couplers_to_s00_regslice_ARREADY),
        .s_axi_arsize(s00_couplers_to_s00_regslice_ARSIZE),
        .s_axi_arvalid(s00_couplers_to_s00_regslice_ARVALID),
        .s_axi_awaddr(s00_couplers_to_s00_regslice_AWADDR),
        .s_axi_awburst(s00_couplers_to_s00_regslice_AWBURST),
        .s_axi_awcache(s00_couplers_to_s00_regslice_AWCACHE),
        .s_axi_awid(s00_couplers_to_s00_regslice_AWID),
        .s_axi_awlen(s00_couplers_to_s00_regslice_AWLEN),
        .s_axi_awlock(s00_couplers_to_s00_regslice_AWLOCK),
        .s_axi_awprot(s00_couplers_to_s00_regslice_AWPROT),
        .s_axi_awqos(s00_couplers_to_s00_regslice_AWQOS),
        .s_axi_awready(s00_couplers_to_s00_regslice_AWREADY),
        .s_axi_awsize(s00_couplers_to_s00_regslice_AWSIZE),
        .s_axi_awvalid(s00_couplers_to_s00_regslice_AWVALID),
        .s_axi_bid(s00_couplers_to_s00_regslice_BID),
        .s_axi_bready(s00_couplers_to_s00_regslice_BREADY),
        .s_axi_bresp(s00_couplers_to_s00_regslice_BRESP),
        .s_axi_bvalid(s00_couplers_to_s00_regslice_BVALID),
        .s_axi_rdata(s00_couplers_to_s00_regslice_RDATA),
        .s_axi_rid(s00_couplers_to_s00_regslice_RID),
        .s_axi_rlast(s00_couplers_to_s00_regslice_RLAST),
        .s_axi_rready(s00_couplers_to_s00_regslice_RREADY),
        .s_axi_rresp(s00_couplers_to_s00_regslice_RRESP),
        .s_axi_rvalid(s00_couplers_to_s00_regslice_RVALID),
        .s_axi_wdata(s00_couplers_to_s00_regslice_WDATA),
        .s_axi_wid(s00_couplers_to_s00_regslice_WID),
        .s_axi_wlast(s00_couplers_to_s00_regslice_WLAST),
        .s_axi_wready(s00_couplers_to_s00_regslice_WREADY),
        .s_axi_wstrb(s00_couplers_to_s00_regslice_WSTRB),
        .s_axi_wvalid(s00_couplers_to_s00_regslice_WVALID));
endmodule

module s00_couplers_imp_DI37BQ
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [11:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [11:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output M_AXI_awvalid;
  input [11:0]M_AXI_bid;
  output M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input M_AXI_bvalid;
  input [31:0]M_AXI_rdata;
  input [11:0]M_AXI_rid;
  input M_AXI_rlast;
  output M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input M_AXI_rvalid;
  output [31:0]M_AXI_wdata;
  output [11:0]M_AXI_wid;
  output M_AXI_wlast;
  input M_AXI_wready;
  output [3:0]M_AXI_wstrb;
  output M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [11:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [11:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input S_AXI_awvalid;
  output [11:0]S_AXI_bid;
  input S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output S_AXI_bvalid;
  output [31:0]S_AXI_rdata;
  output [11:0]S_AXI_rid;
  output S_AXI_rlast;
  input S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output S_AXI_rvalid;
  input [31:0]S_AXI_wdata;
  input [11:0]S_AXI_wid;
  input S_AXI_wlast;
  output S_AXI_wready;
  input [3:0]S_AXI_wstrb;
  input S_AXI_wvalid;

  wire [31:0]s00_couplers_to_s00_couplers_ARADDR;
  wire [1:0]s00_couplers_to_s00_couplers_ARBURST;
  wire [3:0]s00_couplers_to_s00_couplers_ARCACHE;
  wire [11:0]s00_couplers_to_s00_couplers_ARID;
  wire [3:0]s00_couplers_to_s00_couplers_ARLEN;
  wire [1:0]s00_couplers_to_s00_couplers_ARLOCK;
  wire [2:0]s00_couplers_to_s00_couplers_ARPROT;
  wire [3:0]s00_couplers_to_s00_couplers_ARQOS;
  wire s00_couplers_to_s00_couplers_ARREADY;
  wire [2:0]s00_couplers_to_s00_couplers_ARSIZE;
  wire s00_couplers_to_s00_couplers_ARVALID;
  wire [31:0]s00_couplers_to_s00_couplers_AWADDR;
  wire [1:0]s00_couplers_to_s00_couplers_AWBURST;
  wire [3:0]s00_couplers_to_s00_couplers_AWCACHE;
  wire [11:0]s00_couplers_to_s00_couplers_AWID;
  wire [3:0]s00_couplers_to_s00_couplers_AWLEN;
  wire [1:0]s00_couplers_to_s00_couplers_AWLOCK;
  wire [2:0]s00_couplers_to_s00_couplers_AWPROT;
  wire [3:0]s00_couplers_to_s00_couplers_AWQOS;
  wire s00_couplers_to_s00_couplers_AWREADY;
  wire [2:0]s00_couplers_to_s00_couplers_AWSIZE;
  wire s00_couplers_to_s00_couplers_AWVALID;
  wire [11:0]s00_couplers_to_s00_couplers_BID;
  wire s00_couplers_to_s00_couplers_BREADY;
  wire [1:0]s00_couplers_to_s00_couplers_BRESP;
  wire s00_couplers_to_s00_couplers_BVALID;
  wire [31:0]s00_couplers_to_s00_couplers_RDATA;
  wire [11:0]s00_couplers_to_s00_couplers_RID;
  wire s00_couplers_to_s00_couplers_RLAST;
  wire s00_couplers_to_s00_couplers_RREADY;
  wire [1:0]s00_couplers_to_s00_couplers_RRESP;
  wire s00_couplers_to_s00_couplers_RVALID;
  wire [31:0]s00_couplers_to_s00_couplers_WDATA;
  wire [11:0]s00_couplers_to_s00_couplers_WID;
  wire s00_couplers_to_s00_couplers_WLAST;
  wire s00_couplers_to_s00_couplers_WREADY;
  wire [3:0]s00_couplers_to_s00_couplers_WSTRB;
  wire s00_couplers_to_s00_couplers_WVALID;

  assign M_AXI_araddr[31:0] = s00_couplers_to_s00_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = s00_couplers_to_s00_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = s00_couplers_to_s00_couplers_ARCACHE;
  assign M_AXI_arid[11:0] = s00_couplers_to_s00_couplers_ARID;
  assign M_AXI_arlen[3:0] = s00_couplers_to_s00_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = s00_couplers_to_s00_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = s00_couplers_to_s00_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = s00_couplers_to_s00_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = s00_couplers_to_s00_couplers_ARSIZE;
  assign M_AXI_arvalid = s00_couplers_to_s00_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = s00_couplers_to_s00_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = s00_couplers_to_s00_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = s00_couplers_to_s00_couplers_AWCACHE;
  assign M_AXI_awid[11:0] = s00_couplers_to_s00_couplers_AWID;
  assign M_AXI_awlen[3:0] = s00_couplers_to_s00_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = s00_couplers_to_s00_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = s00_couplers_to_s00_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = s00_couplers_to_s00_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = s00_couplers_to_s00_couplers_AWSIZE;
  assign M_AXI_awvalid = s00_couplers_to_s00_couplers_AWVALID;
  assign M_AXI_bready = s00_couplers_to_s00_couplers_BREADY;
  assign M_AXI_rready = s00_couplers_to_s00_couplers_RREADY;
  assign M_AXI_wdata[31:0] = s00_couplers_to_s00_couplers_WDATA;
  assign M_AXI_wid[11:0] = s00_couplers_to_s00_couplers_WID;
  assign M_AXI_wlast = s00_couplers_to_s00_couplers_WLAST;
  assign M_AXI_wstrb[3:0] = s00_couplers_to_s00_couplers_WSTRB;
  assign M_AXI_wvalid = s00_couplers_to_s00_couplers_WVALID;
  assign S_AXI_arready = s00_couplers_to_s00_couplers_ARREADY;
  assign S_AXI_awready = s00_couplers_to_s00_couplers_AWREADY;
  assign S_AXI_bid[11:0] = s00_couplers_to_s00_couplers_BID;
  assign S_AXI_bresp[1:0] = s00_couplers_to_s00_couplers_BRESP;
  assign S_AXI_bvalid = s00_couplers_to_s00_couplers_BVALID;
  assign S_AXI_rdata[31:0] = s00_couplers_to_s00_couplers_RDATA;
  assign S_AXI_rid[11:0] = s00_couplers_to_s00_couplers_RID;
  assign S_AXI_rlast = s00_couplers_to_s00_couplers_RLAST;
  assign S_AXI_rresp[1:0] = s00_couplers_to_s00_couplers_RRESP;
  assign S_AXI_rvalid = s00_couplers_to_s00_couplers_RVALID;
  assign S_AXI_wready = s00_couplers_to_s00_couplers_WREADY;
  assign s00_couplers_to_s00_couplers_ARADDR = S_AXI_araddr[31:0];
  assign s00_couplers_to_s00_couplers_ARBURST = S_AXI_arburst[1:0];
  assign s00_couplers_to_s00_couplers_ARCACHE = S_AXI_arcache[3:0];
  assign s00_couplers_to_s00_couplers_ARID = S_AXI_arid[11:0];
  assign s00_couplers_to_s00_couplers_ARLEN = S_AXI_arlen[3:0];
  assign s00_couplers_to_s00_couplers_ARLOCK = S_AXI_arlock[1:0];
  assign s00_couplers_to_s00_couplers_ARPROT = S_AXI_arprot[2:0];
  assign s00_couplers_to_s00_couplers_ARQOS = S_AXI_arqos[3:0];
  assign s00_couplers_to_s00_couplers_ARREADY = M_AXI_arready;
  assign s00_couplers_to_s00_couplers_ARSIZE = S_AXI_arsize[2:0];
  assign s00_couplers_to_s00_couplers_ARVALID = S_AXI_arvalid;
  assign s00_couplers_to_s00_couplers_AWADDR = S_AXI_awaddr[31:0];
  assign s00_couplers_to_s00_couplers_AWBURST = S_AXI_awburst[1:0];
  assign s00_couplers_to_s00_couplers_AWCACHE = S_AXI_awcache[3:0];
  assign s00_couplers_to_s00_couplers_AWID = S_AXI_awid[11:0];
  assign s00_couplers_to_s00_couplers_AWLEN = S_AXI_awlen[3:0];
  assign s00_couplers_to_s00_couplers_AWLOCK = S_AXI_awlock[1:0];
  assign s00_couplers_to_s00_couplers_AWPROT = S_AXI_awprot[2:0];
  assign s00_couplers_to_s00_couplers_AWQOS = S_AXI_awqos[3:0];
  assign s00_couplers_to_s00_couplers_AWREADY = M_AXI_awready;
  assign s00_couplers_to_s00_couplers_AWSIZE = S_AXI_awsize[2:0];
  assign s00_couplers_to_s00_couplers_AWVALID = S_AXI_awvalid;
  assign s00_couplers_to_s00_couplers_BID = M_AXI_bid[11:0];
  assign s00_couplers_to_s00_couplers_BREADY = S_AXI_bready;
  assign s00_couplers_to_s00_couplers_BRESP = M_AXI_bresp[1:0];
  assign s00_couplers_to_s00_couplers_BVALID = M_AXI_bvalid;
  assign s00_couplers_to_s00_couplers_RDATA = M_AXI_rdata[31:0];
  assign s00_couplers_to_s00_couplers_RID = M_AXI_rid[11:0];
  assign s00_couplers_to_s00_couplers_RLAST = M_AXI_rlast;
  assign s00_couplers_to_s00_couplers_RREADY = S_AXI_rready;
  assign s00_couplers_to_s00_couplers_RRESP = M_AXI_rresp[1:0];
  assign s00_couplers_to_s00_couplers_RVALID = M_AXI_rvalid;
  assign s00_couplers_to_s00_couplers_WDATA = S_AXI_wdata[31:0];
  assign s00_couplers_to_s00_couplers_WID = S_AXI_wid[11:0];
  assign s00_couplers_to_s00_couplers_WLAST = S_AXI_wlast;
  assign s00_couplers_to_s00_couplers_WREADY = M_AXI_wready;
  assign s00_couplers_to_s00_couplers_WSTRB = S_AXI_wstrb[3:0];
  assign s00_couplers_to_s00_couplers_WVALID = S_AXI_wvalid;
endmodule

module s01_couplers_imp_1F0E4QS
   (M_ACLK,
    M_ARESETN,
    M_AXI_araddr,
    M_AXI_arburst,
    M_AXI_arcache,
    M_AXI_arid,
    M_AXI_arlen,
    M_AXI_arlock,
    M_AXI_arprot,
    M_AXI_arqos,
    M_AXI_arready,
    M_AXI_arsize,
    M_AXI_arvalid,
    M_AXI_awaddr,
    M_AXI_awburst,
    M_AXI_awcache,
    M_AXI_awid,
    M_AXI_awlen,
    M_AXI_awlock,
    M_AXI_awprot,
    M_AXI_awqos,
    M_AXI_awready,
    M_AXI_awsize,
    M_AXI_awvalid,
    M_AXI_bid,
    M_AXI_bready,
    M_AXI_bresp,
    M_AXI_bvalid,
    M_AXI_rdata,
    M_AXI_rid,
    M_AXI_rlast,
    M_AXI_rready,
    M_AXI_rresp,
    M_AXI_rvalid,
    M_AXI_wdata,
    M_AXI_wid,
    M_AXI_wlast,
    M_AXI_wready,
    M_AXI_wstrb,
    M_AXI_wvalid,
    S_ACLK,
    S_ARESETN,
    S_AXI_araddr,
    S_AXI_arburst,
    S_AXI_arcache,
    S_AXI_arid,
    S_AXI_arlen,
    S_AXI_arlock,
    S_AXI_arprot,
    S_AXI_arqos,
    S_AXI_arready,
    S_AXI_arsize,
    S_AXI_arvalid,
    S_AXI_awaddr,
    S_AXI_awburst,
    S_AXI_awcache,
    S_AXI_awid,
    S_AXI_awlen,
    S_AXI_awlock,
    S_AXI_awprot,
    S_AXI_awqos,
    S_AXI_awready,
    S_AXI_awsize,
    S_AXI_awvalid,
    S_AXI_bid,
    S_AXI_bready,
    S_AXI_bresp,
    S_AXI_bvalid,
    S_AXI_rdata,
    S_AXI_rid,
    S_AXI_rlast,
    S_AXI_rready,
    S_AXI_rresp,
    S_AXI_rvalid,
    S_AXI_wdata,
    S_AXI_wid,
    S_AXI_wlast,
    S_AXI_wready,
    S_AXI_wstrb,
    S_AXI_wvalid);
  input M_ACLK;
  input M_ARESETN;
  output [31:0]M_AXI_araddr;
  output [1:0]M_AXI_arburst;
  output [3:0]M_AXI_arcache;
  output [4:0]M_AXI_arid;
  output [3:0]M_AXI_arlen;
  output [1:0]M_AXI_arlock;
  output [2:0]M_AXI_arprot;
  output [3:0]M_AXI_arqos;
  input M_AXI_arready;
  output [2:0]M_AXI_arsize;
  output M_AXI_arvalid;
  output [31:0]M_AXI_awaddr;
  output [1:0]M_AXI_awburst;
  output [3:0]M_AXI_awcache;
  output [4:0]M_AXI_awid;
  output [3:0]M_AXI_awlen;
  output [1:0]M_AXI_awlock;
  output [2:0]M_AXI_awprot;
  output [3:0]M_AXI_awqos;
  input M_AXI_awready;
  output [2:0]M_AXI_awsize;
  output M_AXI_awvalid;
  input [5:0]M_AXI_bid;
  output M_AXI_bready;
  input [1:0]M_AXI_bresp;
  input M_AXI_bvalid;
  input [63:0]M_AXI_rdata;
  input [5:0]M_AXI_rid;
  input M_AXI_rlast;
  output M_AXI_rready;
  input [1:0]M_AXI_rresp;
  input M_AXI_rvalid;
  output [63:0]M_AXI_wdata;
  output [4:0]M_AXI_wid;
  output M_AXI_wlast;
  input M_AXI_wready;
  output [7:0]M_AXI_wstrb;
  output M_AXI_wvalid;
  input S_ACLK;
  input S_ARESETN;
  input [31:0]S_AXI_araddr;
  input [1:0]S_AXI_arburst;
  input [3:0]S_AXI_arcache;
  input [4:0]S_AXI_arid;
  input [3:0]S_AXI_arlen;
  input [1:0]S_AXI_arlock;
  input [2:0]S_AXI_arprot;
  input [3:0]S_AXI_arqos;
  output S_AXI_arready;
  input [2:0]S_AXI_arsize;
  input S_AXI_arvalid;
  input [31:0]S_AXI_awaddr;
  input [1:0]S_AXI_awburst;
  input [3:0]S_AXI_awcache;
  input [4:0]S_AXI_awid;
  input [3:0]S_AXI_awlen;
  input [1:0]S_AXI_awlock;
  input [2:0]S_AXI_awprot;
  input [3:0]S_AXI_awqos;
  output S_AXI_awready;
  input [2:0]S_AXI_awsize;
  input S_AXI_awvalid;
  output [4:0]S_AXI_bid;
  input S_AXI_bready;
  output [1:0]S_AXI_bresp;
  output S_AXI_bvalid;
  output [63:0]S_AXI_rdata;
  output [4:0]S_AXI_rid;
  output S_AXI_rlast;
  input S_AXI_rready;
  output [1:0]S_AXI_rresp;
  output S_AXI_rvalid;
  input [63:0]S_AXI_wdata;
  input [4:0]S_AXI_wid;
  input S_AXI_wlast;
  output S_AXI_wready;
  input [7:0]S_AXI_wstrb;
  input S_AXI_wvalid;

  wire S_ACLK_1;
  wire S_ARESETN_1;
  wire [31:0]s01_couplers_to_s01_regslice_ARADDR;
  wire [1:0]s01_couplers_to_s01_regslice_ARBURST;
  wire [3:0]s01_couplers_to_s01_regslice_ARCACHE;
  wire [4:0]s01_couplers_to_s01_regslice_ARID;
  wire [3:0]s01_couplers_to_s01_regslice_ARLEN;
  wire [1:0]s01_couplers_to_s01_regslice_ARLOCK;
  wire [2:0]s01_couplers_to_s01_regslice_ARPROT;
  wire [3:0]s01_couplers_to_s01_regslice_ARQOS;
  wire s01_couplers_to_s01_regslice_ARREADY;
  wire [2:0]s01_couplers_to_s01_regslice_ARSIZE;
  wire s01_couplers_to_s01_regslice_ARVALID;
  wire [31:0]s01_couplers_to_s01_regslice_AWADDR;
  wire [1:0]s01_couplers_to_s01_regslice_AWBURST;
  wire [3:0]s01_couplers_to_s01_regslice_AWCACHE;
  wire [4:0]s01_couplers_to_s01_regslice_AWID;
  wire [3:0]s01_couplers_to_s01_regslice_AWLEN;
  wire [1:0]s01_couplers_to_s01_regslice_AWLOCK;
  wire [2:0]s01_couplers_to_s01_regslice_AWPROT;
  wire [3:0]s01_couplers_to_s01_regslice_AWQOS;
  wire s01_couplers_to_s01_regslice_AWREADY;
  wire [2:0]s01_couplers_to_s01_regslice_AWSIZE;
  wire s01_couplers_to_s01_regslice_AWVALID;
  wire [4:0]s01_couplers_to_s01_regslice_BID;
  wire s01_couplers_to_s01_regslice_BREADY;
  wire [1:0]s01_couplers_to_s01_regslice_BRESP;
  wire s01_couplers_to_s01_regslice_BVALID;
  wire [63:0]s01_couplers_to_s01_regslice_RDATA;
  wire [4:0]s01_couplers_to_s01_regslice_RID;
  wire s01_couplers_to_s01_regslice_RLAST;
  wire s01_couplers_to_s01_regslice_RREADY;
  wire [1:0]s01_couplers_to_s01_regslice_RRESP;
  wire s01_couplers_to_s01_regslice_RVALID;
  wire [63:0]s01_couplers_to_s01_regslice_WDATA;
  wire [4:0]s01_couplers_to_s01_regslice_WID;
  wire s01_couplers_to_s01_regslice_WLAST;
  wire s01_couplers_to_s01_regslice_WREADY;
  wire [7:0]s01_couplers_to_s01_regslice_WSTRB;
  wire s01_couplers_to_s01_regslice_WVALID;
  wire [31:0]s01_regslice_to_s01_couplers_ARADDR;
  wire [1:0]s01_regslice_to_s01_couplers_ARBURST;
  wire [3:0]s01_regslice_to_s01_couplers_ARCACHE;
  wire [4:0]s01_regslice_to_s01_couplers_ARID;
  wire [3:0]s01_regslice_to_s01_couplers_ARLEN;
  wire [1:0]s01_regslice_to_s01_couplers_ARLOCK;
  wire [2:0]s01_regslice_to_s01_couplers_ARPROT;
  wire [3:0]s01_regslice_to_s01_couplers_ARQOS;
  wire s01_regslice_to_s01_couplers_ARREADY;
  wire [2:0]s01_regslice_to_s01_couplers_ARSIZE;
  wire s01_regslice_to_s01_couplers_ARVALID;
  wire [31:0]s01_regslice_to_s01_couplers_AWADDR;
  wire [1:0]s01_regslice_to_s01_couplers_AWBURST;
  wire [3:0]s01_regslice_to_s01_couplers_AWCACHE;
  wire [4:0]s01_regslice_to_s01_couplers_AWID;
  wire [3:0]s01_regslice_to_s01_couplers_AWLEN;
  wire [1:0]s01_regslice_to_s01_couplers_AWLOCK;
  wire [2:0]s01_regslice_to_s01_couplers_AWPROT;
  wire [3:0]s01_regslice_to_s01_couplers_AWQOS;
  wire s01_regslice_to_s01_couplers_AWREADY;
  wire [2:0]s01_regslice_to_s01_couplers_AWSIZE;
  wire s01_regslice_to_s01_couplers_AWVALID;
  wire [5:0]s01_regslice_to_s01_couplers_BID;
  wire s01_regslice_to_s01_couplers_BREADY;
  wire [1:0]s01_regslice_to_s01_couplers_BRESP;
  wire s01_regslice_to_s01_couplers_BVALID;
  wire [63:0]s01_regslice_to_s01_couplers_RDATA;
  wire [5:0]s01_regslice_to_s01_couplers_RID;
  wire s01_regslice_to_s01_couplers_RLAST;
  wire s01_regslice_to_s01_couplers_RREADY;
  wire [1:0]s01_regslice_to_s01_couplers_RRESP;
  wire s01_regslice_to_s01_couplers_RVALID;
  wire [63:0]s01_regslice_to_s01_couplers_WDATA;
  wire [4:0]s01_regslice_to_s01_couplers_WID;
  wire s01_regslice_to_s01_couplers_WLAST;
  wire s01_regslice_to_s01_couplers_WREADY;
  wire [7:0]s01_regslice_to_s01_couplers_WSTRB;
  wire s01_regslice_to_s01_couplers_WVALID;

  assign M_AXI_araddr[31:0] = s01_regslice_to_s01_couplers_ARADDR;
  assign M_AXI_arburst[1:0] = s01_regslice_to_s01_couplers_ARBURST;
  assign M_AXI_arcache[3:0] = s01_regslice_to_s01_couplers_ARCACHE;
  assign M_AXI_arid[4:0] = s01_regslice_to_s01_couplers_ARID;
  assign M_AXI_arlen[3:0] = s01_regslice_to_s01_couplers_ARLEN;
  assign M_AXI_arlock[1:0] = s01_regslice_to_s01_couplers_ARLOCK;
  assign M_AXI_arprot[2:0] = s01_regslice_to_s01_couplers_ARPROT;
  assign M_AXI_arqos[3:0] = s01_regslice_to_s01_couplers_ARQOS;
  assign M_AXI_arsize[2:0] = s01_regslice_to_s01_couplers_ARSIZE;
  assign M_AXI_arvalid = s01_regslice_to_s01_couplers_ARVALID;
  assign M_AXI_awaddr[31:0] = s01_regslice_to_s01_couplers_AWADDR;
  assign M_AXI_awburst[1:0] = s01_regslice_to_s01_couplers_AWBURST;
  assign M_AXI_awcache[3:0] = s01_regslice_to_s01_couplers_AWCACHE;
  assign M_AXI_awid[4:0] = s01_regslice_to_s01_couplers_AWID;
  assign M_AXI_awlen[3:0] = s01_regslice_to_s01_couplers_AWLEN;
  assign M_AXI_awlock[1:0] = s01_regslice_to_s01_couplers_AWLOCK;
  assign M_AXI_awprot[2:0] = s01_regslice_to_s01_couplers_AWPROT;
  assign M_AXI_awqos[3:0] = s01_regslice_to_s01_couplers_AWQOS;
  assign M_AXI_awsize[2:0] = s01_regslice_to_s01_couplers_AWSIZE;
  assign M_AXI_awvalid = s01_regslice_to_s01_couplers_AWVALID;
  assign M_AXI_bready = s01_regslice_to_s01_couplers_BREADY;
  assign M_AXI_rready = s01_regslice_to_s01_couplers_RREADY;
  assign M_AXI_wdata[63:0] = s01_regslice_to_s01_couplers_WDATA;
  assign M_AXI_wid[4:0] = s01_regslice_to_s01_couplers_WID;
  assign M_AXI_wlast = s01_regslice_to_s01_couplers_WLAST;
  assign M_AXI_wstrb[7:0] = s01_regslice_to_s01_couplers_WSTRB;
  assign M_AXI_wvalid = s01_regslice_to_s01_couplers_WVALID;
  assign S_ACLK_1 = S_ACLK;
  assign S_ARESETN_1 = S_ARESETN;
  assign S_AXI_arready = s01_couplers_to_s01_regslice_ARREADY;
  assign S_AXI_awready = s01_couplers_to_s01_regslice_AWREADY;
  assign S_AXI_bid[4:0] = s01_couplers_to_s01_regslice_BID;
  assign S_AXI_bresp[1:0] = s01_couplers_to_s01_regslice_BRESP;
  assign S_AXI_bvalid = s01_couplers_to_s01_regslice_BVALID;
  assign S_AXI_rdata[63:0] = s01_couplers_to_s01_regslice_RDATA;
  assign S_AXI_rid[4:0] = s01_couplers_to_s01_regslice_RID;
  assign S_AXI_rlast = s01_couplers_to_s01_regslice_RLAST;
  assign S_AXI_rresp[1:0] = s01_couplers_to_s01_regslice_RRESP;
  assign S_AXI_rvalid = s01_couplers_to_s01_regslice_RVALID;
  assign S_AXI_wready = s01_couplers_to_s01_regslice_WREADY;
  assign s01_couplers_to_s01_regslice_ARADDR = S_AXI_araddr[31:0];
  assign s01_couplers_to_s01_regslice_ARBURST = S_AXI_arburst[1:0];
  assign s01_couplers_to_s01_regslice_ARCACHE = S_AXI_arcache[3:0];
  assign s01_couplers_to_s01_regslice_ARID = S_AXI_arid[4:0];
  assign s01_couplers_to_s01_regslice_ARLEN = S_AXI_arlen[3:0];
  assign s01_couplers_to_s01_regslice_ARLOCK = S_AXI_arlock[1:0];
  assign s01_couplers_to_s01_regslice_ARPROT = S_AXI_arprot[2:0];
  assign s01_couplers_to_s01_regslice_ARQOS = S_AXI_arqos[3:0];
  assign s01_couplers_to_s01_regslice_ARSIZE = S_AXI_arsize[2:0];
  assign s01_couplers_to_s01_regslice_ARVALID = S_AXI_arvalid;
  assign s01_couplers_to_s01_regslice_AWADDR = S_AXI_awaddr[31:0];
  assign s01_couplers_to_s01_regslice_AWBURST = S_AXI_awburst[1:0];
  assign s01_couplers_to_s01_regslice_AWCACHE = S_AXI_awcache[3:0];
  assign s01_couplers_to_s01_regslice_AWID = S_AXI_awid[4:0];
  assign s01_couplers_to_s01_regslice_AWLEN = S_AXI_awlen[3:0];
  assign s01_couplers_to_s01_regslice_AWLOCK = S_AXI_awlock[1:0];
  assign s01_couplers_to_s01_regslice_AWPROT = S_AXI_awprot[2:0];
  assign s01_couplers_to_s01_regslice_AWQOS = S_AXI_awqos[3:0];
  assign s01_couplers_to_s01_regslice_AWSIZE = S_AXI_awsize[2:0];
  assign s01_couplers_to_s01_regslice_AWVALID = S_AXI_awvalid;
  assign s01_couplers_to_s01_regslice_BREADY = S_AXI_bready;
  assign s01_couplers_to_s01_regslice_RREADY = S_AXI_rready;
  assign s01_couplers_to_s01_regslice_WDATA = S_AXI_wdata[63:0];
  assign s01_couplers_to_s01_regslice_WID = S_AXI_wid[4:0];
  assign s01_couplers_to_s01_regslice_WLAST = S_AXI_wlast;
  assign s01_couplers_to_s01_regslice_WSTRB = S_AXI_wstrb[7:0];
  assign s01_couplers_to_s01_regslice_WVALID = S_AXI_wvalid;
  assign s01_regslice_to_s01_couplers_ARREADY = M_AXI_arready;
  assign s01_regslice_to_s01_couplers_AWREADY = M_AXI_awready;
  assign s01_regslice_to_s01_couplers_BID = M_AXI_bid[5:0];
  assign s01_regslice_to_s01_couplers_BRESP = M_AXI_bresp[1:0];
  assign s01_regslice_to_s01_couplers_BVALID = M_AXI_bvalid;
  assign s01_regslice_to_s01_couplers_RDATA = M_AXI_rdata[63:0];
  assign s01_regslice_to_s01_couplers_RID = M_AXI_rid[5:0];
  assign s01_regslice_to_s01_couplers_RLAST = M_AXI_rlast;
  assign s01_regslice_to_s01_couplers_RRESP = M_AXI_rresp[1:0];
  assign s01_regslice_to_s01_couplers_RVALID = M_AXI_rvalid;
  assign s01_regslice_to_s01_couplers_WREADY = M_AXI_wready;
  ps_ai_s01_regslice_0 s01_regslice
       (.aclk(S_ACLK_1),
        .aresetn(S_ARESETN_1),
        .m_axi_araddr(s01_regslice_to_s01_couplers_ARADDR),
        .m_axi_arburst(s01_regslice_to_s01_couplers_ARBURST),
        .m_axi_arcache(s01_regslice_to_s01_couplers_ARCACHE),
        .m_axi_arid(s01_regslice_to_s01_couplers_ARID),
        .m_axi_arlen(s01_regslice_to_s01_couplers_ARLEN),
        .m_axi_arlock(s01_regslice_to_s01_couplers_ARLOCK),
        .m_axi_arprot(s01_regslice_to_s01_couplers_ARPROT),
        .m_axi_arqos(s01_regslice_to_s01_couplers_ARQOS),
        .m_axi_arready(s01_regslice_to_s01_couplers_ARREADY),
        .m_axi_arsize(s01_regslice_to_s01_couplers_ARSIZE),
        .m_axi_arvalid(s01_regslice_to_s01_couplers_ARVALID),
        .m_axi_awaddr(s01_regslice_to_s01_couplers_AWADDR),
        .m_axi_awburst(s01_regslice_to_s01_couplers_AWBURST),
        .m_axi_awcache(s01_regslice_to_s01_couplers_AWCACHE),
        .m_axi_awid(s01_regslice_to_s01_couplers_AWID),
        .m_axi_awlen(s01_regslice_to_s01_couplers_AWLEN),
        .m_axi_awlock(s01_regslice_to_s01_couplers_AWLOCK),
        .m_axi_awprot(s01_regslice_to_s01_couplers_AWPROT),
        .m_axi_awqos(s01_regslice_to_s01_couplers_AWQOS),
        .m_axi_awready(s01_regslice_to_s01_couplers_AWREADY),
        .m_axi_awsize(s01_regslice_to_s01_couplers_AWSIZE),
        .m_axi_awvalid(s01_regslice_to_s01_couplers_AWVALID),
        .m_axi_bid(s01_regslice_to_s01_couplers_BID[4:0]),
        .m_axi_bready(s01_regslice_to_s01_couplers_BREADY),
        .m_axi_bresp(s01_regslice_to_s01_couplers_BRESP),
        .m_axi_bvalid(s01_regslice_to_s01_couplers_BVALID),
        .m_axi_rdata(s01_regslice_to_s01_couplers_RDATA),
        .m_axi_rid(s01_regslice_to_s01_couplers_RID[4:0]),
        .m_axi_rlast(s01_regslice_to_s01_couplers_RLAST),
        .m_axi_rready(s01_regslice_to_s01_couplers_RREADY),
        .m_axi_rresp(s01_regslice_to_s01_couplers_RRESP),
        .m_axi_rvalid(s01_regslice_to_s01_couplers_RVALID),
        .m_axi_wdata(s01_regslice_to_s01_couplers_WDATA),
        .m_axi_wid(s01_regslice_to_s01_couplers_WID),
        .m_axi_wlast(s01_regslice_to_s01_couplers_WLAST),
        .m_axi_wready(s01_regslice_to_s01_couplers_WREADY),
        .m_axi_wstrb(s01_regslice_to_s01_couplers_WSTRB),
        .m_axi_wvalid(s01_regslice_to_s01_couplers_WVALID),
        .s_axi_araddr(s01_couplers_to_s01_regslice_ARADDR),
        .s_axi_arburst(s01_couplers_to_s01_regslice_ARBURST),
        .s_axi_arcache(s01_couplers_to_s01_regslice_ARCACHE),
        .s_axi_arid(s01_couplers_to_s01_regslice_ARID),
        .s_axi_arlen(s01_couplers_to_s01_regslice_ARLEN),
        .s_axi_arlock(s01_couplers_to_s01_regslice_ARLOCK),
        .s_axi_arprot(s01_couplers_to_s01_regslice_ARPROT),
        .s_axi_arqos(s01_couplers_to_s01_regslice_ARQOS),
        .s_axi_arready(s01_couplers_to_s01_regslice_ARREADY),
        .s_axi_arsize(s01_couplers_to_s01_regslice_ARSIZE),
        .s_axi_arvalid(s01_couplers_to_s01_regslice_ARVALID),
        .s_axi_awaddr(s01_couplers_to_s01_regslice_AWADDR),
        .s_axi_awburst(s01_couplers_to_s01_regslice_AWBURST),
        .s_axi_awcache(s01_couplers_to_s01_regslice_AWCACHE),
        .s_axi_awid(s01_couplers_to_s01_regslice_AWID),
        .s_axi_awlen(s01_couplers_to_s01_regslice_AWLEN),
        .s_axi_awlock(s01_couplers_to_s01_regslice_AWLOCK),
        .s_axi_awprot(s01_couplers_to_s01_regslice_AWPROT),
        .s_axi_awqos(s01_couplers_to_s01_regslice_AWQOS),
        .s_axi_awready(s01_couplers_to_s01_regslice_AWREADY),
        .s_axi_awsize(s01_couplers_to_s01_regslice_AWSIZE),
        .s_axi_awvalid(s01_couplers_to_s01_regslice_AWVALID),
        .s_axi_bid(s01_couplers_to_s01_regslice_BID),
        .s_axi_bready(s01_couplers_to_s01_regslice_BREADY),
        .s_axi_bresp(s01_couplers_to_s01_regslice_BRESP),
        .s_axi_bvalid(s01_couplers_to_s01_regslice_BVALID),
        .s_axi_rdata(s01_couplers_to_s01_regslice_RDATA),
        .s_axi_rid(s01_couplers_to_s01_regslice_RID),
        .s_axi_rlast(s01_couplers_to_s01_regslice_RLAST),
        .s_axi_rready(s01_couplers_to_s01_regslice_RREADY),
        .s_axi_rresp(s01_couplers_to_s01_regslice_RRESP),
        .s_axi_rvalid(s01_couplers_to_s01_regslice_RVALID),
        .s_axi_wdata(s01_couplers_to_s01_regslice_WDATA),
        .s_axi_wid(s01_couplers_to_s01_regslice_WID),
        .s_axi_wlast(s01_couplers_to_s01_regslice_WLAST),
        .s_axi_wready(s01_couplers_to_s01_regslice_WREADY),
        .s_axi_wstrb(s01_couplers_to_s01_regslice_WSTRB),
        .s_axi_wvalid(s01_couplers_to_s01_regslice_WVALID));
endmodule
