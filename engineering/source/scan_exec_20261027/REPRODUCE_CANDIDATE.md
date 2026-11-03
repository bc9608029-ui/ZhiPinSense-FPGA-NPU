# 候选复现说明（不是自动安装脚本）

候选目前在板端 /root/rml24_scan_execution_20261027/final/rml24_final/board_runtime/。
四页瀑布程序在 /root/rml24_scan_execution_20261027/ui_fourpage_waterfall/bin/board_ui_live_rml24_final。
原生产目录 /opt/rml24-system 及两个systemd服务未覆盖，测试后已恢复。

复测前停止原接收服务，确认没有第二个NPU进程；要启动四页UI时也应先停止原UI服务，避免同时写显示。不要重新烧录位流或修改SD启动配置。

电脑使用原240波形与原manifest，启动普通发射器（USB URI每次重新枚举）：

```powershell
python -c "import sys;sys.path.insert(0,r'E:\AMR_Rescue_20261025');import pluto_link_probe as p;print(p.scan_usb())"
python -I "E:\嵌赛\rml24_scan_final_prep1_20261027\pc_runtime\rml24_scan_tx.py" --legacy-root "E:\AMR_Rescue_20261025" --dataset "E:\嵌赛\rml24_stage7_execution_20261027\pc\rml24_final_stage7_pc_selftest\dataset" --manifest "E:\嵌赛\rml24_stage7_execution_20261027\pc\rml24_final_stage7_pc_selftest\pc_runtime\selftest_manifest_240.json" --out "<新的TX输出目录>" --listen-host 192.168.126.50 --tx-uri "<实际USB URI>" --center-hz 2397400000
```

板端原生环境与候选入口：

```bash
export PATH=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:$PATH
bash /root/rml24_scan_execution_20261027/final/rml24_final/board_runtime/run_centered_v2.sh --run /root/<新的测试目录> --legacy-root /root/amr_rescue_20261025 --model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 --control-host 192.168.126.50 --initial-mode BAND_SCAN --scan-start-hz 2395000000 --scan-stop-hz 2405000000 --scan-step-hz 1000000 --save
```

新的目录必须不存在。2397.4MHz测试用2395–2405MHz扫描；2401.3MHz测试用2399–2403MHz扫描。其他参数沿用原固定配置。

将 capture/results.json 复制回电脑，用原 scripts/score_dualmode_run.py 与电脑原 truth/expected_private.json 固定240分母判分；不要向板端复制truth或源波形。跳频与静默复现用本目录scheduled_tx_diagnostic.py及原challenge计划，只能在电脑使用计划和真值。

复制到另一块板时，需要同时具备相同legacy目录、冻结NPU模型、libiio和Python依赖。candidate_v2_fourpage_waterfall_tree.tar.gz 是已组装的树，解包后重新构建UI即可；不能对该已修改树强行重跑只适用于干净Stage7源树的旧增量安装门禁。

复测结束先退出候选UI/接收器，再启动原rml24-ui.service与rml24-receiver.service。原开机程序仍是Stage7定频三页版本。新候选不得被误记为已通过新版本启动验收。