历史与启动时间UI补丁，离线C++单测及完整主机UI编译已通过，未上板。
只覆盖PATCH_IDENTITY所列3个UI文件，接收器、模型、位流不改；以本轮板测delivery_progressfix1为目标，先核对before身份，备份后应用，更新候选源身份清单并重新板端编译。保留已验证run_candidate_finalize_v2.py，不退回旧监督器，不沿用旧VALIDATION_FREEZE声称新UI字节未变。
时间取Linux CLOCK_BOOTTIME，HH:MM:SS，不依赖日期；boot_id用于区分启动，同一板子重启前记录标PREVIOUS RUN，旧V1日历记录也仅标旧运行，不强行换算。正常UI重启但板子未重启仍可使用相同boot时间。
同频当前类别持续更新；同频出现另一类别需3次连续有效观测确认再新增，保留旧类别；不是类别切换一次就新增。最多10条，CLEAR及容量淘汰；频差10kHz是摘要分组规则，不是发射机身份。
时间和历史触控需几分钟板端短测，无需仅为此重跑240项RF；本轮未修改准确率算法或已完成的RF结果。
