# fix10class24-scalarwl-4way 板测快照

状态：**`M29-RML24-FIX10CLASS24-SCALARWL-4WAY-READY-FOR-BOARD-TEST`**（测量，非 PASS）

本 PATCH 是**最小诊断**：一次真实单 SDR 捕获 OQPSK(`source_index=11500`)，同一次恢复产出
scalar + wide-linear 两条模型输入，当前 BF16 模型板端各推理一次；旧混合精度模型在 Windows 离线
处理同样两份输入，四路拼 2×2 表。**不改 0.100 门、不改生产行为、不重训。**

## 前提

- 板端已部署 rxrecovery1 FULL（`6fd93f78…`）+ singlesdr-ab1 PATCH（`82e1aa8d…`）。
- `LIBIIO_ROOT=/opt/sdr/libiio-0.26`（`run_gate9_rml23.sh` 已透传）。
- 解压本 PATCH（flat 路径）覆盖到板端包根；`sha256sum -c FIX10CLASS24_SCALARWL_4WAY_PATCH_SHA256SUMS.txt`。

## 板端（用户串口执行，我不碰板）

```bash
bash scripts/run_fix10class24_singlesdr_scalarwl.sh --rx-uri=usb:1.3.5 \
    --source-index=11500 --out-dir=/root/scalarwl_out
```

判据：`run.log` 含 `FIX10CLASS24_BF16_SCALARWL_DIAG_START` → `..._FIDELITY`（verdict）→
`..._RESULT`（functional_pass / bf16_argmax_scalar / bf16_argmax_wl）→ `..._COMPLETE`；
`scalarwl_diag_manifest.json` 存在且 `fidelity_verdict=="RF_PRESERVES_IQ"`、`bf16_finite==true`、
`inputs_produced==true`。若 `verdict` 非 `RF_PRESERVES_IQ`，看 `recovery_failure` /
`payload_training_residual`（门拒不重试 >3 次）。

## Windows 离线四路（icraft-run.exe）

```bash
python scripts/four_way_oqpsk_scalar_wl.py --phase mixed-precision \
    --out-dir '<OUT_DIR>' --icraft-run /path/to/icraft-run.exe --model-dir model_rml23
python scripts/four_way_oqpsk_scalar_wl.py --phase four-way --out-dir '<OUT_DIR>'
```

判据：`four_way_report.json` 的 `cells`（scalar_bf16 / wl_bf16 / scalar_mixed / wl_mixed）与
`agreement`（五项布尔）。混合精度模型 SHA 与导出输入 SHA 均 fail-closed；`mixed_precision_manifest.json`
记录 repeat determinism。

## 安全与红线

- TX 衰减固定 -40 dB（runner 拒绝 > -40）；`--rf-path=direct-cable`（同轴直连，无天线/放大器）。
- 17 红线头 + 两模型 + 标签序 + 0.100 门 + canonical 3 CI16 + baseline 逐字节未改（打包器已 fail-closed 校验）。

**不写 RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_* / RUNTIME-INTEGRATED。**
