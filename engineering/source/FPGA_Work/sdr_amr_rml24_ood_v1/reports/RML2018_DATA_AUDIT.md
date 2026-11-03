# RadioML2018.01A 严格 24 类数据审计报告

状态：`pass`  —  数据集：`RadioML2018.01A`

## 文件身份

- 本地路径：`F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5`
- 大小：`21449148312` B（≈ 21.45 GiB）
- SHA-256：`e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38`
- 修改时间 ns：`1791042816000000000`（机器本地，跨机不冻结）

## 结构校验

- 样本数：`2555904`（期望 2,555,904）
- 样本形状：`[1024, 2]`（[1024, 2] I/Q 对）
- 类别数：`24`（严格 24）
- 标签顺序：`OOK`, `4ASK`, `8ASK`, `BPSK`, `QPSK`, `8PSK`, `16PSK`, `32PSK`, `16APSK`, `32APSK`, `64APSK`, `128APSK`, `16QAM`, `32QAM`, `64QAM`, `128QAM`, `256QAM`, `AM-SSB-WC`, `AM-SSB-SC`, `AM-DSB-WC`, `AM-DSB-SC`, `FM`, `GMSK`, `OQPSK`
- SNR 档：26 档（-20..30 步长 2），每 (类别,SNR) 4096 样本
- 分层数：`624`（期望 624）
- 有限性 / one-hot / 二值校验：通过（fail-closed）
- 合成回退：`False`

## 切分（防泄漏）

- split_seed：`20261003`
- split_ratios：`[0.6, 0.2, 0.2]`
- split_counts：`{"train": 1533168, "validation": 511056, "test": 511680}`
- 重叠计数：`{"train_validation": 0, "train_test": 0, "validation_test": 0}`
- 索引 SHA-256：`9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335`
- 索引路径（机器本地）：`F:\FPGA_Work\sdr_amr_rml24_ood_v1\data\radioml2018\rml24_split_indices.npz`

## 跨机可移植性

HDF5 SHA-256 与切分索引（split_seed + label + SNR 决定）是跨机不变量；路径与 mtime 为机器本地值，AutoDL 上需重新运行审计，SHA-256 应保持一致。
