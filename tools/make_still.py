"""Siri still with a free-form framing (chest-up, half body, full body). Same identity rules as make_reel.
  python make_still.py <out.png> "<scene + outfit + framing>" [--ref ../identity/v1/s01_front_neutral.png]
"""
import argparse, os, pathlib, sys, urllib.request
HERE = pathlib.Path(__file__).parent; sys.path.insert(0, str(HERE))
import make_candidates as mc, fal_cost
EP = "google/nano-banana-2.1/edit"
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("scene")
ap.add_argument("--ref", default=str(HERE.parent/"identity/v1/s01_front_neutral.png"))
ap.add_argument("--ref2", default=str(HERE.parent/"identity/v1/s13_fullbody_kurti.png"))
a = ap.parse_args()
os.environ["FAL_KEY"] = mc.load_key(); import fal_client
urls = [fal_client.upload_file(a.ref), fal_client.upload_file(a.ref2)]
r = fal_client.subscribe(EP, arguments={"thinking_level": "minimal",
    "prompt": f"Same woman as the reference images, identical face and body proportions. {a.scene}. Real photo shot on an iPhone, natural light, not a studio shoot, no retouching, one person only, no moles. {mc.FACE_TXT} {mc.BODY_TXT}",
    "image_urls": urls, "aspect_ratio": "9:16", "resolution": "1K", "num_images": 1, "output_format": "png"})
urllib.request.urlretrieve(r["images"][0]["url"], a.out); fal_cost.spend(EP, 1, pathlib.Path(a.out).stem); print("ok", a.out)
