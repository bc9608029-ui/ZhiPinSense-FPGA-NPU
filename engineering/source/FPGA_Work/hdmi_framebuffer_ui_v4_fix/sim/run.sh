#!/bin/bash
# run.sh — Verilator compile + run for the HDMI DDR read-path red/green test.
#
# Usage (inside WSL, or via: wsl -e bash -lc '/mnt/f/FPGA_Work/.../sim/run.sh'):
#   bash run.sh
#
# It always compiles the CURRENT aq_axi_master.v under fpga/rtl/display/.
#   * RED:   run with the unmodified aq_axi_master.v -> VERDICT: FAIL (proves bug)
#   * GREEN: after the 3-line fix -> VERDICT: PASS
set -e

SIM_DIR="$(cd "$(dirname "$0")" && pwd)"
RTL_DIR="$(cd "$SIM_DIR/../fpga/rtl" && pwd)"
DISP_DIR="$RTL_DIR/display"
BUILD="$SIM_DIR/obj_dir"

cd "$SIM_DIR"
rm -rf "$BUILD"

# verilator-compatible copy of aq_axi_master: strip the Xilinx-style
# `(* keep = "true" *)wire <ANSI port>` re-declarations (Vivado accepts them,
# verilator rejects them as duplicate declarations).  Logic is untouched.
sed '/\* keep/d' "$DISP_DIR/aq_axi_master.v" > "$SIM_DIR/aq_axi_master_sim.v"

verilator --binary --timing \
  --top tb_read_path \
  -Wno-fatal -Wno-WIDTH -Wno-UNUSED -Wno-DECLFILENAME -Wno-UNOPTFLAT -Wno-UNSIGNED -Wno-PINMISSING -Wno-UNUSEDSIGNAL \
  -I"$DISP_DIR" -I"$SIM_DIR" \
  "$SIM_DIR/afifo_64i_16o_128_beh.v" \
  "$SIM_DIR/afifo_16i_64o_largebuf_beh.v" \
  "$SIM_DIR/fifo_1_beh.v" \
  "$SIM_DIR/axi_mem_model.v" \
  "$DISP_DIR/color_bar.v" \
  "$DISP_DIR/video_rect_read_data.v" \
  "$DISP_DIR/timing_gen_xy.v" \
  "$DISP_DIR/level_cross.v" \
  "$DISP_DIR/frame_read_write_largebuf.v" \
  "$DISP_DIR/frame_fifo_read.v" \
  "$DISP_DIR/frame_fifo_write.v" \
  "$SIM_DIR/aq_axi_master_sim.v" \
  "$SIM_DIR/tb_read_path.sv"

echo "--- simulation ---"
"$BUILD/Vtb_read_path"
