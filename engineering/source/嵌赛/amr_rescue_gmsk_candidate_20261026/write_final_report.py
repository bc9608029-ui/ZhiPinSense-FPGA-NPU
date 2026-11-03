import json,hashlib
from pathlib import Path
r=Path(r"E:\嵌赛\amr_rescue_gmsk_candidate_20261026")
rows=[]
for folder,title,kind in [("development_two_dc_replay","开发集120次已保存真实采集","开发回放"),("validation_rf_r1","独立验证第一轮","新射频采集"),("validation_rf_r2","独立验证第二轮","重新打开设备后新射频采集"),("old24_two_dc_replay","原冻结24次采集回放","开发案例复查")]:
 s=json.loads((r/folder/"paired_score.json").read_text()); b=s["arms"]["baseline"];c=s["arms"]["candidate"]
 rows.append(f"| {title} | {kind} | {b['correct']}/{s['n']} | {c['correct']}/{s['n']} | {len(s['regressions'])} | {c['failures']} |")
text="""# 测试与交接记录（2026-10-26）

状态：TWO_DC_CANDIDATE_VALIDATED_FIXED_PARAMETER_RF；候选处理在两轮独立射频验证均通过预先固定的无退步判据。原冻结工程、模型和24样本集合未改，候选在独立目录。尚未替换原正式启动入口，HDMI尚未修复。

## 实测结果

| 测试 | 性质 | 旧处理正确 | 新处理正确 | 旧正确变新错误 | 新处理接收失败 |
|---|---|---:|---:|---:|---:|
"""+"\n".join(rows)+"""

验证集为24类、每类10个新随机种子，共240个不同样本。两轮使用同一组样本、分别重新收发，合计新处理463/480=96.46%，旧处理403/480=83.96%。不能称为480个不同样本，不能以开发回放24/24宣称100%泛化。每次样本只计一次结果，由8个窗口平均logits决定；8窗口不是8个独立样本。

第一轮GMSK新旧均10/10，第二轮均9/10；原失败GMSK保存采集在同一真实NPU回放由256QAM改为正确GMSK。该旧案例参与开发，不计入独立验证。

所有剩余错误见各目录paired_score.json records和per_class。第二轮候选仍10错，因此不是全部问题已解决。未使用验证集继续调整处理器。

## 修改及边界

模型完全未修改。candidate_two_dc.py利用公开头尾参考，联合估计信道及两种偏置：频偏校正后近似恒定的分量和随校正旋转的分量。此解释由已保存数据诊断和合成数值检查支持，尚不等于已证明全部硬件误差来源。恢复过程不读取调制标签、原始载荷或私有判分文件，不按类别分支。

此前的polar和dual-FIR候选不采用：dual-FIR开发结果106/120，低于旧处理108/120且有2次退步。保留失败记录。

当前测试范围：两台Pluto同轴TX到RX，2.4GHz，采样2.56MS/s，带宽18MHz，TX硬件增益-40dB，RX手动35dB；固定公共前导和尾参考，载荷1024点重复8次，固定发送尺度68.46059377833956。源生成器采用其冻结的各类参数（原生200k、sps8），样本流直接以2.56MS/s播放；不应把原生参数误称为最终射频符号率。属于与RadioML输入张量兼容的自行生成纯净IQ，不是证明对所有RadioML版本或任意发射机通用。

开发120个预定样本中有1个峰值1714.70，高于旧包1600的软余量，但低于12位数值上限2047，按事先种子集合保留，没有缩放单个样本或删除。验证240个均低于1600。完整源哈希和种子在expected_private.json。

未验证：多载频、多采样率、多符号率、多功率、天线空口、低SNR和强干扰、任意无前导盲识别；目前覆盖固定参数系统中的24类与不同消息种子及两轮重复性。HDMI展示、开机启动、长时间连续运行也不属于本次通过项。

## 文件与复现

PC目录：E:\\嵌赛\\amr_rescue_gmsk_candidate_20261026
板端代码：/root/amr_rescue_gmsk_candidate_20261026
板端原始验证采集及逐窗口输入：/root/amr_pair_validation_20261026_r1/capture 和 /root/amr_pair_validation_20261026_r2/capture（全部保留）
板端开发采集：/root/amr_pair_development_20261026_r1/capture；候选回放r2；原24回放r3。

关键文件：candidate_two_dc.py、paired_board_rx_two_dc.py、run_validation_pair.sh、paired_pc_tx.py、score_paired.py、two_dc_frozen_validation_identity.json、post_validation_board_evidence.txt。每轮PC目录包含board_results.json、paired_score.json、expected_private.json、restore.json及串口复制证据；复制核验SHA通过。

复测需使用全新输出目录（禁止覆盖）：
1. PC：python paired_pc_tx.py --dataset validation_seed5100000 --out 新目录
2. 板端：bash /root/amr_rescue_gmsk_candidate_20261026/run_validation_pair.sh /root/新的测试目录
3. copy_pair_results.ps1传回结果，再由score_paired.py按原固定expected_private.json判分。
原脚本内均为绝对路径。启动顺序为PC先等待、板端再连接。每轮开启唯一NPU进程，不可并行启动多个模型。

结果真实运行于原板端NPU，每个240样本对照轮3840个窗口，apply=1/reset=3839/discipline=1；原24回放384窗口。设备恢复均空错误列表；完成后无NPU测试进程残留。原接收文件和模型哈希核对未变，详细证据见post_validation_board_evidence.txt。

后续建议：以本候选作为固定参数演示的候选接收模块；若需要扩大参数范围，建立新的开发集与未触碰验证集，不能沿用这240样本继续调参后仍称独立验证。不要直接把本实验宣称为任意未知信号盲识别已完成。
"""
(r/"TEST_REPORT_20261026.md").write_text(text,encoding="utf-8")
checks=[]
for p in sorted(r.rglob("*")):
 if p.is_file() and p.suffix in (".py",".sh",".json",".md",".ps1") and "baseline_capture" not in p.parts:
  checks.append(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+str(p.relative_to(r)))
(r/"FINAL_SHA256SUMS.txt").write_text("\n".join(checks),encoding="utf-8")
print(r/"TEST_REPORT_20261026.md")