from pathlib import Path
import shutil
here=Path(__file__).resolve().parent
out=here/'shared_pspl';out.mkdir(exist_ok=True)
for p in (here/'routed_pspl').iterdir():
    if p.suffix in {'.sv','.v','.ps1'}:shutil.copy2(p,out/p.name)
shutil.copy2(here/'user_ddr_read_arbiter.sv',out/'user_ddr_read_arbiter.sv')
p=out/'tb_smart_scan_pspl.sv';text=p.read_text()
point='    smart_scan_pspl_engine dut ('
insert='''    wire [31:0] ss_ddr_araddr, ss_ddr_arinfo, ss_ddr_rinfo;
    wire ss_ddr_arvalid, ss_ddr_arready, ss_ddr_rvalid, ss_ddr_rready;
    wire [511:0] ss_ddr_rdata;
    user_ddr_read_arbiter shared_ddr (
        .clk(ddr_clk), .rst_n(ddr_rst_n),
        .ar_araddr(ddr_araddr),.ar_arvalid(ddr_arvalid),.ar_arinfo(ddr_arinfo),.ar_arready(ddr_arready),
        .ar_rdata(ddr_rdata),.ar_rvalid(ddr_rvalid),.ar_rinfo(ddr_rinfo),.ar_rready(ddr_rready),
        .r0_araddr(32'd0),.r0_arvalid(1'b0),.r0_arinfo(32'd0),.r0_rready(1'b0),
        .r1_araddr(ss_ddr_araddr),.r1_arvalid(ss_ddr_arvalid),.r1_arinfo(ss_ddr_arinfo),.r1_arready(ss_ddr_arready),
        .r1_rdata(ss_ddr_rdata),.r1_rvalid(ss_ddr_rvalid),.r1_rinfo(ss_ddr_rinfo),.r1_rready(ss_ddr_rready));
'''
assert point in text;text=text.replace(point,insert+point)
for name in ['araddr','arvalid','arinfo','arready','rdata','rvalid','rinfo','rready']:
    text=text.replace(f'.User_Ddr_{name}(ddr_{name})',f'.User_Ddr_{name}(ss_ddr_{name})')
p.write_text(text)
print('SHARED_ROUTE_DDR_SIM_PREPARED')
