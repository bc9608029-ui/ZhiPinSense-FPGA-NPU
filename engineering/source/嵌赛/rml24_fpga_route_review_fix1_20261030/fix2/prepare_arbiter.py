from pathlib import Path
here=Path(__file__).resolve().parent
src=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/smartscan_integration/rtl/user_ddr_read_arbiter.sv').read_text()
(here/'user_ddr_read_arbiter_original.sv').write_text(src)
src=src.replace('    wire req0   = r0_arvalid;', '    reg busy;\n    wire req0   = r0_arvalid && !busy;')
src=src.replace('    wire req1   = r1_arvalid;', '    wire req1   = r1_arvalid && !busy;')
src=src.replace('ar_arready && !grant1;', 'ar_arready && !grant1 && !busy;')
src=src.replace('ar_arready &&  grant1;', 'ar_arready &&  grant1 && !busy;')
src=src.replace("        if (!rst_n)         owner1 <= 1'b0;\n        else if (rd_accept) owner1 <= grant1;", """        if (!rst_n) begin owner1 <= 1'b0; busy <= 1'b0; end
        else begin
            if (rd_accept) begin owner1 <= grant1; busy <= 1'b1; end
            if (ar_rvalid && ar_rready) busy <= 1'b0;
        end""")
src=src.replace('ar_rvalid && !owner1;', 'ar_rvalid && !owner1 && busy;')
src=src.replace('ar_rvalid &&  owner1;', 'ar_rvalid &&  owner1 && busy;')
src=src.replace('assign ar_rready = owner1 ? r1_rready : r0_rready;', 'assign ar_rready = busy && (owner1 ? r1_rready : r0_rready);')
src=src.replace('// Two-way arbiter', '// One global outstanding read is enforced until the response handshake.\n// Two-way arbiter')
(here/'user_ddr_read_arbiter.sv').write_text(src)
