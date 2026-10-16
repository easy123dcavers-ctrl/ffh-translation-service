"""R106 loopback-only Render-shaped integration smoke test. No external FFH services."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:18737"
OUTPUT = Path("r106-output")
OUTPUT.mkdir(exist_ok=True, parents=True)

def request(path, body=None, method="GET", timeout=12):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        URL + path, data=data, method=method,
        headers={"Content-Type":"application/json"} if body is not None else {})
    begin = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode()),
            # unreachable
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def timed(path, body=None, method="GET", timeout=12):
    start = time.perf_counter()
    status, payload = request(path, body, method, timeout)
    return status, payload, round(time.perf_counter() - start, 3)

def children(pid):
    try:
        raw = Path(f"/proc/{pid}/task/{pid}/children").read_text().strip()
        return [int(x) for x in raw.split()]
    except (FileNotFoundError, ProcessLookupError):
        return []

def vmhwm(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024
    except (FileNotFoundError, ProcessLookupError):
        pass
    return 0.0

def main():
    logfile = OUTPUT / "gunicorn-test-log.txt"
    env = os.environ.copy()
    env.update({
        "FFH_MULTILINGUAL": "false",
        "FFH_TARGET_LANGUAGE": "es",
        "FFH_TRANSLATION_CACHE_ENABLED": "false",
        "PORT": "18737",
    })
    report={
        "experiment":"R106-localhost-FFH-compatible-Gunicorn",
        "production_writes":0,"ffh_private_data":0,"netlify_deploys":0,
        "web_service_only_on_loopback":True,
        "supported_production_install":False,
        "configured_gunicorn_workers":1,
        "configured_gunicorn_threads":2,
        "results":{},
    }
    with logfile.open("w", encoding="utf-8") as output:
        proc=subprocess.Popen([
            sys.executable,"-m","gunicorn",
            "--workers","1","--threads","2","--timeout","120",
            "--bind","127.0.0.1:18737","app:app",
        ],env=env,stdout=output,stderr=subprocess.STDOUT)
        running=True
        peak_master=0.0
        peak_worker=0.0
        worker_seen=False
        def observe():
            nonlocal peak_master,peak_worker,worker_seen
            while running:
                peak_master=max(peak_master,vmhwm(proc.pid))
                for child in children(proc.pid):
                    worker_seen=True
                    peak_worker=max(peak_worker,vmhwm(child))
                time.sleep(0.025)
        monitor=threading.Thread(target=observe,daemon=True)
        monitor.start()
        try:
            for _ in range(150):
                if proc.poll() is not None:
                    raise RuntimeError(f"Gunicorn stopped with {proc.returncode}")
                try:
                    if timed("/health",timeout=1.5)[0]==200:
                        break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Health never started within 15 seconds")
            report["results"]["health_at_start"]=timed("/health")
            report["results"]["info"]=timed("/")
            report["results"]["languages"]=timed("/languages")
            report["results"]["single"]=timed("/translate",
                {"q":"Open page 7 of the notebook.","source":"en","target":"es"},"POST")
            synthetic=[
                {"id":str(i),"q":f"This is mock sentence number {i}."}
                for i in range(25)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                long_request=pool.submit(timed,"/translate-batch",
                    {"items":synthetic,"source":"en","target":"es"},"POST",110)
                # Try health checks while the translator is occupied.
                time.sleep(0.05)
                report["results"]["health_during_batch"]=timed("/health",timeout=5)
                report["results"]["batch"]=long_request.result(timeout=115)
            report["results"]["oversized_batch"]=timed("/translate-batch",
                {"items":["x"]*26,"source":"en","target":"es"},"POST")
            report["results"]["health_after_batch"]=timed("/health")
            assert report["results"]["health_at_start"][0]==200
            assert report["results"]["single"][0]==200
            assert isinstance(report["results"]["single"][1].get("translatedText"),str)
            assert report["results"]["batch"][0]==200
            assert report["results"]["batch"][1].get("count")==25
            assert len(report["results"]["batch"][1].get("results",[]))==25
            assert all(item["ok"] for item in report["results"]["batch"][1]["results"])
            assert report["results"]["oversized_batch"][0]==400
            assert report["results"]["health_during_batch"][0]==200
            assert report["results"]["health_during_batch"][2] < 5
            assert report["results"]["health_after_batch"][0]==200
        except Exception as e:
            report["error"]=repr(e)
            raise
        finally:
            running=False
            monitor.join(timeout=1)
            proc.terminate()
            try: proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            report["observed_peak_master_mib"]=round(peak_master,2)
            report["observed_peak_worker_mib"]=round(peak_worker,2)
            report["upper_bound_peak_sum_mib"]=round(peak_master+peak_worker,2)
            report["worker_process_seen"]=worker_seen
            # Conservative estimate: adding peak RSS values overcounts shared memory.
            report["room_below_512_mib_upper_bound"]=round(512-(peak_master+peak_worker),2)
            (OUTPUT/"r106-summary.json").write_text(
                json.dumps(report, indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            print("R106_SUMMARY",json.dumps({
                k:v for k,v in report.items() if k not in ("results",)
            }),flush=True)
            print("R106_ENDPOINTS",json.dumps({
                k:{"code":v[0],"seconds":v[2]}
                for k,v in report["results"].items()
            }),flush=True)
    if not worker_seen:
        raise RuntimeError("Worker memory could not be observed")
    if report["upper_bound_peak_sum_mib"] >=512:
        raise RuntimeError("Observed process memory did not fit 512 MiB limit")

if __name__ == "__main__":
    main()
