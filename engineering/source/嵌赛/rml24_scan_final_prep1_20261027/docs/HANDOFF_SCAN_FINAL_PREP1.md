# 交接说明：RML24 最终定频 + 扫频 PREP1

## 一句话状态

电脑侧集成准备已经完成；定频基线有真实 RF 证据，扫频新增代码只有主机编译、合成测试和历史真实采集回放证据，尚未上板，不能称扫频完成。

最终传输包位于 `dist/rml24_scan_final_prep1_pc_ready.tar.gz`，外层校验值位于同目录的 `.sha256` 文件。包为单层 gzip，内部 `SHA256SUMS.txt` 覆盖全部 27 个内容文件。

## 先读顺序

1. `docs/PREPARATION_AUDIT.md`：哪些已完成、哪些必须上板。
2. `docs/ARCHITECTURE.md`：本轮为什么不会把能量检测当成识别。
3. `contract/scan_integration_contract.json`：冻结 Stage 7 身份和红线。
4. `docs/BOARDTEST_SCAN.md`：唯一推荐的上板顺序。

## 代码入口

- `runtime/scan_runtime.py`：公共训练段检测、宽频偏估计、LO 计划与扫描选择。
- `runtime/radio_tuning.py`：RX LO 写/读回/flush/restore。
- `runtime/mode_control_server.py`：UI 控制 socket。
- `board_runtime/rml24_dualmode_receiver.py`：FIXED/BAND_SCAN 最终接收入口。
- `board_runtime/run_dualmode_receiver.sh`：NPU + 双模式接收编排。
- `pc_runtime/rml24_scan_tx.py`：只新增公开 `--center-hz` 的 Stage 7 TX。
- `ui_overlay/`：第四个 MODE 页和触控接线的三个增量文件。

## 已通过的电脑侧验证

- Python 主机测试：宽正/负 CFO、噪声反例、覆盖、LO readback/恢复、模式限制、固定 TX 字节一致、无标签静态审计。
- Linux AF_UNIX：UI 需要的 accepted/applied/STATUS 协议实跑。
- C++：四页触控测试通过；完整 UI 用 `-Wall -Wextra -Werror` 编译通过。
- 历史真实 RF：对 Stage 7 保存的原始采集做公共前端 + two-DC 回放；详情见 `results/realrf_scan_frontend_replay.json`。这些数据参与阈值选择，所以只能算开发回放。

## 必须保持的诚实边界

- 475/480 只属于已验证定频 Stage 7，不可自动挪给扫频。
- 扫频的首次发现时延取决于 LO 点数；锁定后才恢复为每帧一次捕获。
- 0.10 是公共参考发现阈值，不是模型准确率门；必须用板端无信号负对照检查误检。
- AUTO LOCK 未实现，服务器会拒绝。
- 不自动修改 systemd，不覆盖 Stage 7 唯一基线。

