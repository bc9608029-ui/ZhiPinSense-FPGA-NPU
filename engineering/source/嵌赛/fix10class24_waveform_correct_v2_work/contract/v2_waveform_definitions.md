# 波形正确性 v2 —— 物理定义与检验判据（回报 ①）

Token: `M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2`

## 1. 数学定义

### Hilbert 变换（离散）
实信号 `a[n]`（N 点）的 Hilbert 变换 `H{a}` 频域定义为
`H(f) = -j·sign(f)·A(f)`（f≠0），`H(0)=0`。
FFT 实现：`H{a} = ifft(A · h)`，其中掩码
`h[0]=1`、`h[1:N/2]=2`、`h[N/2]=1`（N 偶）、`h[N/2+1:]=0`，结果取 **虚部 `.imag`**。
解析信号 `z = a + j·H{a}` 频域 `Z(f) = A(f)(1+sign(f))`：f<0 处为 0（单边带）。
> F1 缺陷 = 取 `.real`（恒等），导致 `z = a(1+j)` 实为双边带。

### USB / LSB（单边带）
- USB（上边带）：`z = a + j·H{a}` → 只有正频率（负频能量≈0）。
- LSB（下边带）：`z = a - j·H{a}` → 只有负频率（正频能量≈0）。
- 冻结生成器注释声明 AM-SSB 为 USB（"analytic audio → USB sideband"），v2 沿用 USB。

### DSB（双边带）
实载波 `cos(2π fc t)` 被实消息 `m(t)` 调制：`x = m(t)·cos(2π fc t)`，
频谱在 `±fc` 对称（正/负边带能量相等）。带载波 WC：`x=(1+m·m(t))·cos(2π fc t)`。

### SC（抑制载波）
- SSB-SC：DC（0 Hz）载波移除 → `x = m·z·e^{jπ/4}`（无 DC，|mean|≈0）。
- DSB-SC：`±fc` 载波移除 → `x = m·s(t)·cos(2π fc t)·e^{jπ/4}`。
- WC 与 SC 的区别必须是**载波存在性**，不是调制指数（v1 F3 缺陷：两者都留载波，仅 m 不同）。

## 2. 检验判据

| id | 判据 | 阈值 |
|---|---|---|
| C1 Hilbert 正交性 | `<a, H{a}>/(‖a‖·‖H{a}‖)` | ≈0（<1e-6）|
| C2 SSB 单边性 | USB 负频占比 `neg/(pos+neg)` | ≈0（<1e-3）|
| C3 DSB 对称性 | `|pos-neg|/(pos+neg)` | ≈0（<1e-3）|
| C4 SC 载波抑制 | SSB-SC DC/边带、DSB-SC ±fc/边带 | < -30 dB |
| C5 WC 载波存在 | SSB-WC DC/边带、DSB-WC ±fc/边带 | > +10 dB |

`fc = 6250 Hz = Fs/32`，N=1024 → 载波精确落在整数 bin 32（无谱泄漏）；DSB 载波只测
±fc 精确 bin（±1 bin 是锯形消息基频边带 Fs/N≈195 Hz，不算载波）。

## 3. 修正范围（v2 变更面）

只改 4 个 AM 类（F1/F2/F3 只影响它们）：
- `AM-SSB-WC`：`(1 + m·z)·e^{jπ/4}`，m=0.06，z=真解析 USB（DC 载波 + 上边带）。
- `AM-SSB-SC`：`m·z·e^{jπ/4}`，m=0.09（抑制 DC 载波）。
- `AM-DSB-WC`：`(1 + m·s)·cos(2π fc t)·e^{jπ/4}`，m=0.10（±fc 载波 + 边带）。
- `AM-DSB-SC`：`m·s·cos(2π fc t)·e^{jπ/4}`，m=0.15（抑制 ±fc 载波）。

其余 20 类（含 GMSK=index22、OQPSK=index23 红线）逐字复用冻结生成器，label order/
种子/RMS 不变。rng 消费顺序与冻结逐字一致（`_audio`/`_sawtooth` 先消费）。
