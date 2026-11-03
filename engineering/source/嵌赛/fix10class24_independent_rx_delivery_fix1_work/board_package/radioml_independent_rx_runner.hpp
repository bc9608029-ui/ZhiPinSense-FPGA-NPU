#pragma once
// radioml_independent_rx_runner.hpp -- fix1 主验收臂板端接收 runner（公共协议 +
// 统一幅度合同）。**本文件未在 aarch64 上编译**（Windows 主机无交叉工具链），
// 上板前须 `make -j1` 原生构建并跑 host 预演核验（见 docs/BOARDTEST.md）。
//
// 与 dualsdr-ab1 runner 的唯一差异（恢复链逐字复用 iqdual23fix10 / iqrfrec）：
//   1. 载荷来源 = 24 个公共协议 burst（preamble ZC + settling-zero + 16QAM 训练块
//      + 波形载荷 + guard-zero + ZC tail），由 fix1 TX 包提供；不是 480 帧。
//   2. 幅度合同三量分离（uniform，类别无关）：
//        tx_digital_scale   S     = 117.84922023433009   （统一量化）
//        rx_gain_estimate   a     = 广线性系数（训练块已知幅度估计，数字域 a≈1）
//        model_input_norm   1/S   = 统一反缩放
//      模型窗口 = 恢复载荷[:1024] * (1/S)。（dualsdr 的 per-class
//      tx_scale=2048/native_rms、unscale=native_rms/2048 在此替换为统一 S / 1/S。）
//   3. 接收端只用公共参考（前导/尾估 CFO·定时、训练块估增益·IQ），定位载荷窗口；
//      禁止读取原始 IQ / 原始 DC / 逐样本尺度 / 标签 / 参考窗口（离线对齐除外）。
//
// 诚实边界：ccr.payload 的「counts vs waveform」域以板端首次构建与主机数字参考
// （scripts/radioml_independent_rx_replay.py 的 recover_model_input）逐字节核验为准；
// 主机参考已确立正确归一化 1/S。0.100 门 + ≤3 次重捕 + 末次选择不变（红线）。

#include "iq_rf_per_frame_recovery.hpp"        // iqrfrec (shim -> iq_rf_sync_recovery.hpp)
#include "iq_dual_sdr_coarse_cfo_recovery.hpp" // iqdual23fix10::recover_payload_with_coarse_cfo
#include "iq_rf_training_frame.hpp"            // iqrftrain::deinterleave / kPayloadTrainingOffset

#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace iqindepfix1 {

// ---- 冻结常量（幅度合同，与主机 radioml_independent_rx_contract.py 一致）--------
constexpr double kTxDigitalScale = 117.84922023433009;   // S = 1600/max_peak（统一）
constexpr double kModelInputNorm = 1.0 / kTxDigitalScale; // 1/S
constexpr double kMaxPeak = 13.576670230134553;           // 24 种子 max|waveform|
constexpr int kSourceCount = 24;
constexpr int kTotalBurstComplex = 59904;                 // 公共协议 burst 复样本
constexpr int kPayloadStartComplex = 3072;                // 载荷起点（preamble+settling）
constexpr int kPayloadComplex = 53760;
constexpr int kModelWindowComplex = 1024;
constexpr double kResidualGate = 0.100;                   // 生产冻结，不改
constexpr double kHardInvalidCeiling = 0.30;

// ---------------------------------------------------------------------------
// 帧记录：fix1 公共协议 manifest 的一行（10 列）。
//   source_id  conversion_version  source_index  class_index  class_name  seed
//   burst_file  burst_sha256  payload_ci16_sha256  model_input_sha256
// ---------------------------------------------------------------------------
struct IndependentRxFrame {
    std::string source_id;
    std::string conversion_version;
    int source_index = -1;       // 1..24（显式 == class_index+1）
    int class_index = -1;        // 0..23（评分标签，仅判定器用，不进接收推理）
    std::string class_name;
    int seed = -1;
    std::string burst_file;
    std::string burst_sha256;
    std::string payload_ci16_sha256;
    std::string model_input_sha256;   // A 层原始 SHA（离线对齐绑定）
    // 派生（uniform 幅度合同）
    double tx_scale = kTxDigitalScale;   // S
    double unscale = kModelInputNorm;    // 1/S
};

inline std::string trim(std::string s) {
    const auto b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    const auto e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

inline std::vector<std::string> split_tsv(const std::string& line) {
    std::vector<std::string> f;
    std::string cur;
    std::istringstream ss(line);
    while (std::getline(ss, cur, '\t')) f.push_back(cur);
    return f;
}

// 解析 fix1 manifest，fail-closed（缺列/身份不符/重复 -> 抛出）。
inline std::vector<IndependentRxFrame> load_independent_rx_manifest(
        const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("independent-rx: cannot open " + path);
    std::string line;
    std::getline(in, line);
    auto header = split_tsv(trim(line));
    if (header.size() < 10)
        throw std::runtime_error("independent-rx: manifest header < 10 cols");
    std::vector<IndependentRxFrame> rows;
    int expected = 1;
    while (std::getline(in, line)) {
        if (trim(line).empty()) continue;
        auto f = split_tsv(line);
        if (f.size() < 10)
            throw std::runtime_error("independent-rx: manifest row < 10 cols");
        IndependentRxFrame fr;
        fr.source_id = trim(f[0]);
        fr.conversion_version = trim(f[1]);
        fr.source_index = std::atoi(f[2].c_str());
        fr.class_index = std::atoi(f[3].c_str());
        fr.class_name = trim(f[4]);
        fr.seed = std::atoi(f[5].c_str());
        fr.burst_file = trim(f[6]);
        fr.burst_sha256 = trim(f[7]);
        fr.payload_ci16_sha256 = trim(f[8]);
        fr.model_input_sha256 = trim(f[9]);
        if (fr.source_index != expected)
            throw std::runtime_error("independent-rx: non-contiguous source_index "
                + std::to_string(fr.source_index) + " (expected "
                + std::to_string(expected) + ")");
        if (fr.source_id != "fix1-public-protocol-24waveforms")
            throw std::runtime_error("independent-rx: bad source_id " + fr.source_id);
        if (fr.conversion_version != "v1")
            throw std::runtime_error("independent-rx: bad conversion_version "
                + fr.conversion_version);
        ++expected;
        rows.push_back(fr);
    }
    if (static_cast<int>(rows.size()) != kSourceCount)
        throw std::runtime_error("independent-rx: manifest has " +
            std::to_string(rows.size()) + " rows (want 24)");
    return rows;
}

// ---------------------------------------------------------------------------
// 单帧恢复：逐字复用粗 CFO 恢复链（公共参考），uniform 1/S 归一化到模型窗口。
// 返回恢复载荷 counts 域（ccr.payload）与 residual/corr/cfo；模型窗口由调用者
// 用 (1/S) 填充。不读标签 / 原始 IQ / DC / 逐样本尺度（只读 burst + 公共参考）。
// ---------------------------------------------------------------------------
struct IndependentRxRecovery {
    iqrfrec::PerFileRecovery rec;
    double coarse_cfo_hz = 0.0;
    double fine_cfo_hz = 0.0;
    double residual = 0.0;
    double corr = 0.0;
    std::vector<std::complex<double>> payload;
};

inline IndependentRxRecovery recover_one(
        const std::vector<std::complex<double>>& rx,
        const iqrfrec::EstimateConfig& cfg) {
    IndependentRxRecovery out;
    auto ccr = iqdual23fix10::recover_payload_with_coarse_cfo(
        rx, cfg, kTxDigitalScale);
    out.rec = ccr.rec;
    out.coarse_cfo_hz = ccr.coarse_cfo_hz;
    out.fine_cfo_hz = ccr.rec.cfo_hz;
    out.residual = ccr.rec.payload_training_residual;
    out.corr = ccr.rec.payload_training_corr;
    out.payload = ccr.payload;
    return out;
}

// 填充 [2,1024] f32 模型输入：payload[:1024] * (1/S)。
inline void fill_model_window_uniform(
        const std::vector<std::complex<double>>& payload,
        std::vector<float>& tensor) {
    if (tensor.size() < static_cast<std::size_t>(2 * kModelWindowComplex))
        tensor.resize(2 * kModelWindowComplex);
    for (int k = 0; k < kModelWindowComplex; ++k) {
        tensor[k] = static_cast<float>(payload[k].real() * kModelInputNorm);
        tensor[kModelWindowComplex + k] =
            static_cast<float>(payload[k].imag() * kModelInputNorm);
    }
}

// 板端结果 TSV 头（C 层，供 judge_radioml_independent_rx.py 核验 SHA）。
inline const char* independent_rx_result_header() {
    return "source_index\tclass_index\tclass_name\tgated\tfinite\tboard_pred\t"
           "residual\tcorr\tcoarse_cfo_hz\tfine_cfo_hz\tmodel_input_sha256";
}

// ---------------------------------------------------------------------------
// 顶层入口 run_radioml_independent_rx（主验收臂板端）。
//
// 与 run_radioml_original_dualsdr_ab（radioml_dualsdr_ab_runner.hpp）结构完全一致，
// 仅三处 delta：
//   D1  manifest loader -> load_independent_rx_manifest()（10 列公共协议源）
//   D2  tx_scale/unscale -> 统一 S = 117.84922023433009 / 1/S（类别无关，
//       替换 dualsdr 的 per-class tx_scale=2048/native_rms、unscale=native_rms/2048）
//   D3  相位名 radioml-independent-rx-public-protocol-24class-bf16-fix1 + C 层结果头
//
// 以下块**逐字复用** dualsdr（负控 / PC-TX 控制通道 iqpctbrx / RX 捕获
// board::capture_contiguous / 7 分支保真门 / ≤3 次重捕 / 末次选择），此处只保留
// fix1 特有段（manifest 装载 + recover_one + 统一归一化 + 分类 + C 层输出），
// 设备控制段以注释标注引用 dualsdr runner 对应行，上板时照抄。
//
// **未 aarch64 编译**：Windows 主机无交叉工具链。上板前 `make -j1` 原生构建，
// 并以 host 数字参考（scripts/radioml_independent_rx_replay.py 的
// recover_model_input）逐字节核验 1/S 归一化。
// ---------------------------------------------------------------------------
struct IndependentRxRunReport {
    int n_sources = 0;
    int n_gated = 0;
    int n_recovered = 0;
    std::string out_dir;
    std::string results_path;
};

inline IndependentRxRunReport run_radioml_independent_rx(
        int argc, char** argv,
        const std::function<void(const rf::ResultFrame&)>& /*on_frame*/) {
    IndependentRxRunReport rep;

    const std::string input_dir = board::get_opt(argc, argv, "--input-dir", "");
    if (input_dir.empty())
        throw std::runtime_error("radioml-independent-rx requires --input-dir="
                                 "<public-protocol tx dir> (manifest + 24 bursts)");
    rep.out_dir = board::get_opt(argc, argv, "--out-dir", "");
    const std::string tx_control = board::get_opt(argc, argv, "--tx-control", "");
    if (tx_control.empty())
        throw std::runtime_error("radioml-independent-rx requires "
                                 "--tx-control=tcp://<PC_IP>:39010");
    const std::string rx_uri = board::get_opt(argc, argv, "--rx-uri", "");
    if (rx_uri.empty())
        throw std::runtime_error("radioml-independent-rx requires "
                                 "--rx-uri=<board RX device uri>");
    const long long sample_rate = static_cast<long long>(
        board::opt_u64(argc, argv, "--sample-rate", 2560000ULL));
    if (sample_rate != 2560000LL)
        throw std::runtime_error("radioml-independent-rx: --sample-rate must be "
                                 "2560000 (2.56 Msps)");
    const double gain_db = board::opt_d(argc, argv, "--rx-gain", 35.0);

    auto frames = load_independent_rx_manifest(
        join_path(input_dir, "public_protocol_tx_manifest.tsv"));
    rep.n_sources = static_cast<int>(frames.size());
    rep.results_path = join_path(rep.out_dir, "board_independent_rx_results.tsv");

    iqrfrec::EstimateConfig rec_cfg;
    rec_cfg.min_corr = /* kFidelityTrainingCorrMin (dualsdr verbatim) */ 0.90;
    rec_cfg.max_residual = iqrfrec::kPayloadTrainingResidualMax;   // 0.100 门
    rec_cfg.max_cfo_hz = /* iqpctbrx::fine_cfo_range_hz() */ 625.0;
    rec_cfg.max_sro_ppm = 30.0;
    rec_cfg.search_limit = 0;
    rec_cfg.payload_tx_target_rms = kTxDigitalScale;   // 统一 S（幅度合同）

    std::ofstream out(rep.results_path);
    out << independent_rx_result_header() << "\n";

    for (const auto& fr : frames) {
        // ---- 设备控制 / 负控 / PC-TX 控制 / 捕获 / ≤3 重捕 / 7 分支门 ----
        // 逐字复用 run_radioml_original_dualsdr_ab（radioml_dualsdr_ab_runner.hpp
        // 负控 + iqpctbrx 控制通道 + board::capture_contiguous + 7 分支保真门）。
        // 唯一 delta：capture 长度 = iqrflayout::capture_complex(delay_margin) 同 dualsdr，
        // 但 TX 载荷由 PC 侧 fix1 TX 包（24 个 public-protocol burst）循环发送。
        std::vector<std::int16_t> rx_int16;   // 由 capture 段填充（dualsdr 同款）
        std::vector<std::complex<double>> rx = iqrftrain::deinterleave(rx_int16);

        IndependentRxRecovery rec = recover_one(rx, rec_cfg);

        const bool gated = rec.rec.valid && rec.residual <= kResidualGate;
        std::vector<float> tensor;
        fill_model_window_uniform(rec.payload, tensor);   // payload[:1024] * (1/S)

        rml24::RML24Result pr;
        const bool ok = rml24::raw24_predict(tensor.data(), &pr);
        const bool finite = ok && std::isfinite(pr.top_score);

        // C 层：写 <source_index>.recovered.tensor.bin + SHA（供 judger 核验）。
        {
            std::ofstream tf(join_path(rep.out_dir,
                std::to_string(fr.source_index) + ".recovered.tensor.bin"),
                std::ios::binary);
            for (std::size_t i = 0; i < tensor.size(); ++i) {
                const std::uint32_t bits = board::f32_bits(tensor[i]);
                tf.write(reinterpret_cast<const char*>(&bits), sizeof(bits));
            }
        }
        const std::string sha = board::sha256_file_hex(join_path(rep.out_dir,
            std::to_string(fr.source_index) + ".recovered.tensor.bin"));

        if (gated) ++rep.n_gated;
        if (rec.rec.valid) ++rep.n_recovered;
        out << fr.source_index << "\t" << fr.class_index << "\t" << fr.class_name
            << "\t" << (gated ? 1 : 0) << "\t" << (finite ? 1 : 0)
            << "\t" << (finite ? pr.top_class : -1)
            << "\t" << rec.residual << "\t" << rec.corr
            << "\t" << rec.coarse_cfo_hz << "\t" << rec.fine_cfo_hz
            << "\t" << sha << "\n";
    }
    out.close();
    std::printf("RADIOML_INDEPENDENT_RX n_sources=%d gated=%d recovered=%d "
                "out_dir=%s\n", rep.n_sources, rep.n_gated, rep.n_recovered,
                rep.out_dir.c_str());
    std::fflush(stdout);
    return rep;
}

}  // namespace iqindepfix1
