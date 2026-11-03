# fix1 板端测试手册（主验收臂）

Status token: `…-READY-FOR-BOARD-TEST`（纯离线；禁 RF_PASS；**板端 C++ 未 aarch64 编译**）

## 诚实缺口（先读）

1. **板端 C++ 未编译**：Windows 主机无 g++/aarch64 交叉工具链。`board_package/` 下
   `radioml_independent_rx_runner.hpp` + `gate9_wiring.patch` 是**写定未编译**的接线与
   恢复核心，上板前必须在板端原生 `make -j1`。
2. **归一化 1/S 须逐字节核验**：板端恢复载荷的「counts vs waveform」域以板端首次构建
   与 host 数字参考 `recover_model_input` 逐字节比对为准；host 参考已确立正确 1/S。
3. **本任务无板端通道**：未实测；本手册只定义上板步骤与验收判据，不宣称两端核验。

## 板端接线（对 dc-ab1 基础树 3 处插入）

在板端基础树 `board_package/` 应用 `gate9_wiring.patch`（或手工照抄）：

1. `gate9_phase.hpp`：`valid_phase` 新增
   `p == "radioml-independent-rx-public-protocol-24class-bf16-fix1"`。
2. `board_gate9_full_chain_rml23.cpp`：`#include "radioml_independent_rx_runner.hpp"`；
   相位提示串新增该相位；dispatch 新增
   `else if (phase == "radioml-independent-rx-public-protocol-24class-bf16-fix1")
    rc = run_radioml_independent_rx(npu, contract, out, sock, timing, argc, argv);`

**边界**：只新增相位，不改 gate-separation1 判读器/共享契约，不动其他 fork 工作树。

## 构建 + 运行命令

```sh
# 板端（原生，单线程；g++15 若在标量 WL 冻结头 sign-compare 报错，仅本测一次性加
#   -Wno-error=sign-compare，不改冻结头/永久 flags）
make -j1

# 运行（显式 24 类 BF16 + --rx-gain=35；TX 由 PC 侧 fix1 TX 包循环发送）
./board_gate9_full_chain_rml23 \
  --phase radioml-independent-rx-public-protocol-24class-bf16-fix1 \
  --input-dir /mnt/fix1/tx_package \
  --out-dir  /mnt/fix1/board_out \
  --tx-control tcp://<PC_IP>:39010 \
  --rx-uri <board RX device uri> \
  --sample-rate 2560000 --rx-gain 35
```

## 三层验收判据（回传 $OUT 后 judge 判定）

| 层 | 来源 | 判据 |
|---|---|---|
| A 原始 | host 离线对齐参考（不进接收推理）| model_input_sha256 逐字节可复现 |
| B 数字公共协议恢复 | host replay | recovered==orig 24/24 无翻转；固定 512 旋转 = 单个 AM-SSB-WC->SC 反例 |
| C 板端模型输入 | board_out `<sid>.recovered.tensor.bin` + SHA | SHA 重算 vs 记录一致；残差≤0.100；预测变化如实记录 |

板端回传 `board_out/`（`board_independent_rx_results.tsv` + 24 个
`<sid>.recovered.tensor.bin`）后，用
`judge_radioml_independent_rx.py --kind digital`（数字域）或未来 board 臂核验。
0.100 门 + ≤3 次重捕 + 末次选择不变（红线）。数字与 RF 同错、无新增翻转时**不**自动
归因 RF（须板端训练块残差单独证据）。
