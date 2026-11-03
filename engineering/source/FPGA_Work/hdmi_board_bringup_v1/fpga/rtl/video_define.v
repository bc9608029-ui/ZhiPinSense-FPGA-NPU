// video_define.v — 720p@60 selection for the standalone HDMI colorbar test.
//
// NEW file (not a frozen official asset).  The official demo ships this file
// with `define VIDEO_1920_1080 selected; this copy selects 720p instead, which
// is the resolution the 悟净 board manual states as reliable ("720P@60HZ 高清
// 传输"; 1080p@60 flickers because 742.5 MHz TMDS exceeds the HR bank 710 MHz
// IO limit).  Only the selected define changes; timing parameters live in
// color_bar.v under `ifdef VIDEO_1280_720.
`define	VIDEO_1280_720
//`define	VIDEO_1920_1080
//`define	VIDEO_3840_2160
