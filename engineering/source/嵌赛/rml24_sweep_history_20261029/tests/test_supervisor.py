import importlib.util
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('supervisor',ROOT/'scripts/run_candidate.py')
supervisor=importlib.util.module_from_spec(spec);spec.loader.exec_module(supervisor)

class Child:
    def __init__(self,role,events,timeout=False):self.role=role;self.events=events;self.timeout=timeout
    def poll(self):return None
    def terminate(self):self.events.append(self.role)
    def wait(self,timeout):
        if self.timeout:raise subprocess.TimeoutExpired('fake',timeout)
        return 0

class SupervisorTests(unittest.TestCase):
    def test_shutdown_rx_first(self):
        events=[];children=[(role,Child(role,events)) for role in ['npu','ui','rx']]
        self.assertEqual(supervisor.stop_children(children),[]);self.assertEqual(events,['rx','ui','npu'])
    def test_timeout_no_force_kill_or_dependency_stop(self):
        events=[];children=[('npu',Child('npu',events)),('ui',Child('ui',events)),('rx',Child('rx',events,True))]
        self.assertTrue(supervisor.stop_children(children));self.assertEqual(events,['rx'])
    def test_preflight_rejects_tampering_before_spawn(self):
        a=type('Args',(),dict(model_dir=ROOT,legacy_root=ROOT,npu_sha='0'*64))()
        with patch.object(supervisor,'sha',return_value='wrong'),patch.object(supervisor.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'candidate SHA mismatch'):supervisor.preflight(a)
            spawn.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
