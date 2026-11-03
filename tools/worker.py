"""Couple GPU worker (Satyam & Padma) (runs on the Windows host). Watches ../jobs/*.json, runs FaceFusion headless, writes <job>.done or <job>.err.
Job json: {"type":"face_restore","source":"identity/v1/hero.png","target":"reels/<f>/motion.mp4","output":"reels/<f>/restored.mp4"}
"""
import json, os, pathlib, subprocess, sys, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
JOBS = ROOT / "jobs"; FF = ROOT / "tools" / "facefusion"
def cuda_path():
    """Put pip's CUDA 12 / cuDNN 9 DLL folders (nvidia-*-cu12) on PATH so onnxruntime-gpu uses the RTX 3050."""
    import site
    for base in {pathlib.Path(site.getusersitepackages()) / "nvidia", pathlib.Path(sys.prefix) / "Lib/site-packages/nvidia"}:
        for b in sorted(base.glob("*/bin")):
            if str(b) not in os.environ["PATH"]:
                os.environ["PATH"] = str(b) + os.pathsep + os.environ["PATH"]
                if hasattr(os, "add_dll_directory"): os.add_dll_directory(str(b))
cuda_path()

def setup_cuda():
    pk = ["nvidia-cublas-cu12", "nvidia-cudnn-cu12", "nvidia-cuda-runtime-cu12", "nvidia-cufft-cu12", "nvidia-curand-cu12", "nvidia-cuda-nvrtc-cu12"]
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", *pk], capture_output=True, text=True, timeout=3600,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    cuda_path()
    chk = subprocess.run([sys.executable, "-c", "import onnxruntime as o; print(o.__version__, o.get_available_providers()); "
                          "import glob,os; print([p for p in os.environ['PATH'].split(os.pathsep) if 'nvidia' in p])"],
                         capture_output=True, text=True, timeout=120)
    return (r.stdout[-1500:] + r.stderr[-800:] + "\n--- check ---\n" + chk.stdout + chk.stderr[-800:])

GPU_OK = False
def gpu_selftest():
    """Prove FaceFusion really runs on the RTX 3050 before any real job: time a 2 s clip and read the provider from its log.
    GPU: well under 60 s. CPU: several minutes. Result goes to jobs/_gpu_selftest.txt."""
    global GPU_OK
    clip = ROOT / "out/gpu_test_2s.mp4"; out = ROOT / "out/gpu_test_out.mp4"
    if out.exists(): out.unlink()
    chk = subprocess.run([sys.executable, "-c", "import onnxruntime as o; print(o.get_available_providers())"], capture_output=True, text=True)
    if "CUDAExecutionProvider" not in chk.stdout:
        (JOBS / "_gpu_selftest.txt").write_text("FAIL: onnxruntime has no CUDAExecutionProvider\n" + chk.stdout + chk.stderr); print("GPU self-test FAIL (no CUDA provider)"); return False
    t0 = time.time()
    r = subprocess.run([sys.executable, str(ROOT/"tools/ff_launch.py"), "headless-run", "--source-paths", str(ROOT/"identity/v1/hero.png"), "--target-path", str(clip),
                        "--output-path", str(out), "--processors", "face_swapper", "face_enhancer", "--execution-providers", "cuda", "--video-memory-strategy", "tolerant", "--execution-thread-count", "2", "--log-level", "debug"],
                       cwd=FF, capture_output=True, text=True)
    dt = time.time() - t0; log = r.stdout + r.stderr
    cpu_fallback = ("CPUExecutionProvider" in log and "CUDAExecutionProvider" not in log) or "cublasLt64" in log or "bad allocation" in log
    ok = out.exists() and dt < 90 and not cpu_fallback
    (JOBS / "_gpu_selftest.txt").write_text(f"{'PASS' if ok else 'FAIL'}: 2 s clip took {dt:.0f} s (GPU target < 90 s)\n" + log[-4000:], encoding="utf-8", errors="replace")
    print(f"GPU self-test {'PASS' if ok else 'FAIL'}: {dt:.0f} s"); GPU_OK = ok; return ok

ADB = pathlib.Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
PHONE_DIR = "/sdcard/DCIM/Couple"

def adb(*a, timeout=300):
    r = subprocess.run([str(ADB), *a], capture_output=True, text=True, timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))   # no popup console windows
    return r.returncode, (r.stdout + r.stderr).strip()

EMU = pathlib.Path.home() / "AppData/Local/Android/Sdk/emulator/emulator.exe"
AVD = "finolex-test"

def emu_running():
    rc, out = adb("devices", timeout=30)
    return any(l.startswith("emulator-") and l.endswith("device") for l in out.splitlines())

def emu_start():
    """Cold boot without snapshots (snapshot loads froze it before). Returns when Android has finished booting."""
    if emu_running(): return "already running"
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([str(EMU), "-avd", AVD, "-no-snapshot", "-no-boot-anim"], creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    adb("wait-for-device", timeout=300)
    t0 = time.time()
    while time.time() - t0 < 300:
        rc, out = adb("shell", "getprop", "sys.boot_completed", timeout=30)
        if out.strip() == "1":
            time.sleep(10)          # let the launcher and media scanner settle
            return f"booted in {time.time()-t0:.0f}s"
        time.sleep(5)
    raise RuntimeError("emulator did not finish booting in 5 min")

def emu_stop():
    if not emu_running(): return "not running"
    adb("emu", "kill", timeout=60)
    for _ in range(30):
        time.sleep(2)
        if not emu_running(): return "stopped"
    return "kill sent"

def adb_push(j):
    """{"type":"adb_push","files":["reels/to_post/11_x.mp4", ...]} -> copies to the emulator gallery and indexes them."""
    log = ["emulator: " + emu_start()]
    for f in j["files"]:
        src = ROOT / f
        if not src.exists(): raise RuntimeError("missing " + f)
        rc, out = adb("push", str(src), PHONE_DIR + "/")
        log.append(out)
        if rc != 0: raise RuntimeError("push failed " + f + ": " + out)
        adb("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", "file://" + PHONE_DIR + "/" + src.name)
    rc, out = adb("shell", "content", "call", "--uri", "content://media", "--method", "scan_volume", "--arg", "external_primary")
    rc, ls = adb("shell", "ls", "-l", PHONE_DIR)
    return "\n".join(log) + "\n--- phone " + PHONE_DIR + " ---\n" + ls
print("worker watching", JOBS)
if os.environ.pop("COUPLE_RELOAD", None): print("reloaded; keeping previous GPU self-test:", (JOBS/"_gpu_selftest.txt").read_text(errors="replace")[:60] if (JOBS/"_gpu_selftest.txt").exists() else "none"); GPU_OK = (JOBS/"_gpu_selftest.txt").exists() and (JOBS/"_gpu_selftest.txt").read_text(errors="replace").startswith("PASS")
else: gpu_selftest()
_ME = pathlib.Path(__file__).resolve(); _MTIME = _ME.stat().st_mtime
while True:
    if _ME.stat().st_mtime != _MTIME:              # code was updated: restart in place with the new version
        print("worker.py changed, reloading"); os.environ["COUPLE_RELOAD"] = "1"
        os.execv(sys.executable, [f'"{sys.executable}"' if os.name == "nt" else sys.executable, str(_ME)])   # quote: path has spaces
    for job in sorted(JOBS.glob("*.json")):
        done, err = job.with_suffix(".done"), job.with_suffix(".err")
        if done.exists() or err.exists():
            continue
        j = json.load(open(job)); print("job", job.name, j)
        try:
            if j["type"] == "cmd":
                r = subprocess.run(j["cmd"], shell=True, capture_output=True, text=True, timeout=j.get("timeout", 120), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                done.write_text(r.stdout + "\n--- stderr ---\n" + r.stderr[-2000:], encoding="utf-8", errors="replace"); print("done", job.name); continue
            if j["type"] == "gpu_bench":
                code = r"""
import onnxruntime as o, numpy as np, time, glob, subprocess
o.preload_dlls(); print('ort', o.__version__, 'device build:', o.get_device())
m = glob.glob(r'FFDIR/.assets/models/*swapper*128*.onnx')[0]
def run(provs):
    so = o.SessionOptions(); so.log_severity_level = 1
    s = o.InferenceSession(m, so, providers=provs); print('  providers:', s.get_providers())
    feeds = {}
    for i in s.get_inputs():
        shp = [d if isinstance(d, int) else 1 for d in i.shape]; dt = np.float16 if 'float16' in i.type else np.float32
        feeds[i.name] = np.random.rand(*shp).astype(dt)
    s.run(None, feeds); t = time.time(); n = 0
    while time.time() - t < 8: s.run(None, feeds); n += 1
    q = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader'], capture_output=True, text=True).stdout.strip()
    print('  %.1f ms / run, nvidia-smi util %s' % ((time.time()-t)*1000/n, q))
print('CUDA:'); run([('CUDAExecutionProvider', {'device_id': 0}), 'CPUExecutionProvider'])
print('CPU:'); run(['CPUExecutionProvider'])
""".replace("FFDIR", str(FF).replace("\\", "/"))
                r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=FF)
                done.write_text(r.stdout + "\n--- stderr ---\n" + r.stderr[-3000:]); print("done", job.name); continue
            if j["type"] == "gpu_watch":
                # run FaceFusion on the 2 s clip and sample nvidia-smi while it runs: is the RTX 3050 actually busy?
                clip = ROOT/"out/gpu_test_2s.mp4"; outp = ROOT/"out/gpu_watch_out.mp4"
                pr = subprocess.Popen([sys.executable, str(ROOT/"tools/ff_launch.py"), "headless-run", "--source-paths", str(ROOT/"identity/v1/hero.png"),
                      "--target-path", str(clip), "--output-path", str(outp), "--processors", "face_swapper", "face_enhancer",
                      "--execution-providers", "cuda", "--video-memory-strategy", "tolerant", "--execution-thread-count", "2", "--log-level", "debug"], cwd=FF, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                samples = []
                for _ in range(8):
                    time.sleep(5)
                    q = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
                    samples.append(q.stdout.strip() or q.stderr.strip()[:200])
                    p2 = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"], capture_output=True, text=True)
                    samples.append("  apps: " + (p2.stdout.strip().replace("\n", " | ") or "none"))
                pr.kill(); outlog = pr.communicate()[0] or ""
                warn = [l for l in outlog.splitlines() if "onnxruntime" in l.lower() or "provider" in l.lower() and "processing" not in l]
                done.write_text("nvidia-smi samples:\n" + "\n".join(samples) + "\n\nonnxruntime/provider lines:\n" + "\n".join(warn[:30]), encoding="utf-8", errors="replace"); print("done", job.name); continue
            if j["type"] == "gpu_probe":
                code = ("import onnxruntime as o, glob, time\n"
                        "print('ort', o.__version__, 'preload', hasattr(o,'preload_dlls'))\n"
                        "o.preload_dlls() if hasattr(o,'preload_dlls') else None\n"
                        "m = glob.glob(r'%s')[0]; print('model', m)\n"
                        "s = o.InferenceSession(m, providers=['CUDAExecutionProvider','CPUExecutionProvider'])\n"
                        "print('session providers:', s.get_providers())\n") % str(FF/".assets/models/*swapper*128*.onnx").replace("\\","/")
                r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=FF)
                done.write_text(r.stdout + "\n--- stderr ---\n" + r.stderr[-3000:]); print("done", job.name); continue
            if j["type"] == "gpu_test":
                ok = gpu_selftest(); (done if ok else err).write_text((JOBS/"_gpu_selftest.txt").read_text(encoding="utf-8", errors="replace")); continue
            if j["type"] == "face_restore" and not GPU_OK:
                raise RuntimeError("GPU self-test did not pass; refusing to run FaceFusion on the CPU. See jobs/_gpu_selftest.txt")
            if j["type"] == "face_restore":
                print("emulator:", emu_stop())      # FaceFusion needs the RAM the emulator holds
                # One pass per person. A two-person clip gets "passes": [{source, mode:"many", gender, age}, ...]; each pass only
                # touches the faces FaceFusion classifies as that gender/age, and pass 2 runs on pass 1's output. A plain
                # {"source": ...} job (single person, Siri-style) is one pass with face-selector-mode one.
                tgt, out = ROOT / j["target"], ROOT / j["output"]
                passes = j.get("passes") or [{"source": j["source"], "mode": "one"}]
                def gpu_state():
                    q = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,clocks.sm,clocks.max.sm,power.draw,fan.speed,clocks_throttle_reasons.active", "--format=csv,noheader"], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    return q.stdout.strip()
                logtxt = ""; cur = tgt
                for k, p in enumerate(passes):
                    last = k == len(passes) - 1
                    outk = out if last else out.with_name(f"{out.stem}_pass{k+1}{out.suffix}")
                    cmd = [sys.executable, str(ROOT/"tools/ff_launch.py"), "headless-run",
                           "--source-paths", str(ROOT / p["source"]), "--target-path", str(cur), "--output-path", str(outk),
                           "--processors", "face_swapper", "face_enhancer",
                           "--face-swapper-model", j.get("swapper", "inswapper_128_fp16"),
                           "--face-enhancer-model", j.get("enhancer", "gfpgan_1.4"),
                           "--face-enhancer-blend", str(j.get("enhancer_blend", 45)),
                           "--face-mask-blur", str(j.get("mask_blur", 0.5)),
                           *(["--face-mask-types", *j["mask_types"]] if j.get("mask_types") else []),
                           *(["--face-mask-regions", *j["mask_regions"]] if j.get("mask_regions") else []),
                           "--face-selector-mode", p.get("mode", "one"), "--face-selector-order", "large-small",
                           *(["--face-selector-gender", p["gender"]] if p.get("gender") else []),
                           *(["--face-selector-age-start", str(p["age"][0]), "--face-selector-age-end", str(p["age"][1])] if p.get("age") else []),
                           "--execution-providers", "cuda", "--video-memory-strategy", "tolerant", "--execution-thread-count", "2", "--output-video-quality", "90",
                           "--output-video-encoder", "libx264", "--log-level", "info"]
                    g0 = gpu_state(); t0 = time.time()
                    r = subprocess.run(cmd, cwd=FF, capture_output=True, text=True)
                    g1 = gpu_state()
                    logtxt += f"--- pass {k+1}/{len(passes)} {p.get('source')} {p.get('gender','')} elapsed {time.time()-t0:.0f}s\ngpu before: {g0}\ngpu after:  {g1}\n" + r.stdout[-6000:] + r.stderr[-3000:] + "\n"
                    job.with_suffix(".log").write_text(logtxt, encoding="utf-8", errors="replace")
                    if r.returncode != 0 or not outk.exists():
                        raise RuntimeError(f"pass {k+1} failed: " + r.stdout[-2000:] + r.stderr[-2000:])
                    cur = outk
            elif j["type"] == "setup_cuda":
                done.write_text(setup_cuda()); print("done", job.name); continue
            elif j["type"] in ("emu_start", "emu_stop"):
                done.write_text(emu_start() if j["type"] == "emu_start" else emu_stop()); print("done", job.name); continue
            elif j["type"] == "adb_push":
                done.write_text(adb_push(j)); print("done", job.name); continue
            else:
                raise RuntimeError("unknown job type " + j["type"])
            done.write_text("ok"); print("done", job.name)
        except Exception as e:
            err.write_text(str(e)); print("ERR", job.name, str(e)[-500:])
    time.sleep(5)
