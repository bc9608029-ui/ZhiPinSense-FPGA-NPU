from pathlib import Path
import hashlib,json,sys,platform
P=Path(__file__).parent
items={'master':(Path('E:/嵌赛/rml24_master_handoff_20261027.zip'),'0429261b02adb92ffbb5150aaabe091ad65aec9bce2dc3f4b0f3fb85d0b77758'),'migration':(Path('E:/嵌赛/rml24_fpga_feature_migration_prep_20261027.zip'),'d379a9c11056803ea47fbbc89fde8622d008b42efe4fe4315f5f4af360aa9fb9')}
out={}
for name,(p,h) in items.items():
 got=hashlib.sha256(p.read_bytes()).hexdigest();assert got==h;out[name]={'path':str(p),'sha256':got,'bytes':p.stat().st_size}
(P/'INPUT_IDENTITY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
import numpy
(P/'HOST_ENVIRONMENT.json').write_text(json.dumps({'python':sys.version,'executable':sys.executable,'numpy':numpy.__version__,'platform':platform.platform(),'procise_path':'D:/FMSH/Procise','xsim_path':'D:/Xilinx_2018_3/Vivado/2018.3/bin','board':'aarch64','client_date':'2026-10-27','board_clock_warning':'Board clock differs from PC; original logs preserved without timestamp changes.'},indent=2),encoding='utf-8')
p=P/'HANDOFF_FPGA_EXECUTION.md';s=p.read_text(encoding='utf-8');s+='\n## 复现提示\n\n- 仿真执行命令保存在xvlog/xelab/xsim各日志中；测试源在source/tb。先运行make_stress_vectors.py生成统计参考，再在source目录编译。xsim.dir仅为可再生模拟器缓存，不纳入交付。\n- compare_vectors.py只比较双方都有的5个整数特征字段；别直接比较CSV整行结构。\n- Procise用独立新工作目录执行对应run.tcl；不要直接重跑覆盖现有证据。进程环境设置TCL_LIBRARY、ICTIME_HOME、APP_DIR、FMSH_DB到D:/FMSH/Procise相应路径，并将dll、bin加入PATH。\n- 板端时钟与电脑日期不一致，保留原始日志时间；本轮归档日期按电脑2026-10-27。\n- baseline_backup是恢复资料，整包不作为板端应用部署包。新代码未部署，当前系统无需执行回滚。\n';p.write_text(s,encoding='utf-8')
print('INPUT_IDENTITIES_AND_HOST_METADATA_PASS')