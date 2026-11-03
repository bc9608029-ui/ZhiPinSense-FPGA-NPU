from pathlib import Path
import hashlib,json,zipfile
r=Path(r'E:\嵌赛\rml24_boot_persistence_20261027');items=[r/'HANDOFF_BOOT_PERSISTENCE.md',r/'RECOVERY_QUICK.md',r/'BOOT_PERSISTENCE_STATUS.json',r/'candidate_payload.tar.gz',r/'backup/boot_original_backup_20261027.tar.gz']+list((r/'evidence').glob('*'))+list((r/'candidate').rglob('*'))+[r/'tools/install_runtime.sh',r/'tools/install_sd_boot.sh'];items=[p for p in items if p.is_file()];manifest='\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(r)).replace('\\','/') for p in sorted(items))+'\n';(r/'DELIVERY_SHA256SUMS.txt').write_bytes(manifest.encode('utf-8'))
with zipfile.ZipFile(r/'rml24_sd_persistent_autostart_verified_20261027.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
 for p in items+[r/'DELIVERY_SHA256SUMS.txt']:z.write(p,str(p.relative_to(r)))
print('DELIVERY_SHA256',hashlib.sha256((r/'rml24_sd_persistent_autostart_verified_20261027.zip').read_bytes()).hexdigest())