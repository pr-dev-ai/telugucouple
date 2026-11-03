"""Motion bake-off on WaveSpeed: one still + one reference through the $0.04/s animators. Control = existing Kling output.
  python bakeoff_wavespeed.py <dir> submit [480p|720p]   # needs WAVESPEED_API_KEY in D:\telugucouple\.env; still.png + ref24.mp4 in <dir>
  python bakeoff_wavespeed.py <dir> poll
Uploads go through fal storage (public URLs, free) so WaveSpeed can fetch them."""
import sys, os, json, pathlib, time, urllib.request, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).parent)); import make_candidates as mc, fal_cost
ROOT = pathlib.Path(__file__).resolve().parent.parent
d = pathlib.Path(sys.argv[1]); cmd = sys.argv[2]; res = sys.argv[3] if len(sys.argv) > 3 else "480p"
key = next((l.split("=",1)[1].strip() for l in (ROOT/".env").read_text().splitlines() if l.startswith("WAVESPEED_API_KEY=")), "")
if not key: sys.exit("add WAVESPEED_API_KEY=... to D:\\telugucouple\\.env first")
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
LOOK = ("Character appearance description: a young Indian woman, same person as the reference image, ruby red pattu langa with a broad gold zari border, "
        "royal blue silk half-saree dupatta, red silk blouse, gold jhumkas, long braid.\n"
        "Background description: plain cement rooftop terrace of an ordinary apartment building in Kompally at night, black Sintex water tank, "
        "clothesline with towels, old steel railing, a single white tube light on the stairwell wall, a few lit windows of neighbouring houses, dim orange street light.")
MODELS = {  # name: (endpoint path, extra args)
    "animate2":     ("wavespeed-ai/wan-2.2/animate-2", {"prompt": LOOK, "motion_prompt": "Telangana folk dance steps, energetic, on the beat", "resolution": res}),
    "scail2":       ("wavespeed-ai/scail-2",           {"prompt": LOOK, "mode": "animate", "resolution": res}),
    "steadydancer": ("wavespeed-ai/steadydancer",      {"resolution": res}),
    "dreamactor2":  ("bytedance/dreamactor-v2",        {}),
}
rq = d / f"wavespeed_{res}.json"
def req(url, data=None):
    r = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=H, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp: return json.loads(resp.read())
    except urllib.error.HTTPError as e: return {"http": e.code, "body": e.read().decode()[:300]}
if cmd == "submit":
    os.environ["FAL_KEY"] = mc.load_key(); import fal_client
    img = fal_client.upload_file(str(d / "still.png")); vid = fal_client.upload_file(str(d / "ref24.mp4"))
    secs = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(d/"ref24.mp4")],capture_output=True,text=True).stdout)
    ids = json.load(open(rq)) if rq.exists() else {}
    for name, (ep, extra) in MODELS.items():
        if name in ids: print(name, "already submitted"); continue
        out = req(f"https://api.wavespeed.ai/api/v3/{ep}", {"image": img, "video": vid, **extra})
        rid = (out.get("data") or {}).get("id") if isinstance(out, dict) else None
        if not rid: print(name, "NOT submitted:", str(out)[:200]); continue
        ids[name] = rid; json.dump(ids, open(rq, "w"))
        bill = max(3, -(-secs // 1)); fal_cost.spend(ep, bill, f"bakeoff {d.name} {name} {res}")
        print(name, "submitted", rid, f"~${bill*fal_cost.PRICES[ep][1]*(2 if res=='720p' and ep!='bytedance/dreamactor-v2' else 1):.2f}")
else:
    ids = json.load(open(rq))
    for name, rid in ids.items():
        out = d / f"{name}_{res}.mp4"
        if out.exists(): print(name, "done"); continue
        r = req(f"https://api.wavespeed.ai/api/v3/predictions/{rid}/result")
        data = r.get("data") or {}; st = data.get("status")
        if st == "completed":
            url = (data.get("outputs") or [None])[0]
            if url: urllib.request.urlretrieve(url, out); print(name, "saved", out.name)
            else: print(name, "completed but no output", str(data)[:200])
        elif st == "failed":
            print(name, "FAILED", data.get("error")); fal_cost.refund(MODELS[name][0], 15, f"bakeoff {name}")
        else: print(name, st or r)
