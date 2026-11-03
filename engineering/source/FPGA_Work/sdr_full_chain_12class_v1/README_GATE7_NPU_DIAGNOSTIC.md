# Gate 7 十二类 NPU 低匹配率诊断（补丁）

任务 39e5 第二批（十二类 Gate 6–9）。板测 Gate 7 现象：`matched=3/240,
match_rate=0.0125`（**低于随机 8.3%**），但 ONNX 黄金集自洽性 98.3%。本补丁新增
`--diagnostic` 诊断模式 + 一套离线成对验证证据，用于**定位板端真机 NPU 执行异常**。
状态：**`NEEDS-GATE7-NPU-CONTRACT-FIX`**（未上板复测，**非 PASS**）。

## 0. 结论先行（离线审计已确认的事实）

| 审计项 | 结论 |
|---|---|
| 编译产物 `model_12class.json/.raw` 本身 | **正确**。fake_qf Host 全 240 条 = **237/240 (98.75%)**，与 ONNX 黄金自洽性 98.3% 一致，甚至略高 |
| 真实 int8 语义（Host，无反量化近似） | **忠实**。仅把 margin 极小的 64QAM→16QAM 边界样本翻到 16QAM，其余 12 类全部 argmax 一致 |
| C++ 封装 `npu_classifier.hpp` | **正确**，与已上板通过的 8 类 `npu_only_smoke` 逐行一致 |
| 输入布局 / 量化契约 | **正确**。input_000 四种布局（planar/交织/IQ交换/Q取反）均 argmax=0(OOK)，planar 与契约吻合 |
| 校准数据 252 条 | **正确**。全 8192B、fp32 planar `[I1024][Q1024]`、forward_list 1:1 对齐、全 SNR 域（RMS 0.19–11.3，peak 最大 43） |
| 黄金集格式/传输 | 模型与黄金 SHA/字节与板端一致（此前已排除传输损坏） |

**板端 1.25% 无法在离线复现**：同一份 json/raw + 同一批输入，离线 fake_qf 98.75%、
真实 int8 ~95.8%。因此板端异常指向 **ZG330 真机执行侧**（而非模型/封装/量化/校准）。
`--diagnostic` 就是要抓取板端**逐条真实 logits**，把「恒定垃圾值 / logits 正确但
argmax 错误 / logits 排列错位 / NaN/Inf / 单类偏置」这几种失败模式区分开。

## 1. 板端现象与已知排除项

- 模型与黄金 SHA/字节与本地一致 → 排除传输损坏。
- `Device::Open` 成功、240/240 全完成、无超时无异常 → 排除「没跑起来」。
- Gate 7 结果 `matched=3/240 (0.0125)`，低于随机 → 不是「差一点」，是「几乎全错」。
- ONNX 黄金自洽性 98.3% → 黄金集本身可信。

离线复现（本补丁证据）：
```
verify_all_240.py   fake_qf Host 全 240 条   matched=237/240 (0.9875)
                    3 条 mismatch 全部 ref=10(64QAM) -> pred=9(16QAM)
verify_paired.py    每类 2 条 + 3 条 mismatch   fake_qf 24/27、real-int8 23/27
                    所有翻转集中在 64QAM 且 ONNX margin<0.25 的边界样本
verify_calibration.py 252 条全 8192B fp32 planar，forward_list 1:1 对齐，bad=0
layout_abcd.py      input_000 四种布局均 argmax=0(OOK)
```

## 2. 本补丁改了什么

### 2.1 `board_package/board_gate7_12class_npu.cpp`（唯一代码改动）

新增 `--diagnostic` 标志（默认关闭，**不改变正式 0.90 门限**）。开启后逐条缓存
NPU 返回的 12 维原始 logits，循环结束后输出 `DIAGNOSTIC_BEGIN ... DIAGNOSTIC_END`：

1. 前 24 条 `sample=/ref=/pred=/label=/logits=[12]`；
2. `logits_total= finite= nan_inf= min= max= mean=`（全体 logits 统计）；
3. `pred_hist=` 12 类预测直方图；
4. 12×12 `confusion_row_%02d_<类>=` 混淆矩阵。

**新增 NaN/Inf 失败即停**：任一 logits 非有限值时 `nan_inf>0`，强制
`result=FAIL` + 退出码非零（在 0.90 门限之外叠加的硬门，见下「红线」）。

### 2.2 离线证据脚本（`.diag/`，复现用，非板端必需）

- `verify_all_240.py` — fake_qf 全 240 条比对（237/240）。
- `verify_paired.py` — 每类 2 条 + 3 条 mismatch，ONNX vs fake_qf vs real-int8 成对。
- `layout_abcd.py` — input_000 四种输入布局 forward。
- `verify_calibration.py` — 252 条校准数据格式/对齐/RMS/peak 校验。

## 3. 复测命令（板端，仅用户本人执行）

```bash
# 1) 解包覆盖（补丁相对工程根目录）
cd sdr_full_chain_12class_v1
tar xzf gate7_npu_diagnostic_patch.tar.gz

# 2) 自校验（必须全 OK）
sha256sum -c SHA256SUMS.txt

# 3) 重编译（ICRAFT_CMAKE_DIR 换成板端实际路径）
ICRAFT_CMAKE_DIR=/usr/cmake ./board_package/build_npu_on_board.sh --gate7-only
# 产物自动装到顶层 bin/board_gate7_12class_npu

# 4) 板端复测（先跑诊断模式抓逐条 logits；run 脚本已留 "$@"，可直接追加 --diagnostic）
./bin/board_gate7_12class_npu --diagnostic --golden=deployment_golden --count=240
#    等价：./scripts/run_gate7.sh --diagnostic
#   注意输出里的 DIAGNOSTIC_BEGIN ... DIAGNOSTIC_END 整段，回传给我分析。
# 5) 正式门限复测（判据不变）
./bin/board_gate7_12class_npu --golden=deployment_golden --count=240
```

## 4. 如何读 `--diagnostic` 输出（失败模式判读）

| 诊断输出特征 | 指向的根因 | 下一步 |
|---|---|---|
| `nan_inf>0`（应已直接 FAIL） | 真机算爆/未初始化 logits | 检查 NPU 数据搬运/同步 |
| `pred_hist=` 几乎全挤在 1 个类 | 恒定垃圾 logits（如全为某常数/全 0） | 真机 NPU 没真算，查权重加载/DMA |
| logits 数值合理但 argmax 整体错 | 输入布局/半字序在真机端被反转 | 对照 layout_abcd.py 的 B/C/D 模式 |
| `pred_hist` 均匀但混淆矩阵呈固定错位 | logit 通道排列错位（permutation） | 查输出 tensor 通道序 |
| 只有 margin 小的 64QAM 翻 16QAM（<0.25） | **正常量化边界翻转**，与离线一致 | 这是可接受的，非 bug |

红线：`match_rate >= 0.90` 判据**不变**；模型/黄金集/类顺序/量化契约**不变**；
不引入 HostBackend 回退掩盖 NPU 错误；不修改黄金答案或调门限。

## 5. 状态红线

- 本补丁离线制作，板端复测由用户本人执行；我（助手）不碰板、不写 Flash。
- 上板复测 `match_rate >= 0.90` 且 240/240 完成、无 NaN/Inf、退出码真透传之前，
  状态只写 **`NEEDS-GATE7-NPU-CONTRACT-FIX`**，**绝不写 PASS/READY**。
