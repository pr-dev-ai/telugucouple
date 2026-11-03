"""The flat, generated once and never again: one plate per room/angle in sets/<name>.png (9:16, no people).
Every still prompt gets the plate as a reference image, so the sofa, the almirah and the window never change between reels.

  python make_sets.py --dry-run            # print the prompts
  python make_sets.py                      # all plates that do not exist yet (~$0.15 each on Nano Banana Pro)
  python make_sets.py hall_a bedroom_a     # only these
  python make_sets.py contact              # sets/_contact.jpg to eyeball them
"""
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import characters as ch, make_candidates as mc

EP = "fal-ai/nano-banana-pro"
SETS_DIR = ch.ROOT / "sets"


def make(names, dry):
    SETS_DIR.mkdir(exist_ok=True)
    todo = [n for n in names if not (SETS_DIR / f"{n}.png").exists()]
    print(f"{len(todo)} plates, about ${0.15*len(todo):.2f}")
    if dry:
        for n in todo:
            print(f"\n[{n}] {ch.SETS[n]}")
        return
    os.environ["FAL_KEY"] = mc.load_key(); import fal_client
    for n in todo:
        r = mc.fal_call(EP, {"prompt": f"{ch.SETS[n]} Empty room, absolutely no people, no text. {ch.NEG}",
                             "aspect_ratio": "9:16", "resolution": "1K", "num_images": 1, "output_format": "png"}, os.environ["FAL_KEY"], f"set_{n}")
        mc.save_result(r, SETS_DIR / f"{n}.png")      # retries: the VM's DNS blips
        print("ok", n, flush=True)


def contact():
    from PIL import Image, ImageDraw
    src = sorted(SETS_DIR.glob("*.png"))
    w, h, cols = 270, 480, 4
    rows = (len(src) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * w, rows * h), "white"); d = ImageDraw.Draw(canvas)
    for i, p in enumerate(src):
        im = Image.open(p).convert("RGB"); im.thumbnail((w, h))
        x, y = (i % cols) * w, (i // cols) * h
        canvas.paste(im, (x, y)); d.rectangle([x, y, x + 120, y + 20], fill="black"); d.text((x + 4, y + 4), p.stem, fill="white")
    out = SETS_DIR / "_contact.jpg"; canvas.save(out, quality=88); print("wrote", out)


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if args == ["contact"]:
        contact()
    else:
        bad = [n for n in args if n not in ch.SETS]
        if bad:
            sys.exit(f"unknown sets {bad}; known: {list(ch.SETS)}")
        make(args or list(ch.SETS), "--dry-run" in sys.argv)
