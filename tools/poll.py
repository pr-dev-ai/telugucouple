"""Poll fal requests saved in a reels folder's requests.json and download finished videos.
  python poll.py ../reels/2026-10-31_compare
"""
import json, os, pathlib, sys, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import make_candidates as mc

EP = {"replace": "fal-ai/wan/v2.2-14b/animate/replace",
      "motion": "fal-ai/kling-video/v2.6/standard/motion-control",
      "i2v": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"}

d = pathlib.Path(sys.argv[1])
reqs = json.load(open(d / "requests.json"))
os.environ["FAL_KEY"] = mc.load_key()
import fal_client
for key, rid in reqs.items():
    if key == "endpoint": continue
    out = d / f"{key}.mp4"
    if out.exists():
        print(key, "done"); continue
    ep = EP[key.split("_")[0]]
    try:
        st = type(fal_client.status(ep, rid, with_logs=False)).__name__
        r = fal_client.result(ep, rid) if st == "Completed" else None
    except Exception as e:
        msg = str(e)
        if not (d / f"{key}.error.txt").exists():      # log the fal refund once per failed request id
            try:
                import fal_cost, json as _j
                plan = {x["shot"]: x for x in _j.load(open(d / "shots.json"))} if (d / "shots.json").exists() else {}
                tag = key.split("_")[1]; secs = plan[tag]["end"] - plan[tag]["start"] if tag in plan else 0
                if secs: fal_cost.refund(ep, round(secs, 2), f"{d.name}_{tag} {rid[:8]}")
            except Exception as ex: print("refund log skipped:", ex)
        (d / f"{key}.error.txt").write_text(msg)
        print(key, "FAILED:", msg[msg.find("msg"):msg.find("msg")+160] if "msg" in msg else msg[:160]); continue
    if st == "Completed":
        tmp = out.with_suffix(".part")
        urllib.request.urlretrieve(r["video"]["url"], tmp)
        # integrity check: a cut-off download decodes with errors and turns into black frames later
        import subprocess
        errs = subprocess.run(["ffmpeg","-v","error","-i",str(tmp),"-f","null","-"],capture_output=True,text=True).stderr.strip()
        if errs:
            tmp.unlink(); print(key, "download damaged, deleted; run poll again"); continue
        tmp.rename(out); print(key, "saved (verified)")
    else:
        print(key, st)
