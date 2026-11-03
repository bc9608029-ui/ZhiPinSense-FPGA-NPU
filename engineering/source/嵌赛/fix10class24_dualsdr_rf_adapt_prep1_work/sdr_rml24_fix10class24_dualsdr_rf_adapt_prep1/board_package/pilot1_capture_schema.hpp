#pragma once

// pilot1_capture_schema.hpp -- M29-RML24-REALRF-FINETUNE-PILOT1 / 线 B 采集 schema。
//
// 32 字段 save-before-gate 逐样本 TSV 的**唯一权威**定义（与 contract/shared_contract.py
// 的 RESULT_TSV_FIELDS 逐字节一致，判读器 judge_realrf_pilot.py 的 CAPTURE_COLS 也引用
// 同一顺序）。本头文件 iCraft-free / libiio-free / SDR-free：host 测试可直接编译并断言
// 表头与行发射（真实 C++ save-before-gate 逻辑），而非只构造 Python dict。
//
// 关键纪律（红线）：
//   * 保存动作在门控判断**之前**：每个 source_id 无条件先写一行 + 落 raw_rx / model_input
//     / logits / 双预测，再判 gate_pass。
//   * 门拒 / hard-invalid / 无同步 / 削顶一律不剔除 960 分母。
//   * 门拒若能形成有限 tensor 必须记 board_pred1/2 + model_input/logits SHA，标
//     gate_pass=0 + failure_token，不得伪装生产结果。
//   * digital_pred / digital_label_correct 板端留空（数字基线是 Host 侧，离线回填）。
//   * class_index / class_name / dataset_index / split / source_iq_sha256 / label 板端
//     一律留空（评审 39e5 Blocker 2：接收端不得持有类别真值），由主机真值清单
//     `line_a/results/source_manifest_960.tsv` 离线按 source_id 回填（judge/train/eval）。

#include <cstddef>
#include <cstdint>
#include <ostream>
#include <sstream>
#include <string>

namespace pilot1 {

constexpr std::size_t kResultFieldCount = 32;

inline const char* const* result_tsv_fields() {
    static const char* const kFields[kResultFieldCount] = {
        "session_id", "source_id", "class_index", "class_name", "dataset_index",
        "split", "source_iq_sha256", "tx_payload_sha256", "raw_rx_sha256",
        "model_input_sha256", "logits_sha256", "digital_pred", "digital_label_correct",
        "board_pred1", "board_pred2", "label", "capture_ok", "no_sync", "rx_clipped",
        "hard_invalid", "gate_pass", "failure_token", "coarse_cfo_hz",
        "fractional_timing", "timing_offset", "corr", "training_residual",
        "training_residual_rel", "a_real", "a_imag", "b_real", "b_imag",
    };
    return kFields;
}

inline std::string result_tsv_header() {
    std::ostringstream oss;
    for (std::size_t i = 0; i < kResultFieldCount; ++i) {
        if (i) oss << '\t';
        oss << result_tsv_fields()[i];
    }
    return oss.str();
}

// 逐样本行：32 字段全部为字符串（SHA 为 64 hex 或空，数字为可打印十进制，布尔为 "0"/"1"）。
// 顺序必须与 result_tsv_fields() 完全一致。
struct CaptureRow {
    std::string session_id;         // 0
    std::string source_id;          // 1
    std::string class_index;        // 2  （板端留空，离线按 source_id 回填）
    std::string class_name;         // 3  （板端留空，离线按 source_id 回填）
    std::string dataset_index;      // 4  （板端留空，离线按 source_id 回填）
    std::string split;              // 5  （板端留空，离线按 source_id 回填）
    std::string source_iq_sha256;   // 6  （板端留空，离线按 source_id 回填）
    std::string tx_payload_sha256;  // 7  （TX manifest 身份回填）
    std::string raw_rx_sha256;      // 8
    std::string model_input_sha256; // 9
    std::string logits_sha256;      // 10
    std::string digital_pred;       // 11 （板端留空）
    std::string digital_label_correct; // 12 （板端留空）
    std::string board_pred1;        // 13
    std::string board_pred2;        // 14
    std::string label;              // 15 （= class_index；板端留空，离线回填）
    std::string capture_ok;         // 16
    std::string no_sync;            // 17
    std::string rx_clipped;         // 18
    std::string hard_invalid;       // 19
    std::string gate_pass;          // 20
    std::string failure_token;      // 21
    std::string coarse_cfo_hz;      // 22
    std::string fractional_timing;  // 23
    std::string timing_offset;      // 24
    std::string corr;               // 25
    std::string training_residual;  // 26
    std::string training_residual_rel; // 27
    std::string a_real;             // 28
    std::string a_imag;             // 29
    std::string b_real;             // 30
    std::string b_imag;             // 31
};

inline void emit_result_row(std::ostream& os, const CaptureRow& r) {
    os << r.session_id << '\t' << r.source_id << '\t' << r.class_index << '\t'
       << r.class_name << '\t' << r.dataset_index << '\t' << r.split << '\t'
       << r.source_iq_sha256 << '\t' << r.tx_payload_sha256 << '\t'
       << r.raw_rx_sha256 << '\t' << r.model_input_sha256 << '\t'
       << r.logits_sha256 << '\t' << r.digital_pred << '\t'
       << r.digital_label_correct << '\t' << r.board_pred1 << '\t'
       << r.board_pred2 << '\t' << r.label << '\t' << r.capture_ok << '\t'
       << r.no_sync << '\t' << r.rx_clipped << '\t' << r.hard_invalid << '\t'
       << r.gate_pass << '\t' << r.failure_token << '\t' << r.coarse_cfo_hz << '\t'
       << r.fractional_timing << '\t' << r.timing_offset << '\t' << r.corr << '\t'
       << r.training_residual << '\t' << r.training_residual_rel << '\t'
       << r.a_real << '\t' << r.a_imag << '\t' << r.b_real << '\t' << r.b_imag
       << '\n';
}

inline std::string render_result_row(const CaptureRow& r) {
    std::ostringstream oss;
    emit_result_row(oss, r);
    return oss.str();
}

// 列数不变式（host 测试断言）：表头 32 列，且每行 split('\t') 后恰 32 字段。
inline std::size_t count_tab_fields(const std::string& line) {
    std::size_t n = 1;
    for (char c : line) if (c == '\t') ++n;
    // 行尾换行不改变字段数；这里按调用方约定传入不含换行的行。
    return n;
}

}  // namespace pilot1
