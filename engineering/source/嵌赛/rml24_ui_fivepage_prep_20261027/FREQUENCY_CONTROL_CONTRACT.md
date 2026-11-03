# 第五页频率输入控制合同

状态：`DESIGN_FROZEN_IMPLEMENTATION_PENDING_BOARD_PROTOCOL_INTEGRATION`

现有控制通道只可靠支持模式切换和 START/STOP。五页显示候选已经编译通过，但不能在没有接收端确认的情况下让输入框假装修改了 SDR。

## 新命令

```text
SET_FIXED_HZ <unsigned_hz>
SET_SCAN_RANGE_HZ <start_hz> <stop_hz> <step_hz>
GET_TUNING
```

## 成功响应

```text
OK command_id=<id> requested_fixed_hz=<hz> applied_fixed_hz=<readback_hz>
OK command_id=<id> requested_start_hz=<hz> requested_stop_hz=<hz> requested_step_hz=<hz> scan_points=<n>
```

UI 只有收到 `OK` 和 SDR 读回值后才能把输入状态标为“已应用”。发送成功不等于应用成功。

## 失败响应

```text
ERR command_id=<id> reason=<INVALID_NUMBER|OUT_OF_RANGE|START_GE_STOP|STEP_INVALID|DEVICE_REJECTED|BUSY>
```

失败时保留上一次已应用值，不允许 UI 自己更新顶部频率。

## 校验

- 频率上下限来自接收器启动配置，不在 UI 中硬编码 Pluto 理论范围。
- `start_hz < stop_hz`。
- `step_hz > 0`，且扫描点数不得超过接收器配置上限。
- 预计首次扫描时间 = 扫描点数 × 实测单点捕获时间，只能标“预计”。
- 切换模式不自动清除用户输入，但只有当前模式相关参数生效。
- 参数改变时必须解除旧锁并重新扫描/捕获。

## 触控输入

- 数字键盘包含 0–9、退格、清空、取消、应用。
- 页面显示单位 MHz，但协议只发送整数 Hz。
- 每个输入框同时显示 requested 与 applied/readback，避免误解。
- BAND_SCAN 输入：起点、终点、步进；缺一不可。

## 尚未实现的部分

- 控制服务解析与 SDR 应用。
- UI 数字键盘和输入框。
- 读回状态加入 UI 事件。
- 板端实际触控、越界反例与调谐验证。

这些项目必须与接收器一起上板验证，不能仅靠 PC 截图验收。
