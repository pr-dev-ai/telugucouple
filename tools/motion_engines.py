"""Motion engines behind one interface (5 Nov 2026). Default engine: dreamactor (passed the 5-reel bake-off, Rs 66 vs Kling Rs 92 per 15 s).
  kling       fal Kling 2.6 Standard Motion Control ($0.070/s, 720p, sharpest)
  dreamactor  WaveSpeed bytedance/dreamactor-v2 ($0.05/s, ~694x1242, max 30 s)
  scail2      WaveSpeed hosted SCAIL-2 480p ($0.04/s)  - fallback when our own GPU is not up
  scail2gpu   our rented GPU (gpu/ queue, see tools/gpu/README.md) - ~Rs 5-10 per clip
Every engine returns a request id; poll.py looks the engine up in requests.json["engines"].
"""
import json, math, pathlib, subprocess, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
WS = {"dreamactor": "bytedance/dreamactor-v2", "scail2": "wavespeed-ai/scail-2"}
ENGINES = ("kling", "dreamactor", "scail2", "scail2gpu")

def _env(k):
    for l in (ROOT / ".env").read_text().splitlines():
        if l.startswith(k + "="): return l.split("=", 1)[1].strip()
    return ""

def ws_upload(path):
    out = subprocess.run(["curl", "-s", "-X", "POST", "-H", f"Authorization: Bearer {_env('WAVESPEED_API_KEY')}", "-F", f"file=@{path}",
                          "https://api.wavespeed.ai/api/v3/media/upload/binary"], capture_output=True, text=True).stdout
    return json.loads(out)["data"]["download_url"]

def _ws(url, data=None):
    r = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, method="POST" if data is not None else "GET",
                               headers={"Authorization": f"Bearer {_env('WAVESPEED_API_KEY')}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp: return json.loads(resp.read())
    except urllib.error.HTTPError as e: return {"http": e.code, "body": e.read().decode()[:300]}

def billed_units(engine, secs):
    return max(3, math.ceil(secs)) if engine in WS else round(secs, 2)

def cost_endpoint(engine):
    return {"dreamactor": "bytedance/dreamactor-v2", "scail2": "wavespeed-ai/scail-2"}.get(engine)

def submit_ws(engine, seg, still, prompt=""):
    args = {"image": ws_upload(still), "video": ws_upload(seg)}
    if engine == "scail2": args.update({"mode": "animate", "resolution": "480p", "prompt": prompt or "the same person as the image, dancing naturally"})
    out = _ws(f"https://api.wavespeed.ai/api/v3/{WS[engine]}", args)
    rid = (out.get("data") or {}).get("id")
    if not rid: raise RuntimeError(f"{engine} submit failed: {str(out)[:200]}")
    return rid

def submit_gpu(seg, still, out_mp4, tag, mode="replace", people=1):
    """Drop a job for the rented-GPU runner (tools/gpu/run_batch.py picks these up in the daily window)."""
    q = ROOT / "gpu_queue"; q.mkdir(exist_ok=True)
    job = {"engine": "scail2", "still": str(pathlib.Path(still).resolve().relative_to(ROOT)), "ref": str(pathlib.Path(seg).resolve().relative_to(ROOT)),
           "out": str(pathlib.Path(out_mp4).resolve().relative_to(ROOT)), "resolution": "720p", "mode": mode, "people": people, "tag": tag}   # 720p; solo = replace (5 Nov), couple = 2-person animate in the flat (6 Nov)
    p = q / (pathlib.Path(out_mp4).parent.name + "_" + tag + ".json"); json.dump(job, open(p, "w"), indent=1)
    return "gpu:" + p.name

def poll_ws(engine, rid):
    """-> ('done', url) | ('failed', msg) | ('running', status)"""
    r = _ws(f"https://api.wavespeed.ai/api/v3/predictions/{rid}/result"); d = r.get("data") or {}
    st = d.get("status")
    if st == "completed": return "done", (d.get("outputs") or [None])[0]
    if st == "failed": return "failed", str(d.get("error"))[:200]
    return "running", st or str(r)[:120]
