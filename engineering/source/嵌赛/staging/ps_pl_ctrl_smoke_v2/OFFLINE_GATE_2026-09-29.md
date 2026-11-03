# PS-PL control smoke V2 offline gate (2026-09-29)

This record covers the offline build only. It does **not** claim that the Linux-to-PL hardware smoke test has passed.

## Scope

- Vivado 2018.3 with the existing FMSH project-local hooks
- Part: `xc7z030ffg676-2`
- Top: `ps_pl_ctrl_smoke_top`
- Effective User GP0 smoke-register base read from the copied BD: `0x400C0000`
- No QSPI or SD-card programming
- Intended programming artifact: PL-JTAG-only `ps_pl_ctrl_smoke_top_disable_icap.bit`

## Functional simulation gates

- `AXI_GP_RFU_RESPONDER_PASS`
- `PS_PL_CTRL_SMOKE_GP0_CHAIN_PASS`

The first test covers the two safe responders used for the otherwise absent BYolo GP0/GP1 windows. The second test covers the official `gp_io/gp0_manager` path through `User_Reg_*` to `ps_pl_ctrl_smoke_regs` and checks VERSION, SCRATCH, START/DONE, and RUN_COUNT behavior.

## Build result

- Main build result: `PS_PL_CTRL_SMOKE_BUILD_PASS`
- Synthesis status: complete
- Implementation/bitstream status: complete
- Routed WNS: `+4.155 ns`
- Routed TNS: `0.000 ns`
- Routed WHS: `+0.063 ns`
- Routed THS: `0.000 ns`
- Setup failing endpoints: `0`
- Hold failing endpoints: `0`
- Unconstrained internal endpoints: `0`
- Registers/latches with no clock: `0`
- Combinational loops: `0`
- Fully routed nets: `3557 / 3557`
- Nets with routing errors: `0`

## Routed utilization

- Slice LUTs: `1796` (`2.28%`)
- Slice registers: `2132` (`1.36%`)
- Block RAM tiles: `0`
- DSPs: `0`
- BUFGCTRL: `3`

## Reviewed warnings

- `RTSTAT-10`: unused PS HP2 return nets and unused internal FIFO status nets have no routable loads. This smoke design intentionally does not use the HP2/PL-DDR data path. There are no routing errors.
- `TIMING-27`: the official PS IP creates `clk_fpga_0` on the internal `FCLKCLK[0]` hierarchical pin. The same warning exists in the earlier copied official-PS smoke builds. In the complete routed design, `clk_fpga_0` is present at 50 MHz, `clk_out1_clk_wiz_0` is present at 100 MHz, and all internal endpoints are constrained.
- PJTAG output-delay messages occur only while synthesizing the official processing-system IP out of context, where `PJTAG_TCK` is absent. The same messages exist in earlier builds using the same official PS IP. They do not appear as unconstrained endpoints in the complete routed design.
- The copied official project references absent optional `implementation_place_pre.tcl` and `implementation_place_post.tcl` hooks. The existing FMSH `implementation_opt_post.tcl`, `implementation_route_post.tcl`, `write_bitstream_pre.tcl`, and `write_bitstream_post.tcl` hooks executed. The original project and installed FMSH patch were not modified.
- The local Tcl-store warning falls back to the installed Tcl store and does not change the generated design.

## Artifact hashes

- `rtl/axi_gp_rfu_responder.sv`: `15A6CE7BC7DC879CBEB09238445A3E113A3EC33CF581807BA68F436E2C958791`
- `rtl/ps_pl_ctrl_smoke_regs.sv`: `D2CC170C65FA83A0CA0D65724D670176E753F04A43A87A35552C607967907ADE`
- `rtl/ps_pl_ctrl_smoke_top.sv`: `42EAEE353502B488AD33F98C33177C1B34B56502296B35FE07D0DB2771F46498`
- `linux/ps_pl_ctrl_smoke.cpp`: `8FDFAFC76AA4D53A4C5A712D3297890A9B4F4BD21B2235AB6B008C7F017CBE0D`
- Original bitstream: `BD6E6ED7A3B59199FCB574AB95E496D9BFDB1DC6B8F77A91598DD558AD5A290A`
- Disable-ICAP bitstream: `19A6BD2ED8400714E5A29DE41078E851C6CDDD90CFF8702A28F9C36E77B2F7DA`
- Routed timing report: `6B939CAC26D8854EF5105EB53BC918975E05DD1ADEB56BD55B9B1EB80736D2C5`
- Routed DRC report: `978B52B0CB96BE3FFA56CBFBB7D64724798F4B1320DF579440BB9164327A5F23`
- Routed utilization report: `23000AEAF17F8D5CBBDD7AFF3C3B062C103C7C5935E0F27C8691FC1410FF4ED6`

## Exact artifacts

- Project: `F:/FPGA_Work/ps_pl_ctrl_smoke_v2/fpai_demo_fpga/fpai_demo_vivado.xpr`
- Disable-ICAP bitstream: `F:/FPGA_Work/ps_pl_ctrl_smoke_v2/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/ps_pl_ctrl_smoke_top_disable_icap.bit`
- Programming Tcl: `F:/FPGA_Work/ps_pl_ctrl_smoke_v2/fpai_demo_fpga/program_ps_pl_ctrl_smoke_v2.tcl`
- Linux test source: `F:/FPGA_Work/ps_pl_ctrl_smoke_v2/fpai_demo_fpga/linux/ps_pl_ctrl_smoke.cpp`
- Reports: `F:/FPGA_Work/ps_pl_ctrl_smoke_v2/fpai_demo_fpga/reports/ps_pl_ctrl_smoke_v2/`

## Remaining hardware gate

The only remaining milestone is a controlled real-board run:

1. Temporarily program the disable-ICAP bitstream through PL JTAG.
2. Transfer and compile the exact recorded C++ source on the board.
3. Read `VERSION == 0x20260927`.
4. Write/read `SCRATCH == 0x12345678`.
5. Issue START and verify DONE with RUN_COUNT incremented by one.
6. Require final output `PS_PL_CTRL_SMOKE_LINUX_PASS`.

Do not proceed to PL DDR integration until this hardware gate passes.
