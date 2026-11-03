# 增益与重复段数：测试前准备

本目录是独立实验工具，不替换正式服务，不改模型、检测门或位流。最高状态OFFLINE_PREP_VERIFIED_RF_PENDING，不是效果通过。发射GUI扩展暂缓。

## 实验口径

先固定TX -40dB、2.56MS/s、18MHz、公共帧和八次重复；RX固定2.4GHz。先比较manual 25/35/45dB与slow_attack AGC。每个增益臂必须重新采集，不能把已有IQ简单缩放冒充改变硬件增益。测试同一冻结消息集合，顺序交错/平衡、保留基线复测，不能按结果挑参数。

随后对每臂保存的同一次raw，冻结two-DC恢复一次，分别以前1/2/4/8段平均后复制到原[8,2,1024]输入；NPU均8窗口，消除输入形状和调用数差异。不能从已经平均复制的输入反推1/2/4效果。本实验只评估可用重复段的平均收益，不能声称已经验证实际TX缩帧效率。是否真正改帧另行设计，不在本包。

## 入口

电脑：`python -I selftest.py`。只模拟设备、纯数字验证，不推理、不发射。依赖numpy/scipy，路径及模型/NPU与本轮稳定版本核对后使用。

板端先停止占用RX的服务，记录原服务状态；不使用旧自动正式回归入口。先无发射/单类短测，再固定24类小规模集合。不要立即跑四臂240项。

```bash
PY=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3
# cd 到本包实际解压位置；OUT必须全新；URI先只读核对
"$PY" capture_gain.py --link /root/amr_rescue_20261025/pluto_link_probe.py \
 --rx-uri usb:1.3.5 --out /root/gain_manual35_new --mode manual --gain 35 --count 120
# 其他臂独立新目录：manual --gain 25、manual --gain 45、slow_attack（不传gain）
```

每个采集入口真实打开RX，默认不从电脑自动运行。TX独立发射，不向RX传类别、时间或尺度。该工具不启动NPU或UI，因此不能与正式RX并发抢SDR。接收配置和原属性恢复写入日志，正常退出另建只读context回读恢复。异常分支保存错误并尝试close，若没有restore_readback.json，不能宣称恢复已确认，须停下核对。AGC原先处于自动模式时瞬时gain本身会变，只核对原模式/采样率/带宽，不要求其瞬时gain保持不变。

AGC采集前后gain读回不证明帧内gain没有变化；须结合头尾恢复残差、同步失败、原始幅度/削顶和分类评估。稳定等待1秒是实验初值，不是稳定性保证。带宽仍18MHz，不做带宽自适应。

```bash
# 先只恢复/准备张量；不加--npu-socket不会推理
"$PY" replay_repeats.py --captures /root/gain_manual35_new \
 --recovery /root/当前稳定树/rml24_final/recovery/candidate_two_dc.py \
 --out /root/gain_manual35_replay_new
# 推理时另起经过身份核验的原npu_stream，追加--npu-socket 本轮独占socket。
```

模型JSON/RAW必须保持28272abc…/c1781aec…；本工具不包含或重编NPU。two-DC SHA硬核验e0aa1202…；Radio SHA硬核验1b248f8f…。每次NPU请求固定8192字节、返回96字节，最终检查frames=有效raw记录数×4臂×8；失败/非有限不能剔分母，不能选择有利窗口。

## 计分与晋级

捕获文件不携带类别，事后主机用TX私有计划与时钟偏移映射。沿用首次有效计划机会而非找正确帧；须先冻结具体时槽、预热、捕获窗口与固定分母。若没有时间映射/真值，不能只用成功raw计算“总体准确率”。本工具输出逐raw/逐N预测与SHA，不自行宣称正式准确率。

同raw比较N臂的正确/错误翻转、恢复覆盖；不同gain臂另比较同步/恢复/端到端正确率、削顶和恢复残差。准备的数据量只支持初筛；小样本相等不证明统计等效。至少新会话复验后才考虑改正式参数。

本轮大体积原始IQ仍在板端，现有电脑摘要不能直接完成真实1/2/4/8推理。需要取回raw或按上面采集。没有板测aarch64验证、真实AGC效果或实际缩帧实验。结束后恢复原本active的服务，不改enable，不写自启动。
