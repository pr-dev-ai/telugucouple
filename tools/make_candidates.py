"""
Identity day 1 for ONE character of the couple (run once per character). Lives in D:\\telugucouple\\tools.
  python make_candidates.py candidates --who satyam --dry-run   # print the prompts and the cost, no API call
  python make_candidates.py candidates --who satyam             # 10 hero candidates on Nano Banana Pro (~$1.50)
  python make_candidates.py contact --who satyam                # labelled contact sheet -> out/<who>/candidates_contact.png
  python make_candidates.py sheet --who satyam --face out/satyam/candidates/c04.png   # 10-image reference sheet (~$1.50)
  python make_candidates.py freeze --who satyam                 # copy the sheet into identity/satyam/v1 (frozen; never regenerate)
  python make_candidates.py pair                                # 3 images of BOTH in the hall (needs both identities + sets/hall_a.png)

No LoRA step: the reel pipeline (make_multishot.py) drives Nano Banana edit with the reference images, so a LoRA is never used.
Field names checked against fal's API pages on 31 Oct 2026 (nano-banana-pro, nano-banana-pro/edit).
Reads FAL_KEY from D:\\telugucouple\\.env, then D:\\animusic\\.env, then the environment.
"""
import argparse, itertools, json, os, pathlib, shutil, sys, urllib.request

import characters as ch

HERE = pathlib.Path(__file__).parent
ROOT = ch.ROOT
PRICE_PER_IMAGE = 0.15  # Nano Banana Pro, 1K/2K, fal list price Oct 2026

FACE_TXT, BODY_TXT, CLOTHES, NEG = ch.FACE_TXT, ch.BODY_TXT, ch.CLOTHES, ch.NEG

# 5 scenes x 2 variations = 10 candidates per character, all inside the flat. Face text identical in all of them.
SCENES = {
    "satyam": [
        "head and shoulders portrait of a plain bald middle-aged uncle sitting on a blue plastic chair in a small Kukatpally flat hall, faded grey round-neck T-shirt, tube light, mild shy smile",
        "head and shoulders portrait at the open entrance door of the flat just back from the office, old-fashioned ironed checked half-sleeve shirt tucked in, office bag on the shoulder, morning daylight",
        "portrait on a narrow balcony with an iron grill and drying clothes, white banian, holding a steel chai glass, squinting in the afternoon sun",
        "portrait in a small kitchen with steel vessels behind, lungi and banian, laughing, tube light",
        "portrait sitting on the edge of a double cot in a small bedroom, steel almirah behind, plain white banian, scrolling his phone, slightly bored",
    ],
    "padma": [
        f"head and shoulders portrait of a beautiful housewife in a small Kukatpally flat hall, bright maroon saree and deep-neck blouse, jasmine in the plait, tube light, warm teasing smile. {CLOTHES['padma']}",
        "portrait in front of a steel almirah mirror in a small bedroom, adjusting her saree pallu, bangles, jasmine, morning window light",
        "portrait in a narrow balcony hanging clothes on the line, cotton saree, plait over the shoulder, afternoon sun, laughing",
        "portrait in a small kitchen with a pressure cooker behind, green saree, hair tied, looking over the shoulder at the camera, soft smile",
        "portrait at the entrance door with a tulasi pot, blue silk saree, big bindi, gold earrings, ready to go out, evening light",
    ],
}
VARIATIONS = ["shot on a phone camera, 35mm look, looking straight into the camera",
              "candid, three-quarter angle, looking slightly off camera, shot on a phone"]

SHEET = {
    "satyam": [
        ("s01_front_neutral",  "studio-style head and shoulders, plain light grey background, front view, neutral expression, even soft light"),
        ("s02_front_smile",    "same background, front view, warm toothy smile"),
        ("s03_front_laugh",    "same background, front view, laughing loudly"),
        ("s04_threequarter_l", "same background, three-quarter view turned left, neutral"),
        ("s05_threequarter_r", "same background, three-quarter view turned right, slight smile"),
        ("s06_profile_l",      "same background, full left profile, the bald crown and the ring of grey hair clearly visible"),
        ("s07_profile_r",      "same background, full right profile"),
        ("s08_fullbody_front", f"full body, head to feet, front view, plain light grey background, faded blue-checked lungi and old white banian, bare feet, black thread on the right wrist. {BODY_TXT['satyam']}"),
        ("s09_fullbody_shirt", f"full body, head to feet, front view, plain background, crumpled cream half-sleeve shirt untucked over the lungi, rubber chappals. {BODY_TXT['satyam']}"),
        ("s10_fullbody_dance", f"full body, front view, plain background, mid dance step with both arms up, stiff clumsy pose, banian and lungi, big grin. {BODY_TXT['satyam']}"),
    ],
    "padma": [
        ("s01_front_neutral",  "studio-style head and shoulders, plain light grey background, front view, neutral expression, even soft light"),
        ("s02_front_smile",    "same background, front view, warm genuine smile with dimples"),
        ("s03_front_laugh",    "same background, front view, laughing"),
        ("s04_threequarter_l", "same background, three-quarter view turned left, neutral"),
        ("s05_threequarter_r", "same background, three-quarter view turned right, soft smile"),
        ("s06_profile_l",      "same background, full left profile, the plait with jasmine visible"),
        ("s07_profile_r",      "same background, full right profile"),
        ("s08_fullbody_front", f"full body, head to feet, front view, plain light grey background, maroon saree draped low with the waist showing, fitted deep-neck blouse with elbow sleeves, bangles, anklets. {BODY_TXT['padma']}"),
        ("s09_fullbody_halfsaree", f"full body, head to feet, front view, plain background, parrot-green half saree (langa voni) with the waist showing, plait with jasmine. {BODY_TXT['padma']}"),
        ("s10_fullbody_dance", f"full body, front view, plain background, graceful mid dance step, one hand on the hip, saree pallu flying, smiling. {BODY_TXT['padma']}"),
    ],
}


def load_key():
    for env in (ROOT / ".env", pathlib.Path(r"D:\animusic\.env")):
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("FAL_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    k = os.environ.get("FAL_KEY")
    if k:
        return k
    sys.exit("FAL_KEY not found (D:\\telugucouple\\.env, D:\\animusic\\.env or the environment)")


def fal_call(endpoint, args, key, note="", tries=4):
    import fal_client, time  # pip install fal-client
    os.environ["FAL_KEY"] = key
    for k in range(tries):
        try:
            res = fal_client.subscribe(endpoint, arguments=args, with_logs=False); break
        except Exception as e:      # DNS blip or fal 5xx: nothing billed, try again
            if k == tries - 1: raise
            print("fal retry", k + 1, str(e)[:120], flush=True); time.sleep(8 * (k + 1))
    try:
        import fal_cost; fal_cost.spend(endpoint, 1, note or "candidates/sheet")
    except Exception: pass
    return res


def save_result(res, path, tries=8):
    """Download with retries: the VM's DNS drops out for a few seconds now and then, and the image is already paid for."""
    import time
    url = res["images"][0]["url"]
    for k in range(tries):
        try:
            urllib.request.urlretrieve(url, path); return path
        except Exception as e:
            if k == tries - 1: raise
            print("download retry", k + 1, e, flush=True); time.sleep(5 * (k + 1))


def out_dir(who):
    d = ROOT / "out" / who
    d.mkdir(parents=True, exist_ok=True)
    return d


def candidates(who, dry, base=None, prefix="c"):
    """base: an earlier candidate to vary from (same face, the current FACE_TXT age/look applied) -> y01..y05 via nano-banana-pro/edit."""
    d = out_dir(who) / "candidates"; d.mkdir(exist_ok=True)
    if base:
        jobs = [(f"{prefix}{i+1:02d}", f"The same {'man' if who == 'satyam' else 'woman'} as the reference image: identical face structure, eyes, "
                 f"nose, smile{' and dimples' if who == 'padma' else ''}, but now exactly as described here (age and look): {FACE_TXT[who]} "
                 f"{scene}. {VARIATIONS[i % 2]}. {NEG} One person only.")
                for i, scene in enumerate(SCENES[who])]
    else:
        jobs = [(f"{prefix}{i+1:02d}", f"{scene}. {FACE_TXT[who]} {var}. {NEG} One person only.")
                for i, (scene, var) in enumerate(itertools.product(SCENES[who], VARIATIONS))]
    print(f"{who}: {len(jobs)} candidates, about ${len(jobs)*PRICE_PER_IMAGE:.2f} on Nano Banana Pro{' (edit from ' + base + ')' if base else ''}")
    if dry:
        for name, p in jobs:
            print(f"\n[{name}] {p}")
        return
    key = load_key()
    log = json.load(open(d / "prompts.json")) if (d / "prompts.json").exists() else {}
    base_url = None
    if base:
        import fal_client; os.environ["FAL_KEY"] = key; base_url = fal_client.upload_file(base)
    for name, prompt in jobs:
        path = d / f"{name}.png"
        if path.exists():
            continue
        if base_url:
            res = fal_call("fal-ai/nano-banana-pro/edit", {"prompt": prompt, "image_urls": [base_url], "aspect_ratio": "3:4",
                                                           "resolution": "1K", "num_images": 1, "output_format": "png"}, key, f"{who}_cand_{name}")
        else:
            res = fal_call("fal-ai/nano-banana-pro", {
                "prompt": prompt, "aspect_ratio": "3:4", "resolution": "1K", "num_images": 1, "output_format": "png",
            }, key, f"{who}_cand_{name}")
        save_result(res, path)
        log[name] = prompt
        print("ok", name, flush=True)
    (d / "prompts.json").write_text(json.dumps(log, indent=2))
    print(f"Now: python make_candidates.py contact --who {who}  and pick one face")


def sheet(who, face, dry):
    d = out_dir(who) / "sheet"; d.mkdir(exist_ok=True)
    items = SHEET[who]
    print(f"{who}: {len(items)} sheet images, about ${len(items)*PRICE_PER_IMAGE:.2f} per pass")
    if dry:
        for name, p in items:
            print(f"\n[{name}] {p}")
        return
    key = load_key()
    import fal_client
    os.environ["FAL_KEY"] = key
    face_url = fal_client.upload_file(face)
    label = ch.CHARS[who]["label"]
    for name, desc in items:
        path = d / f"{name}.png"
        if path.exists():
            continue
        prompt = (f"The same {'man' if who == 'satyam' else 'woman'} as the reference image ({label}), identical face, identical age, "
                  f"{'same bald head and grey beard' if who == 'satyam' else 'same hair, bindi and nose pin, no moles anywhere'}. "
                  f"{desc}. {FACE_TXT[who]} {NEG} One person only.")
        res = fal_call("fal-ai/nano-banana-pro/edit", {
            "prompt": prompt, "image_urls": [face_url], "aspect_ratio": "3:4" if "fullbody" not in name else "9:16",
            "resolution": "1K", "num_images": 1, "output_format": "png",
        }, key, f"{who}_sheet_{name}")
        save_result(res, path)
        print("ok", name, flush=True)
    print(f"Check out/{who}/sheet as a contact sheet; redo any that drift (delete the file and rerun). Then: freeze --who {who}")


def contact(who, sub="candidates", pattern="c*.png"):
    """One image with every candidate labelled, for picking a face."""
    from PIL import Image, ImageDraw
    src = sorted((out_dir(who) / sub).glob(pattern))
    if not src:
        sys.exit(f"no {sub} yet for {who}")
    w, h, cols = 300, 400, 5
    rows = (len(src) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * w, rows * h), "white")
    d = ImageDraw.Draw(canvas)
    for i, p in enumerate(src):
        im = Image.open(p).convert("RGB")
        im.thumbnail((w, h))
        x, y = (i % cols) * w, (i // cols) * h
        canvas.paste(im, (x + (w - im.width) // 2, y + (h - im.height) // 2))
        d.rectangle([x, y, x + 150, y + 22], fill="black")
        d.text((x + 4, y + 4), p.stem, fill="white")
    out = out_dir(who) / f"{sub}_contact.jpg"
    canvas.save(out, quality=88)
    print("wrote", out)


def freeze(who):
    """Copy hero + sheet + texts into identity/<who>/v1. Frozen from then on."""
    src = sorted((out_dir(who) / "sheet").glob("s*.png"))
    if len(src) < 8:
        sys.exit(f"only {len(src)} sheet images for {who}; finish the sheet first")
    hero = out_dir(who) / "hero.png"
    if not hero.exists():
        sys.exit(f"copy the chosen candidate to {hero} first (the face the sheet was made from)")
    dst = ch.ident(who); dst.mkdir(parents=True, exist_ok=True)
    for p in src + [hero]:
        shutil.copy(p, dst / p.name)
    (dst / "FACE_TXT.txt").write_text(FACE_TXT[who])
    (dst / "BODY_TXT.txt").write_text(BODY_TXT[who])
    print(f"identity/{who}/v1 frozen with {len(src)} sheet images + hero. Now: python face_gate.py init --who {who}")


def pair(dry):
    """Three images of both of them together in the hall: proves two different faces survive one frame, and gives the profile picture."""
    d = ROOT / "out" / "pair"; d.mkdir(parents=True, exist_ok=True)
    shots = [
        ("pair_01_standing", "both standing side by side in the middle of the hall facing the camera, she is leaning on his shoulder smiling, he looks grumpy but happy, full body, tube light"),
        ("pair_02_sofa",     "both sitting on the sofa, she is laughing at him, he is holding the TV remote, half body, evening tube light"),
        ("pair_03_dance",    "both mid dance step in the hall, she graceful with the pallu flying, he stiff with both arms up, full body, phone video frame look"),
    ]
    print(f"{len(shots)} pair images, about ${len(shots)*PRICE_PER_IMAGE:.2f}")
    if dry:
        return
    key = load_key()
    import fal_client
    os.environ["FAL_KEY"] = key
    ids = [fal_client.upload_file(str(p)) for p in ch.refs("satyam") + ch.refs("padma")] + [fal_client.upload_file(str(ch.set_plate("hall_a")))]
    for name, desc in shots:
        path = d / f"{name}.png"
        if path.exists():
            continue
        prompt = (f"Two people, a married couple. The man in images 1-4 is Satyam: identical face, bald head and grey beard. "
                  f"The woman in images 5-8 is Padma: identical face. The room is EXACTLY the room in image 9, same furniture and walls. "
                  f"{desc}. He wears {CLOTHES['satyam']} She wears {CLOTHES['padma']} {FACE_TXT['satyam']} {FACE_TXT['padma']} "
                  f"Real candid phone photo in an ordinary small flat. {NEG} Exactly two people, both faces clearly visible.")
        res = fal_call("fal-ai/nano-banana-pro/edit", {
            "prompt": prompt, "image_urls": ids, "aspect_ratio": "9:16", "resolution": "1K", "num_images": 1, "output_format": "png",
        }, key, f"pair_{name}")
        save_result(res, path)
        print("ok", name, flush=True)
    print("Now: python face_gate.py check --who couple out/pair")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["candidates", "sheet", "contact", "freeze", "pair"])
    ap.add_argument("--who", choices=ch.WHO)
    ap.add_argument("--face", help="chosen candidate png (for sheet)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sub", default="candidates", help="contact: which out/<who>/<sub> folder (candidates or sheet)")
    ap.add_argument("--from", dest="base", help="candidates: vary from this earlier candidate png (edit), named y01..")
    ap.add_argument("--prefix", default="c", help="candidates: file name prefix (c for fresh, y for --from variants, r for a redo round)")
    a = ap.parse_args()
    if a.cmd == "pair":
        pair(a.dry_run)
    else:
        if not a.who:
            sys.exit("--who satyam|padma required")
        if a.cmd == "candidates":
            candidates(a.who, a.dry_run, a.base, a.prefix if a.prefix != "c" else ("y" if a.base else "c"))
        elif a.cmd == "sheet":
            if not a.face:
                sys.exit("--face required")
            sheet(a.who, a.face, a.dry_run)
        elif a.cmd == "freeze":
            freeze(a.who)
        else:
            contact(a.who, a.sub, f"{a.prefix}*.png" if a.sub == "candidates" else "s*.png")
