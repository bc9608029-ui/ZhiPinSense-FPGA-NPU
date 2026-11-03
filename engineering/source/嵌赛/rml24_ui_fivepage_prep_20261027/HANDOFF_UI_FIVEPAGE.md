# 五页 UI 候选交接

状态：`PC_BUILD_PASS_FREQUENCY_INPUT_PROTOCOL_PENDING_BOARD_INTEGRATION`

## 已完成

- 基于已验证四页瀑布候选建立独立副本，没有覆盖原包。
- 底部导航改为五页：CLASSIFY / MEASURE / WATERFALL / CONSTELLATION / SETUP。
- 24 类主页面从完整类别分页改为 Top 3。
- 数值参数与瀑布正式拆页。
- 星座页和设置页索引随五页导航修正。
- 只有第五页允许发送模式/启停控制，其他页面仍为只读。
- WSL g++ 15.2.0 使用原 `-Werror` 构建脚本完成 x86-64 离线编译；这不是 aarch64 板端构建。

## 未完成且不得误报

- 第五页的定频频率、扫频起止/步进输入尚未接入接收端；协议见 `FREQUENCY_CONTROL_CONTRACT.md`。
- 扫频第一页目前仍复用单信号 Top 3，没有实现多条发现列表的数据模型。
- 扫频全带拼接瀑布尚未实现；当前瀑布反映当前捕获/锁定频点。
- 未上板、未实屏、未做触控命中和性能测试。

## 后续最短路径

1. 实现控制服务的三条频率命令和 SDR 读回。
2. 在 UI 事件中加入 requested/applied tuning 与 scan progress。
3. 实现第五页数字键盘。
4. 实现最多 5 条的扫频发现缓存；第一页选择项驱动测量、瀑布和星座。
5. 上板构建，逐页截图并做触控边界测试。

源码根：`ui_fivepage_candidate/`

构建：

```bash
cd ui_fivepage_candidate/board_package
bash build_ui_live_rml24_final.sh
```

成功标志：`UI_BUILD_RESULT result=PASS`。

必须在 aarch64 板端重新构建。`host_tests/bin/*.host_x86_64` 只证明离线编译，不得部署到板端。
