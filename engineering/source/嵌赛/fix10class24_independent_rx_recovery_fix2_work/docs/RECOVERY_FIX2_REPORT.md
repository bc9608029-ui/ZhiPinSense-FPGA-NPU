# RECOVERY_FIX2_REPORT — fix1v2 独立接收恢复链 CFO 缺陷修复（A 线报告）

状态令牌：`…-HOST-A-LINE-COMPLETE`（纯离线，禁 RF_PASS / 禁 PROJECT_COMPLETE）。板端 C++ 未
aarch64 编译（Windows 主机无交叉链），上板前须在板端原生构建并逐字节核验。

---

## 0. 结论一句话

fix1 独立接收的**公共前导两半 CFO 估计器被 ZC chirp 的分数定时 τ 耦合污染**：24 帧真实双 SDR
捕获的 coarse CFO 漂到 ±1000 Hz（真实 ~-100 Hz），旧链路 `training_residual_rel` **0/24 < 0.100**。
fix2 改为在**已知 16QAM 载荷训练块**上做 (cfo, τ) 联合 2D 网格 + 广线性拟合，CFO 收敛到
-120…-88 Hz 紧凑区间，`training_residual_rel` **23/24 < 0.100**。C++ 与 Python 逐字节一致，
干净数字域 fix2 == fix1 逐字节一致（回归无破坏）。诚实边界：分离验证段 rr 仍在 0.12–0.16，
**0/24 < 0.100**。这**只能证明**「CFO+τ+广线性模型在独立验证段未达 0.100」，**不能单独归因于
时变/非线性**——需进一步排除估计过拟合、插值边界、验证实现本身的贡献（§7b）。未排除前，
本修复不宣称 RF 恢复完成，也不宣称已定位残余根因。

---

## 1. Q1 — 复现 24 帧原始恢复结果与误差容差

**方法**：`scripts/export_fix2_cpp_reference.py` 对 24 份真实 v2 双 SDR 捕获（
`board_capture/rml24_independent_v2_dual_1773374217_210`）读原始 int16 → 暴力前导定位 →
精确切片 59904 复样本 → 落盘 `<sid>.burst.i16`（原始 int16 子区间，**无重量化**）→ 计算
fix2 估计 + v2 恢复张量 SHA（`results/fix2_cpp_ref/`）。

**C++ 交叉核验**（`host_tests/test_recovery_fix2.cpp`，g++ 15.2.0，**27/0 PASS**）：

| 量 | 容差 | 结果 |
|---|---|---|
| joint CFO 网格坐标 | 精确（<1e-9 Hz） | **24/24 精确（max err 0.000e+00）** |
| joint τ 网格坐标 | 精确（<1e-12） | **24/24 精确（max err 0.000e+00）** |
| 旧前导 CFO（诊断） | <1e-4 Hz（放宽：angle 放大末位 ULP） | 24/24（max err 3.251e-6） |
| training_residual / _rel | <1e-9 | 24/24（rr max err 6.939e-17） |
| 恢复 v2 张量 SHA | 逐字节 | **24/24** |

网格坐标精确 0 误差是因为它们是 argmin 网格下标，非由数据派生的浮点；数据派生的 double
（legacy CFO / residual）允许末位 ULP 差异（numpy vs C++ 求和 / sin-cos）。

---

## 2. Q2 — 公共前导 CFO 估计机制 vs 分数定时 / 滤波 / IQ 不平衡

**旧机制**（fix1 `estimate_coarse_cfo_hz`）：前导两半互相关相位差
`cfo = -angle(cB/cA)·Fs/(2π·512)`，其中 `cA=vdot(rx[:512],pre[:512])`、
`cB=vdot(rx[512:1024],pre[512:1024])`。

**缺陷根因**：该估计器假设「前导被**整数采样**对齐」。ZC chirp 的瞬时频率随 n 扫过，当接收
端存在**分数定时 τ**（非整数采样偏移，来自 ADC 采样相位 / 模拟时延）时，两半相关质心被 τ
牵引，`angle(cB/cA)` 不再是纯 CFO 相位，混入 τ 的一阶项。对 τ∈[-0.5,0.5] 可产生
±1000 Hz 量级的伪 CFO（见 §6 旧指标 scatter：-1093.7…1008.9 Hz）。

**排除的其它解释**（diagnose_fix2_part2.py + a_line 诊断）：
- **训练块共轭积 CFO 估计器**也被 IQ 不平衡 b·conj(x)² 项偏置（诊断已证），故不能单独用。
- **纯 IQ 不平衡 / 纯增益**不产生 τ 依赖的 CFO 偏置（宽线性模型可吸收常数增益/相位/IQ 不平衡，
  但不能吸收 τ 引起的频率依赖相位）。
- **滤波**：接收链无额外滤波（公共协议不滤波，仅分数定时校正），故滤波不参与偏置。

唯一无偏做法 = 在已知训练块上显式 2D 网格拟合 `r ≈ a·x_τ + b·conj(x_τ)`（x_τ 为 τ 移位参考，
r 为去 CFO 后接收训练块），以增益无关 residual_rel 为目标（§3）。

---

## 3. Q3 — 细化 CFO + 分数定时（联合估计设计）

**模型**（每网格点）：`r_d = derot(r_full, cfo)`，`x_τ = frac_delay_sinc(x_train, τ)`，
`wide_linear_fit(x_τ, r_d)` → a, b, residual_rel。取 `argmin residual_rel`。

**网格**（与 C++ 逐字一致）：

| 段 | cfo | τ |
|---|---|---|
| 粗 | -1800…1800 step 20（181） | -0.5…0.5 step 0.05（21） |
| 细 | best±20 step 1（41） | best±0.05 step 0.01（11） |

**分数延迟**：33 抽头（M=16）Hann 加窗 sinc，circular FIR：
`y[n]=Σ_{m=-M..M} x[(n-m) mod N]·sinc(m-τ)·win(m-τ)`，`sinc(t)=sin(πt)/(πt)`（t=0→1），
`win(t)=0.5(1+cos(πt/M))`。选加窗 sinc 而非 FFT：载荷 53760 / 整帧 59904 **非 2 的幂**，
radix-2 需补零换 wrap 周期破坏跨语言一致；加窗 sinc 无幂 2 约束、同公式逐字节一致，且真实
数据 **23/24 < 0.100 优于 FFT 22/24**（`a_line_interp_test.py`）。

**关键恒等修正（本轮）**：`frac_delay_sinc(x, 0.0)` 必须**精确返回 x**（恒等）。原实现中
`sin(kPi·m)`（整数 m≠0）因 `kPi≈π` 非精确而 ~1e-16 而非 0，把载荷里 522 个精确 0 样本污染成
~1e-17 次正规数，破坏干净数字域 fix2==fix1 逐字节一致（22/24 翻车）。已双端特例化 `τ==0.0 → 恒等`，
真实 24 帧 τ 全非 0 不受影响。

---

## 4. Q4 — CFO 补偿符号 / 相位参考 / 相位连续性

- **符号约定**：接收模型 `r[n] = x[n]·exp(+j·2π·cfo·n/Fs)`（正 cfo = 频率上偏），补偿
  `derot = aligned·exp(-j·2π·cfo·n/Fs)`。R4 合成反例（注入 cfo=+137.0）联合估计 `est=+137.00`，
  符号自洽。
- **相位参考 / 连续性**：估计与恢复使用**同一 derot 函数**与**同一绝对样本下标 n**（训练段
  derot 用 `start=TRAIN_POS=2048`，恢复 derot 用整 burst 从 0 起的 n），相位斜坡在训练段与载荷
  段**连续**（无 2048/3072 边界跳变）。`recover_model_input` 与 `estimate_public_reference`
  的对齐 + 去 CFO 代码逐字复制，杜绝估计/恢复相位参考漂移。
- **恢复顺序**（模型一致）：`对齐(整定时) → 去 CFO → 广线性逆 → 分数延迟 -τ → 1/S`。

---

## 5. Q5 — 统一幅度语义

保持 fix1 的**统一、类别无关**幅度合同不变：`S = 1600/max_peak`，`model_input_norm = 1/S`，
v1 `S=117.84922023433009`、v2 `S=71.609111379029812`。fix2 **只改 CFO/τ 估计**，不改 S、不改
归一化、不改宽线性逆的形式。`training_residual_rel = sqrt(Σ|e|²/Σ|r|²)`（相对接收能量，增益无关，
门限统计量）与 `training_residual = sqrt(Σ|e|²/Σ|x|²)`（相对 TX 参考，诊断）语义不变，门限 0.100
逐字不变。

---

## 6. Q6 — 旧 / 新指标全 24 帧

`results/fix2_recovery_metrics.json` / `results/fix2_cpp_ref/metrics.tsv`（真实 24 帧）：

| 量 | 旧（前导两半 CFO） | 新（联合 cfo+τ） |
|---|---|---|
| CFO 范围 | **-1093.7 … 1008.9 Hz**（scatter） | **-120.0 … -88.0 Hz**（紧凑） |
| CFO 均值 | -92.5（正负伪值相消） | -107.0 |
| τ 范围 | —（无估计） | -0.52 … 0.44 |
| residual_rel < 0.100 | **0/24**（min 0.1133，max 0.6674） | **23/24**（min 0.0843，max 0.1191） |

唯一不达标帧：`sid=18`（AM-SSB-SC）`training_residual_rel = 0.119149`，仍 > 0.100（诚实保留，
不剔除、不调门限）。旧链路的 0/24 → 新链路 23/24 是 CFO 偏置被消除的直接证据。

---

## 7. Q7 — 分离估计区 vs 独立验证区 + 合成反例

### 7a. 合成反例（`radioml_independent_rx_recovery_fix2.py --self-test`，10/10 PASS）

| 反例 | 注入 | 恢复 | 判定 |
|---|---|---|---|
| R3 CFO | +137.0 Hz | **137.00 Hz**（|err|<2） | PASS |
| R3 τ | -0.31 | **-0.31**（|err|<0.05） | PASS |
| R3 residual | gain 0.85+0.12j, iq_b 0.04+0.02j | rr=0.0095 | PASS |
| R4 legacy 偏置 | 注入 τ=-0.3（无 CFO） | 旧前导 CFO **=705.9 Hz**（|cfo|>100） | 证明 bug 存在 |
| R4 joint 无偏 | 同上 | 联合 CFO **=0.0 Hz**（|cfo|<10） | PASS |

R4 是关键的**正反例**：纯 τ 注入下旧前导估计器读出 705.9 Hz 伪 CFO，联合估计读 0.0 Hz，直接
复现并修复了 fix1 的 CFO-τ 耦合。

### 7b. 分离估计区 vs 独立验证区（`a_line_split_validation.py`，诚实负结论）

训练块前半 `[0:512]` 估 (cfo,τ,a,b)，后半 `[512:1024]` **独立验证**（同一 16QAM 参考，仅样本
不同）：

```
rr_est ∈ [0.076, 0.118]（估计段，拟合目标）
rr_val ∈ [0.124, 0.160]（独立验证段）
split validation-half residual_rel < 0.100: 0/24
```

**负结论（克制表述）**：验证段 rr 系统性高于估计段、且 **0/24 < 0.100**。这**只证明**
「CFO + 分数定时 + 广线性」模型在独立验证段未达 0.100，即该模型**尚未被独立验证段证伪的范围内
成立**，因此不能宣称 RF 恢复完成。但**不能据此单独断定**残余一定是「时变 / 非线性」——候选
解释至少包括：

1. **估计过拟合**：(cfo,τ,a,b) 以估计段 `[0:512]` 残差为拟合目标，估计段 rr 低于验证段是
   预期，不代表验证段有新的物理机制。
2. **插值边界效应**：33 抽头 Hann 加窗 sinc 是 circular FIR，训练块首尾样本的分数延迟会
   用到相邻 guard/载荷样本；τ 非零时边界卷积混入，可能抬高验证段残差。
3. **验证实现本身**：独立验证用同一参考但不同样本区间，其对齐/去 CFO/分数延迟下标一致性
   若与估计段有细微差异，也会产生可观的验证段残差。
4. **真实时变/非线性信道分量**（与既有 dualsdr-rxrecovery2 结论一致的一种可能，但非唯一）。

未做针对性区分实验（例：τ=0 干净合成下验证段是否归零、换用非 circular 边界处理、固定
(cfo,τ) 后单独拟合高阶项）之前，**不能**把「验证段未达 0.100」写死为「存在时变/非线性分量」。
本修复**不**将 23/24 < 0.100 解释为「RF 恢复完成」，**也不**宣称已定位残余根因。

---

## 8. 交付物与验证矩阵

| 项 | 状态 |
|---|---|
| `radioml_independent_rx_public_recovery.hpp`（fix2 联合估计 + τ 恒等修正） | 改 |
| `radioml_independent_rx_runner.hpp`（23 列输出 + FFT 同步 + 资源计量） | 改 |
| `sdr_adapter/latency_stats.hpp`（同步计时） | 改 |
| `radioml_independent_rx_fft.hpp`（FFT 前导定位，B 线） | 新 |
| `scripts/radioml_independent_rx_recovery_fix2.py`（A 线契约 + self-test） | 新 |
| `scripts/{reproduce_fix2_diagnosis,a_line_interp_test,a_line_split_validation,diagnose_fix2_part2,export_fix2_cpp_reference}.py` | 新 |
| `host_tests/{test_recovery_fix2,test_sync_bench,test_sync_fft_invariant}.cpp` | 新 |
| `scripts/judge_radioml_independent_rx_board.py`（21→23 列） | 改 |
| `docs/RECOVERY_FIX2_BLINE_EFFICIENCY.md` | 新 |

**验证（纯离线，全 host）**：
- `python -I scripts/radioml_independent_rx_recovery_fix2.py --self-test` → **10/10**。
- `python -I scripts/judge_radioml_independent_rx_board.py --self-test` → **13/13**。
- `test_recovery_fix2 --ref-dir results/fix2_cpp_ref` → **27/0**（sha 24/24，cfo/τ 精确）。
- `test_radioml_independent_rx`（v1 + v2 干净数字）→ **8/0 + 8/0**（fix2==fix1 逐字节）。
- `test_sync_fft_invariant` → **offset 24/24 + no_sync 24/24 + max_score_err 0.000e+00**。
- `test_sync_bench` → **FFT 5.2×**（host x86；板端 ARM 更大，因消除 ~78M 次/帧 sin/cos）。
- `a_line_split_validation.py` → 独立验证段 **0/24 < 0.100**（诚实负结论，见 §7b）。

---

## 9. 红线遵守

不上板 / 不操作 SDR / 不发射 / 不训练 / 不改模型·预处理·门限·幅度合同·独立接收边界。原始载荷
IQ 仅用于恢复参数冻结后的离线诊断，未进入接收算法。门拒样本不剔 24 分母（sid=18 保留）。
审阅通过前不恢复 READY。板端 C++ 未 aarch64 编译，诚实标注。
