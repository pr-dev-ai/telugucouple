"""Telugu talking-head bake-off on WaveSpeed (5 Nov 2026). Same still + same Telugu voice through each model; control = existing omni.mp4.
  python talk_bakeoff.py <reel_dir> submit      # needs still_omni.jpg (or still_fx.png) + voice.mp3 in <reel_dir>; ~$4.6 for a 14 s line
  python talk_bakeoff.py <reel_dir> poll        # downloads <model>.mp4 into <reel_dir>/talk_bakeoff/
Then: FaceFusion restore with the mouth excluded (same as the live chain) before judging.
"""
import json, math, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent)); import motion_engines as me, fal_cost
d = pathlib.Path(sys.argv[1]).resolve(); cmd = sys.argv[2]; out = d / "talk_bakeoff"; out.mkdir(exist_ok=True)
PROMPT = "A beautiful Indian woman in a saree talking warmly to the camera at home, natural head and hand movement, handheld phone video"
MODELS = {   # name: (endpoint, extra args, $/s)
    "infinitetalk_480":  ("wavespeed-ai/infinitetalk",            {"resolution": "480p", "prompt": PROMPT}, 0.03),
    "infinitetalk_720":  ("wavespeed-ai/infinitetalk",            {"resolution": "720p", "prompt": PROMPT}, 0.06),
    "infinitetalk_fast": ("wavespeed-ai/infinitetalk-fast",       {"prompt": PROMPT}, 0.015),
    "longcat_480":       ("wavespeed-ai/longcat-avatar-1.5",      {"resolution": "480p", "prompt": PROMPT}, 0.04),
    "longcat_720":       ("wavespeed-ai/longcat-avatar-1.5",      {"resolution": "720p", "prompt": PROMPT}, 0.08),
    "hunyuan_480":       ("wavespeed-ai/hunyuan-avatar",          {"resolution": "480p", "prompt": PROMPT}, 0.03),
    "wan_s2v_480":       ("wavespeed-ai/wan-2.2/speech-to-video", {"resolution": "480p", "prompt": PROMPT}, 0.03),
    "pruna_768":         ("pruna-ai/p-video-2-pro/avatar",        {"resolution": "768p", "prompt": PROMPT}, 0.04),
}
rq = out / "requests.json"; ids = json.load(open(rq)) if rq.exists() else {}
if cmd == "submit":
    still = next(p for p in (d / "still_omni.jpg", d / "still_fx.png", d / "still.png") if p.exists()); voice = d / "voice.mp3"
    secs = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(voice)],capture_output=True,text=True).stdout)
    img, aud = me.ws_upload(still), me.ws_upload(voice); total = 0
    for name, (ep, extra, rate) in MODELS.items():
        if name in ids: print(name, "already submitted"); continue
        r = me._ws(f"https://api.wavespeed.ai/api/v3/{ep}", {"image": img, "audio": aud, **extra})
        rid = (r.get("data") or {}).get("id")
        if not rid: print(name, "NOT submitted:", str(r)[:220]); continue
        ids[name] = [ep, rid]; json.dump(ids, open(rq, "w"), indent=1)
        usd = max(3, math.ceil(secs)) * rate; total += usd
        fal_cost.spend("wavespeed/" + ep, 0, f"talk_bakeoff {name} ${usd:.2f}")   # amount in note; prices not in PRICES table
        print(name, "submitted", f"~${usd:.2f}")
    print(f"total ~${total:.2f} (Rs {total*88:.0f})")
else:
    import urllib.request
    for name, (ep, rid) in ids.items():
        f = out / f"{name}.mp4"
        if f.exists(): print(name, "done"); continue
        r = me._ws(f"https://api.wavespeed.ai/api/v3/predictions/{rid}/result"); dd = r.get("data") or {}
        if dd.get("status") == "completed" and dd.get("outputs"): urllib.request.urlretrieve(dd["outputs"][0], f); print(name, "saved")
        else: print(name, dd.get("status"), str(dd.get("error") or "")[:150])
