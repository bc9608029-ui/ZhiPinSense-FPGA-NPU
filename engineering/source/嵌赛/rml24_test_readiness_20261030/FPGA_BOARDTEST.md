# FPGA候选：临时上板、same-IQ与回退

## 0. 先后关系与验收边界

先在原正式位流上完成参数实验，冻结拟保留参数。再进行本步骤。这里是隔离的硬件辅助通路验收，不是宣称已把FPGA后端装进正式扫频器。诊断与正式NPU不能同时运行；DDR仲裁器目前固定NPU优先，没有有界公平性保证，不开展NPU/扫频并发性能声明。

本包保留两项与旧基线相同的NPU最小周期违规（详见 evidence），是沿用既有工程政策的受控候选。不得称完整STA全通过，不写Flash/SD/BOOT.bin或修改自启动。

## 1. 完整回退材料

- 候选 `fpga/smartscan_fix2_disable_icap.bit`：SHA256 `47b9e1fd2154104bb1bf34e247af07db6908f70436e2ec68845d617e47514ccd`。
- 原已用位流 `fpga/rollback_original.bit`：SHA256 `22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9`。
- 正式服务/程序均不覆盖。先记录当前正式服务名、active状态和程序路径。若无法明确恢复它们，停在只读收集，不加载候选。
- 新旧bit均走此前成功的 **Procise/JTAG临时下载流程**，器件 JFMQL30TAI676H。下载选择应留截图/工具日志及所选文件SHA。不是烧写Flash。这里不编造未核实的JTAG命令行。

## 2. 板端原生构建（可在加载候选前完成）

板端解压独立board包到 `/root/rml24_test_readiness_20261030`，默认有iCraft 3.39、aarch64 g++。使用实际numpy/scipy解释器。所有目录全新；运行编号示例001若已存在则换002，不删除历史日志。

```bash
ROOT=/root/rml24_test_readiness_20261030
PY=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3
test -x "$PY"
"$PY" -I "$ROOT/preflight.py"
bash "$ROOT/fpga/build_board.sh"
```

需要 `SMARTSCAN_BOARD_BUILD PASS`；否则先修编译，不加载。`ICRAFT_INCLUDE`默认/usr/include、`ICRAFT_LIB`默认/usr/lib/aarch64-linux-gnu；若SDK实际不同，只能设为实际验证路径。脚本使用gnu++17，与厂商GNU可变参数宏兼容；厂商头通过-isystem，自己代码-Werror。

## 3. 停服务、临时加载及只读探针

1. 按实际服务名停止RX/NPU/UI（FPGA重配期间不能让它们继续访问PL），记录原active状态，不disable、不广泛pkill。串口保持可用，SD/Flash启动内容不动。
2. 用此前同一Procise/JTAG流程选择候选bit临时下载。没有本次下载成功日志，不能仅凭寄存器VERSION认定加载的是预期SHA。
3. 本例探针通过XRT Device::Open及默认RegRegion读取；它不写scan寄存器、不启动DDR作业，但**不保证厂商Device::Open本身完全无初始化副作用**。必须在服务停后执行。

```bash
"$ROOT/fpga/scan_xrt" --probe
```

必须 `SMARTSCAN_PROBE version=1 idle=1`。扫描bank基址0x400D0000由当前router合同推导、RTL联测覆盖；板端探针是该映射第一次真机核对。版本不符停下并回退，不尝试乱扫/乱写地址。

## 4. 同一IQ A/B，固定向量集合

```bash
"$PY" -I "$ROOT/fpga/make_vectors.py" --out /root/scan_vectors_001
"$PY" -I "$ROOT/fpga/run_suite.py" --vectors /root/scan_vectors_001 --out /root/scan_sw_001 --backend software
"$PY" -I "$ROOT/fpga/run_suite.py" --vectors /root/scan_vectors_001 --out /root/scan_hw_001 --backend fpga --driver "$ROOT/fpga/scan_xrt"
```

8例：零/DC/+37bin/−37bin/511bin/双音/随机/脉冲。文件均为1024复数点、小端int16交错I,Q；恰4096B。驱动通过XRT MemRegion动态申请64B对齐DDR，写入后读回核验。没有用固定物理缓冲地址、没有mmap CPU缓存别名，也不改变NPU输入。

协议检查：版本1、开始前idle、接受1024、本次单帧作业frame_id=1、committed bank、错误/溢出、每次回读ready、u54高10位为0、整帧generation一致。硬件START会复位扫描核，frame_id不是跨作业累计值（pspl_register_map §4 / core_job_rst_n接线）；测试驱动已对此修正并覆盖连续两次作业。实际FFT与NumPy不是逐bit合同：逐向量相对L1≤2%、峰值功率误差≤2%、峰bin在Golden最大值1%范围内；2%是已冻结的数值对照阈值，不是凭RF分类结果后调。窗口量化沿用Q1.15 Hann；峰值近似不证明低噪声底测量精度。

summary须expected=8/executed=8/passed=8、每个result comparison.pass_=true；失败即停，不只报完成的几例。原始PSD与日志全部保留。

## 5. auto诊断与故障边界

```bash
"$PY" -I "$ROOT/fpga/run_suite.py" --vectors /root/scan_vectors_001 --out /root/scan_auto_001 --backend auto --driver "$ROOT/fpga/scan_xrt"
```

健康候选每例backend_used应为fpga。显式故障演示（只验证启动失败软件回退，不冒充物理故障）：

```bash
"$PY" -I "$ROOT/fpga/same_iq.py" --iq /root/scan_vectors_001/plus37.i16 --out /root/scan_fallback_001 --backend auto --driver /nonexistent/rml24_intentional_missing_driver
```

应backend_used=software、fallback_reason含driver_launch_failed；输出软件PSD。C++主机mock另外覆盖version/超时/计数/错误码/u54/generation，不是板上真实故障注入。

**若驱动rc=3或出现UNSAFE_BUSY_REQUIRES_BOARD_RESET：立即停测，不恢复NPU，不再次申请DDR，不把软件结果当整机恢复成功。** 驱动有意不释放仍可能被PL读取的DDR。必须先重启/重配清除硬件作业并按旧位流恢复，再考虑继续。不能用kill后释放内存“修复”超时。

没有安全验证的硬件复位寄存器，因此不做“任意死锁自动恢复”承诺。正常空闲故障可回退软件；仍忙故障是明确的安全停止状态。

## 6. 从已保存真实IQ继续验证

8向量通过后，才把已保存RX raw取**预先固定的**1024点窗，固定量化比例转换到int16作为额外same-IQ输入。转换必须另外冻结比例/位置，记录削顶，不能按类别调比例或改变原模型IQ。这是下一阶段扩大数据范围，不用本包8向量通过冒充已经完成。

本包尚不将驱动接入正式扫描循环。实际接入应复用已验PSD、如实上报software/fpga/auto，并重新验证候选频点/漏检和24+24、240+240分类回归；在本次硬件通路尚未通过前不提前改正式入口。

## 7. 结束与回退

全部程序停止后，使用同一JTAG临时流程下载 `rollback_original.bit`。核验原HDMI/UI、原NPU可正常推理，按测试前active记录恢复正式服务，不改变enable。异常仍忙则先复位，不直接启动旧进程。

回收：编译日志、下载日志/文件SHA、probe输出、sw/hw/auto所有目录、服务前后状态。没有现场设备结果前，这个包最高只写电脑准备完成。
