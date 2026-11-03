# M29 RML23 Stage H-G / Route G fix10 — Task A 官方资料与环境审计（预启动门）

状态：**`M29-RML23-EXTERNAL-PLUTO-RF-TASK-A-AUDIT-READY`**

本审计是 fix10（Route G 双 SDR：外部 Pluto 发射 → 板端 Pluto 接收）在 **§1.2 启动门通过前**唯一允许开展的预备工作之一（官方资料审计）。fix10 的**完整实现与正式打包仍被门禁 BLOCKED**，须先等板端 46 样本回归返回 `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`。

分类约定（每条事实标注其一）：

- **OFFICIAL_EXPLICIT** — 官方文档（ADI / Microsoft / MathWorks）明示。
- **CODE_CONFIRMED** — 本项目既有源码逐条印证。
- **PROJECT_INFERENCE** — 来自本项目既往板测证据 / 记忆的推断，未经官方文档明示。
- **BOARD_REQUIRED** — 必须上板或连接真实设备才能确定，离线不可证。

---

## 0. 门禁状态与本审计范围

- `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`：**尚未返回**。fix9r1 板端 46 样本复测仍 `PENDING`。
- §1.2 允许的预门工作 = 官方资料审计（本文）+ 协议设计 + Windows/WSL 设备枚举脚本 + 不接板的 host 单元测试。
- 本文只做**审计**，不写任何 fix10 实现代码、不打包、不声明可上板验收。
- 基线（§1.1）：`sdr_rml23_live_board_package_iq_rf_loopback_fix9r1.tar.gz` SHA `306873e100a8238e…`（572 内容文件）。不从未收尾的 fix10 草稿、也不从 fix9/fix9r 旧包继续开发。

---

## 1. 官方资料审计

### 1.1 libiio context URI 与 USB 枚举

| 事实 | 分类 |
|---|---|
| `iio_create_context_from_uri("usb:3.80.5")`，格式 `usb:设备:端口:实例`；仅一台 USB 设备时可简写 `usb:`；另有 `ip:x.x.x.x`、`serial:…`。后端 = local / network(ip) / USB / PCIe / serial | **OFFICIAL_EXPLICIT**（[libiio Context Functions](https://developer.analog.com/docs/libiio/main/api/c/context.html)） |
| `iio_info -s` 枚举并打印 `[usb:X.X.X]` / `[ip:…]`；`iio_attr -u usb:…` 指定上下文 | **OFFICIAL_EXPLICIT**（[libiio Usage Model](https://developer.analog.com/docs/libiio/main/usage.html)） |
| libiio v1.x 起除 local 外后端为动态插件（如 `libiio1-backend-usb`）；v0.x 内建 | **OFFICIAL_EXPLICIT** |
| 本项目 `pluto_device_libiio.cpp:192-208`：无显式 URI 时 `iio_create_scan_context("usb",0)` → `iio_scan_context_get_info_list` → 取**第一台** `iio_context_info_get_uri`；有 URI 时 `iio_create_context_from_uri(uri)` | **CODE_CONFIRMED** |
| 序列号 = 上下文属性 `hw_serial`：`iio_context_get_attr_value(ctx_,"hw_serial")`（`pluto_device_libiio.cpp:344`） | **CODE_CONFIRMED**（官方名需上机 `iio_info -u usb:` 复核） |

**fix10 安全含义**：发射侧必须**显式 `--uri` + 显式 `--serial`** 逐字比对（已有 fix10 草稿 `tools/pluto_external_tx.cpp` 注释与 §1.2 均要求）。但「默认 `usb:` 取第一台」的既有后端逻辑**不可**用于双 Pluto（会选错设备），发射工具必须走显式 URI 路径。

### 1.2 WSL2 USB/IP（usbipd-win）拓扑

| 事实 | 分类 |
|---|---|
| `winget install dorssel.usbipd-win`；要求 WSL2 内核 ≥ 5.10.60.1（`wsl --update`） | **OFFICIAL_EXPLICIT**（[Microsoft Learn — Connect USB devices](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)） |
| `usbipd list`（管理员）→ 记 BUSID；`usbipd bind --busid <B>`（一次性，`--force` 若 Windows 驱动占用）；`usbipd attach --wsl --busid <B>`；WSL 内 `lsusb` 校验；`usbipd detach/unbind` 收尾 | **OFFICIAL_EXPLICIT** |
| usbipd-win ≥ 4.0.0 后 **WSL 内无需** usbip 客户端 | **OFFICIAL_EXPLICIT** |
| 附加到 WSL 期间 **Windows 无法使用该设备**（反之亦然） | **OFFICIAL_EXPLICIT / PROJECT_INFERENCE** |

**fix10 含义**：若走「WSL 侧发射 Pluto」，PC 上的 Pluto 必须经 usbipd-win 附到 WSL；期间 Windows 侧 radioconda libiio **不能**同时访问该 Pluto（互斥）。这是发射路径二选一的硬约束，见 §4。

### 1.3 iio_context 生命周期

| 事实 | 分类 |
|---|---|
| context 是**时点快照**：创建后新增设备/触发器不出现，须 `iio_context_destroy` 后重建 | **OFFICIAL_EXPLICIT** |
| 每个 API 独立于创建 context 的函数 | **OFFICIAL_EXPLICIT** |
| 本项目 `close()` 调 `iio_context_destroy(ctx_)`（`pluto_device_libiio.cpp:270`）；`read_rx` 前 `iio_context_set_timeout(ctx_, tmo)`（`:722`） | **CODE_CONFIRMED** |

### 1.4 AD936x 器件族与 TX LO / gain 语义（含一处命名澄清）

| 事实 | 分类 |
|---|---|
| **AD9364 = 1T1R**，70–6000 MHz，<200 kHz–56 MHz；AD9361 = 2T2R（70–6000 MHz）；AD9363 = 2T2R 但 325–3800 MHz / 20 MHz（Pluto 出厂默认） | **OFFICIAL_EXPLICIT**（[ADI AD9361 Family](https://deepwiki.com/analogdevicesinc/TransceiverToolbox/3.1-ad9361-family) / [MathWorks Pluto 参数](https://de.mathworks.com/help/comm/plutoradio/ug/plutoradio-parameters-and-supported-ranges.html)） |
| **TX 无 PA/增益级，只有衰减**：`hardwaregain`（IIO）实为 **TX 衰减**，范围 **−89.75 ～ 0 dB**、步进 0.25 dB（0 dB ≈ ~7 dBm，随频率）；RX gain −3 ～ 71 dB（随频率） | **OFFICIAL_EXPLICIT**（[AD9364 TX gain EZ](https://ez.analog.com/rf/wide-band-rf-transceivers/design-support/f/q-a/107559/ad9364-iio-system-object-transmitter-gain/318710) / [pyadi-iio ad936x](https://analogdevicesinc.github.io/pyadi-iio/devices/adi.ad936x.html)） |
| 本项目器件名：`ad9361-phy`（phy）、`cf-ad9361-lpc`（RX DMA）、`cf-ad9361-dds-core-lpc`（TX DMA）；RX LO = `altvoltage0`(output=true)、TX LO = `altvoltage1`(output=true)；TX `hardwaregain`（衰减）写 `iio_channel_attr_write_double(phy_tx_ch_,"hardwaregain",…)`（`pluto_device_libiio.cpp:218-235,515`） | **CODE_CONFIRMED** |
| 安全上限 `kSafeTxAttenDb=-89.75` / `kSafeTxCeilingDb=-40.0`（`pluto_tx.hpp:38-39`） | **CODE_CONFIRMED** |

**命名澄清（对 §2 措辞）**：任务书 §2 写「AD9361 TX LO」。板端 Pluto Rev.C 实际硅片是 **AD9364（1T1R）**；Linux IIO 驱动把 AD9361/9363/9364 一族统一报为 `ad9361-phy` 器件名。故「ad9361-phy」是**驱动族名**，不是芯片型号。功能无影响，但双 SDR 里两台 Pluto 各自只有 **1 TX / 1 RX**，恰好满足「外部 1 发 + 板端 1 收」的最小拓扑。

### 1.5 采样率 / 带宽 / 12-bit 格式

| 事实 | 分类 |
|---|---|
| AD936x 基带采样率约 520.833 kHz–61.44 MSPS；AD9364 1R1T 经 USB 最高 61.44 MSPS（2R2T 降到 30.72 MSPS，USB 2.0 吞吐限制） | **OFFICIAL_EXPLICIT**（MathWorks） |
| D2 用 **2.56 MSPS**，远在范围内 | **PROJECT_INFERENCE** |
| `set_sample_rate` 同时写 RX/TX phy 的 `sampling_frequency`（`pluto_device_libiio.cpp:465-468`、`pluto_device.hpp:192-196`） | **CODE_CONFIRMED** |
| AD9364 = 12-bit；host int16 满量程 ±2^11 = 2048（`kDacFullScale=2048`）；TX 走 `iio_channel_convert_inverse`（int16→12-bit DAC 字）、RX 走 `iio_channel_convert` | **CODE_CONFIRMED**（`pluto_tx.hpp:41-47`、`pluto_device_libiio.cpp:390,409,557,572,639`） |

### 1.6 cyclic TX buffer 语义

| 事实 | 分类 |
|---|---|
| v0.x：`iio_device_create_buffer(dev,n,cyclic=true)` 提交的缓冲**无限重复**直到 `iio_buffer_destroy`；cyclic 下**不允许再次 push**，改数据须 destroy→recreate | **OFFICIAL_EXPLICIT** |
| **libiio v1.x API 大改**：`iio_buffer_refill/push` 移除，改为 `iio_block` / `iio_stream`（`iio_buffer_create_stream` 等） | **OFFICIAL_EXPLICIT** |
| 本项目用 v0.x API：`iio_device_create_buffer(tx_,n,true)`(cyclic) + `iio_buffer_push` + `iio_buffer_destroy`（`pluto_device_libiio.cpp:534,597,546`） | **CODE_CONFIRMED** |
| 板端 libiio 版本 = **0.26**（`/tmp/sdr_pluto_gate1_5/libiio-arm64`）→ 板端/本项目目标是 **v0.x API** | **CODE_CONFIRMED / PROJECT_INFERENCE** |

**fix10 含义（关键兼容约束）**：任何编译发射工具的宿主，其 libiio 必须是 **v0.x（0.21–0.26）**，否则 `pluto_device_libiio.cpp`（`iio_buffer_push/refill`）**无法编译**。现代发行版 apt 可能装 v1.x —— 须锁定版本。

### 1.7 双独立 Pluto 的 CFO/SRO 来源（fix10 的核心物理量）

| 事实 | 分类 |
|---|---|
| 两台 Pluto = 两颗独立参考晶振。2.4 GHz 载波、±20 ppm → **CFO 至多 ≈ ±48 kHz**；±20 ppm → **SRO**，53760 复采样载荷漂移 ≈ 1.075 采样 | **PROJECT_INFERENCE**（由晶振 ppm 定义导出） |
| fix9 同机回环共用一颗 AD9364 时钟 → **零 CFO/SRO**，故其 `circular_sync` 只假定单整数移位、零频偏 | **PROJECT_INFERENCE**（fix9 审计 + 记忆） |
| TX LO 每 `tx_start_cyclic`（cyclic buffer 重建）重锁 → 逐文件随机相位（fix9 根因） | **PROJECT_INFERENCE**（fix9r 审计） |
| 接收端须逐文件估计/补偿 CFO/SRO/帧起点/相位（这是 fix10 接收 runner 的核心任务，实现属门禁后） | **PROJECT_INFERENCE** |

---

## 2. 环境现实核对（本次实测，BOARD_REQUIRED 前置）

在 WSL（Git Bash `wsl.exe`）实测：

```
usbipd        -> no usbipd
usbip         -> no usbip
pkg-config libiio -> no pkg-config libiio
/usr/lib/x86_64-linux-gnu/libiio* -> no system libiio
iio_info      -> no iio_info
```

即当前 WSL **既无 libiio 也无 usbipd/usbip**，发射工具在 WSL 侧**无法编译、无法运行**。相关环境事实：

| 事实 | 分类 |
|---|---|
| Windows 侧 libiio 在 **radioconda**（Pluto 回环已在该环境跑通，2026-10-05） | **PROJECT_INFERENCE**（[pluto-sdr-bringup 记忆](../../../.claude/projects/F--/memory/pluto-sdr-bringup.md)） |
| 板端 libiio-arm64 0.26 在 `/tmp/sdr_pluto_gate1_5/libiio-arm64` | **CODE_CONFIRMED / PROJECT_INFERENCE** |
| PC 侧 Pluto 的 USB BUSID、`hw_serial`、Windows 是否能被 usbipd `bind`（驱动是否占用） | **BOARD_REQUIRED** |
| 两台 Pluto 之间的真实 CFO/SRO 数值 | **BOARD_REQUIRED**（须链路建立后实测） |
| LO 重调后的实际锁定时间 / 频率沉降 | **BOARD_REQUIRED** |

---

## 3. 架构影响（发射路径二选一，属门禁后 Task B 决策）

任务书把发射 Pluto 描述为「WSL/USB Pluto-A」。但 §2 实测 WSL 无 libiio、无 usbipd，因此存在两条可行路径，**二者互斥**（同一 Pluto 不能同时被 Windows 与 WSL 占用）：

- **路径 (a) WSL 发射**（任务书字面）：装 `usbipd-win`（Windows 管理员）+ WSL 内装 libiio v0.x（0.21–0.26，与板端 API 一致）→ 用草稿 `tools/build_external_pluto_tx.sh` 的 g++ 路径编译。
- **路径 (b) Windows 直发**：直接用 radioconda 的 libiio 从 Windows 驱动发射 Pluto（原生 exe 或 Python libiio 驱动），完全绕开 usbipd。

两条路径共同前置：PC 端 Pluto 的 **USB BUSID + `hw_serial`** 枚举（`BOARD_REQUIRED`，用户提供）。这是 fix10 解锁后（门禁通过）需用户拍板的**第一个架构决策**，本审计只记录、不决定。

---

## 4. 结论

1. **Task A（官方资料审计）完成**：libiio URI/USB 枚举、WSL2 USB/IP、iio_context 生命周期、AD936x 族（AD9364 1T1R 命名澄清）、采样率/带宽/12-bit、cyclic TX、双晶振 CFO/SRO 七项，全部按四分类标注并引用官方源。
2. **最关键的预门发现**：当前 **WSL 无 libiio、无 usbipd** → 「WSL 侧发射 Pluto」目前不可构建；且 WSL 编译必须用 **libiio v0.x**（v1.x API 与 `pluto_device_libiio.cpp` 不兼容）。发射路径 (a) WSL vs (b) Windows 需在门禁通过后由用户决策。
3. **fix10 完整实现与打包仍 BLOCKED**，等待 `ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`（fix9r1 板端 46 样本回归）。本审计未写任何实现代码、未打包、未声明可上板验收。

后续预门可选工作（§1.2 同样允许）：Task C 协议设计、Windows/WSL 设备枚举脚本、不接板的 host 单元测试。

## 5. 官方资料来源

- [libiio Context Functions](https://developer.analog.com/docs/libiio/main/api/c/context.html)
- [libiio Usage Model](https://developer.analog.com/docs/libiio/main/usage.html)
- [Microsoft Learn — Connect USB devices (WSL)](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)
- [ADI TransceiverToolbox — AD9361 Family](https://deepwiki.com/analogdevicesinc/TransceiverToolbox/3.1-ad9361-family)
- [MathWorks — ADALM-PLUTO 参数与范围](https://de.mathworks.com/help/comm/plutoradio/ug/plutoradio-parameters-and-supported-ranges.html)
- [ADI EZ — AD9364 TX gain (attenuation)](https://ez.analog.com/rf/wide-band-rf-transceivers/design-support/f/q-a/107559/ad9364-iio-system-object-transmitter-gain/318710)
- [pyadi-iio — ad936x](https://analogdevicesinc.github.io/pyadi-iio/devices/adi.ad936x.html)
