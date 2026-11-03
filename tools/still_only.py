"""Make candidate stills for one shot without animating (to eyeball before paying for Kling).
   python still_only.py <reel_dir> <tag> <n> "<look>"   -> cand_<tag>_1.png ... + gate scores"""
import sys, os, pathlib, subprocess, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import make_multishot as m, make_candidates as mc, fal_cost
d, tag, n, look = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4]
os.environ["FAL_KEY"] = mc.load_key(); import fal_client
ids = [fal_client.upload_file(str(m.ROOT/f"identity/v1/{x}")) for x in ("hero.png","s01_front_neutral.png","s04_threequarter_l.png","s13_fullbody_kurti.png")]
frame = fal_client.upload_file(str(d/f"frame_{tag}.jpg"))
prompt = (f"The woman from the first four images, identical face and body. Recreate the exact camera framing, crop, pose, body angle and lighting direction of the last image, "
  f"but it is HER, not the person in the last image. Her look and place: {look}. {m.GLAM} Lighting must be motivated by the scene itself: she is lit only by the light sources "
  "visible in the place, with the same colour temperature, soft shadows and light falloff, never evenly studio-lit or flash-lit. Background slightly out of focus like a phone "
  "portrait shot, visible sensor noise and slight motion softness in low light, real candid handheld phone video frame, ordinary everyday location, nothing glossy or cinematic. "
  "Real photo shot on an iPhone, no retouching, one person only, no moles. Absolutely no text, captions, stickers, logos or watermarks anywhere in the image. "
  f"{mc.FACE_TXT} {mc.BODY_TXT}")
for i in range(1, n+1):
    out = d/f"cand_{tag}_{i}.png"
    r = fal_client.subscribe(m.EDIT_EP, arguments={"thinking_level": "minimal", "aspect_ratio": "9:16", "resolution": "1K", "num_images": 1,
        "output_format": "png", "image_urls": ids + [frame], "prompt": prompt})
    urllib.request.urlretrieve(r["images"][0]["url"], out); fal_cost.spend(m.EDIT_EP, 1, f"{d.name}_{tag}_cand")
    g = subprocess.run([sys.executable, str(pathlib.Path(__file__).parent/"face_gate.py"), "check", str(out)], capture_output=True, text=True)
    print(out.name, (g.stdout.strip().splitlines() or ["?"])[-1], flush=True)
