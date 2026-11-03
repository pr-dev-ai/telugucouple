"""
Make one reel from a reference video and one locked identity (single-person path kept from Siri).

  python make_reel.py <ref_video> --name <slug> [--still identity/v1/s10_fullbody_front_gym.png]
                      [--start 0 --dur 10] [--scene "in a modern gym"] [--mode motion|replace] [--res 720p]

Steps: trim ref to 9:16 720x1280 -> (optional) Siri still placed in a scene with Nano Banana 2 Edit ->
Kling Motion Control (her body, face, outfit, scene from the still; movement from the ref)  OR
Wan Animate Replace (keeps the ref's real background, swaps the person) -> face gate on every 12th frame
-> 1080x1920 export with a small "AI" mark -> reels/<date>_<slug>/final.mp4
Pick trending audio inside Instagram when posting; this script strips audio on purpose.
"""
import argparse, json, os, pathlib, subprocess, sys, time, urllib.request
HERE = pathlib.Path(__file__).parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE)); import make_candidates as mc, fal_cost
EDIT_EP = "google/nano-banana-2.1/edit"

def sh(*a): subprocess.run(a, check=True)

ap = argparse.ArgumentParser()
ap.add_argument("ref"); ap.add_argument("--name", required=True)
ap.add_argument("--still", default=str(ROOT/"identity/v1/s10_fullbody_front_gym.png"))
ap.add_argument("--start", type=float, default=0); ap.add_argument("--dur", type=float, default=22)  # house length: 20-25 s reels
ap.add_argument("--scene", help="if given, place Siri in this scene first with Nano Banana 2 Edit ($0.08)")
ap.add_argument("--mode", choices=["motion","replace"], default="motion")
ap.add_argument("--res", default="480p", help="replace mode only: 480p $0.04/s, 580p $0.06, 720p $0.08 (FaceFusion + upscale after)")
ap.add_argument("--fps", type=int, default=24, help="reference fps; Wan Animate bills frames/16, so --fps 16 for replace mode is 1.5x cheaper than 24")
ap.add_argument("--orientation", choices=["video","image"], default="video", help="motion mode: video=complex full-body motion (<=30s), image=camera-led (<=10s)")
a = ap.parse_args()

out = ROOT/"reels"/f"{time.strftime('%Y-%m-%d')}_{a.name}"; out.mkdir(parents=True, exist_ok=True)
ref = out/"ref.mp4"
sh("ffmpeg","-v","error","-y","-ss",str(a.start),"-t",str(a.dur),"-i",a.ref,
   "-vf","scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280","-r",str(a.fps),"-an","-c:v","libx264","-crf","20",str(ref))

os.environ["FAL_KEY"] = mc.load_key(); import fal_client
still = pathlib.Path(a.still)
if a.scene:
    still = out/"still.png"
    if not still.exists():
        r = fal_client.subscribe(EDIT_EP, arguments={"thinking_level": "minimal",
            "prompt": f"Same woman as the reference, identical face and body, full body visible head to shoes, standing naturally {a.scene}. Photograph, phone camera, natural light, one person only, no moles. {mc.FACE_TXT} {mc.BODY_TXT}",
            "image_urls":[fal_client.upload_file(a.still)], "aspect_ratio":"9:16", "resolution":"1K", "num_images":1, "output_format":"png"})
        urllib.request.urlretrieve(r["images"][0]["url"], still); fal_cost.spend(EDIT_EP, 1, a.name); print("still ok")

vid_url = fal_client.upload_file(str(ref)); img_url = fal_client.upload_file(str(still))
if a.mode == "motion":
    ep, args = "fal-ai/kling-video/v2.6/standard/motion-control", {"video_url":vid_url,"image_url":img_url,
        "character_orientation":a.orientation,"keep_original_sound":False,
        "prompt":"A young Indian woman, same person as the image, performing the movement naturally"}
else:
    ep, args = "fal-ai/wan/v2.2-14b/animate/replace", {"video_url":vid_url,"image_url":img_url,"resolution":a.res}
h = fal_client.submit(ep, arguments=args)
billed = a.dur if a.mode == "motion" else a.dur * a.fps / 16     # Kling MC: reference length; Wan: frames/16
usd = fal_cost.spend(ep, round(billed, 2), a.name, res=a.res)
print(f"billed {billed:.1f} s, about ${usd:.2f} (₹{usd*88:.0f})")
json.dump({a.mode: h.request_id, "endpoint": ep}, open(out/"requests.json","w"))
print("submitted", h.request_id, "-> then: python poll.py", out, "&& python finish.py", out)
