// ============================================================================
//  fit_test_lip.scad — lid-lip / base-wall slip-fit test piece (enclosure-prep2)
//  Purpose: verify the lid locating-lip tolerance (fit_clearance) and confirm
//  that the 1.6 mm lip prints cleanly, WITHOUT printing the whole 220x160 shell.
//
//  Values MUST be kept in sync with the matching parameter block at the top of
//  rough_enclosure_v1.scad.
//
//  Prints flat, no supports. Two bars are produced:
//    - lip_plate  : lid edge replica (flat plate + standing lip)
//    - slot_plate : base wall replica (floor + standing wall)
//  Assembly check on a table: press the lip OUTER face against the wall INNER
//  face. The intended gap is fit_clearance (0.35 mm): it should slide with
//  light resistance and no visible slop.
// ============================================================================

$fn = 72;

part = "both";   // "lip" | "slot" | "both"

// ---- keep in sync with rough_enclosure_v1.scad ----
lid_thickness     = 2.4;
lid_lip_height    = 4.0;
lid_lip_thickness = 1.6;
wall_thickness    = 2.4;
base_thickness    = 3.0;
fit_clearance     = 0.35;
// ------------------------------------------------

test_len    = 40;   // length of the test segment
plate_depth = 12;   // depth of the lid plate replica

// lid edge replica: plate flat on the bed, lip standing on top (print-friendly)
module lip_plate() {
  cube([test_len, plate_depth, lid_thickness]);
  translate([0, plate_depth - lid_lip_thickness, lid_thickness])
    cube([test_len, lid_lip_thickness, lid_lip_height]);
}

// base wall replica: floor flat on the bed, wall standing (print-friendly)
module slot_plate() {
  cube([test_len + 8, plate_depth, base_thickness]);
  translate([0, 0, base_thickness])
    cube([test_len + 8, wall_thickness, 12]);
}

if (part == "lip") {
  lip_plate();
} else if (part == "slot") {
  slot_plate();
} else {
  lip_plate();
  translate([0, -plate_depth - 6, 0]) slot_plate();
}
