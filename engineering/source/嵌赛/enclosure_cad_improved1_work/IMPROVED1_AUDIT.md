# Enclosure improved1 audit

## Verdict

The original enclosure is a useful parameterized rough model, not a final
print-ready enclosure. Its existing STL files are structurally readable and the
independent read-only STL audit found finite coordinates, zero zero-area
triangles, zero boundary/non-manifold edges, and a watertight edge graph for the
base, lid, and three fit coupons.

All 42 dimension-ledger rows remain placeholders. No physical board, connector,
cable, heatsink, fan, switch, LED, or printer-fit measurement has been entered.

## Improvements made in this isolated copy

1. Added fail-fast assertions for shell, lip, wall, floor, mounts, and fastener
   parameters.
2. Added printer-bed margin warning. The current 220 mm shell length plus a
   5 mm edge margin does not fit the placeholder 220 mm usable bed.
3. Added preview-solid boundary warnings. The current Pluto placeholder reaches
   x=218 mm while the right inner wall is x=217.6 mm, so it intersects the wall
   by about 0.4 mm.
4. Changed coplanar stud/post-floor unions to a 0.20 mm physical overlap.
5. Increased the tall corner posts from 7 mm to 10 mm OD and connected each to
   its two adjacent walls with 2.4 mm ribs below the lid lip.
6. Split the former shared 3.2 mm fastener diameter into a provisional 2.7 mm
   printed-plastic pilot and a 3.4 mm lid clearance hole.
7. Updated the dimension ledger and removed a stale README sentence that claimed
   OpenSCAD had not been installed.

## Export and independent mesh validation

OpenSCAD 2021.01 exported the improved parts with `Simple: yes`. A separate
standard-library STL parser then checked the emitted triangles:

| Artifact | Triangles | Bounding box mm | Zero area | Boundary edges | Non-manifold edges | Connected components |
|---|---:|---|---:|---:|---:|---:|
| improved base | 9,604 | 220 × 160 × 67.6 | 0 | 0 | 0 | 1 |
| improved lid | 23,100 | 220 × 160 × 6.4 | 0 | 0 | 0 | 1 |
| improved assembly | 32,400 | 220 × 160 × 70 | 0 | 0 | 0 | 1 |
| M3 pilot coupon | 1,740 | 52 × 22 × 15 | 0 | 0 | 0 | 1 |

The first rib revision produced 10 zero-area triangles where ribs touched the
wall coplanarly. It was rejected. The ribs now overlap the wall by 0.20 mm; the
second export is the validated artifact.

Current per-export SHA-256 values (geometry identity should still use topology
and dimensions because CGAL triangle order can vary):

- base: `a614faf8d2e21ef3ba9edbe51ca7e9ae387a1775594363f0f058a5bb698c3915`
- lid: `ed1113785e50df6d061c9d492fe1d4987aba605fd6419055ba61a0233dd5393b`
- assembly v2: `80b81f7213d7b89c863fb4de03344c491ad8eddcc49c0a1f6c201bfa4956b670`
- M3 coupon: `ef919c3d4a6854cdea7c75c81d439c1842be9a22be336250a99303dcab3ebccf`

## Still blocked on measurements

- Final outside size and actual printer usable bed.
- Main-board outline, tallest component, heatsink, and four mount holes.
- RX Pluto outline, orientation, fastening method, and connector protrusion.
- RJ45/USB/serial/power/SMA envelopes with plugs installed.
- Cable bend radii and strain relief.
- Fan/vent requirement after a closed-case temperature test.
- Switch, LED, label, rubber-foot, and screwdriver-access locations.
- M3 self-tap versus heat-set insert decision and printed fastener coupon.

Do not print the full shell until these values are measured. Print the lip,
RJ45, SMA, and a new fastener coupon first; then print a low-height base fit
slice before committing to the full-height enclosure.
