#pragma once

// pilot1_tx_manifest.hpp -- M29-RML24-REALRF-FINETUNE-PILOT1 / 线 B: 分会段**板端公共**
// TX manifest 加载器（3 列）。这是 `export_finetune_tx_payload.py` 产出的
// `line_b/tx_payload/S{sn}/tx_manifest.tsv` 的**唯一板端权威解析**。iCraft-free /
// libiio-free / SDR-free：host 测试直接编译并断言 fail-closed。
//
// 评审 39e5 Blocker 2（三清单拆分）：板端只持**采集身份**，绝不持有类别真值。
// 3 列（TX_MANIFEST_HEADER，逐字节一致）：
//   0 session_id   1 source_id   2 tx_payload_sha256
//
// 被移走的真值列（板端一律不得拥有，由主机真值清单离线回填）：
//   class_index / class_name / dataset_index / split / source_iq_sha256
// 被移走的 PC 私有列（PC 发射端私有清单 tx_payload_manifest.tsv 才持有）：
//   tx_payload_file（= source_id + ".i16"；板端只发 source_id，PC 侧据此寻址）
//
// 关键纪律：
//   * 每会话恰 240 行（24 类 × 10 实例），source_id 唯一。
//   * source_id 格式 = s{sn}_c{ci:02d}_i{inst:02d}（sn∈1..4, ci∈0..23, inst∈0..9）。
//   * tx_payload_sha256 列必须 64 小写 hex（身份，非幅度）。
//   * 幅度合同是统一公开常数 S（TX_DIGITAL_SCALE，见 pilot1_capture_runner.hpp），
//     不随样本变化，故不在此 manifest 中承载。
//   * 任一违例 throw（fail-closed），绝不静默降级。

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace pilot1 {

constexpr std::size_t kTxManifestFieldCount = 3;
constexpr std::size_t kSamplesPerSession = 240;
constexpr std::size_t kClassCount = 24;

inline const char* const* tx_manifest_fields() {
    static const char* const kFields[kTxManifestFieldCount] = {
        "session_id", "source_id", "tx_payload_sha256",
    };
    return kFields;
}

struct TxManifestRow {
    std::string session_id;        // 0
    std::string source_id;         // 1
    std::string tx_payload_sha256; // 2
};

inline bool valid_sha64(const std::string& v) {
    if (v.size() != 64) return false;
    for (char c : v)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

inline std::vector<std::string> split_tab(const std::string& line, std::size_t expect,
                                          const std::string& ctx) {
    std::vector<std::string> f;
    f.reserve(expect);
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = line.find('\t', start);
        if (pos == std::string::npos) {
            f.push_back(line.substr(start));
            break;
        }
        f.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    if (f.size() != expect)
        throw std::runtime_error(ctx + ": expected " + std::to_string(expect) +
                                 " tab-separated fields, got " +
                                 std::to_string(f.size()));
    return f;
}

// source_id 格式检查：s{sn}_c{ci:02d}_i{inst:02d}，sn∈1..4，ci∈0..23，inst∈0..9。
inline bool valid_source_id_format(const std::string& sid, int* sn, int* ci, int* inst) {
    // 形如 "s1_c00_i00"：位置 0='s'，随后 1 位数字，然后 "_c"，2 位数字，"_i"，2 位数字。
    if (sid.size() != 10) return false;
    if (sid[0] != 's' || sid[1] < '1' || sid[1] > '4') return false;
    if (sid[2] != '_' || sid[3] != 'c') return false;
    if (sid[6] != '_' || sid[7] != 'i') return false;
    const int s = sid[1] - '0';
    const int c = (sid[4] - '0') * 10 + (sid[5] - '0');
    const int i = (sid[8] - '0') * 10 + (sid[9] - '0');
    for (int k : {4, 5, 8, 9})
        if (sid[k] < '0' || sid[k] > '9') return false;
    if (c < 0 || c >= static_cast<int>(kClassCount)) return false;
    if (i < 0 || i > 9) return false;
    if (sn) *sn = s;
    if (ci) *ci = c;
    if (inst) *inst = i;
    return true;
}

// 加载并 fail-closed 校验分会段**板端公共** TX manifest。`path` 指向 tx_manifest.tsv。
// 返回行顺序 = 文件顺序（export 按 source_id 升序写出），板端按此顺序给每行一个
// 采集序号（0..239）作为控制通道的 source_index。
inline std::vector<TxManifestRow> load_tx_manifest(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in)
        throw std::runtime_error("pilot1 tx manifest: cannot open " + path);

    std::vector<TxManifestRow> rows;
    std::string line;
    bool first = true;
    std::size_t lineno = 0;
    while (std::getline(in, line)) {
        ++lineno;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        const std::string ctx = path + ":" + std::to_string(lineno);

        if (first) {
            const std::vector<std::string> hdr = split_tab(line, kTxManifestFieldCount, ctx);
            for (std::size_t k = 0; k < kTxManifestFieldCount; ++k)
                if (hdr[k] != tx_manifest_fields()[k])
                    throw std::runtime_error(ctx + ": header col " + std::to_string(k) +
                                             " = '" + hdr[k] + "', want '" +
                                             tx_manifest_fields()[k] + "'");
            first = false;
            continue;
        }

        const std::vector<std::string> f =
            split_tab(line, kTxManifestFieldCount, ctx);
        TxManifestRow r;
        r.session_id = f[0];
        r.source_id = f[1];
        r.tx_payload_sha256 = f[2];

        if (r.session_id.empty() || r.session_id.size() != 2 || r.session_id[0] != 'S' ||
            (r.session_id[1] < '1' || r.session_id[1] > '4'))
            throw std::runtime_error(ctx + ": bad session_id '" + r.session_id + "'");
        if (!valid_sha64(r.tx_payload_sha256))
            throw std::runtime_error(ctx + ": tx_payload_sha256 not 64-hex");

        int sn = 0, ci = 0, inst = 0;
        if (!valid_source_id_format(r.source_id, &sn, &ci, &inst))
            throw std::runtime_error(ctx + ": bad source_id '" + r.source_id + "'");
        if (r.session_id != "S" + std::to_string(sn))
            throw std::runtime_error(ctx + ": source_id session " + std::to_string(sn) +
                                     " != session_id '" + r.session_id + "'");

        rows.push_back(std::move(r));
    }

    if (first)
        throw std::runtime_error("pilot1 tx manifest: empty file " + path);
    if (rows.size() != kSamplesPerSession)
        throw std::runtime_error("pilot1 tx manifest: " + std::to_string(rows.size()) +
                                 " rows, want " + std::to_string(kSamplesPerSession));

    // source_id 唯一；session_id 全会话一致；四轮身份零重叠由判读器（离线）在
    // 960 全集上复核，此处仅保证单会话内部唯一。
    std::set<std::string> sid_set;
    std::string first_session;
    for (const auto& r : rows) {
        if (!sid_set.insert(r.source_id).second)
            throw std::runtime_error("pilot1 tx manifest: duplicate source_id " + r.source_id);
        if (first_session.empty()) first_session = r.session_id;
        else if (r.session_id != first_session)
            throw std::runtime_error("pilot1 tx manifest: mixed session_id '" +
                                     r.session_id + "' vs '" + first_session + "'");
    }
    return rows;
}

}  // namespace pilot1
