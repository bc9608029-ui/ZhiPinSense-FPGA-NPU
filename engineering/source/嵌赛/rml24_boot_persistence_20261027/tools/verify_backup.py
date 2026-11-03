from pathlib import Path
import hashlib,json
r=Path(r'E:\嵌赛\rml24_boot_persistence_20261027');b=r/'backup';checks={}
for line in (b/'raw_backup.sha256').read_text().splitlines():
 h,p=line.split(maxsplit=1);f=b/Path(p).name;checks[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()==h
for line in (b/'sd_boot_backup/boot_partition.sha256').read_text().splitlines():
 h,size,rel=line.split(maxsplit=2);f=b/'sd_boot_backup/backup'/rel;checks['sd/'+rel]=len(f.read_bytes())==int(size) and hashlib.sha256(f.read_bytes()).hexdigest()==h
assert all(checks.values());(r/'evidence/backup_independent_verify.json').write_bytes(json.dumps(dict(passed=len(checks),total=len(checks),checks=checks),indent=2).encode('utf-8'));print('BACKUP_INDEPENDENT_VERIFY',len(checks))