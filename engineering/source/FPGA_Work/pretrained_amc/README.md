# 预训练信号识别模型库(已下载)

目标:一个**类别可灵活替换**的多分类信号识别系统。以下模型全部带已训练权重,
可直接用于推理或换最后一层(classification head)微调到你的类别集合。

## 已就绪

| 模型 | 目录 | 权重文件 | 大小 | 类别 / 数据集 | 许可证 |
|---|---|---|---|---|---|
| DSC-AMCNet | `dsc_amcnet/` | `dscamcnet_best.pt` + `dscamcnet_int8.onnx` + `ulcnn_fp32_fixed.onnx` + `split_indices.npz` | 37 KB + 58 KB + 53 KB + 1.7 MB | RML2016.10a(11 类),**INT8 量化 + MCU 部署** | MIT |
| AMC-Net | `amcnet/` | `checkpoint/2016.10a_AMC_Net.pkl` + `2016.10b_AMC_Net.pkl` | 各 1.89 MB | 2016.10a(11 类)/ 2016.10b(10 类) | MIT |
| AWN | `awn/` | `2016.10a_AWN.pkl` + `2016.10b_AWN.pkl` + `2018.01a_AWN.pkl` | 507 / 506 / 1546 KB | 2016.10a(11)/2016.10b(10)/2018.01a(24),自适应小波 lifting 网络 | MIT |
| SemiAMC | `semiamc/` | `saved_models/weight_{simclr,sup,tune}.hdf5` | 1.5 / 4.5 / 2.7 MB | RML2016.10a(11 类),自对比 + 半监督 | 无 LICENSE |
| WavesFM | `wavesfm/` | `wavesfm-v1p0.pth` | 29.8 MB | 无线**基础模型**(ViT),支持调制分类/IQ 下游任务 | 见 HF 模型卡 |
| CLDNN | `cldnn/` | `model_for_hub.pt` + `config.json` | 970 KB | CLDNN(CNN+LSTM+Dense),11 类,79.0% 全 SNR / **93.65% @ SNR≥0dB** | MIT |

## 已下载(需解压)

| 模型 | 目录 | 说明 |
|---|---|---|
| Meta-Transformer | `meta_transformer/` + `meta_transformer_ckpt.egg` | RML2018.01a,元学习(含 few-shot 未见类)。268 MB,是 **ALZip EGG** 压缩格式,需 7-Zip 解压:`7z x meta_transformer_ckpt.egg`(本机未装 7-Zip,尚未解压) |

## 完整性校验

所有文件魔数已校验为真实权重格式(zip/torch、HDF5、protobuf/ONNX),非 HTML
错误页。DSC-AMCNet 五件套的 MD5 与 Zenodo 官方记录逐字节一致。

## 下一步(换头微调思路)

1. 加载任意 `.pth/.pkl` 权重,`model.fc`(或等价输出层)替换成你的类别数;
2. 冻结主干、只训最后一层,或全量低学习率微调;
3. 上板前用 `dscamcnet_int8.onnx` 作为 INT8 量化/算子适配的参照。
