// M26 fixed-point helper package (round-half-away-from-zero, saturation, Q-format
// conversions).  These mirror the C++ bit-exact model `golden/m26_fixed_model.hpp`
// one-for-one and implement the arithmetic in `docs/M26_FIXED_POINT_CONTRACT.md`.
//
// Conventions:
//   * IQ sample       : signed 16-bit Q1.15  -> logic signed [15:0]
//   * power           : unsigned 32-bit Q0.30
//   * wide accumulator: signed 64-bit, 30 fractional bits (Q33.30), mirroring the
//     C++ i64 accumulator exactly; the narrowest per-stage registers (dc 40-bit,
//     FIR 48-bit) all sign-extend losslessly into this width, so no stage truncates
//     before the final round+sat.
//
// No production RTL/XDC/bitstream is touched; these are standalone offline modules.
package m26_fxp_pkg;

  // ------------------------------------------------------------------ round-half-away
  // Round-half-away-from-zero then arithmetic-shift right by `sh`.
  // For two's-complement arithmetic shift (floor), round-half-away is:
  //   v >= 0 : (v + half) >> sh
  //   v <  0 : (v + half - 1) >> sh      (add half-1 so the .5 tie moves away from 0)
  function automatic logic signed [63:0] rshift_round(
      input logic signed [63:0] v, input int sh);
    logic signed [63:0] half;
    logic signed [63:0] adj;
    half = 64'sd1 << (sh - 1);
    adj  = (v < 0) ? 64'sd1 : 64'sd0;
    return (v + half - adj) >>> sh;      // >>> = arithmetic shift on signed
  endfunction

  // round-half-away + shift + symmetric saturation to signed 16-bit (Q1.15).
  function automatic logic signed [15:0] rshift_round_sat16(
      input logic signed [63:0] v, input int sh);
    logic signed [63:0] r;
    r = rshift_round(v, sh);
    if (r > 64'sd32767)  return 16'sd32767;
    if (r < -64'sd32768) return -16'sd32768;
    return r[15:0];
  endfunction

  // symmetric saturation of a signed 64-bit value to 16-bit (Q1.15), no shift.
  function automatic logic signed [15:0] sat16(input logic signed [63:0] v);
    if (v > 64'sd32767)  return 16'sd32767;
    if (v < -64'sd32768) return -16'sd32768;
    return v[15:0];
  endfunction

  // signed 16-bit Q1.15 -> 40-bit with 30 fractional bits (Q9.30): sign-extend, <<15.
  function automatic logic signed [39:0] q15_to_q930(input logic signed [15:0] v);
    return {{24{v[15]}}, v, 15'b0};
  endfunction

endpackage
