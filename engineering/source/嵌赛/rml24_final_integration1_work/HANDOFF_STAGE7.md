# 第七项交接：24 类最终双 SDR 闭环与板端 UI 集成

> **已被最终实机交付取代（2026-10-27）。** 本文件是上板前准备记录，不再是
> 最新执行入口。当前环境对应的权威文件为：
> `F:\嵌赛\rml24_stage7_execution_20261027\NEXT_AGENT_HANDOFF_STAGE7_VERIFIED.md`
> 与
> `F:\嵌赛\rml24_boot_persistence_20261027\HANDOFF_BOOT_PERSISTENCE.md`。
> 最新实机结果为 475/480（98.96%），SD 持久化、软件重启和物理断电自启均已
> 验证；长期稳定性测试仍按用户明确要求暂不执行。

日期：2026-10-27  
状态：`READY_FOR_STAGE7_BOARD_INTEGRATION_RAW_REPLAY_PENDING`

这表示电脑侧准备已经完成，可以进入上板集成；不表示已经取得新的
`RF_PASS`、`HDMI_PASS`、aarch64 构建通过或开机自启动通过。

## 1. 不要重新做的已冻结结论

- 最终接收恢复候选：`recovery/candidate_two_dc.py`
  - SHA-256：`e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a`
- 冻结 BF16 模型 raw：
  `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151`
- 冻结 BF16 模型 JSON：
  `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42`
- 固定条件真实 RF 独立验证：候选 `463/480 = 96.46%`，原处理
  `403/480 = 83.96%`，修正 60 帧、回退 0 帧、捕获失败 0 帧。
- 测试范围：24 类自行生成的 RadioML 张量兼容纯净 IQ、公开固定前后参考、
  双 Pluto 同轴、2.4 GHz、2.56 MS/s、18 MHz、TX -40 dB、RX 35 dB、
  1024 点载荷重复 8 次。不能外推成任意发射机/无前导/空口/扫频结论。

## 2. 电脑侧已经完成

工作树：`F:\嵌赛\rml24_final_integration1_work`

- 正式 PC TX：公共清单只含 `seq/file/SHA`，控制网只传 `seq`。
- 正式板端 RX：默认只运行 candidate；paired 仅诊断；失败帧不强行分类。
- 原始 24 类保持不合并，AM-SSB-WC/SC 仍是两个类别。
- 同一恢复张量同时生成 NPU 输入、256 点星座和 256-bin 相对频谱。
- UI 三页：24 类分类、相对频谱/瀑布、恢复 IQ 星座。
- 板端包不含标签、期望预测、private truth、电脑判分数据。
- PC 包含 240 个不同波形及仅限电脑端的 private truth 和正式判分器。
- 板端包已内置经过验证的 UI 基线源码 `base_ui`，不用再猜旧 UI 工程目录。

最终回归证据：

- Python：24/24 PASS。
- C++ 24 类严格解析器：4/4 PASS。
- 完整 UI 临时组装并全链接：PASS。
- 冻结证据审计：36/36 PASS。
- 两轮历史结果重新计分：403/480 → 463/480，60 fixes，0 regressions。
- 两个包确定性构建、独立解包、逐文件 SHA、单层 gzip：全部 PASS。

## 3. 唯一有效的两个部署包

目录：`F:\嵌赛\rml24_final_integration1_work\dist`

1. 板端真值隔离包：
   `rml24_final_stage7_board_overlay.tar.gz`
   - SHA-256：`21c426ef5f0bc41565d789ec7f1f2b88e48f5dab52708fb3d33286d31fdda9de`
   - 174 个成员（含逐文件 `SHA256SUMS.txt`）

2. 电脑 TX/自测包：
   `rml24_final_stage7_pc_selftest.tar.gz`
   - SHA-256：`e23cf53c249f8b2c17611a8047fc0b583fc92be51a17b57359138a14362c61a3`
   - 246 个成员，其中波形文件恰好 240 个

旧 SHA/旧包不得再用。完整命令见板端包内 `docs/BOARDTEST_STAGE7.md`。

## 4. 下一位执行者的顺序

### A. 上板前

1. 分别上传两个包：板端包到板子，PC 包留在电脑。
2. 对两个 tar.gz 核对上面的完整 SHA。
3. 解压后分别按包内 `SHA256SUMS.txt` 逐文件复核。
4. 确认 PC `192.168.126.10/24`、板端 `192.168.126.49/24` 可互 ping。
5. 确认 PC 只看到 TX Pluto，板端只看到 RX Pluto；记录两个 URI。

### B. 板端集成

1. 使用包内 `base_ui` 和 `deploy/assemble_stage7_board_tree.sh` 生成新树；
   不覆盖已有能工作的树。
2. 在新树运行 `board_package/build_ui_live_rml24_final.sh`。
3. 必须看到 `UI_BUILD_RESULT result=PASS`。
4. 烧入/加载已经验证过的 HDMI 位流后先启动 UI；必须看到：
   - `UI_VERSION_CHECK ... ok=YES`
   - `UI_FB_READY ...`
5. 再启动 PC TX，最后启动板端 RX。PC 地址固定为 `192.168.126.10`，
   控制端口为 `39012`。

### C. 先小后大

正式包当前清单是 240 帧。第一次建议复制清单生成只含 24 帧的临时冒烟清单，
仅验证通信、恢复、NPU、UI 和恢复动作；冒烟成功后再恢复原始 240 帧清单跑正式
全量。不要用冒烟准确率代替 240 帧结果。

### D. 离线判分

把板端 `<RUN>/capture/results.json` 复制回 PC 包，执行：

```powershell
python -I scripts/score_stage7_run.py `
  --expected truth/expected_private.json `
  --results <COPIED_RESULTS_JSON> `
  --out stage7_score.json
```

固定分母为 240；缺失、恢复失败、推理失败全部计错，不得剔除。

## 5. Stage 7 的通过条件

- PC TX 与板端 RX 完成全部请求帧，TX/RX 均恢复原状态。
- candidate 文件和模型 SHA 与本文件一致。
- 板端没有 private truth/标签/期望预测，也没有逐样本补偿参数。
- 24 类不合并；UI 分类、瀑布和星座实时更新。
- 星座与频谱来自同一恢复张量，不是模拟动画或文件回放。
- 失败恢复不显示伪造类别。
- 正式 240 帧以全分母判分，并保存混淆矩阵与每类准确率。
- 停止后再完整运行一次，确认不是单次偶然成功。

## 6. 仍然诚实保留的缺口

1. 本轮未在 aarch64 板端编译，也未实际连接 HDMI/触摸屏跑新 UI。
2. 新正式入口尚未重新取得一轮 240 帧 RF 结果；96.46% 来自已经冻结的两轮
   独立验证证据，不是 Stage 7 新跑结果。
3. 历史 480 份板端 raw capture 尚未复制到当前 F 盘，所以严格 raw→tensor
   逐字节复放仍是 `PENDING_CAPTURE_COPY`。这不否定既有结果，但不得宣称该项已闭合。
4. HDMI 位流掉电持久化是独立问题；本包只负责运行时 UI，不宣称重启自动显示。
5. PC TX 与板端 RX 仍依赖已验证的 `pluto_link_probe.py` / `pilot_recovery.py`
   和板端 `npu_stream`/模型目录。它们不是这次算法修改内容，执行时必须给出真实路径。

## 7. 红线

- 不在冻结 R1/R2 或本次正式 240 帧结果上继续调参后仍称其为独立验证。
- 不把 private truth 上传板端。
- 不恢复 23 类 AM-SSB 合并。
- 不按类别或样本身份选择恢复参数。
- 不因门拒、缺帧或失败而缩小准确率分母。
- 未取得板端证据前，不写 `RF_PASS`、`HDMI_PASS`、`PROJECT_COMPLETE`。

交接结论：第七项的电脑侧准备已经完成；下一动作是按上述顺序进行板端集成，
而不是继续修改接收算法或模型。
