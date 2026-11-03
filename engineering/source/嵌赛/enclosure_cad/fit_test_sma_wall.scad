// ============================================================================
//  fit_test_sma_wall.scad — SMA interface cutout test plate (enclosure-prep2)
//  Purpose: verify the SMA round-hole diameter against the actual SMA bulkhead
//  connector before cutting the full enclosure. Size is PLACEHOLDER — 待实测.
//
//  Values MUST be kept in sync with the matching parameter block at the top of
//  rough_enclosure_v1.scad (interfaces[4] / interfaces[5]).
//
//  Prints flat, no supports: a flat plate with a round hole through its 2.4 mm
//  thickness. Check an actual SMA bulkhead connector passes through freely.
// ============================================================================

$fn = 72;

// ---- keep in sync with rough_enclosure_v1.scad ----
wall_thickness = 2.4;
sma_d = 6.5;   // SMA bulkhead hole diameter [placeholder, 待实测]
// ------------------------------------------------
margin = 10;

plate_w = sma_d + 2*margin;
plate_h = sma_d + 2*margin;

difference() {
  cube([plate_w, plate_h, wall_thickness]);
  translate([plate_w/2, plate_h/2, -1])
    cylinder(d = sma_d, h = wall_thickness + 2);
}
