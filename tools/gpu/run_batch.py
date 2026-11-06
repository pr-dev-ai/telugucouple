"""SCAIL-2 on a rented GPU, one batch a day. Jobs come from D:\\siri\\gpu_queue\\*.json (make_multishot.py --engine scail2gpu).
  python run_batch.py init EU-RO-1        # once: create the 60 GB network volume in that data center (needs a 5090/4090 there)
  python run_batch.py setup               # once: start a pod, install ComfyUI + nodes + models onto the volume, stop
  python run_batch.py run [--res 720p]    # daily: start pod, render every queued job, download, DELETE the pod
  python run_batch.py status              # queue + spend so far
The pod is always deleted in a finally block; a hard timer (max_hours_per_batch) and a daily $ cap (max_usd_per_day) stop runaway spend.
"""
import base64, csv, json, math, pathlib, subprocess, sys, time, uuid, urllib.parse, urllib.request
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); import runpod_api as rp, ui2api
CFG_P = HERE / "gpu_config.json"; cfg = json.load(open(CFG_P))
Q = ROOT / "gpu_queue"; LEDGER = ROOT / "out" / "spend.csv"; USD_INR = 88

def start_cmd():
    setup = base64.b64encode((HERE / "setup_volume.sh").read_bytes()).decode()
    return (f"mkdir -p /workspace && if [ ! -f /workspace/.setup_done ]; then echo {setup} | base64 -d > /workspace/setup.sh && "
            f"bash /workspace/setup.sh > /workspace/setup.log 2>&1 && touch /workspace/.setup_done; fi; "
            f"mkdir -p /workspace/ComfyUI/output && cp /workspace/setup.log /workspace/ComfyUI/output/ 2>/dev/null; "
            f"cd /workspace/ComfyUI && . /workspace/venv/bin/activate && exec python main.py --listen 0.0.0.0 --port 8188")

def http(url, data=None, ctype="application/json", timeout=60):
    r = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET", headers={"Content-Type": ctype} if data is not None else {})
    with urllib.request.urlopen(r, timeout=timeout) as resp: return resp.read()

def upload(base, path):
    b = uuid.uuid4().hex; name = f"{uuid.uuid4().hex[:8]}_{path.name}"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() \
           + path.read_bytes() + f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{b}--\r\n".encode()
    return json.loads(http(base + "/upload/image", body, f"multipart/form-data; boundary={b}", 300))["name"]

def spent_today():
    if not LEDGER.exists(): return 0.0
    day = time.strftime("%Y-%m-%d")
    return sum(float(r["usd"]) for r in csv.DictReader(open(LEDGER)) if r["date"].startswith(day) and r["endpoint"].startswith("runpod/"))

def log_gpu(gpu, hours, usd, note):
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["date", "endpoint", "units", "unit", "usd", "inr", "note"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M"), f"runpod/{gpu}", round(hours, 3), "hour", round(usd, 4), round(usd * USD_INR, 1), note])

def wait_ready(base, minutes):
    t0 = time.time()
    while time.time() - t0 < minutes * 60:
        try: http(base + "/system_stats", timeout=10); return True
        except Exception: time.sleep(15)
    return False

def build_job(api, info, still_name, ref_name, frames, res):
    g = json.loads(json.dumps(api))
    def node(cls): return next(k for k, v in g.items() if v["class_type"] == cls)
    g[node("LoadImage")]["inputs"]["image"] = still_name
    v = g[node("VHS_LoadVideo")]["inputs"]; v.update({"video": ref_name, "force_rate": 16, "frame_load_cap": frames, "skip_first_frames": 0})
    s = g[node("WanSCAILToVideo")]["inputs"]
    for k, val in list(s.items()):
        if val == 125: s[k] = frames                      # the template's frame count
    mp = {"480p": 0.42, "720p": 0.9}[res]                  # reference resize target, megapixels (template: 0.5)
    for k, val in g.items():
        if val["class_type"] == "ResizeImageMaskNode":
            for kk, vv in list(val["inputs"].items()):
                if vv == 0.5: val["inputs"][kk] = mp
    for k, val in g.items():                               # neutral positive prompt (template describes a stretch routine)
        if val["class_type"] == "CLIPTextEncode" and isinstance(val["inputs"].get("text"), str) and val["inputs"]["text"].startswith("A woman in a black coat"):
            val["inputs"]["text"] = "A young Indian woman, the same person as the reference image, dancing energetically to the beat, filmed on a handheld phone, sharp detailed face and hands."
    ks = g[node("KSampler")]["inputs"]; ks["seed"] = int(time.time()) % 100000
    if "RIFE VFI" in info:                                 # 16 fps -> 32 fps for smooth dance
        dec = node("VAEDecode"); cv = node("CreateVideo")
        g["9001"] = {"class_type": "RIFE VFI", "inputs": {"ckpt_name": "rife47.pth", "frames": [dec, 0], "clear_cache_after_n_frames": 10,
                     "multiplier": 2, "fast_mode": True, "ensemble": True, "scale_factor": 1.0}}
        g[cv]["inputs"]["images"] = ["9001", 0]; g[cv]["inputs"]["fps"] = 32
    return g

def render(base, api, info, job, res):
    still = ROOT / job["still"]; ref = ROOT / job["ref"]; out = ROOT / job["out"]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ref)], capture_output=True, text=True).stdout)
    frames = int(math.ceil(dur * 16)) // 4 * 4 + 1          # Wan wants 4n+1 frames
    g = build_job(api, info, upload(base, still), upload(base, ref), frames, res)
    pid = json.loads(http(base + "/prompt", json.dumps({"prompt": g}).encode()))["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(10)
        h = json.loads(http(f"{base}/history/{pid}"))
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error": raise RuntimeError(json.dumps(st)[:600])
            for o in h[pid]["outputs"].values():
                for f in o.get("images", []) + o.get("videos", []) + o.get("gifs", []):
                    if f["filename"].endswith(".mp4"):
                        q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
                        tmp = out.with_suffix(".part"); tmp.write_bytes(http(f"{base}/view?{q}", timeout=600)); tmp.rename(out)
                        return time.time() - t0
            if st.get("completed"): raise RuntimeError("finished without an mp4 output")
        if time.time() - t0 > 45 * 60: raise RuntimeError("one clip took over 45 min, giving up")

def run(res, setup_only=False):
    jobs = [] if setup_only else sorted(p for p in Q.glob("*.json") if not p.with_suffix(".done").exists() and not (ROOT / json.load(open(p))["out"]).exists())
    if not setup_only and not jobs: print("queue empty"); return
    if not cfg["volume_id"]: sys.exit("run init first")
    if spent_today() >= cfg["max_usd_per_day"]: sys.exit(f"daily GPU cap ${cfg['max_usd_per_day']} reached")
    pod = rp.create_pod(cfg, start_cmd()); pid = pod.get("id")
    if not pid: sys.exit(f"pod not created: {pod}")
    gpu = (pod.get("machine") or {}).get("gpuTypeId") or pod.get("gpuTypeId") or cfg["gpu_types"][0]
    price = cfg["price_per_hour_usd"].get(gpu, max(cfg["price_per_hour_usd"].values()))
    t_start = time.time(); base = rp.proxy(pid); print("pod", pid, gpu, f"${price}/h", base)
    try:
        if not wait_ready(base, 40 if setup_only else 15): raise RuntimeError("ComfyUI did not come up (see setup.log on the volume)")
        if setup_only: print("setup done, ComfyUI is up"); return
        info = json.loads(http(base + "/object_info", timeout=120))
        missing = sorted({n["type"] for n in json.load(open(HERE / "scail_2_animation_ctxwin_ui.json"))["nodes"]} - set(info) - ui2api.SKIP)
        if missing: raise RuntimeError(f"nodes missing on the pod: {missing}")
        api = ui2api.convert(json.load(open(HERE / "scail_2_animation_ctxwin_ui.json")), info)
        for p in jobs:
            if (time.time() - t_start) / 3600 > cfg["max_hours_per_batch"]: print("batch hour cap reached, rest stays queued"); break
            job = json.load(open(p))
            try:
                secs = render(base, api, info, job, job.get("resolution", res)); p.with_suffix(".done").write_text(f"{secs:.0f}s")
                print(p.stem, f"rendered in {secs/60:.1f} min")
            except Exception as ex:
                p.with_suffix(".err").write_text(str(ex)); print(p.stem, "FAILED:", str(ex)[:300])
    finally:
        rp.delete_pod(pid); hrs = (time.time() - t_start) / 3600
        log_gpu(gpu, hrs, hrs * price, "setup" if setup_only else f"batch {len(jobs)} jobs")
        print(f"pod deleted. {hrs*60:.0f} min, ${hrs*price:.2f} (Rs {hrs*price*USD_INR:.0f})")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "init":
        dc = sys.argv[2]; v = rp.create_volume("studio-models", cfg["volume_gb"], dc); print(v)
        if v.get("id"): cfg.update({"volume_id": v["id"], "datacenter": dc}); json.dump(cfg, open(CFG_P, "w"), indent=1)
    elif cmd == "setup": run(cfg["default_resolution"], setup_only=True)
    elif cmd == "run": run(sys.argv[sys.argv.index("--res") + 1] if "--res" in sys.argv else cfg["default_resolution"])
    else:
        q = list(Q.glob("*.json")); print(f"queue: {len(q)} jobs, {sum(1 for p in q if p.with_suffix('.done').exists())} done; GPU spend today ${spent_today():.2f}")
