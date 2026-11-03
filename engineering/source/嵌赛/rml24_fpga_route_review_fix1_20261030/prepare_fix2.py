from pathlib import Path
import shutil, json, hashlib
HERE=Path(__file__).resolve().parent
SRC=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga')
OUT=HERE/'fix2'
OUT.mkdir(exist_ok=True)
for name in ['user_reg_router.sv','pl_ddr_mandatory_core_top_combined_smartscan.sv']:
    text=(SRC/'smartscan_integration/rtl'/name).read_text()
    assert "18'h0F000" in text
    (OUT/name).write_text(text.replace("18'h0F000", "18'h3F000"))
fifo=(SRC/'pl_ddr_integration_v1/deps/adapters/async_fifo_gray.sv').read_text()
old='''            if (s_transfer)
                mem[wr_bin[ADDR_WIDTH-1:0]] <= s_data;
'''
assert old in fifo
fifo=fifo.replace(old,'')
fifo=fifo.replace("            m_data  <= {DATA_WIDTH{1'b0}};\n",'')
fifo=fifo.replace('                m_data  <= mem[rd_bin[ADDR_WIDTH-1:0]];\n','')
point='    always @(posedge s_clk or negedge s_rst_n) begin'
assert point in fifo
fifo=fifo.replace(point,'''    // Keep RAM ports out of asynchronously reset control processes.
    // m_data is unspecified when m_valid=0, as permitted by ready/valid.
    // Valid data, output latency, pointer advance and backpressure are unchanged.
    always @(posedge s_clk) begin
        if (s_rst_n && s_transfer)
            mem[wr_bin[ADDR_WIDTH-1:0]] <= s_data;
    end
    always @(posedge m_clk) begin
        if (m_rst_n && load_output && !fifo_empty)
            m_data <= mem[rd_bin[ADDR_WIDTH-1:0]];
    end

'''+point,1)
(OUT/'async_fifo_gray.sv').write_text(fifo)
shutil.copy2(SRC/'pl_ddr_integration_v1/deps/adapters/async_fifo_gray.sv',OUT/'async_fifo_gray_original.sv')
shutil.copy2(SRC/'smartscan_integration/rtl/user_reg_router.sv',OUT/'user_reg_router_original.sv')
sim=OUT/'routed_pspl'
sim.mkdir(exist_ok=True)
for f in (HERE/'pspl_regression').iterdir():
    if f.suffix in {'.sv','.v','.ps1'}:shutil.copy2(f,sim/f.name)
shutil.copy2(OUT/'async_fifo_gray.sv',sim/'async_fifo_gray.sv')
shutil.copy2(OUT/'user_reg_router.sv',sim/'user_reg_router.sv')
tb=(sim/'tb_smart_scan_pspl.sv').read_text()
marker='    smart_scan_pspl_engine dut ('
assert marker in tb
insert='''    wire [31:0] sa,sd,sra,srd; wire sv,swr,sar,sarr,srv,srr;
    user_reg_router router (
        .clk(gp_clk),.rst_n(gp_rst_n),
        .awwaddr(awwaddr),.awwdata(awwdata),.awwvalid(awwvalid),.awwready(awwready),
        .araddr(araddr),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rready(rready),
        .e0_awwready(1'b1),.e0_arready(1'b1),.e0_rdata(32'hbad00000),.e0_rvalid(1'b0),
        .e1_awwaddr(sa),.e1_awwdata(sd),.e1_awwvalid(sv),.e1_awwready(swr),
        .e1_araddr(sra),.e1_arvalid(sar),.e1_arready(sarr),
        .e1_rdata(srd),.e1_rvalid(srv),.e1_rready(srr));
'''
tb=tb.replace(marker,insert+marker)
mapping={'User_Reg_awwaddr':'sa','User_Reg_awwdata':'sd','User_Reg_awwvalid':'sv','User_Reg_awwready':'swr','User_Reg_araddr':'sra','User_Reg_arvalid':'sar','User_Reg_arready':'sarr','User_Reg_rdata':'srd','User_Reg_rvalid':'srv','User_Reg_rready':'srr'}
oldnames={'User_Reg_awwaddr':'awwaddr','User_Reg_awwdata':'awwdata','User_Reg_awwvalid':'awwvalid','User_Reg_awwready':'awwready','User_Reg_araddr':'araddr','User_Reg_arvalid':'arvalid','User_Reg_arready':'arready','User_Reg_rdata':'rdata','User_Reg_rvalid':'rvalid','User_Reg_rready':'rready'}
for port,new in mapping.items():tb=tb.replace(f'.{port}({oldnames[port]})',f'.{port}({new})')
tb=tb.replace('awwaddr = addr;',"awwaddr = 32'h10000 + addr;").replace('araddr = addr;',"araddr = 32'h10000 + addr;")
(sim/'tb_smart_scan_pspl.sv').write_text(tb)
identity={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.sv')}
(OUT/'IDENTITY.json').write_text(json.dumps(identity,indent=2))
print('FIX2_PREPARED',OUT)
