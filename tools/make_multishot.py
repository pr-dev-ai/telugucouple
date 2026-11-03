"""
Couple reel from a trending reference: split the reference at its cuts, make one still of Satyam + Padma per shot that copies the
shot's framing inside the flat, animate, face-restore, join.

  python make_multishot.py submit <ref.mp4> --name chinni --start 0 --dur 15 --set hall_a --look "she in a red saree, he in banian and lungi" --route mc
  python poll.py ../reels/<date>_<name>                       # downloads motion_*.mp4 / i2v_*.mp4 (verified)
  python make_multishot.py restore ../reels/<date>_<name>     # queues FaceFusion jobs (two passes for two-person clips)
  python make_multishot.py join ../reels/<date>_<name>        # merges split halves if any, concats shots -> joined.mp4

Routes (--route), decided by the bake-off:
  mc     Kling Motion Control with the couple still + the full reference (Kling copies only the LARGEST dancer's motion)
  split  one still per person on the same room plate, the reference masked to one dancer each, Kling MC twice, halves merged
  i2v    Kling 2.5 turbo pro image-to-video from the couple still with a dance prompt (5 or 10 s, no beat-exact steps)
Shots shorter than MIN_SHOT seconds are merged into the previous one (Kling needs ~3 s).
"""
import argparse, json, os, pathlib, subprocess, sys, time, urllib.request

HERE = pathlib.Path(__file__).parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE)); import make_candidates as mc, characters as ch, fal_cost


def fetch(url, dst, tries=6):
    """urlretrieve with retries: the VM's DNS drops out for a few seconds now and then (3 Nov 2026)."""
    for k in range(tries):
        try: return urllib.request.urlretrieve(url, dst)
        except Exception as e:
            if k == tries - 1: raise
            print("download retry", k + 1, e, flush=True); time.sleep(5 * (k + 1))


EDIT_EP = "google/nano-banana-2.1/edit"
MC_EP = "fal-ai/kling-video/v2.6/standard/motion-control"
I2V_EP = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
MIN_SHOT = 3.0; SCENE_T = 0.35


def sh(*a, **k): return subprocess.run(a, check=True, capture_output=True, text=True, **k)


def dur_of(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)


def cuts(path, start, dur):
    r = subprocess.run(["ffmpeg", "-ss", str(start), "-t", str(dur), "-i", str(path), "-vf", f"select='gt(scene,{SCENE_T})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    ts = [float(l.split("pts_time:")[1].split()[0]) for l in r.splitlines() if "pts_time:" in l]
    edges = [0.0] + ts + [dur]; shots = []
    for a, b in zip(edges, edges[1:]):
        if shots and (b - a < MIN_SHOT or shots[-1][1] - shots[-1][0] < MIN_SHOT): shots[-1] = (shots[-1][0], b)
        else: shots.append((a, b))
    if len(shots) > 1 and shots[-1][1] - shots[-1][0] < MIN_SHOT:
        last = shots.pop(); shots[-1] = (shots[-1][0], last[1])
    return shots


def gate(path, who="couple"):
    g = subprocess.run([sys.executable, str(HERE / "face_gate.py"), "check", "--who", who, str(path)], capture_output=True, text=True)
    line = (g.stdout.strip().splitlines() or ["?"])[-1]
    return g.returncode == 0, line


def couple_prompt(look, glam, light, order, anchor):
    left, right = ("Satyam", "Padma") if order == "satyam-left" else ("Padma", "Satyam")
    anchor_txt = ("One image shows the same two people earlier in this same video: keep EXACTLY the same garments, fabric, colours, "
                  "jewellery, hairstyles and room as in that image. " if anchor else "")
    return (f"Two people, a married couple, in ONE frame. The man in the first four images is Satyam: identical face, bald head, grey beard, belly. "
            f"The woman in the next four images is Padma: identical face and body. {anchor_txt}"
            f"The place is EXACTLY the empty room shown in one of the images: same walls, floor, furniture, window and door. "
            f"Recreate the exact camera framing, crop, both poses, body angles and the lighting direction of the LAST image, but it is THEM, "
            f"not the people in the last image: {left} stands where the left person is and {right} where the right person is. "
            f"Their look: {look}. He wears {ch.CLOTHES['satyam']} She wears {ch.CLOTHES['padma']} "
            f"{(ch.GLAM['padma'] + ' ' + ch.GLAM['satyam'] + ' ') if glam else ''}"
            f"{ch.LIGHT[light]}, lit only by the light sources visible in the room, with the same colour temperature, soft shadows and light "
            f"falloff spilling onto their skin and clothes, never evenly studio-lit or flash-lit. Background slightly out of focus like a phone "
            f"video frame, a little sensor noise, real candid handheld phone video of a couple dancing at home, nothing glossy or cinematic. "
            f"Exactly two people, both faces frontal or three-quarter and clearly visible, hands visible. Absolutely no text, captions, stickers, "
            f"logos or watermarks. {ch.FACE_TXT['satyam']} {ch.FACE_TXT['padma']} {ch.BODY_TXT['satyam']} {ch.BODY_TXT['padma']}")


def solo_still(fal_client, couple_still, who, out):
    """split route: the same photo with only one of them in it (the other removed, room filled in)."""
    other = "the woman (Padma)" if who == "satyam" else "the man (Satyam)"
    keep = "the man (Satyam)" if who == "satyam" else "the woman (Padma)"
    r = fal_client.subscribe(EDIT_EP, arguments={"thinking_level": "minimal", "aspect_ratio": "9:16", "resolution": "1K", "num_images": 1,
        "output_format": "png", "image_urls": [fal_client.upload_file(str(couple_still))],
        "prompt": (f"Remove {other} completely from this photo and fill the space with the room background that would be behind them. "
                   f"Keep {keep} exactly as is, same pose, same clothes, same position in the frame. Keep the room, framing, crop, colours "
                   f"and lighting pixel-identical. One person only in the result. No text or watermark.")})
    fetch(r["images"][0]["url"], out); fal_cost.spend(EDIT_EP, 1, f"solo_{out.stem}")


def masked_ref(seg, out, split, keep_left):
    """Black out the other dancer's side of the reference so Kling sees one dancer."""
    w = 720; x0, x1 = (int(w * split), w) if keep_left else (0, int(w * split))
    sh("ffmpeg", "-v", "error", "-y", "-i", str(seg), "-vf", f"drawbox=x={x0}:y=0:w={x1-x0}:h=ih:color=black:t=fill",
       "-c:v", "libx264", "-crf", "18", "-an", str(out))


def submit(a):
    out = ROOT / "reels" / f"{time.strftime('%Y-%m-%d')}_{a.name}"; out.mkdir(parents=True, exist_ok=True)
    ref = out / "ref.mp4"
    sp = f",setpts={a.slow}*PTS" if a.slow != 1 else ""
    sh("ffmpeg", "-v", "error", "-y", "-ss", str(a.start), "-t", str(a.dur / a.slow), "-i", a.ref,
       "-vf", f"scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280{sp}", "-r", "24", "-an", "-c:v", "libx264", "-crf", "18", str(ref))
    a.dur = dur_of(ref)
    if a.cuts:
        cs = [float(x) * a.slow for x in a.cuts.split(",")]; e = [0.0] + cs + [a.dur]; shots = list(zip(e, e[1:]))
    else:
        shots = cuts(ref, 0, a.dur)
    print("shots:", [(round(x, 1), round(y, 1)) for x, y in shots], "route:", a.route)
    for s_, e_ in shots:        # Kling MC accepts 3-30 s per request; a 422 (bad input) CAN be billed, a 5xx is not
        assert 3.0 <= (e_ - s_) <= 30.0, f"shot {s_:.1f}-{e_:.1f} is {e_-s_:.2f}s, Kling needs 3-30 s (merge or re-cut)"
    os.environ["FAL_KEY"] = mc.load_key(); import fal_client
    ids = [fal_client.upload_file(str(p)) for p in ch.refs("satyam") + ch.refs("padma")]
    plate = fal_client.upload_file(str(ch.set_plate(a.set)))
    rq = out / "requests.json"
    reqs = json.load(open(rq)) if rq.exists() else {"endpoint": MC_EP}
    plan = json.load(open(out / "shots.json")) if (out / "shots.json").exists() else []
    looks = [x.strip() for x in a.look.split("||")]
    meta = {"route": a.route, "set": a.set, "order": a.order, "split": a.split, "light": a.light, "look": a.look}
    json.dump(meta, open(out / "meta.json", "w"), indent=1)
    for i, (s, e) in enumerate(shots, 1):
        look = looks[min(i - 1, len(looks) - 1)]
        tag = f"s{i:02d}"
        keys = [f"motion_{tag}"] if a.route == "mc" else ([f"i2v_{tag}"] if a.route == "i2v" else [f"motion_{tag}L", f"motion_{tag}R"])
        if all(k in reqs for k in keys): print(tag, "already submitted"); continue
        seg = out / f"ref_{tag}.mp4"; frame = out / f"frame_{tag}.jpg"; still = out / f"still_{tag}.png"
        first = out / "still_s01.png"      # outfit anchor: later shots see shot 1's still so colours do not drift
        sh("ffmpeg", "-v", "error", "-y", "-ss", str(s), "-t", str(e - s), "-i", str(ref), "-c:v", "libx264", "-crf", "18", "-an", str(seg))
        fts = [float(x) for x in a.frame.split(",")] if a.frame else []
        ft = fts[i - 1] if i - 1 < len(fts) and fts[i - 1] >= 0 else s + 0.3
        if not frame.exists() or a.frame: sh("ffmpeg", "-v", "error", "-y", "-ss", str(ft), "-i", str(ref), "-frames:v", "1", str(frame))
        # ---- the couple still, gated on BOTH faces ----
        for attempt in range(3):
            if still.exists():
                ok, line = gate(still); print(tag, "gate:", line)
                if ok: break
                still.rename(still.with_name(f"{still.stem}_fail{attempt}{still.suffix}"))   # no delete permission in the VM
            anchor = [fal_client.upload_file(str(first))] if (i > 1 and first.exists() and a.anchor) else []
            r = fal_client.subscribe(EDIT_EP, arguments={"thinking_level": "minimal", "aspect_ratio": "9:16", "resolution": "1K",
                "num_images": 1, "output_format": "png", "image_urls": ids + anchor + [plate, fal_client.upload_file(str(frame))],
                "prompt": couple_prompt(look, a.glam, a.light, a.order, bool(anchor))})
            fetch(r["images"][0]["url"], still); fal_cost.spend(EDIT_EP, 1, f"{a.name}_{tag}")
        ok, line = gate(still)
        if not ok and not a.force:
            print(tag, "STILL FAILS THE COUPLE GATE after 3 tries, not animated:", line, "(--force to animate anyway)"); continue
        im = __import__("cv2").imread(str(still)); assert im is not None and min(im.shape[:2]) >= 720, f"{still.name} under 720 px (Kling 422 risk)"
        # ---- animate ----
        if a.route == "mc":
            h = fal_client.submit(MC_EP, arguments={"video_url": fal_client.upload_file(str(seg)), "image_url": fal_client.upload_file(str(still)),
                "character_orientation": "video", "keep_original_sound": False,
                "prompt": "An older bald Indian man with a grey beard and a beautiful Indian woman in a saree, the same two people as the image, dancing together in their small flat, performing the movement naturally"})
            fal_cost.spend(MC_EP, round(e - s, 2), f"{a.name}_{tag}")
            reqs[f"motion_{tag}"] = h.request_id; plan.append({"shot": tag, "start": s, "end": e})
        elif a.route == "i2v":
            d = "10" if (e - s) > 5.5 else "5"
            h = fal_client.submit(I2V_EP, arguments={"image_url": fal_client.upload_file(str(still)), "duration": d, "cfg_scale": 0.5,
                "prompt": (f"The same two people dancing together to a fast Telugu folk song in their small flat: {look}. The woman dances gracefully "
                           f"with energetic full-body steps and her saree pallu swinging; the bald old man copies her steps stiffly and clumsily but with "
                           f"full enthusiasm. Handheld phone video, static camera, both stay fully in frame, faces visible."),
                "negative_prompt": "blur, distortion, low quality, extra people, text, watermark, morphing faces"})
            fal_cost.spend(I2V_EP, int(d), f"{a.name}_{tag}")
            reqs[f"i2v_{tag}"] = h.request_id; plan.append({"shot": tag, "start": s, "end": s + int(d)})
        else:   # split
            for side, who in (("L", "satyam" if a.order == "satyam-left" else "padma"), ("R", "padma" if a.order == "satyam-left" else "satyam")):
                key = f"motion_{tag}{side}"
                if key in reqs: continue
                solo = out / f"still_{tag}{side}.png"; segm = out / f"ref_{tag}{side}.mp4"
                if not solo.exists(): solo_still(fal_client, still, who, solo)
                ok1, line1 = gate(solo, who); print(tag + side, "gate:", line1)
                if not ok1 and not a.force: print(tag + side, "solo still fails the gate, skipped (--force to animate anyway)"); continue
                masked_ref(seg, segm, a.split, keep_left=(side == "L"))
                h = fal_client.submit(MC_EP, arguments={"video_url": fal_client.upload_file(str(segm)), "image_url": fal_client.upload_file(str(solo)),
                    "character_orientation": "video", "keep_original_sound": False,
                    "prompt": ("An older bald Indian man with a grey beard" if who == "satyam" else "A beautiful Indian woman in a saree")
                              + ", the same person as the image, dancing in a small flat, performing the movement naturally"})
                fal_cost.spend(MC_EP, round(e - s, 2), f"{a.name}_{tag}{side}")
                reqs[key] = h.request_id; plan.append({"shot": tag + side, "start": s, "end": e})
                json.dump(reqs, open(rq, "w"))
        json.dump(reqs, open(rq, "w"))      # save after every shot so a timeout never loses a paid job
        json.dump(plan, open(out / "shots.json", "w"), indent=1)
        print(tag, f"{e-s:.1f}s submitted ({a.route})", flush=True)
    mult = 2 if a.route == "split" else 1
    print(f"total {a.dur:.0f}s, about ${a.dur*0.07*mult + len(shots)*0.054*(1+2*(a.route=='split')):.2f}. Next: python poll.py {out}")


def restore(d):
    d = pathlib.Path(d).resolve(); rel = d.relative_to(ROOT)
    for p in sorted(list(d.glob("motion_s*.mp4")) + list(d.glob("i2v_s*.mp4"))):
        tag = p.stem.split("_")[1]; src = d / f"src_{d.name}_{tag}.mp4"
        if not src.exists(): src.write_bytes(p.read_bytes())
        job = ROOT / "jobs" / f"{d.name}_{tag}_restore.json"
        if job.exists(): continue
        if tag.endswith(("L", "R")):
            meta = json.load(open(d / "meta.json")) if (d / "meta.json").exists() else {"order": "satyam-left"}
            left_is = "satyam" if meta.get("order", "satyam-left") == "satyam-left" else "padma"
            who = left_is if tag.endswith("L") else ("padma" if left_is == "satyam" else "satyam")
            passes = [{"source": f"identity/{who}/v1/hero.png", "mode": "one"}]
        else:
            passes = [{"source": f"identity/{w}/v1/hero.png", "mode": "many", "gender": ch.CHARS[w]["gender"], "age": ch.CHARS[w]["age"]} for w in ch.WHO]
        job.write_text(json.dumps({"type": "face_restore", "target": f"{rel}/{src.name}", "output": f"{rel}/restored_{tag}.mp4", "passes": passes}, indent=1))
        print("queued", job.name, [p_["source"].split("/")[1] for p_ in passes])


def merge_halves(left, right, out, split=0.5, feather=40):
    """Left half of clip L + right half of clip R, blended over `feather` px at the split line. Both from the same room plate."""
    import cv2, numpy as np
    cl, cr = cv2.VideoCapture(str(left)), cv2.VideoCapture(str(right))
    n = int(min(cl.get(cv2.CAP_PROP_FRAME_COUNT), cr.get(cv2.CAP_PROP_FRAME_COUNT)))
    fps = cl.get(cv2.CAP_PROP_FPS) or 24
    w, h = int(cl.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cl.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cut = int(w * split); x0, x1 = max(0, cut - feather), min(w, cut + feather)
    alpha = np.zeros((1, w, 1), np.float32); alpha[:, :x0] = 1.0; alpha[:, x0:x1, 0] = np.linspace(1, 0, x1 - x0)
    tmp = out.with_suffix(".raw.mp4"); vw = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for _ in range(n):
        okl, fl = cl.read(); okr, fr = cr.read()
        if not (okl and okr): break
        if fr.shape != fl.shape: fr = cv2.resize(fr, (w, h))
        vw.write((fl.astype(np.float32) * alpha + fr.astype(np.float32) * (1 - alpha)).astype(np.uint8))
    vw.release()
    sh("ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-an", str(out))
    tmp.unlink(missing_ok=True)


def join(d):
    d = pathlib.Path(d)
    meta = json.load(open(d / "meta.json")) if (d / "meta.json").exists() else {}
    tags = sorted({p.stem.split("_")[1].rstrip("LR") for p in d.glob("*_s*.mp4") if p.stem.split("_")[0] in ("motion", "i2v", "restored")})
    parts = []
    for tag in tags:
        L = next((p for p in [d / f"restored_{tag}L.mp4", d / f"motion_{tag}L.mp4"] if p.exists()), None)
        R = next((p for p in [d / f"restored_{tag}R.mp4", d / f"motion_{tag}R.mp4"] if p.exists()), None)
        if L and R:
            m = d / f"merged_{tag}.mp4"
            if not m.exists(): merge_halves(L, R, m, meta.get("split", 0.5)); print("merged", tag)
            parts.append(m); continue
        p = next((p for p in [d / f"restored_{tag}.mp4", d / f"motion_{tag}.mp4", d / f"i2v_{tag}.mp4"] if p.exists()), None)
        if p: parts.append(p)
    lst = d / "concat.txt"; lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "scale=720:1280,fps=30", "-an",
       "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", str(d / "joined.mp4"))
    print("joined", len(parts), "shots ->", d / "joined.mp4")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["submit", "restore", "join"]); ap.add_argument("path")
    ap.add_argument("--name"); ap.add_argument("--start", type=float, default=0); ap.add_argument("--dur", type=float, default=15)
    ap.add_argument("--look", default="she in a bright saree, he in banian and lungi")
    ap.add_argument("--set", default="hall_a", choices=list(ch.SETS)); ap.add_argument("--light", default="evening", choices=list(ch.LIGHT))
    ap.add_argument("--route", default="mc", choices=["mc", "split", "i2v"])
    ap.add_argument("--order", default="satyam-left", choices=["satyam-left", "padma-left"], help="who stands on the left in the reference")
    ap.add_argument("--split", type=float, default=0.5, help="split route: x fraction of the frame where the two dancers divide")
    ap.add_argument("--plain", dest="glam", action="store_false"); ap.add_argument("--force", action="store_true", help="animate even if the gate fails")
    ap.add_argument("--cuts", default="", help="manual cut times in the original reference, comma separated")
    ap.add_argument("--no-anchor", dest="anchor", action="store_false", help="transition reels: do NOT copy shot 1's outfits into later shots")
    ap.add_argument("--frame", default="", help="comma list: time in the trimmed ref to take each shot's still frame from; -1 = default s+0.3")
    ap.add_argument("--slow", type=float, default=1.0, help="1.2 = play the reference 20%% slower (longer reel)")
    a = ap.parse_args()
    {"submit": lambda: submit(argparse.Namespace(ref=a.path, **{k: v for k, v in vars(a).items() if k not in ("cmd", "path")})),
     "restore": lambda: restore(a.path), "join": lambda: join(a.path)}[a.cmd]()
