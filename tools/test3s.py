"""Gate 2: render only a 3-second slice (the hardest moves) before paying for the full reel.
   python test3s.py submit <reel_dir> <tag> <endpoint> <start> [--no-element]
   python test3s.py poll <reel_dir> <tag>           -> test_<tag>.mp4 (+ queues FaceFusion restore -> test_<tag>_restored.mp4)
Uses the reel's existing still_s01.png and its (mirrored) ref_s01.mp4, so versions are directly comparable."""
import sys, json, os, pathlib, subprocess, argparse
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import make_candidates as mc, make_multishot as m, fal_cost
ROOT = m.ROOT; ID = ROOT/"identity/padma/v1"
PROMPT = ("@Element1 dancing naturally, filmed on an ordinary handheld phone: real skin texture, natural motion blur on fast moves, "
          "fabric that swings and folds like real cloth, the same light as the place, same face, hair, jewellery and outfit in every frame, "
          "background stays still and unchanged. Relaxed smooth forehead, no frown creases.")
def sh(*a): return subprocess.run(a, check=True, capture_output=True, text=True)
ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("reel"); ap.add_argument("tag"); ap.add_argument("endpoint", nargs="?")
ap.add_argument("start", nargs="?", type=float); ap.add_argument("--no-element", dest="element", action="store_false"); ap.add_argument("--dur", type=float, default=3.0)
a = ap.parse_args(); d = pathlib.Path(a.reel).resolve(); st = d/f"test_{a.tag}.json"
os.environ["FAL_KEY"] = mc.load_key(); import fal_client
if a.cmd == "submit":
    seg = d/f"test_ref_{a.start:.2f}.mp4"
    sh("ffmpeg", "-v", "error", "-y", "-ss", str(a.start), "-t", str(a.dur), "-i", str(d/"ref_s01.mp4"), "-c:v", "libx264", "-crf", "18", "-an", str(seg))
    args = {"video_url": fal_client.upload_file(str(seg)), "image_url": fal_client.upload_file(str(d/"still_s01.png")),
            "character_orientation": "video", "keep_original_sound": False}
    if "v3" in a.endpoint and a.element:
        args["elements"] = [{"frontal_image_url": fal_client.upload_file(str(ID/"hero.png")),
                             "reference_image_urls": [fal_client.upload_file(str(ID/"s01_front_neutral.png")), fal_client.upload_file(str(ID/"s04_threequarter_l.png"))]}]
        args["prompt"] = PROMPT
    else:
        args["prompt"] = PROMPT.replace("@Element1", "The woman")
    h = fal_client.submit(a.endpoint, arguments=args)
    price = {"v3/pro": 0.168, "v3/standard": 0.126}.get(next((k for k in ("v3/pro", "v3/standard") if k in a.endpoint), ""), 0.07)
    fal_cost.spend(a.endpoint, a.dur, f"{d.name}_test_{a.tag}") if a.endpoint in getattr(fal_cost, "PRICES", {}) else None
    json.dump(dict(endpoint=a.endpoint, rid=h.request_id, start=a.start, dur=a.dur, seg=seg.name, usd=round(price * a.dur, 3)), open(st, "w"))
    print("submitted", a.tag, h.request_id, f"~${price * a.dur:.2f}")
else:
    j = json.load(open(st)); out = d/f"test_{a.tag}.mp4"
    if not out.exists():
        s = type(fal_client.status(j["endpoint"], j["rid"], with_logs=False)).__name__
        if s != "Completed": print(a.tag, s); sys.exit(2)
        r = fal_client.result(j["endpoint"], j["rid"]); m.fetch(r["video"]["url"], out); print(a.tag, "saved")
    job = ROOT/"jobs"/f"{d.name}_test_{a.tag}_restore.json"
    if not job.exists():
        rel = d.relative_to(ROOT); src = d/f"src_test_{a.tag}.mp4"; src.write_bytes(out.read_bytes())
        job.write_text(json.dumps({"type": "face_restore", "source": "identity/padma/v1/hero.png", "target": f"{rel}/{src.name}",
                                   "output": f"{rel}/test_{a.tag}_restored.mp4", "enhancer_blend": 25}, indent=1)); print("restore queued")
