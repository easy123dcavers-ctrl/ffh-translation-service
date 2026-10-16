"""R120 cross-worker file lock contract; Linux-only and completely synthetic."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_r116_guarded_api import load, SINGLE, BATCH

class CrossWorkerLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = load(True)
        cls.app.testing = True
        cls.globals = cls.app.view_functions[
            "experimental_guarded_translate"].__globals__

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=str(Path(self.tmp.name)/"bounded-admission.lock")
        self.location=mock.patch.dict(self.globals,{"GUARDED_LOCK_FILE":self.path})
        self.location.start()
        self.addCleanup(self.location.stop)
        self.client=self.app.test_client()
        self.body={"source":"en","target":"es","q":"Fictional label."}

    def lock_other_process(self):
        script=(
            "import os,fcntl,sys;"
            "fd=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600);"
            "fcntl.flock(fd,fcntl.LOCK_EX);"
            "print('LOCKED',flush=True);"
            "sys.stdin.read(1);"
            "fcntl.flock(fd,fcntl.LOCK_UN);"
            "os.close(fd)"
        )
        proc=subprocess.Popen(
            [sys.executable,"-u","-c",script,self.path],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,
        )
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        self.assertEqual(proc.stdout.readline().strip(),"LOCKED")
        return proc

    def test_01_independent_process_lock_causes_single_429(self):
        process=self.lock_other_process()
        busy=self.client.post(SINGLE,json=self.body)
        self.assertEqual(busy.status_code,429)
        self.assertEqual(busy.headers.get("Retry-After"),"2")
        process.stdin.write("x")
        process.stdin.flush()
        self.assertEqual(process.wait(timeout=4),0)
        good=self.client.post(SINGLE,json=self.body)
        self.assertEqual(good.status_code,200)

    def test_02_other_process_lock_blocks_whole_batch(self):
        process=self.lock_other_process()
        r=self.client.post(BATCH,json={"source":"en","target":"es","items":["mock"]})
        self.assertEqual(r.status_code,429)
        process.stdin.write("x")
        process.stdin.flush()
        self.assertEqual(process.wait(timeout=4),0)
        good=self.client.post(BATCH,json={
            "source":"en","target":"es","items":["mock"]})
        self.assertEqual(good.status_code,200)

    def test_03_symlink_refused_fail_closed(self):
        target=Path(self.tmp.name)/"target"
        target.write_text("do not overwrite")
        Path(self.path).symlink_to(target)
        r=self.client.post(SINGLE,json=self.body)
        self.assertEqual(r.status_code,503)
        self.assertEqual(target.read_text(),"do not overwrite")

    def test_04_available_after_normal_request(self):
        self.assertEqual(self.client.post(SINGLE,json=self.body).status_code,200)
        self.assertEqual(self.client.post(SINGLE,json=self.body).status_code,200)

    def test_05_failed_translation_releases_both_locks(self):
        with mock.patch.dict(self.globals,{"guarded_draft":lambda *_:(_ for _ in ()).throw(
                RuntimeError("synthetic failure"))}):
            with self.assertRaises(RuntimeError):
                self.client.post(SINGLE,json=self.body)
        self.assertEqual(self.client.post(SINGLE,json=self.body).status_code,200)

if __name__=="__main__":
    unittest.main()
