#pragma once

// radioml_independent_rx_public_recovery.hpp -- fix10class24-independent-rx-delivery-fix1
// 公共协议独立接收的**类别无关**恢复（板端 C++ 侧，逐字对照主机数字参考
// scripts/radioml_independent_rx_contract.py 的 estimate_public_reference /
// recover_model_input / wide_linear_fit / wide_linear_inverse）。
//
// 为什么不是 iqdual23fix10::recover_payload_with_coarse_cfo：dualsdr 恢复把载荷按
// **每类** tx_scale（2048/native_rms）反缩放，且只做单一复增益（非广线性）；而 fix1
// 的幅度合同是**统一、类别无关**的 S = 1600/max_peak，接收端用公共参考（前导/尾估
// 定时·CFO、载荷训练块估广线性增益·IQ 补偿）定位 1024 点窗口，再用统一 1/S 归一化。
// 二者幅度语义不同，逐字复用 dualsdr 会得到错误的「双重缩放」，因此本头文件实现的是
// 与主机数字参考**逐字节一致**的公共参考恢复，而不是复用 dualsdr 的 per-class 链路。
//
// 诚实边界：本恢复只读 burst + 公共参考（ZC 前导/尾 + 16QAM 载荷训练块），绝不读
// 原始 IQ / 原始 DC / 逐样本尺度 / 标签 / 参考窗口（离线对齐除外）。数字域 a≈1、b≈0
// 只证明「TX->模型归一化链路自洽」，不证明 RF 模拟增益 G 已恢复。
//
// iCraft-free / libiio-free：仅依赖 iqrftrain（iq_rf_training_frame.hpp，冻结），
// 主机与板端编译完全一致，可用 host 测试逐字节核验。

#include "iq_rf_training_frame.hpp"        // iqrftrain (frozen: ZC 前导/尾 + 16QAM 训练块)

#include <cmath>
#include <complex>
#include <cstddef>
#include <vector>

namespace iqindepfix1 {

// ---- 公共协议布局（冻结，逐字 iq_rf_training_frame.hpp / Python）----------------
constexpr int kTotalBurstComplexPub = 59904;   // == iqrftrain::kTotalBurstComplex
constexpr int kPreambleComplexPub = 1024;      // ZC 前导
constexpr int kPayloadTrainingPosPub = 2048;   // 载荷训练块起点（preamble 1024 + settling 1024）
constexpr int kPayloadStartPub = 3072;         // 载荷起点（== iqrftrain::kPayloadStart）
constexpr int kPayloadComplexPub = 53760;      // 载荷复样本
constexpr int kModelWindowComplexPub = 1024;   // 模型窗口
constexpr int kTimingSearchSpan = 512;         // 定时搜索半宽（Python estimate_timing_offset 默认）

// ---- 联合 (cfo, τ) 网格（fix2：在已知 16QAM 训练块上联合估计 CFO + 分数定时）----
// 为什么：前导两半 CFO 估计器被 ZC chirp 的分数定时耦合污染（±1000 Hz 伪值，真实 ~-100 Hz），
// 而训练块共轭积 CFO 估计器又被 IQ 不平衡 b·conj(x)² 偏置（诊断 part-2 已证）。唯一无偏做法
// 是在训练块上 2D 网格显式拟合广线性模型 r ≈ a·x + b·conj(x)（x 为 τ 移位参考，r 为去 CFO 后
// 接收训练块），以增益无关 residual_rel 为目标。
// 粗网格覆盖粗估误差（伪 CFO ±1000 + 真实 ±150）与 τ 满周期；细网格在粗网格最佳点邻域细化。
constexpr double kCfoGridCoarseStep = 20.0;
constexpr double kCfoGridCoarseMin = -1800.0;
constexpr double kCfoGridCoarseMax = 1800.0;
constexpr double kTauGridCoarseStep = 0.05;
constexpr double kTauGridCoarseMin = -0.5;
constexpr double kTauGridCoarseMax = 0.5;
constexpr double kCfoGridFineStep = 1.0;
constexpr double kCfoGridFineSpan = 20.0;      // [best-20, best+20]
constexpr double kTauGridFineStep = 0.01;
constexpr double kTauGridFineSpan = 0.05;      // [best-0.05, best+0.05]

// 加窗 sinc 分数延迟半长 M（总抽头 2M+1=33）。与 Python FRAC_DELAY_HALF 逐字一致。
constexpr int kFracDelayHalf = 16;

// ---- 公共参考估计结果 ----------------------------------------------------------
struct PublicReference {
    int timing_offset = 0;                  // ZC 前导互相关定位的 burst 起点（数字域 0）
    double coarse_cfo_hz = 0.0;             // 用于恢复的 CFO（fix2：训练块联合 (cfo,τ) 估计，非前导两半）
    double fractional_timing = 0.0;         // fix2：联合估计的分数定时 τ（采样周期，[-0.5,0.5]）
    double cfo_preamble_legacy_hz = 0.0;    // fix2：旧前导两半 CFO（诊断保留，被分数定时污染）
    std::complex<double> a{1.0, 0.0};       // 广线性系数 a（载荷训练块 LS）
    std::complex<double> b{0.0, 0.0};       // 广线性系数 b（IQ 不平衡）
    double training_residual = 0.0;         // 训练块广线性拟合残差（相对 TX 参考，增益相关，诊断）
    double training_residual_rel = 0.0;     // 相对接收能量（增益无关，门限统计量）
};

// 前导参考（与 Python deinterleave_int16(preamble_int16()) 逐字节一致：量化 int16）。
inline std::vector<std::complex<double>> preamble_ref() {
    return iqrftrain::deinterleave(iqrftrain::preamble());
}

// 载荷训练块参考（16QAM，量化 int16，与 Python payload_training_complex() 逐字节一致）。
inline std::vector<std::complex<double>> payload_training_ref() {
    return iqrftrain::payload_gain_training_complex();
}

// vdot(seg, ref) == sum(conj(seg)*ref)（Python np.vdot）。
inline std::complex<double> vdot(const std::complex<double>* seg,
                                 const std::complex<double>* ref, std::size_t n) {
    std::complex<double> s(0.0, 0.0);
    for (std::size_t k = 0; k < n; ++k) s += std::conj(seg[k]) * ref[k];
    return s;
}

// ---- estimate_timing_offset：ZC 前导互相关定位 burst 起点 -------------------------
//   对称搜索 [-span, span]（修正了 Python 参考的非对称 bug）：
//     d < 0:  前导在 rx 内「绕回尾端」——部分相关  seg=rx[0:K+d]  vs  pre[-d:]（长度 K+d）
//     d == 0: 全相关  seg=rx[0:K] vs pre（长度 K）
//     d > 0:  前导在 rx 内「连续前移」——全相关  seg=rx[d:d+K] vs pre（长度 K）
//   roll(burst,+100) 返回 +100；roll(burst,-100) 返回 -100（此前 d>0 恒被跳过，+100 被
//   误估为 -4）。交叉语言相等≠正确：旧 Python 参考对 d>0 分支尺寸恒不等而 continue，
//   本实现不再复刻该 bug（干净数字域 timing=0 分支不受影响，与主机参考仍逐字节一致）。
inline int estimate_timing_offset(const std::vector<std::complex<double>>& rx,
                                  int search_span = kTimingSearchSpan) {
    const std::vector<std::complex<double>> pre = preamble_ref();
    const std::size_t n = rx.size();
    const std::size_t K = static_cast<std::size_t>(kPreambleComplexPub);
    int best = -1;
    double best_v = -1.0;
    for (int d = -search_span; d <= search_span; ++d) {
        if (d < 0) {
            // 部分相关：前导绕回尾端，重叠长度 K - |d|。
            const int len = kPreambleComplexPub + d;   // d<0 -> len < K
            if (len < 0) continue;
            const std::size_t ref_off = static_cast<std::size_t>(-d);
            if (ref_off > pre.size()) continue;
            if (static_cast<std::size_t>(len) > n) continue;
            const double v = std::abs(vdot(rx.data(), pre.data() + ref_off,
                                           static_cast<std::size_t>(len)));
            if (v > best_v) { best_v = v; best = d; }
        } else if (d == 0) {
            if (K > n) continue;
            const double v = std::abs(vdot(rx.data(), pre.data(), K));
            if (v > best_v) { best_v = v; best = d; }
        } else {
            // 全相关：前导连续前移，seg = rx[d:d+K]（长度 K）。
            const std::size_t off = static_cast<std::size_t>(d);
            if (off + K > n) continue;
            const double v = std::abs(vdot(rx.data() + off, pre.data(), K));
            if (v > best_v) { best_v = v; best = d; }
        }
    }
    return best;
}

// ---- estimate_coarse_cfo_hz：前导两半互相关相位差（Python 逐字）------------------
//   cA=vdot(rx[:512],pre[:512]), cB=vdot(rx[512:1024],pre[512:1024]),
//   cfo = -angle(cB/cA)·Fs/(2π·512)。
inline double estimate_coarse_cfo_hz(const std::vector<std::complex<double>>& rx) {
    const std::vector<std::complex<double>> pre = preamble_ref();
    const std::size_t half = static_cast<std::size_t>(kPreambleComplexPub / 2);
    if (rx.size() < kPreambleComplexPub) return 0.0;
    const std::complex<double> cA = vdot(rx.data(), pre.data(), half);
    const std::complex<double> cB = vdot(rx.data() + half, pre.data() + half, half);
    if (std::abs(cA) == 0.0) return 0.0;
    const double dphi = std::arg(cB / cA);
    return -dphi * static_cast<double>(iqrftrain::kFs) /
           (2.0 * iqrftrain::kPi * static_cast<double>(half));
}

// ---- wide_linear_fit：LS 拟合 r ≈ a·x + b·conj(x) --------------------------------
//   P=Σ|x|²（实），Cc=Σ x²（复二阶矩），det=P²-|Cc|²，
//   a=(P·rhs0 - conj(Cc)·rhs1)/det, b=(P·rhs1 - Cc·rhs0)/det。
//
//   残差给出两套（R3 修正——增益无关相对保真）：
//     residual     = sqrt(Σ|e|² / Σ|x|²)   —— 相对 TX 参考，随接收增益缩放（保留作诊断）
//     residual_rel = sqrt(Σ|e|² / Σ|r|²)   —— 相对接收能量，增益无关（门限统计量）
//   后者复用生产定义（iq_digital_loopback_sync.hpp: normalized_residual = ||y-ax||²/||y||²
//   = 1-|corr|²，分母 = RX 能量而非 TX 能量）——那是**平方** NMSE；本头文件取它的平方根
//   作为门限统计量：residual_rel = sqrt(Σ|e|²/Σ|r|²)。数值上
//   对增益 G：e、r 同乘 G，二者分子分母同乘 G² 相消 → residual_rel 与增益无关。
//   门限 0.100 的数学含义即该增益无关统计量（而非旧的增益相关量），不再「静默换义」。
struct WideLinearFit {
    std::complex<double> a{1.0, 0.0};
    std::complex<double> b{0.0, 0.0};
    double residual = 0.0;        // 相对 TX 参考（增益相关，诊断）
    double residual_rel = 0.0;    // 相对接收能量（增益无关，门限统计量）
};

inline WideLinearFit wide_linear_fit(const std::vector<std::complex<double>>& x,
                                     const std::vector<std::complex<double>>& r) {
    WideLinearFit out;
    const std::size_t n = x.size() < r.size() ? x.size() : r.size();
    if (n == 0) return out;
    double P = 0.0;                          // Σ|x|²
    double R = 0.0;                          // Σ|r|²（接收能量）
    std::complex<double> Cc(0.0, 0.0);
    std::complex<double> rhs0(0.0, 0.0);   // vdot(x, r) = sum(conj(x)*r)
    std::complex<double> rhs1(0.0, 0.0);   // sum(x * r)
    for (std::size_t k = 0; k < n; ++k) {
        P += std::norm(x[k]);
        R += std::norm(r[k]);
        Cc += x[k] * x[k];
        rhs0 += std::conj(x[k]) * r[k];
        rhs1 += x[k] * r[k];
    }
    const double det = P * P - std::norm(Cc);
    if (std::fabs(det) < 1e-300) {
        out.residual = std::numeric_limits<double>::infinity();
        out.residual_rel = std::numeric_limits<double>::infinity();
        return out;
    }
    out.a = (P * rhs0 - std::conj(Cc) * rhs1) / det;
    out.b = (P * rhs1 - Cc * rhs0) / det;
    double num = 0.0;
    for (std::size_t k = 0; k < n; ++k) {
        const std::complex<double> e =
            r[k] - out.a * x[k] - out.b * std::conj(x[k]);
        num += std::norm(e);
    }
    out.residual = (P > 0.0) ? std::sqrt(num / P) : std::numeric_limits<double>::infinity();
    out.residual_rel = (R > 0.0) ? std::sqrt(num / R) : std::numeric_limits<double>::infinity();
    return out;
}

// ---- wide_linear_inverse：x = (conj(a)·r - b·conj(r)) / (|a|²-|b|²)（Python 逐字）--
inline std::vector<std::complex<double>> wide_linear_inverse(
        const std::vector<std::complex<double>>& r,
        const std::complex<double>& a, const std::complex<double>& b) {
    const double denom = std::norm(a) - std::norm(b);
    std::vector<std::complex<double>> out(r.size());
    if (std::fabs(denom) < 1e-300) {
        for (std::size_t k = 0; k < r.size(); ++k)
            out[k] = std::complex<double>(
                std::numeric_limits<double>::quiet_NaN(),
                std::numeric_limits<double>::quiet_NaN());
        return out;
    }
    for (std::size_t k = 0; k < r.size(); ++k)
        out[k] = (std::conj(a) * r[k] - b * std::conj(r[k])) / denom;
    return out;
}

// ---- frac_delay_sinc：加窗 sinc 分数延迟（正 tau = 延迟），circular FIR ----------
//   y[n] = sum_{m=-M..M} x[(n-m) mod N] * sinc(m-tau) * win(m-tau)，
//   sinc(t)=sin(pi t)/(pi t)（t=0 -> 1），win(t)=0.5*(1+cos(pi t/M))（Hann，M=kFracDelayHalf）。
//   与 Python radioml_independent_rx_recovery_fix2.frac_delay_sinc 逐字一致。
//   为什么不用 FFT：载荷 53760 / 整帧 59904 非 2 的幂，radix-2 需补零换 wrap 周期破坏
//   跨语言一致性；加窗 sinc 无幂 2 约束、同公式逐字节一致，且真实数据上 23/24 优于
//   FFT 22/24（见 a_line_interp_test.py）。
inline std::vector<std::complex<double>> frac_delay_sinc(
        const std::vector<std::complex<double>>& x, double tau,
        int half = kFracDelayHalf) {
    const std::size_t n = x.size();
    if (tau == 0.0) {
        // 恒等（分数延迟 0 == 原信号）。不加此特例时 sin(kPi*m)（m 为整数 m!=0）
        // 因 kPi 非精确 π 而 ~1e-16 而非 0，会把载荷中的精确 0 样本污染成 ~1e-17
        // 次正规数，改变恢复张量的 float32 字节（破坏干净数字域 fix1==fix2）。
        return x;
    }
    const int M = half;
    std::vector<double> h(static_cast<std::size_t>(2 * M + 1));
    for (int i = 0; i <= 2 * M; ++i) {
        const int m = i - M;
        const double t = static_cast<double>(m) - tau;
        double s;
        if (t == 0.0) {
            s = 1.0;
        } else {
            s = std::sin(iqrftrain::kPi * t) / (iqrftrain::kPi * t);
        }
        const double w = (M > 0)
            ? 0.5 * (1.0 + std::cos(iqrftrain::kPi * t / static_cast<double>(M)))
            : 1.0;
        h[static_cast<std::size_t>(i)] = s * w;
    }
    std::vector<std::complex<double>> y(n, std::complex<double>(0.0, 0.0));
    for (int i = 0; i <= 2 * M; ++i) {
        const int m = i - M;
        const double hh = h[static_cast<std::size_t>(i)];
        for (std::size_t k = 0; k < n; ++k) {
            long long idx = static_cast<long long>(k) - static_cast<long long>(m);
            idx %= static_cast<long long>(n);
            if (idx < 0) idx += static_cast<long long>(n);
            y[k] += x[static_cast<std::size_t>(idx)] * hh;
        }
    }
    return y;
}

// ---- joint_cfo_tau_estimate：训练段联合 (cfo, τ) 网格（粗 -> 细）------------------
//   在已知 16QAM 训练块上 2D 网格显式拟合广线性模型 r ≈ a·x + b·conj(x)（x 为 τ 移位
//   参考），以增益无关 residual_rel 为目标。粗网格覆盖伪 CFO ±1000 + 真实 ±150 与 τ 满
//   周期；细网格在粗网格最佳点邻域细化。与 Python joint_cfo_tau 逐字一致。
struct JointEstimate {
    double cfo_hz = 0.0;
    double tau = 0.0;
    std::complex<double> a{1.0, 0.0};
    std::complex<double> b{0.0, 0.0};
    double residual = 0.0;
    double residual_rel = 0.0;
};

inline JointEstimate joint_cfo_tau_estimate(
        const std::vector<std::complex<double>>& aligned) {
    const std::vector<std::complex<double>> x_train = payload_training_ref();
    const std::size_t s0 = static_cast<std::size_t>(kPayloadTrainingPosPub);
    JointEstimate best;
    best.residual = std::numeric_limits<double>::infinity();
    best.residual_rel = std::numeric_limits<double>::infinity();
    if (s0 + x_train.size() > aligned.size()) return best;

    std::vector<std::complex<double>> r_full(
        aligned.begin() + static_cast<std::ptrdiff_t>(s0),
        aligned.begin() + static_cast<std::ptrdiff_t>(s0 + x_train.size()));

    auto scan = [&](double cfo_min, double cfo_step, int cfo_n,
                    double tau_min, double tau_step, int tau_n) {
        std::vector<std::vector<std::complex<double>>> refs;
        refs.reserve(static_cast<std::size_t>(tau_n));
        for (int it = 0; it < tau_n; ++it)
            refs.push_back(frac_delay_sinc(x_train, tau_min + it * tau_step));
        std::vector<std::complex<double>> r_d(r_full.size());
        for (int ic = 0; ic < cfo_n; ++ic) {
            const double cfo = cfo_min + ic * cfo_step;
            for (std::size_t k = 0; k < r_full.size(); ++k) {
                const double ph = -2.0 * iqrftrain::kPi * cfo *
                    static_cast<double>(s0 + k) / static_cast<double>(iqrftrain::kFs);
                r_d[k] = r_full[k] * std::complex<double>(std::cos(ph), std::sin(ph));
            }
            for (int it = 0; it < tau_n; ++it) {
                const WideLinearFit wl = wide_linear_fit(refs[it], r_d);
                if (wl.residual_rel < best.residual_rel) {
                    best.cfo_hz = cfo;
                    best.tau = tau_min + it * tau_step;
                    best.a = wl.a;
                    best.b = wl.b;
                    best.residual = wl.residual;
                    best.residual_rel = wl.residual_rel;
                }
            }
        }
    };

    const int n_c = static_cast<int>(
        std::llround((kCfoGridCoarseMax - kCfoGridCoarseMin) / kCfoGridCoarseStep)) + 1;
    const int n_t = static_cast<int>(
        std::llround((kTauGridCoarseMax - kTauGridCoarseMin) / kTauGridCoarseStep)) + 1;
    scan(kCfoGridCoarseMin, kCfoGridCoarseStep, n_c,
         kTauGridCoarseMin, kTauGridCoarseStep, n_t);
    const int n_cf = static_cast<int>(
        std::llround(2.0 * kCfoGridFineSpan / kCfoGridFineStep)) + 1;
    const int n_tf = static_cast<int>(
        std::llround(2.0 * kTauGridFineSpan / kTauGridFineStep)) + 1;
    scan(best.cfo_hz - kCfoGridFineSpan, kCfoGridFineStep, n_cf,
         best.tau - kTauGridFineSpan, kTauGridFineStep, n_tf);
    return best;
}

// ---- estimate_public_reference（fix2：联合 (cfo,τ) 估计）-------------------------
//   定时 -> 对齐 -> 旧前导 CFO（诊断保留） + 训练段联合 (cfo,τ) -> 广线性。
inline PublicReference estimate_public_reference(
        const std::vector<std::complex<double>>& rx) {
    PublicReference est;
    est.timing_offset = estimate_timing_offset(rx);

    // 对齐（数字域 timing=0；有定时时循环移位 -timing）。
    std::vector<std::complex<double>> aligned = rx;
    if (est.timing_offset != 0) {
        const std::size_t n = rx.size();
        const int t = est.timing_offset;
        aligned.assign(n, std::complex<double>(0.0, 0.0));
        for (std::size_t k = 0; k < n; ++k) {
            long long src = static_cast<long long>(k) + t;   // roll(-t): out[k]=rx[k+t]
            if (src < 0) src += static_cast<long long>(n);
            if (src >= static_cast<long long>(n)) src -= static_cast<long long>(n);
            aligned[k] = rx[static_cast<std::size_t>(src)];
        }
    }

    // fix2：旧前导两半 CFO（诊断保留，被分数定时污染）+ 训练段联合 (cfo, τ)。
    est.cfo_preamble_legacy_hz = estimate_coarse_cfo_hz(aligned);
    const JointEstimate j = joint_cfo_tau_estimate(aligned);
    est.coarse_cfo_hz = j.cfo_hz;
    est.fractional_timing = j.tau;
    est.a = j.a;
    est.b = j.b;
    est.training_residual = j.residual;
    est.training_residual_rel = j.residual_rel;
    return est;
}

// ---- recover_model_input（Python 逐字）------------------------------------------
//   载荷[:1024] 广线性逆 + 统一归一化 norm（=1/S，v1/v2 各自常数）。
inline std::vector<std::complex<double>> recover_model_input(
        const std::vector<std::complex<double>>& rx, const PublicReference& est,
        double norm) {
    // 对齐 + 去 CFO（与 estimate 相同，逐字）。
    std::vector<std::complex<double>> aligned = rx;
    if (est.timing_offset != 0) {
        const std::size_t n = rx.size();
        const int t = est.timing_offset;
        aligned.assign(n, std::complex<double>(0.0, 0.0));
        for (std::size_t k = 0; k < n; ++k) {
            long long src = static_cast<long long>(k) + t;
            if (src < 0) src += static_cast<long long>(n);
            if (src >= static_cast<long long>(n)) src -= static_cast<long long>(n);
            aligned[k] = rx[static_cast<std::size_t>(src)];
        }
    }
    std::vector<std::complex<double>> derot(aligned.size());
    for (std::size_t k = 0; k < aligned.size(); ++k) {
        const double ph = -2.0 * iqrftrain::kPi * est.coarse_cfo_hz *
                          static_cast<double>(k) / static_cast<double>(iqrftrain::kFs);
        derot[k] = aligned[k] * std::complex<double>(std::cos(ph), std::sin(ph));
    }

    const std::size_t ps = static_cast<std::size_t>(kPayloadStartPub);
    const std::size_t plen = static_cast<std::size_t>(kPayloadComplexPub);
    if (ps + plen > derot.size()) {
        std::vector<std::complex<double>> empty(kModelWindowComplexPub);
        return empty;
    }
    std::vector<std::complex<double>> payload(derot.begin() + static_cast<std::ptrdiff_t>(ps),
                                              derot.begin() + static_cast<std::ptrdiff_t>(ps + plen));
    std::vector<std::complex<double>> wl =
        wide_linear_inverse(payload, est.a, est.b);

    // fix2：分数定时校正（广线性逆之后，-τ 延迟；与估计模型一致）。
    std::vector<std::complex<double>> shifted =
        frac_delay_sinc(wl, -est.fractional_timing);

    std::vector<std::complex<double>> out(kModelWindowComplexPub);
    for (int k = 0; k < kModelWindowComplexPub; ++k)
        out[static_cast<std::size_t>(k)] = shifted[static_cast<std::size_t>(k)] * norm;
    return out;
}

}  // namespace iqindepfix1
