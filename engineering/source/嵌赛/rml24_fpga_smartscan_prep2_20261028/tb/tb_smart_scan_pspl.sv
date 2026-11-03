`timescale 1ns/1ps
// Smart-scan PS/PL engine bus simulation + fault injection.
//
// Drives smart_scan_pspl_engine through bus-functional models of the platform
// channels and the real vendor XFFT behavioural netlist:
//   - User_Reg_* : 32-bit register channel BFM (reg_write / reg_read tasks).
//   - User_Ddr_* : 512-bit read memory model with a programmable mid-frame
//                  stall (fault injection for input starvation -> overflow).
//
// Clean cases:
//   case zero_1frame    : 1 frame of zeros -> done, committed, PSD all zero,
//                         anti-tear recheck passes.
//   case tone_1frame    : 1 frame, +37-bin complex tone -> fftshift peak 549.
//   case tone_2frames   : 2 continuous frames -> frame_id=2, committed bank 1,
//                         peak 549 (bank flip + anti-tear recheck).
// Fault cases:
//   fault bad_config    : IQ_BYTES=4000 (not a 4096 multiple) -> done+error,
//                         SS_ERR_CODE[0]=1.
//   fault ddr_stall     : stall the DDR read mid-frame -> event_data_in_channel
//                         halt -> status_overflow latched (input starvation,
//                         not "output too slow").
module tb_smart_scan_pspl;

    // --- clocks: gp 100 MHz, ddr 200 MHz, core 100 MHz -------------------
    reg gp_clk = 0;   always #5   gp_clk   = ~gp_clk;
    reg ddr_clk = 0;  always #2.5 ddr_clk  = ~ddr_clk;
    reg core_clk = 0; always #5   core_clk = ~core_clk;

    reg gp_rst_n = 0, ddr_rst_n = 0, core_rst_n = 0;

    // --- User_Reg BFM signals --------------------------------------------
    reg [31:0] awwaddr = 0, awwdata = 0; reg awwvalid = 0; wire awwready;
    reg [31:0] araddr = 0; reg arvalid = 0; wire arready;
    wire [31:0] rdata; wire rvalid; reg rready = 0;

    // --- User_Ddr BFM signals --------------------------------------------
    wire [31:0]  ddr_awwaddr;  wire [511:0] ddr_awwdata;  wire [71:0] ddr_awwinfo;
    wire         ddr_awwvalid; reg           ddr_awwready = 0;
    wire [31:0]  ddr_araddr;   wire          ddr_arvalid;  wire [31:0] ddr_arinfo;
    reg          ddr_arready = 0;
    reg [511:0]  ddr_rdata = 0; reg ddr_rvalid = 0; reg [31:0] ddr_rinfo = 0;
    wire         ddr_rready;

    smart_scan_pspl_engine dut (
        .gp_clk(gp_clk), .gp_rst_n(gp_rst_n),
        .ddr_clk(ddr_clk), .ddr_global_rst_n(ddr_rst_n),
        .core_clk(core_clk), .core_global_rst_n(core_rst_n),
        .User_Reg_awwaddr(awwaddr), .User_Reg_awwdata(awwdata),
        .User_Reg_awwvalid(awwvalid), .User_Reg_awwready(awwready),
        .User_Reg_araddr(araddr), .User_Reg_arvalid(arvalid),
        .User_Reg_arready(arready), .User_Reg_rdata(rdata),
        .User_Reg_rvalid(rvalid), .User_Reg_rready(rready),
        .User_Ddr_awwaddr(ddr_awwaddr), .User_Ddr_awwdata(ddr_awwdata),
        .User_Ddr_awwinfo(ddr_awwinfo), .User_Ddr_awwvalid(ddr_awwvalid),
        .User_Ddr_awwready(ddr_awwready),
        .User_Ddr_araddr(ddr_araddr), .User_Ddr_arvalid(ddr_arvalid),
        .User_Ddr_arinfo(ddr_arinfo), .User_Ddr_arready(ddr_arready),
        .User_Ddr_rdata(ddr_rdata), .User_Ddr_rvalid(ddr_rvalid),
        .User_Ddr_rinfo(ddr_rinfo), .User_Ddr_rready(ddr_rready));

    // ------------------------------------------------------------------
    // DDR memory model: 512 beats x 512-bit (32 KiB), single-outstanding
    // read with a programmable stall (0 = never stall).
    // ------------------------------------------------------------------
    reg [511:0] ddr_mem [0:511];
    reg [31:0]  ddr_pending_addr;
    reg         ddr_serving;
    reg [31:0]  ddr_beats_served;
    reg [31:0]  ddr_stall_after;   // stall once beats_served >= this (0 = off)

    always @(posedge ddr_clk or negedge ddr_rst_n) begin
        if (!ddr_rst_n) begin
            ddr_arready      <= 1'b0;
            ddr_serving      <= 1'b0;
            ddr_rvalid       <= 1'b0;
            ddr_rdata        <= 512'd0;
            ddr_rinfo        <= 32'd0;
            ddr_pending_addr <= 32'd0;
            ddr_beats_served <= 32'd0;
        end else begin
            if (ddr_serving) begin
                ddr_rvalid <= 1'b1;
                ddr_rdata  <= ddr_mem[ddr_pending_addr[31:6]];
                ddr_rinfo  <= {25'd0, 6'd0, 1'b1};  // single beat, last=1
                if (ddr_rvalid && ddr_rready) begin
                    ddr_serving      <= 1'b0;
                    ddr_rvalid       <= 1'b0;
                    ddr_beats_served <= ddr_beats_served + 1'b1;
                end
            end else begin
                ddr_arready <= (ddr_stall_after != 0 &&
                                ddr_beats_served >= ddr_stall_after) ? 1'b0 : 1'b1;
                if (ddr_arvalid && ddr_arready) begin
                    ddr_pending_addr <= ddr_araddr;
                    ddr_serving      <= 1'b1;
                    ddr_arready      <= 1'b0;
                end
            end
        end
    end

    // ------------------------------------------------------------------
    // Register BFM tasks
    // ------------------------------------------------------------------
    localparam [17:0] ADDR_IQ_BASE     = 18'h00000;
    localparam [17:0] ADDR_IQ_BYTES    = 18'h00004;
    localparam [17:0] ADDR_CTRL        = 18'h00008;
    localparam [17:0] ADDR_VERSION     = 18'h0000C;
    localparam [17:0] ADDR_STATUS      = 18'h00010;
    localparam [17:0] ADDR_FRAME_ID    = 18'h00014;
    localparam [17:0] ADDR_IQ_ACCEPTED = 18'h00018;
    localparam [17:0] ADDR_ERR_CODE    = 18'h0001C;
    localparam [17:0] ADDR_RD_CTRL     = 18'h00020;
    localparam [17:0] ADDR_RD_DATA_LO  = 18'h00024;
    localparam [17:0] ADDR_RD_DATA_HI  = 18'h00028;

    task reg_write(input [31:0] addr, input [31:0] data);
        begin
            awwaddr = addr; awwdata = data; awwvalid = 1'b1;
            do @(posedge gp_clk); while (!awwready);
            awwvalid = 1'b0;
            @(posedge gp_clk);
            awwaddr = 32'd0; awwdata = 32'd0;
        end
    endtask

    task reg_read(input [31:0] addr, output [31:0] data);
        begin
            araddr = addr; arvalid = 1'b1;
            do @(posedge gp_clk); while (!rvalid);
            data = rdata;
            rready = 1'b1;
            @(posedge gp_clk);
            rready = 1'b0; arvalid = 1'b0; araddr = 32'd0;
        end
    endtask

    // ------------------------------------------------------------------
    // Stimulus loaders
    // ------------------------------------------------------------------
    task load_iq_tone(input integer n_frames, input integer bin, input integer amp);
        integer s, total, b, w, i_val, q_val;
        real arg;
        begin
            total = n_frames * 1024;
            for (s = 0; s < total; s = s + 1) begin
                arg = 2.0 * 3.14159265358979323846 * bin * s / 1024.0;
                i_val = $rtoi(amp * $cos(arg));
                q_val = $rtoi(amp * $sin(arg));
                b = s / 16;
                w = s % 16;
                ddr_mem[b][w*32 +: 32] = {q_val[15:0], i_val[15:0]};
            end
        end
    endtask

    task load_iq_zero(input integer n_frames);
        integer s, total, b, w;
        begin
            total = n_frames * 1024;
            for (s = 0; s < total; s = s + 1) begin
                b = s / 16; w = s % 16;
                ddr_mem[b][w*32 +: 32] = 32'd0;
            end
        end
    endtask

    // ------------------------------------------------------------------
    // Scan driver helpers
    // ------------------------------------------------------------------
    task poll_done(output [31:0] status_out);
        integer cnt;
        reg [31:0] st;
        begin
            for (cnt = 0; cnt < 2000000; cnt = cnt + 1) begin
                reg_read(ADDR_STATUS, st);
                status_out = st;
                if (st[1]) return;            // done
            end
            $fatal(1, "poll_done timeout: status=%h", st);
        end
    endtask

    reg [63:0] psd [0:1023];

    task read_psd(input [0:0] bank);
        integer a, p;
        reg [31:0] st, lo, hi;
        begin
            for (a = 0; a < 1024; a = a + 1) begin
                reg_write(ADDR_RD_CTRL, {21'd0, bank, a[9:0]});
                st = 32'd0;
                for (p = 0; p < 10000; p = p + 1) begin
                    reg_read(ADDR_STATUS, st);
                    if (st[7]) break;         // rd_ready
                end
                if (!st[7]) $fatal(1, "rd_ready timeout at bin %0d", a);
                reg_read(ADDR_RD_DATA_LO, lo);
                reg_read(ADDR_RD_DATA_HI, hi);
                psd[a] = {hi, lo};
            end
        end
    endtask

    task find_peak(output integer peak_bin, output reg [63:0] peak_val);
        integer k, max1_bin;
        reg [63:0] max1, max2;
        begin
            max1 = 64'd0; max2 = 64'd0; max1_bin = -1;
            for (k = 0; k < 1024; k = k + 1) begin
                if (psd[k] > max1) begin
                    max2 = max1; max1 = psd[k]; max1_bin = k;
                end else if (psd[k] > max2) begin
                    max2 = psd[k];
                end
            end
            peak_bin = max1_bin; peak_val = max1;
        end
    endtask

    // Run a clean scan and return status/err/frame_id; caller reads PSD.
    task run_clean(input [31:0] bytes, output [31:0] st, output [31:0] err,
                   output [31:0] fid);
        begin
            reg_write(ADDR_CTRL, 32'h2);       // CLEAR
            reg_write(ADDR_IQ_BASE, 32'd0);
            reg_write(ADDR_IQ_BYTES, bytes);
            reg_write(ADDR_CTRL, 32'h1);       // START
            poll_done(st);
            reg_read(ADDR_ERR_CODE, err);
            reg_read(ADDR_FRAME_ID, fid);
            if (err != 0 || !st[3]) $fatal(1, "clean scan error: status=%h err=%h", st, err);
        end
    endtask

    // ------------------------------------------------------------------
    // Main sequence
    // ------------------------------------------------------------------
    integer npass, nfault, peak_bin;
    reg [63:0] peak_val;
    reg [31:0] st, err, fid, fid_before, fid_after, ver;
    reg [0:0]  bank;
    integer k;

    initial begin : main
        npass = 0; nfault = 0;
        ddr_stall_after = 0;
        ddr_awwready = 1'b1;

        // reset
        gp_rst_n = 0; ddr_rst_n = 0; core_rst_n = 0;
        repeat (20) @(posedge core_clk);
        gp_rst_n = 1; ddr_rst_n = 1; core_rst_n = 1;
        repeat (20) @(posedge core_clk);

        // version check (must be readable before any START); counted separately,
        // not as a scan case -- it prints its own PSPL_VERSION PASS token.
        reg_read(ADDR_VERSION, ver);
        if (ver != 8'h01) $fatal(1, "version mismatch: %h", ver);
        $display("PSPL_VERSION PASS version=%h", ver);

        // --- case 1: zero / 1 frame -------------------------------------
        load_iq_zero(1);
        ddr_beats_served <= 0;
        run_clean(4096, st, err, fid);
        if (fid != 1) $fatal(1, "zero_1frame fid=%0d (expect 1)", fid);
        bank = st[4];
        reg_read(ADDR_FRAME_ID, fid_before);
        read_psd(bank);
        reg_read(ADDR_FRAME_ID, fid_after);
        reg_read(ADDR_STATUS, st);
        if (fid_before != fid_after || st[4] != bank)
            $fatal(1, "zero_1frame generation changed");
        find_peak(peak_bin, peak_val);
        if (peak_val != 64'd0) $fatal(1, "zero_1frame peak=%h (expect 0)", peak_val);
        $display("PSPL_CASE PASS case=zero_1frame fid=%0d bank=%0b", fid, bank);
        npass = npass + 1;

        // --- case 2: +37-bin tone / 1 frame -----------------------------
        load_iq_tone(1, 37, 8000);
        ddr_beats_served <= 0;
        run_clean(4096, st, err, fid);
        bank = st[4];
        reg_read(ADDR_FRAME_ID, fid_before);
        read_psd(bank);
        reg_read(ADDR_FRAME_ID, fid_after);
        reg_read(ADDR_STATUS, st);
        if (fid_before != fid_after || st[4] != bank)
            $fatal(1, "tone_1frame generation changed");
        find_peak(peak_bin, peak_val);
        if (peak_bin != 549) $fatal(1, "tone_1frame peak_bin=%0d (expect 549)", peak_bin);
        if (peak_val == 64'd0) $fatal(1, "tone_1frame zero peak");
        $display("PSPL_CASE PASS case=tone_1frame peak_bin=%0d peak=%h", peak_bin, peak_val);
        npass = npass + 1;

        // --- case 3: +37-bin tone / 2 continuous frames ------------------
        load_iq_tone(2, 37, 8000);
        ddr_beats_served <= 0;
        run_clean(8192, st, err, fid);
        if (fid != 2) $fatal(1, "tone_2frames fid=%0d (expect 2)", fid);
        if (st[4] != 1'b1) $fatal(1, "tone_2frames committed_bank=%0b (expect 1)", st[4]);
        bank = st[4];
        reg_read(ADDR_FRAME_ID, fid_before);
        read_psd(bank);
        reg_read(ADDR_FRAME_ID, fid_after);
        reg_read(ADDR_STATUS, st);
        if (fid_before != fid_after || st[4] != bank)
            $fatal(1, "tone_2frames generation changed");
        find_peak(peak_bin, peak_val);
        if (peak_bin != 549) $fatal(1, "tone_2frames peak_bin=%0d (expect 549)", peak_bin);
        $display("PSPL_CASE PASS case=tone_2frames fid=%0d bank=%0b peak_bin=%0d",
                 fid, bank, peak_bin);
        npass = npass + 1;

        // --- fault 1: bad config (byte count not 4096-multiple) ----------
        reg_write(ADDR_CTRL, 32'h2);
        reg_write(ADDR_IQ_BASE, 32'd0);
        reg_write(ADDR_IQ_BYTES, 32'd4000);
        reg_write(ADDR_CTRL, 32'h1);
        poll_done(st);
        reg_read(ADDR_ERR_CODE, err);
        if (!st[2] || !err[0])
            $fatal(1, "bad_config not detected: status=%h err=%h", st, err);
        $display("PSPL_FAULT PASS case=bad_config err=%h", err);
        nfault = nfault + 1;

        // --- fault 2: mid-frame DDR stall -> input starvation -> overflow -
        load_iq_tone(1, 37, 8000);
        ddr_beats_served <= 0;
        ddr_stall_after <= 8;                 // serve 8 beats (128 samples), then stall
        reg_write(ADDR_CTRL, 32'h2);
        reg_write(ADDR_IQ_BASE, 32'd0);
        reg_write(ADDR_IQ_BYTES, 32'd4096);
        reg_write(ADDR_CTRL, 32'h1);
        repeat (6000) @(posedge core_clk);    // let the FIFO drain and the core halt
        reg_read(ADDR_STATUS, st);
        if (!st[6]) $fatal(1, "ddr_stall did not latch overflow: status=%h", st);
        $display("PSPL_FAULT PASS case=ddr_stall overflow=%0b", st[6]);
        nfault = nfault + 1;
        ddr_stall_after <= 0;                 // release for a clean finish

        $display("TB_SMART_SCAN_PSPL PASS cases=%0d faults=%0d", npass, nfault);
        $finish;
    end

    initial begin
        #40000000;                            // 40 ms watchdog
        $fatal(1, "tb_smart_scan_pspl timeout");
    end
endmodule
