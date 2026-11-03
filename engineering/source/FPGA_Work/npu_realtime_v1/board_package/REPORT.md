# iCraft 3.39 / ZG330 常驻进程连续推理 — 只读审计报告

本文是「先审计再修改」的审计结论，全部基于 iCraft 3.39.0 官方头文件与设备文档
（`C:/Icraft/CLI v3.39.0/`）。未依赖任何对 API 名称的猜测；未写任何私有寄存器。

## A. 根因

`Session::forward()` 对 ZG330 后端是**异步**的：它返回一个输出 `Tensor`，其「是否完成」
由两个成员编码（`icraft-xrt/core/tensor.h`）：

```cpp
class TensorNode {
    ...
    bool ready_ = true;                                      // 软件 ready 缓存，默认 true
    std::function<bool(const Device& device)> check_func_;    // 硬件完成状态轮询
};
```

`Tensor::waitForReady()`（tensor.h:195-219）的关键实现：

```cpp
auto mptr = get_mutable();
if (mptr->ready_) return true;               // ① ready_==true 直接返回，不查硬件
...
while (!mptr->check_func_(device)) { ... }  // ② 只有 ready_==false 才轮询 check_func_
mptr->ready_ = true;
```

两处共同导致「一帧旧结果」：

1. **软件缓存不重 arm**：复用 Session 时，`Session::forward()` 从 `SessionNode::tmap_`
   返回**同一个** `TensorNode`，上一帧 `waitForReady()` 已把它置 `ready_=true`。下一帧
   `waitForReady()` 在①处短路，直接读到上一帧输出。
2. **硬件完成状态是单调的、不重 arm**：ZG330 后端的 `check_func_` 轮询 FPGA 的
   层计数 / 状态寄存器（`zg330_device.h` 的 `FPGA_LAYER_CNT_REG=0x0C`、`FPGA_STATE_REG=0x08`，
   `HardOpInfo::sync_idx = <network_view_idx, layer_count>`）。该计数/状态在同一个 Device
   生命周期内**单调递增、不回零**，只有 Device 初始化（`Open`）或 `Device::reset` 才清除。
   因此即使每帧新建 Session/Tensor（`ready_=false`），②处 `check_func_` 也因计数器已达标
   立即返回 true → 仍读到上一帧输出。

这与 7 组真板实验完全吻合：**只有每帧 `Device::Close/Open`（exp4）** 重建了硬件完成状态
（12/12）；所有「保持 Device 常驻」的方案（exp0/1/2/3/5/6）都是 1~5/12。

## B. 可用的官方 API 与证据

| 用途 | API | 证据 |
|---|---|---|
| 完成等待 | `Tensor::waitForReady(timeout)` | tensor.h:195，轮询 `check_func_` |
| 就绪查询 | `Tensor::isReady()` | tensor.h:136 |
| **软件重 arm** | `Tensor::setReady(bool)` | tensor.h:99「设置张量的状态」 |
| 状态检查函数 | `Tensor::setCheckFunc(CheckFunc)` | tensor.h:93 |
| **硬件重 arm** | `Device::reset(int level)` | device.h:742 |
| 层计数（只读） | `ZG330Device::layerCount()` | zg330_device.h:209 |
| 设备检查 | `Device::check(int level)` | device.h:750 |

`Device::reset(level)` 的 level 语义在**两份**官方设备文档中一致（`docs/axizg330aiu/index.html`
与 `docs/socketzg330aiu/index.html`）：

```
0 : 复位全部状态，包括 FPGA, NPU
1 : 只复位 FPGA 状态
其他： 无效值，不会做任何操作
```

（注：axi 文档的复位小节标题误写为「AXIQL100AIUDevice」，但内容与 socket 文档一致，属于
复制粘贴笔误，不影响 level 语义。）

**审计确认：不存在** `finish / synchronize / release / rebind / flush / barrier` 之类的
官方同步接口（全 SDK 头文件 grep，仅 `serialize.h` 有一个无关的 `finish`）。因此
`waitForReady` 是唯一的官方完成等待接口，`setReady` 与 `Device::reset` 是仅有的重 arm 接口。

## C. 显式禁止（本轮不碰）

- 私有 FPGA/NPU 寄存器：`FPGA_STATE_CLEAR 0x04` / `FPGA_STATE 0x08` /
  `EXHS_VLD 0x20` / `EXHS_ACK 0x28` / `FPGA_RESET 0x34`（任何 `/dev/mem` 写）。
- `setOpWait()` / `getOpWait()`（握手寄存器，header 有声明但**未文档化语义**）。
- `clearMMUCache()`、`icoreCalc()`。
- 假延时、丢首帧、整体平移结果、假预热帧、把「每帧独立进程」宣称为实时。

`layerCount()` 仅**只读**观测（不改任何状态）。

## D. 尚需真板确认的语义（若 sweep 不 PASS 则报 FMSH）

`Device::reset(1)` 的「只复位 FPGA 状态」是**文档化但粗粒度**的描述：文档未说明它是否
会清掉 `Session::apply()` 已部署的指令/权重，以及是否足够快。因此 `npu_realtime` 用
`--rearm` sweep 把每个机制各测一遍（每次只改一个变量）：

- `none`（复现 2/12）
- `setready`（软件重 arm，单独验证 ready_ 缓存是否就是全部问题）
- `reset1`（硬件重 arm，最可能的最小修复）
- `reset1_apply`（reset1 + 重新 apply，覆盖「reset 会清掉已部署状态」的可能）
- `reopen`（已知 12/12 的正确性对照，用于校验 harness）

若 `reset1`/`reset1_apply` 仍不 PASS，则说明需要更细的完成握手语义，届时应带着本报告
与 `RT_*` 输出向 FMSH FAE 书面确认 `getOpWait/setOpWait`/私有状态寄存器的精确语义。

## E. 生命周期与每帧同步（`npu_realtime.cpp` 的设计）

- **Device 只 Open 一次、Close 一次**（持久路径）；Network 只加载一次；Session 只创建
  一次并 `apply()` 一次。
- 每帧：反量化 SInt8→FP32 → 建输入 Tensor → `[re-arm]` → `forward()` → `waitForReady()`
  → `read()` 拷贝 logits（纯 `std::vector<float>`，不借用 Session 内对象）。
- 重 arm 位置：`reset1`/`reset1_apply` 在**每帧 forward 之前**（首帧除外，首帧无陈旧态）；
  `setready` 在 **forward 之后、waitForReady 之前**。
- 销毁顺序与 fpga_npu_joint_v1 一致：输出 Tensor → 输入 Tensor → Session → Device::Close；
  `reopen` 路径用 RAII `DeviceGuard` 保证每帧 Device 一定被关闭且不早于 Session/Tensor 销毁。
- 全程不写任何 FPGA 寄存器；`layerCount()` 仅读取记录 `layer_b/layer_a` 用于观测。

## F. 验证与 PASS 判定

- `--test sequence --frames 100`：帧 7..18 循环，argmax 对 `reference_argmax.txt`，
  统计 `match / delay_shift / timeout / error`。PASS = 全匹配、`delay_shift=0`、
  `timeout=0`、`error=0`。
- `--test alternating`：先用已知正确的 `reopen` 路径取帧 7（BPSK argmax0）与帧 10
  （QPSK argmax1）的真值 logits 作为基线，再在持久 Device 上交替跑 7/10，**逐帧比对
  完整 logits**（max-abs-diff，阈值 1e-3），而非只比 argmax。任何陈旧输出都会表现为
  对自身帧基线的 logits 偏差超标。PASS = 无 stale、argmax 全对、两帧 logits 明确可分。

`run_realtime.sh` 跑 3 轮 100 帧 + 1 轮交替测试，全部 `RT_RESULT=PASS` 才 exit 0。
