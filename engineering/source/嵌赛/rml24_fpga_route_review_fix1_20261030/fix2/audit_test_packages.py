"""Read-only artifact audit. No device access or hardware imports."""
import hashlib,json,zipfile
from pathlib import Path

work=Path('F:/嵌赛')
gain=work/'rml24_gain_repeat_prep_20261029'
bit=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030/outputs/smartscan_fix2_candidate')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
archive=gain/'gain_repeat_test_prep.zip'
assert sha(archive)==(gain/'gain_repeat_test_prep.zip.sha256').read_text().split()[0]
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    members=[]
    for n in z.namelist():
        if n.endswith('/'): continue
        if Path(n).name=='SHA256SUMS.txt':
            for line in z.read(n).decode().splitlines():
                digest,member=line.split(None,1)
                member=member.lstrip('* ')
                assert hashlib.sha256(z.read(member)).hexdigest()==digest,member
            continue
        p=gain/Path(n).name
        assert p.is_file(),n
        assert z.read(n)==p.read_bytes(),n
        members.append(n)
r=json.loads((bit/'CANDIDATE_RECEIPT.json').read_text())
for name,v in r['artifacts'].items():
    p=bit/name
    assert p.stat().st_size==v['bytes'] and sha(p)==v['sha256'],name
assert r['automatic_and_explicit_conversion_byte_identical']
assert sha(bit/'smartscan_fix2_disable_icap.bit')==sha(bit/'smartscan_fix2_vendor_auto_disable_icap.bit')
print(json.dumps({'gain_zip_sha_and_crc':'PASS','gain_archive_members_match_worktree':members,
                 'bit_artifact_sha_and_sizes':'PASS','conversion_identity':'PASS',
                 'device_validation_performed':False},indent=2))
