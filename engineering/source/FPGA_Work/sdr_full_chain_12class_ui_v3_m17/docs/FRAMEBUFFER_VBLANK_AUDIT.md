# FRAMEBUFFER_VBLANK_AUDIT.md — HDMI 帧缓冲翻转 / 垂直消隐同步审计（M17 Task D）

> 本文只读审计冻结位流对应的 RTL 显示读路径，**不修改任何 RTL**（红线：源工程
> `sdr_full_chain_12class_combined_v1` 冻结只读，本工程只做软件侧缓解）。
> 结论用于支撑 M17 Task E（撕裂/闪烁）与 Task F（启动条纹）的软件修复设计。

## 1. 结论（TL;DR）

- 双缓冲翻转选择 `read_buf_sel` 来自 `camera_wr_addr[0]`（PS 每帧重写），经 **2-FF 同步器**
  （`buf_sel_sync1 → buf_sel_sync2`，`hp_clk` 域）跨时钟，并在**帧起始**（`frame_fifo_read`
  的 `S_ACK` 态 `read_addr_index_d1 → rd_burst_addr`）被锁存。
- **没有任何**「当前正在扫描哪个缓冲」或「翻转已生效」的读回/ack 寄存器，也**没有**
  vblank 状态寄存器 → **软件既无法垂直消隐同步翻转，也无法检测撕裂**。
- `display_en = ~disable_hdmi_2`（`slv_reg30` bit0 经 **3-FF 同步**），**复位为 1**；
  `camera_rd_addr` 复位为 `27'h7E0_0000`。因此在「位流加载完成 → 软件编程 rd_addr」
  之间，PL 会以复位地址 `0x7E00000` 读取 DDR 残留并显示 → 这就是**启动条纹**的根因。
- 翻转在帧边界**原子生效**（锁存于帧起始），所以「写背缓冲 → 拷贝/同步完成 → 再翻转选择」
  的顺序是安全的；M16 的缺陷是**每个显示 tick 都重翻转**（每 ~33 ms），翻转频率与显示
  帧率接近且无 vblank 同步，造成置信度数字连续变化的可见闪烁。

## 2. 寄存器图（字节偏移 = 4 × slv_regN）

| slv_regN | 字节偏移 | 名称 | 复位值 | 说明 |
|---|---|---|---|---|
| slv_reg3  | `0x0C` | `frame_ctrl_ver` | `32'h20230218` | 版本门（软件写任何寄存器前先核对） |
| slv_reg20 | `0x50` | `camera_wr_addr` | `27'h7C0_0000` | **bit0 = `read_buf_sel`**（双缓冲选择 0/1） |
| slv_reg21 | `0x54` | `camera_rd_addr` | `27'h7E0_0000` | 帧缓冲基址 `>> 3` |
| slv_reg30 | `0x78` | `disable_hdmi` | `1'b0` | bit0=1 时 `display_en=0`（消隐） |
| slv_reg37 | `0x94` | `H_SYNC` | `32'd44` | 行同步（诊断只读） |
| slv_reg41 | `0xA4` | `V_SYNC` | `32'd5` | 场同步（诊断只读） |
| slv_reg45 | `0xB4` | `vtc_enable` | `1'b0` | VTC 使能（诊断只读） |

## 3. 读路径（`fb_read_720p.sv`，冻结只读）

- 帧尺寸 `1280×720×2` = 1,843,200 字节 = 921,600 RGB565 半字；双缓冲共 3,686,400 字节。
- `read_len = 27'd230400`（`230400 = 1280*720*16/64`，64-bit 突发粒度）。
- `read_addr_0 = camera_rd_addr`；`read_addr_1 = camera_rd_addr + 27'd230400`。
- `read_addr_index = {1'b0, buf_sel_sync2}`（bit1 恒 0，只有 2 个缓冲）。

```systemverilog
// 2-FF 同步器（hp_clk 域），bit0 为缓冲选择：
always @(posedge hp_clk or posedge rst_hp) begin
    if (rst_hp) begin buf_sel_sync1 <= 1'b0; buf_sel_sync2 <= 1'b0; end
    else begin buf_sel_sync1 <= read_buf_sel; buf_sel_sync2 <= buf_sel_sync1; end
end
```

- `read_buf_sel` 由 PS 每帧重写（ping-pong），**非准静态**，故必须同步，且只 bit0 跨域。
- 同步后的值在**帧起始**锁存（`frame_fifo_read` `S_ACK` 态 `read_addr_index_d1 → rd_burst_addr`），
  因此**帧中重写选择不会撕裂当前在途帧**。

## 4. 消隐链（`frame_ctrl.v`，冻结只读）

```verilog
// slv_reg30 bit0 -> 3-FF 同步 -> display_en（复位 1，即默认显示）
disable_hdmi    <= S_AXI_WDATA[0];                 // 复位 1'b0
{disable_hdmi_2,disable_hdmi_1,disable_hdmi_0} <=
    {disable_hdmi_1,disable_hdmi_0,disable_hdmi};  // 复位 3'b0
assign display_en = ~disable_hdmi_2;
```

- `display_en` 在 `fb_read_720p.sv` 里门控时序：`timing_hs/vs/de = cb_hs/vs/de & display_en`。
  `display_en=0` → `de=0` → HDMI TX 无有效像素输出（消隐/黑屏）。

## 5. 对软件侧的三条硬结论

1. **无法 vblank 同步翻转**：无 vblank 状态寄存器、无翻转 ack。软件只能保证「先写背缓冲、
   拷贝/同步完成后再翻转选择」，翻转在下一帧起始原子生效；不能等待某个消隐信号。
2. **无法检测撕裂**：没有任何读回能告诉软件「PL 当前扫描哪个缓冲」。正确做法是让软件侧
   每次都写 `front ^ 1`（背缓冲），并在内容**未变化时停止翻转**，从源头消除撕裂机会。
3. **启动条纹根因是复位地址残留**：`display_en` 复位为 1 且 `camera_rd_addr` 复位为
   `0x7E00000`，位流加载后、软件编程 rd_addr 之前 PL 已开始以复位地址扫描 DDR 残留。
   软件必须在**编程 rd_addr 之前**先消隐（`disable_hdmi=1`），待帧 0 有效且 rd_addr 已指向
   帧 0 后再解除消隐。

## 6. M17 软件缓解（本工程落地，不碰 RTL）

- **Task E/G（撕裂/闪烁 + 空闲 CPU）**：`ui_dirty_state.hpp` 的 `display_changed` +
  `FlipScheduler` 让翻转**事件驱动**——只有显示内容真实变化（新帧/状态/控制/触摸/翻页）才
  翻转，且受 `min_interval_ms` 下限约束（≥1 个显示帧周期）；稳定信号不再每 tick 重翻转。
- **Task F（启动条纹）**：`DirectFramebufferBackend::set_display_enable` 写
  `disable_hdmi`（slv_reg30 bit0）。启动顺序改为：
  **消隐 → 清空两帧 → render → submit_frame(0) → 编程 rd_addr → 解除消隐**，
  使 PL 首次扫描读到的就是有效帧 0。

## 7. 状态红线

- 本文只做只读审计 + 软件缓解，**不改 RTL/XDC/位流**；冻结位流
  `combined_npu_hdmi_disable_icap.bit`（SHA `22fec95c…`）保持不变。
- 软件修复未经实机验证只能标 `READY-FOR-M17-GATE10-UI-INTEGRITY-AND-TOUCH-HARDWARE-TEST`，
  绝不写 `SCREEN_PASS / DISPLAY_INTEGRITY_PASS`。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
