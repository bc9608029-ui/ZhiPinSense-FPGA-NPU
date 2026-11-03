# 未来实时集成接口（future_live_integration.md）

本离线原型**只实现了 `FileIqFrameSource`**。实时来源（UnixSocket / SharedMemory）在本阶段**只定义接口、不做实现**，且**不修改** `/run/sdr_amr_ui_rml23.sock` 的既有协议。

## 1. 帧源接口（已定义，见 `src/IqFrame.hpp`）

```cpp
class IqFrameSource {
public:
    virtual ~IqFrameSource() = default;
    // 拉取下一帧。返回 false 表示流结束或硬错误（error 被填充）。
    // 损坏帧必须停止播放，绝不自动跳过。
    virtual bool nextFrame(IqFrame& frame, std::string& error) = 0;
};
```

`IqFrame` 是 Qt-free 的帧结构（stage/dtype/layout/complex_count/payload_sha256/i/q 等，见 `src/IqFrame.hpp`）。渲染器（`ConstellationItem`）和 Controller（`src/main.cpp`）只消费 `IqFrame`，与来源无关。

## 2. 已实现

- `class FileIqFrameSource : public IqFrameSource`（`src/IqFrameLoader.hpp/.cpp`）：包装单个 sidecar JSON，`nextFrame()` 返回一次后即 EOF。

## 3. 未来桩（本阶段不实现）

```cpp
// class UnixSocketIqFrameSource : public IqFrameSource
//   未来：连接 /run/sdr_amr_ui_rml23.sock（AF_UNIX SOCK_STREAM，JSON-lines，
//   schema "rml23-chain-v2"），逐行解析为 IqFrame。
//   注意：该 socket 协议属既有板端 UI 契约，集成前必须逐字段对齐，
//         不得在本阶段修改。

// class SharedMemoryIqFrameSource : public IqFrameSource
//   未来：从共享内存环缓冲读取 [2,1024] 张量 + 元数据。
```

## 4. 实时集成时的接入点（Controller）

`src/main.cpp` 的 `Controller` 目前直接调用 `cst::load_sidecar_frame()` / `cst::list_sidecars()`。接入实时源时只需：

1. 在 `Controller` 中增加一个 `std::unique_ptr<cst::IqFrameSource>`；
2. 把 `onTimer()` / `step()` 里的“读 sidecar 文件”替换为 `source_->nextFrame(frame, err)`；
3. 复用现有 `applyFrame()`（抽稀 / 坐标 / 颜色 / 推送渲染全部不变）。

这样渲染路径、坐标数学、校验语义与离线模式完全一致，实时模式只是换了帧来源。

## 5. 不改动的红线

- 不修改 `/run/sdr_amr_ui_rml23.sock` 协议；
- 不实现网络传输；
- 不加入分类算法 / 模型权重；
- 不把过采样数据伪造成 SYMBOL_SAMPLED。
