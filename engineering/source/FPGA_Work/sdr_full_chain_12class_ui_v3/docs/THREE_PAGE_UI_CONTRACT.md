# 三页 UI 契约（任务 39e5 UI v3 · M5 + M14 生产者接线）

> 状态：**生产者接线完成（READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST 的软件里程碑）**。
> 渲染：`ui_sw/ui_render.{hpp,cpp}`（Style A，新增 `render_parameters` / `render_mode`）。
> 桥接：`board_package/ui_state_map.hpp`（`map_to_state` 填充 v3 测量/运行态字段 + 生产者回传 work_mode/run_state）。
> 服务端：`board_package/board_ui_live_12class.cpp`（页面分发，只显示、不产生产） 。
> 触摸：`board_package/touch_geometry.hpp` + `touch_evdev.hpp`（三区导航不变，仅标签名更新）。
> 主机测试 `host_tests/test_ui_v3_pages.cpp`（30 断言，ASan/UBSan 零失败）。

## 1. 目的

把既有单页分类 UI 升级为**三页**：CLASSIFY（实时分类结果）、PARAMETERS（M3 轻量 DSP
参数测量 + M1/M2 运行态）、MODE（工作模式 FIXED/AUTO LOCK/BAND SCAN）。顶部状态徽标
（LIVE/STALE/ERROR/MOCK + 模型短 SHA）与底部信息条（SNR/LATENCY/FRAME/SOURCE）三页共享；
底部触摸导航三区切换。**触摸导航状态机与几何不变**，仅标签名随页名更新，故 smoke_v2 触摸
回归仍适用（`test_touch.cpp` 45 断言继续通过）。

## 2. 页面布局（1280×720 Style A，横向 5px / 纵向 6px 网格）

| 页 | 渲染函数 | 内容 |
|----|----------|------|
| CLASSIFY（页 0） | `render_main` | 顶部结果卡（argmax 类名 + 置信度 + 置信条）+ 双列 12 类概率卡 |
| PARAMETERS（页 1） | `render_parameters`（新增） | 左卡 SIGNAL & SPECTRUM（8 项）+ 右卡 LEVEL & MODEL（8 项） |
| MODE（页 2） | `render_mode`（新增） | 三张模式卡（FIXED/AUTO LOCK/BAND SCAN，激活高亮）+ 当前模式 + M1/M2 运行态 |

- 三页都画 `draw_header`（标题 + 状态徽标 + 模型短 SHA）+ `draw_info_strip`（SNR/LATENCY/
  FRAME/SOURCE）+ `draw_nav`（底部三区）。
- 底部导航标签：`CLASSIFY` / `PARAMETERS` / `MODE`（`draw_nav` 三区几何不变，
  `touch_geometry.hpp` 的 `kNavY0=630` / `kNavY1=719` / `kTabCount=3` 不变）。

## 3. PARAMETERS 页数据来源

| 键 | 来源 | 无数据时 |
|----|------|----------|
| power_dbfs / noise_floor_dbfs / snr_est_db / psd_peak_prominence / occupied_bins / occupied_bw_hz / spectral_centroid_hz / clip_ratio | M3 `measurements`（频谱域，M14 由生产者每帧真实测量） | `--` |
| rms_counts / peak_counts / papr_db / model_rms | M3 `measurements`（原始/模型域） | `--` |
| presence / level_mode / model_scale / rf_gain_db | M1/M2 运行态（M14 生产者每帧回传） | `--` / `--` / `1.000x` / `0.0 dB` |

- 测量派生数字以 `st.meas.valid`（== `ResultFrame::has_measurements`）门控：无 v3 生产者时
  显示 `--` 占位，**绝不显示假零**。M14 后 Gate 9 每帧都产真实测量，PARAMETERS 页不再只有占位。
- `model_scale` / `rf_gain_db` 来自运行态（恒有安全默认 1.0 / 0.0），不冒充测量值。

## 4. MODE 页与生产者/UI 的边界（M14）

- `UiState::work_mode` / `running` **由 `map_to_state` 从每条 `12class-chain-v2` 结果帧写入**
  （生产者回传的权威 `work_mode`/`run_state`；`mode_from_token` 把 wire token 转显示名，空 token
  回退 FIXED）。UI 服务端**不自改**这些字段冒充模式生效。
- 反向控制通道由 **Gate 9 生产者**唯一持有（`board_mode_ctl` 是客户端），UI 服务端不持有
  ModeState；未知字符串回落按 FIXED 卡高亮（不越界、不崩溃）。

## 5. 触摸导航回归

- 触摸映射（swap-XY / invert-X / invert-Y / 裁剪到屏内）、三区命中、UP 边沿翻页、
  `debounce_ms` 折叠——**全部不变**，仅在注释与导航标签名上把 `MAIN/DIAGNOSTICS/TOUCH`
  更新为 `CLASSIFY/PARAMETERS/MODE`。
- `touch_geometry.hpp` 的语义红线不变：触摸只切页，绝不改类别契约/分类结果/TX 功率/RF 路径。
- 既有 `host_tests/test_touch.cpp`（45 断言）在 M5 后仍全 PASS（触摸回归通过）。

## 6. 主机测试（`test_ui_v3_pages.cpp`，3 组 / 30 断言）

1. **v3 映射**：`map_to_state` 从含 `measurements` 的 v3 帧复制全部 12 个测量标量 +
   presence/level_mode/model_scale/rf_gain_db；`work_mode`/`running` 由生产者回传 token
   （`AUTO_LOCK`→显示 `AUTO LOCK`、`RUNNING`→running，空 token 回退 FIXED）。
2. **v1 默认**：无测量/运行态的帧 → `meas.valid==false`、`presence=="--"`、`level_mode=="--"`。
3. **渲染**：PARAMETERS（有数据 + 占位）与 MODE（FIXED/AUTO LOCK/BAND SCAN + 未知模式）
   均渲染出大量非背景像素，无越界（ASan/UBSan 守护真实边界）。

## 7. 红线

- 三页均 fail-safe：无数据/占位/未知模式只降级显示，绝不崩溃、绝不伪造数值。
- 状态徽标语义不变：MOCK 永不画成 LIVE；异常帧画 ERROR；静默喂流画 STALE。
- UI 只显示生产者回传的权威状态，绝不本地自改 work_mode/run_state 冒充模式生效。
- 未实机验证只标 `READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST`。
