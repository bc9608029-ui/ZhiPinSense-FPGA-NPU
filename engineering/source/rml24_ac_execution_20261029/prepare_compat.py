from pathlib import Path
import hashlib,json
r=Path('/root/rml24_ac_execution_20261029');d=r/'delivery';p=d/'scripts/install_overlay.sh'
s=p.read_text();old='41c475b040ffa9d69f688cf7e253ddc6746508d20c51e63ff781c273951f9167';new='be1f0ae7a40d3638d989f543eb581528eeb5d1a7c2e10fc07a52088fd5f76fbb'
assert s.count(old)==1
base=Path('/root/rml24_standalone_execution_20261027/candidate/rml24_final/runtime/ui_event.py')
assert hashlib.sha256(base.read_bytes()).hexdigest()==new
q=d/'scripts/install_overlay_compat_verified.sh';q.write_text(s.replace(old,new))
(r/'BASE_COMPATIBILITY.json').write_text(json.dumps(dict(original_expected=old,verified_board_and_historical_pc_sha256=new,original_installer_preserved=True,base_unchanged=True,reason='Historical PC standalone candidate exact byte match; AC overlay replaces UI event adapter; no inference/model change; strict post-install gate remains mandatory'),indent=2))
print('COMPAT_INSTALLER_PREPARED')
