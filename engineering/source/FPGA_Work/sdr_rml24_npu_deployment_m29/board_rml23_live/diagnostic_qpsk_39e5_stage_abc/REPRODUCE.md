# Stage A/B/C 复现命令

所有脚本纯 stdlib + numpy + h5py + onnxruntime + onnx + matplotlib，无随机种子依赖（确定性）。
运行环境：Windows，`python` = Anaconda 3.13.5（numpy 2.1.3 / h5py 3.12.1 / onnxruntime 1.30.0 /
onnx 1.23.1 / matplotlib 3.10.7）。**不要用 `-I`**（onnxruntime 装在用户 site-packages，`-I` 会跳过）。

```bash
cd F:/FPGA_Work/sdr_rml24_npu_deployment_m29/board_rml23_live/diagnostic_qpsk_39e5_stage_abc

# Stage B —— 域对比（产 out/domain_comparison.json）
python stage_b_domain_comparison.py

# Stage B 图表 + spectral_summary 补全（产 7 张 fig_*.png）
python stage_b_charts.py

# Stage C —— 12 项预处理消融（产 out/preprocess_ablation.json）
python stage_c_preprocess_ablation.py

# 自洽断言（可选，验证三份 JSON 结构 + 决定性数值不变）
python self_check.py
```

## 输入（只读，逐字节不改）

| 输入 | 路径 | SHA256 |
|---|---|---|
| RadioML HDF5 | `F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5` | `e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38` |
| 划分索引 | `F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz` | `9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335` |
| FP32 ONNX | `F:/FPGA_Work/sdr_rml24_npu_deployment_m29/work/onnx/rml24_24class_opset17.onnx` | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` |
| 真实 78 帧 | `C:/Users/shado/Downloads/rml23_analysis_20261011_225430/rml23_capture_39e5_final_1773383076/live_rx_tensor_*.f32` | 见 `out/domain_comparison.json` 的 `input_sha256` |

## 决定性数值（复现应完全一致）

- RadioML QPSK@30dB FP32 top-1 = **200/200 QPSK**；真实 78 帧 = **0/78 QPSK**（16/64/128/256-QAM）。
- 带宽对齐低通 8.125 kHz：真实 QPSK **35/78（44.9%）**、RadioML golden **179/200**。
- DC 去除：RadioML golden **111/200**（模型 DC 脆弱性）。
- 66 层激活 real/rm RMS 比均值 **1.26**、最大 **1.85**（`features/features.7/conv2/Conv`）。

## 红线

未改模型 / 标签 / golden / 预处理 / RTL / 位流 / Flash / UI；未训练；未写 `*_PASS` / `PROJECT_COMPLETE`；
未用测试帧挑超参（cutoff 由 RadioML 训练域 −20 dB 占用带宽导出）；128 点未插值成 1024 点。
