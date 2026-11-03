from pathlib import Path
import json,hashlib
r=Path(r'E:\嵌赛\rml24_boot_persistence_20261027');boot=(r/'evidence/reboot_serial_01.txt').read_text(encoding='utf-8',errors='replace');assert 'RML24_BOOT_PL_LOADED' in boot;assert 'RML24 verified' in boot and 'RML24 frozen' in boot
s=dict(status='SD_PERSISTENCE_SOFT_REBOOT_PASSED_COLD_BOOT_PENDING',date='2026-10-27',method='Existing vendor BOOT.bin -> U-Boot imports uEnv -> fatload mmc0:1 download.bit -> fpga loadb -> existing Linux -> enabled UI and RX services',boot_bin_changed=False,kernel_changed=False,qspi_written=False,working_bit_sha256='22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9',uenv_sha256='b81563447febf35023b7c99a918bd204270518a87ea9cff169a11fbf26d1f4a9',backup_archive_sha256='44fcdd2bd7704e9e24a6fa7421913ff2d52125d448c2279cb8f04ea7983d7503',backup_independent_checks=14,soft_reboot_user_confirmed_display=True,soft_reboot_pc_tx_completed_frames=24,board_login_during_soft_reboot_validation=False,stability_test='Deferred by explicit user request; not performed',cold_power_cycle='pending normal shutdown and physical off/on')
(r/'BOOT_PERSISTENCE_STATUS.json').write_bytes(json.dumps(s,indent=2,ensure_ascii=False).encode('utf-8'))
text='''# SD持久化与自动启动交接（2026-10-27）

当前状态：软件重启自动加载、自动显示和24帧真实收发已通过；物理断电重开待验收。没有执行长期稳定性测试，用户明确要求先不做。

## 实现方式

保留原BOOT.bin、Image、设备树、QSPI原内容。从SD启动分区增加工作位流download.bit，修正uEnv.txt中的加载路径，从原错误的fatload mmc0:2改为mmc0:1；uenvcmd先run loadbit，成功后打印RML24_BOOT_PL_LOADED，再用原地址加载原Image和DTB。bootcmd改为run uenvcmd。没有重做或替换BOOT.bin，不需要PC每次JTAG加载。

工作位流SHA256：22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9。
新uEnv SHA256：b81563447febf35023b7c99a918bd204270518a87ea9cff169a11fbf26d1f4a9。
原BOOT.bin仍为ff350477e624c50d2f8180fb4b9130ec7688fbc7ca553412ed7c3dd2a68b31ef。
原Image仍为ee88eae627df17fdf615b44cb9fc5a7a7a37d2baaa3f21e90d613f48bedf0929。

应用安装在/opt/rml24-system；最终UI二进制3950201f64f4575755840df2d98879b5d3e44a109372192366d67a90652adaf6，仍是已验证的瀑布修复版；模型和接收恢复均未改。
新增且已启用/etc/systemd/system/rml24-ui.service、rml24-receiver.service。前者等待设备、校验UI哈希后启动；后者使用明确的conda Python和冻结模型，连接电脑192.168.126.50:39012。电脑发射程序未启动时会等待/失败后30秒重试；这是等待信号源，不是稳定性测试。
原/etc/rc.local保持不变，继续提供板端192.168.126.49网络。

## 验证与备份

1. SD分区只读备份11项文件，加上QSPI bootloader4MiB、QSPI kernel16MiB及SD首1MiB分区元数据。全部复制回PC，归档SHA=44fcdd2bd7704e9e24a6fa7421913ff2d52125d448c2279cb8f04ea7983d7503；独立验证14项SHA全部一致。
2. 服务在不继承登录shell环境时启动成功，UI_VERSION_CHECK ok=YES、UI_FB_READY，通过一次24帧服务短测。
3. 写SD配置时检查实际SD身份、1GiB分区大小、原BOOT.bin/uEnv哈希，先写并校验新文件再改名，原uEnv额外保留为uEnv.pre_rml24.txt。分区已sync并卸载。
4. 已执行一次systemctl reboot。完整串口evidence/reboot_serial_01.txt出现fpga_loadbitstream和RML24_BOOT_PL_LOADED，Linux自动启动两个RML24服务。用户确认未再下载、未手动启动而自动出现正常界面。未登录板子，PC启动24帧TX后自动接收服务完成所有请求，TX restore_errors=0。
5. 冷启动还未完成；需先正常关机，用户断电5秒再上电，不操作JTAG、不手动启动，再看自动界面和做短测。

## 当前目录与运行

PC：E:\\嵌赛\\rml24_boot_persistence_20261027
板端工作：/root/rml24_boot_persistence_20261027
系统应用：/opt/rml24-system
结果：/var/log/rml24/runs，每次服务尝试独立目录。
模型：/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16
legacy：/root/amr_rescue_20261025
Python：/root/miniconda3/envs/torch_v2.0.1_aarch64/bin

正常演示只需板子上电、PC网口.50、TX Pluto接电脑、RX Pluto接板子及同轴连接；PC运行原TX程序即可，不要另外手动起第二个接收/NPU进程。
若要用旧的手动测试入口，先systemctl stop rml24-receiver.service；结束再systemctl start rml24-receiver.service。停UI前先停接收器。

## 回退

详见RECOVERY_QUICK.md。关键是恢复SD FAT启动分区的原uEnv.txt，原SHA a13c985eb5031d75ec7069333897cae38944ba5fbadd509828b63e6a48408560，并停用rml24-ui/rml24-receiver服务。原文件在PC backup/sd_boot_backup/backup/uEnv.txt及SD uEnv.pre_rml24.txt。BOOT.bin和QSPI未改，回退不需要写Flash。
若U-Boot因新加载步骤停住，可使用原配置中的fatload Image、fatload DTB和booti序列进入原Linux；不要saveenv。详细命令见恢复说明。

## 保留边界

仍是固定参数、带公共参考的双Pluto同轴系统。PC仍作为TX信号源；自动启动不等于无需任何外部发射源。没有实现扫频、任意无前导识别或新的模型训练。长期稳定性测试按用户要求不做。
''';(r/'HANDOFF_BOOT_PERSISTENCE.md').write_bytes(text.encode('utf-8'));print('SOFT_REBOOT_EVIDENCE_RECORDED')