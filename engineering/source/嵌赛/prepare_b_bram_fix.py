from pathlib import Path
import hashlib,json
r=Path(__file__).parent/'rml24_fpga_route_review_fix1_20261030';r.mkdir(exist_ok=True)
s=Path('F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration/rtl/smart_scan_psd_buffers.sv')
original=s.read_text();(r/'original.sv').write_text(original)
fixed=original.replace('    reg [63:0] mem0', '    (* ram_style = "block" *) reg [63:0] mem0').replace('    reg [63:0] mem1','    (* ram_style = "block" *) reg [63:0] mem1')
fixed=fixed.replace('    assign rd_data             = rd_bank ? mem1[rd_addr] : mem0[rd_addr];','''    // Synchronous reads: block RAM inference requires a registered read port.
    // Existing PSPL RD_WAIT -> RD_CAPTURE leaves the required clock of latency.
    reg [63:0] rd0, rd1;
    reg rd_bank_q;
    always @(posedge clk) begin
        rd0 <= mem0[rd_addr];
        rd1 <= mem1[rd_addr];
        rd_bank_q <= rd_bank;
    end
    assign rd_data = rd_bank_q ? rd1 : rd0;''')
assert fixed!=original
(r/'smart_scan_psd_buffers.sv').write_text(fixed)
(r/'IDENTITY.json').write_text(json.dumps({'source':str(s),'original_sha256':hashlib.sha256(s.read_bytes()).hexdigest(),'fix_sha256':hashlib.sha256((r/'smart_scan_psd_buffers.sv').read_bytes()).hexdigest()},indent=2))
(r/'compare_synth.tcl').write_text('''set_param general.maxThreads 2
foreach variant {original fixed} {
  create_project -in_memory -part xc7z030ffg676-2
  if {$variant eq "original"} {set src original.sv} else {set src smart_scan_psd_buffers.sv}
  read_verilog -sv $src
  synth_design -top smart_scan_psd_buffers -part xc7z030ffg676-2 -mode out_of_context
  report_utilization -hierarchical -file ${variant}_utilization.rpt
  set brams [llength [get_cells -hier -filter {REF_NAME =~ RAMB*}]]
  puts "BRAM_COMPARISON variant=$variant bram_cells=$brams"
  if {$variant eq "fixed" && $brams == 0} {error "fixed read port did not infer BRAM"}
  close_project
}
exit
''')
print(r)
