#!/usr/bin/env bash
# 生成 SOURCE_PROVENANCE_SHA256.txt：冻结十二类 Gate 6–9 全链路所依赖的
# 全部【只读来源资产】的 SHA256，证明本工程未修改任何上游资产。
#
# 本脚本只 sha256sum 读取上游文件，绝不写入/改写它们。生成清单后建议：
#   ( cd 上游工程 && sha256sum -c <此清单> )   # 每类路径需先换成相对路径
# 实际校验由 docs/SOURCE_PROVENANCE.md 里的逐类命令完成。
#
# Usage (inside WSL):  bash tools/make_source_provenance.sh
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=SOURCE_PROVENANCE_SHA256.txt
: > "$OUT"

# 每个来源资产一行：SHA256  (两个空格)  绝对路径  ; 归类用 # 注释头。
# sha256sum 的 -b 二进制模式输出 "SHA  *path"，我们手动拼相对上游的路径。
note() { printf '# %s\n' "$1" >> "$OUT"; }
h() {   # h <label> <path>
  local label="$1" path="$2"
  local sha
  sha=$(sha256sum -b "$path" | awk '{print $1}')
  printf '%s  %s  # %s\n' "$sha" "$path" "$label" >> "$OUT"
}

UP12=/f/FPGA_Work/_tmp_ad_amr_results_verify/ad_amr_data_v3_12class_ff2b3fb3_run/outputs/ad_amr_v1_1_data_v3_12class
V3=/f/FPGA_Work/sdr_preparation_v3_logging_fix
G15=/f/FPGA_Work/sdr_pluto_board_integration_v1
UI=/f/FPGA_Work/hdmi_framebuffer_ui_v5_visual/sw
NPU8=/f/FPGA_Work/npu_stage_v1

{
  echo "SOURCE_PROVENANCE_SHA256.txt — 十二类 SDR→NPU→UI 全链路（Gate 6–9）来源冻结清单"
  echo "生成时间（UTC）: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "约定: 每行 = '<SHA256>  <绝对路径>  # <来源说明>'；本清单只读哈希，不修改上游。"
  echo
} >> "$OUT"

note "==== §A 十二类 ONNX 模型（链路上唯一推理模型，标 12CLASS_CHAIN_VALIDATION_MODEL）===="
h "12class ONNX (input [1,2,1024] -> logits [1,12], opset17)" "$UP12/formal/export/onnx/ad_amr_v1_1_opset17.onnx"
h "12class export_report.json" "$UP12/formal/export/onnx/export_report.json"
h "12class acceptance.json (OOD gate NO_GO)" "$UP12/formal/acceptance.json"

note "==== §B 类别契约（十二类顺序权威源）===="
h "categories.hpp (target_12, 两处一致 cd3f336d...)" "$V3/sdr_adapter/categories.hpp"
h "categories.hpp (sdr_pluto 副本, 与上逐字节一致)" "$G15/sdr_adapter/categories.hpp"

note "==== §C FPGA↔NPU 寄存器契约 ===="
h "pl_ddr_register_map.hpp (VERSION 0x20260929)" "$V3/board_package/pl_ddr_register_map.hpp"

note "==== §D 现有位流（权威上板位流，只读冻结，禁写 Flash）===="
h "v4_fix 权威 HDMI 位流 (df8a0c66...)" "/f/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit"
h "PL-DDR Mandatory Core 位流 (70a0e21e...)" "/f/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_disable_icap.bit"

note "==== §E UI 渲染核心（十二类 UI，本链路不改）===="
h "ui_render.hpp (UiState/classes_12/card_grid)" "$UI/ui_render.hpp"
h "ui_render.cpp (Style A 三页渲染)" "$UI/ui_render.cpp"

note "==== §F 八类参考模型资产（仅资产审计，不接入十二类）===="
h "8class 编译产物 rfnet_npu_ZG.json" "$NPU8/compile/jsonraw/rfnet_npu_ZG.json"
h "8class 编译产物 rfnet_npu_ZG.raw" "$NPU8/compile/jsonraw/rfnet_npu_ZG.raw"
h "8class 源模型 time_power_phase_npu_partition_opset17.onnx" "$NPU8/models/time_power_phase_npu_partition_opset17.onnx"
h "8class board model.json" "$NPU8/board_package/model.json"
h "8class board model.raw" "$NPU8/board_package/model.raw"

note "==== §G Gate 1–5 核心源码（复用来源，逐文件冻结）===="
# 只冻结源码（hpp/cpp/h/md/sh），不含编译产物/位流/大二进制。
find "$G15/sdr_adapter" "$G15/board_package" "$G15/contracts" -type f \
  \( -name '*.hpp' -o -name '*.cpp' -o -name '*.h' -o -name '*.md' -o -name '*.sh' \) \
  2>/dev/null | sort | while IFS= read -r f; do
  h "Gate1-5 源码" "$f"
done

echo "Wrote $OUT ($(grep -c '^[0-9a-f]\{64\}  ' "$OUT") frozen entries)"
