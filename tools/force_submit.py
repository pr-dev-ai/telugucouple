"""Submit an eyeballed still to Kling when the face gate fails only because the face is small (far full-body shots).
   python force_submit.py <reel_dir> <tag> <start> <end> <name>"""
import sys, json, os, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import make_multishot as m, make_candidates as mc, fal_cost
d, tag, s, e, name = pathlib.Path(sys.argv[1]), sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
os.environ["FAL_KEY"] = mc.load_key(); import fal_client
rq = d/"requests.json"; reqs = json.load(open(rq)) if rq.exists() else {"endpoint": m.MC_EP}
if f"motion_{tag}" in reqs: sys.exit(f"{tag} already submitted")
h = fal_client.submit(m.MC_EP, arguments={"video_url": fal_client.upload_file(str(d/f"ref_{tag}.mp4")), "image_url": fal_client.upload_file(str(d/f"still_{tag}.png")),
    "character_orientation": "video", "keep_original_sound": False, "prompt": "A young Indian woman, same person as the image, performing the movement naturally"})
fal_cost.spend(m.MC_EP, round(e-s, 2), f"{name}_{tag}"); reqs[f"motion_{tag}"] = h.request_id; json.dump(reqs, open(rq, "w"))
sp = d/"shots.json"; plan = json.load(open(sp)) if sp.exists() else []; plan.append({"shot": tag, "start": s, "end": e}); json.dump(plan, open(sp, "w"), indent=1)
print(tag, "forced submit", h.request_id)
