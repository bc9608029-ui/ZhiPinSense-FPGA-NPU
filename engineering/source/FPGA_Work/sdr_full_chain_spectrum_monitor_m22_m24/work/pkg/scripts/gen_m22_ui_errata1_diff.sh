#!/usr/bin/env bash
# gen_m22_ui_errata1_diff.sh -- regenerate docs/M22_UI_ERRATA1_DIFF.md from the
# frozen baselines (historical M22 runtime patch + M19 UI source) vs the current
# work/pkg tree.  Run from work/pkg.  Requires the M19 project at the sibling
# path and the historical M22 patch in ../../dist.
set -euo pipefail
cd "$(dirname "$0")/.."   # work/pkg

M22PKG="../../dist/m22_runtime_fix_patch.tar.gz"
M19UI="../../../sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw"
OUT="docs/M22_UI_ERRATA1_DIFF.md"

[[ -f "$M22PKG" ]] || { echo "missing $M22PKG" >&2; exit 1; }
[[ -d "$M19UI" ]] || { echo "missing $M19UI" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$M22PKG" -C "$TMP"

{
  echo "# M22.1 勘误 — 完整 diff 清单"
  echo
  echo "生成时间: $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo
  echo "基线:"
  echo "- 脚本基线: \`dist/m22_runtime_fix_patch.tar.gz\`（历史 M22 runtime 包）"
  echo "- UI 基线:  \`sdr_full_chain_12class_ui_v3_m19/work/pkg/ui_sw/\`（M19 基线）"
  echo "- 当前树:   \`work/pkg/\`（M22.1 勘误后）"
  echo
  echo "## 一、变更文件总表"
  echo
  echo "| 文件 | 类型 | 说明 |"
  echo "|---|---|---|"
  echo "| scripts/m22_harness.sh | 修改 | 后台 PID 经 \`printf -v\` 返回调用者变量，修复 wait 非子进程错误 |"
  echo "| scripts/run_m22_runtime_baseline.sh | 修改 | 同上（基线脚本） |"
  echo "| scripts/run_m22_runtime_regression.sh | 修改 | 同上（回归脚本） |"
  echo "| scripts/test_m22_harness_errata.sh | 新增 | 脚本进程管理回归测试（21/21 PASS） |"
  echo "| ui_sw/font_atlas.hpp | 修改 | 新增 text_box()/draw_text_clipped()/文本 trace（真实字体度量） |"
  echo "| ui_sw/font_atlas.cpp | 修改 | trace 实现 + 裁剪光栅化 |"
  echo "| ui_sw/ui_layout.hpp | 修改 | LayoutMetrics 单一布局源 + 最小尺寸门禁 + 顶栏锚点修正 |"
  echo "| ui_sw/ui_render.hpp | 修改 | region 容器枚举 + region_rect() 单一几何源 |"
  echo "| ui_sw/ui_render.cpp | 修改 | 全量布局重构：裁剪保护/真实度量/长文本策略/列对齐 |"
  echo "| host_tests/test_ui_layout_boundaries.cpp | 新增 | 布局边界回归测试（§五 12 项，2242 pass） |"
  echo "| host_tests/make_ui_m22_1_snapshots.cpp | 新增 | 模拟预览快照（after + worst-case） |"
  echo "| host_tests/build_host_tests.sh | 修改 | 增编两个新测试目标 |"
  echo "| docs/M22_UI_LAYOUT_ERRATA.md | 新增 | UI 修改说明 |"
  echo "| docs/M22_BOARD_RETEST.md | 新增 | 板端复测说明 |"
  echo
  echo "## 二、完整 unified diff"
  echo
} > "$OUT"

# Task A: the three scripts vs the historical M22 patch.
for f in m22_harness.sh run_m22_runtime_baseline.sh run_m22_runtime_regression.sh; do
  {
    echo "### scripts/$f"
    echo '```diff'
    diff -u "$TMP/scripts/$f" "scripts/$f" || true
    echo '```'
    echo
  } >> "$OUT"
done

# Task B: the five UI files vs the M19 baseline.
for f in font_atlas.hpp font_atlas.cpp ui_layout.hpp ui_render.hpp ui_render.cpp; do
  {
    echo "### ui_sw/$f"
    echo '```diff'
    diff -u "$M19UI/$f" "ui_sw/$f" || true
    echo '```'
    echo
  } >> "$OUT"
done

{
  echo "## 三、未修改证明"
  echo
  echo "本勘误补丁**不含**以下路径（故未修改模型、标签序、预处理、RTL、XDC、位流、SDR 数据链、NPU 推理逻辑）："
  echo
  echo "- 模型:  \`model_12class/\`、\`*.raw\`、\`*.onnx\`、\`*.pt\`"
  echo "- 标签序: \`contracts/\`、\`deployment_golden/\`"
  echo "- RTL/XDC/位流: \`*.v\`、\`*.sv\`、\`*.xdc\`、\`*.bit\`、\`*.tcl\`"
  echo "- 数据链/NPU 推理: \`board_package/board_gate9_full_chain_12class.cpp\`、\`board_package/npu_classifier.hpp\`、\`sdr_adapter/classify.hpp\`、\`sdr_adapter/ui_report.hpp\`"
  echo
  echo "补丁内容仅涉及 \`scripts/\`（进程编排）、\`ui_sw/\`（纯渲染层，仅读 UiState 不改模型输出）、\`host_tests/\` 与 \`docs/\`。"
} >> "$OUT"

echo "gen_m22_ui_errata1_diff.sh: OK -> $OUT"
wc -l "$OUT"
