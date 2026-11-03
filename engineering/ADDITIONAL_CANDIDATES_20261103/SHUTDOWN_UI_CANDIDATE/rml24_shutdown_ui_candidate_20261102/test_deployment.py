from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
import stage_on_board as S
import activate_on_board as A

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'final_submission_20261102/源码提交/FINAL_BOARD_SNAPSHOT_20261102/release'
if not BASE.exists(): BASE=S.BASE

def compiler(out):
    (out/S.UI).write_bytes(b'TEST_BINARY_NOT_FOR_DEPLOYMENT')

class DeploymentTests(unittest.TestCase):
    def test_exact_base_identity(self):self.assertEqual(len(S.verify_base(BASE)),224)
    def test_bad_base_fails_before_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            base=Path(td)/'base';shutil.copytree(BASE,base)
            (base/'deployment_launcher.py').write_text('tampered')
            out=Path(td)/'candidate'
            with self.assertRaisesRegex(RuntimeError,'SHA mismatch'):S.stage_tree(base,out,compiler)
            self.assertFalse(out.exists())
    def test_staging_only_ui_and_original_unchanged(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            out=Path(td)/'candidate';before=S.verify_base(BASE)
            result=S.stage_tree(BASE,out,compiler)
            self.assertEqual(before,S.verify_base(BASE))
            self.assertEqual(result['status'],'STAGED_BUILD_PASS_NOT_ACTIVATED')
            self.assertFalse(json.loads((out/'PROMOTED_RELEASE.json').read_text())['all_promotion_gates_passed'])
            frozen=json.loads((out/'evidence/CANDIDATE_SOURCE_IDENTITY.json').read_text())
            self.assertTrue(all(S.sha(out/n)==h for n,h in frozen.items()))
            for name in before:
                if name in S.PATCHES+[S.UI,'evidence/CANDIDATE_SOURCE_IDENTITY.json','PROMOTED_RELEASE.json','SHA256SUMS.txt']:continue
                self.assertEqual(S.sha(BASE/name),S.sha(out/name),name)
            receipt=json.loads((out/'PROMOTED_RELEASE.json').read_text())
            for name,digest in receipt['files'].items():
                # External /root dependencies are rechecked on board, not mocked
                # into a claim of current hardware identity on Windows.
                if not name.startswith('/'):self.assertEqual(S.sha(out/name),digest,name)
            for line in (out/'SHA256SUMS.txt').read_text().splitlines():
                digest,name=line.split('  ',1);self.assertEqual(S.sha(out/name),digest,name)
    def test_failed_compile_remains_unpromoted(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            out=Path(td)/'candidate'
            def fail(_):raise RuntimeError('mock compile failure')
            with self.assertRaisesRegex(RuntimeError,'compile failure'):S.stage_tree(BASE,out,fail)
            self.assertFalse(json.loads((out/'PROMOTED_RELEASE.json').read_text())['all_promotion_gates_passed'])
            S.verify_base(BASE)
    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            out=Path(td)/'candidate';out.mkdir();(out/'keep').write_text('keep')
            with self.assertRaisesRegex(RuntimeError,'already exists'):S.stage_tree(BASE,out,compiler)
            self.assertEqual((out/'keep').read_text(),'keep')
    def test_dirty_guard_blocks_switch(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            guard=Path(td)/'guard';guard.write_text('{}')
            with patch.object(A,'GUARD',guard),patch.object(A.subprocess,'run') as run:
                run.return_value=Mock(stdout='ActiveState=inactive\nMainPID=0\n')
                with self.assertRaisesRegex(RuntimeError,'guard retained'):A.stop_clean()
                self.assertEqual(len(run.call_args_list),2)
    def test_still_running_blocks_switch(self):
        with patch.object(A.subprocess,'run') as run:
            run.return_value=Mock(stdout='ActiveState=deactivating\nMainPID=123\n')
            with self.assertRaisesRegex(RuntimeError,'not fully stopped'):A.stop_clean()

if __name__=='__main__':unittest.main(verbosity=2)
