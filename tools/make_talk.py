"""
Padma talking reel: she talks to the phone about her day (Telugu-English), bold saree look, lip-synced, in the flat.

  python make_talk.py new     <slug> --text "<script>"                 # reels/<date>_<slug>/script.txt (or write it yourself)
  python make_talk.py voice   ../reels/<date>_<slug> [--speed 1.06]    # ElevenLabs take + Scribe check of every Telugu word, retakes (<=4) -> voice.mp3
                                                                      #   exit 3 = run again to continue, exit 4 = a word is still wrong (clips in takes_*/)
  python make_talk.py still   ../reels/<date>_<slug> --set kitchen_a --look "..." --action "stirring a pan"
  python make_talk.py animate ../reels/<date>_<slug> [--sync]          # OmniHuman 1.5 (static camera) [+ lipsync-2-pro]; resumable
  python make_talk.py poll    ../reels/<date>_<slug>                   # downloads omni.mp4 / sync.mp4 (verified)
  python make_talk.py restore ../reels/<date>_<slug>                   # FaceFusion one pass, mouth NOT touched -> joined.mp4
  python make_multishot.py blend ../reels/<date>_<slug>                # person sits in the room
  python make_talk.py post    ../reels/<date>_<slug>                   # realism export + burned subtitles + voice -> post.mp4 (+ _ig copy < 10 MB)

Look rule (Pradeep, 4 Nov): bold but recommendable. Deep-neck blouse, saree low on the waist, cleavage visible naturally while she does
home things; never a camera zoom or a pose aimed at the chest; nothing sexual in the words. Captions/hook do the selling.
"""
import argparse, base64, json, os, pathlib, subprocess, sys, time, urllib.request

HERE = pathlib.Path(__file__).parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import make_candidates as mc, make_multishot as mm, characters as ch, fal_cost

OMNI_EP = "fal-ai/bytedance/omnihuman/v1.5"
SYNC_EP = "fal-ai/sync-lipsync/v2/pro"
FONT_DIR = ROOT / "assets" / "fonts"
TALK_STYLE = ("Glamorous but natural home look in exactly the outfit described: well-fitted to her curvy figure, any neckline worn naturally "
              "with natural cleavage where the outfit allows, kajal and glossy lips. Natural candid framing, the camera is NOT zoomed on her chest and "
              "she is not posing for it; she is simply going about her day. Fully clothed, no lingerie.")


def env(k):
    for line in open(ROOT / ".env"):
        if line.startswith(k + "="): return line.split("=", 1)[1].strip().strip('"')
    sys.exit(f"{k} missing in .env")


def sh(*a): return subprocess.run(a, check=True, capture_output=True, text=True)


def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)


def fetch(url, dst): return mm.fetch(url, dst)


# ---------------------------------------------------------------- script
def new(slug, text):
    d = ROOT / "reels" / f"{time.strftime('%Y-%m-%d')}_{slug}"; d.mkdir(parents=True, exist_ok=True)
    (d / "script.txt").write_text(text.strip(), encoding="utf-8"); print("wrote", d / "script.txt"); return d


# ---------------------------------------------------------------- voice
def voice(d, speed=1.06, max_takes=6, budget=140, who="padma"):
    """ElevenLabs take -> Scribe check of EVERY Telugu word -> retake flagged words with respellings (up to 4 takes, resumable).
    Pradeep 4 Nov: no pronunciation mistake anywhere ("ఈరోజు" came out as "elohu"). Fixes that work go to voice/pronounce.json.
    If a word is still wrong after 4 takes: NO voice.mp3, exit 4, clips of the bad words in takes_*/check_*.mp3 for Pradeep."""
    import hashlib, re as _re
    import pron_check as pc
    t_start = time.time()
    vf = ROOT / "voice" / f"{who}_voice.json"           # padma_voice.json / satyam_voice.json: same guard for both (Pradeep 4 Nov)
    if not vf.exists(): sys.exit(f"{vf.name} missing: design {who}'s voice first (voice/design_voice.py)")
    v = json.load(open(vf))
    script = (d / "script.txt").read_text(encoding="utf-8").strip()
    ws = pc.words_of(script)
    pr = ROOT / "voice" / "pronounce.json"
    fixes = json.load(open(pr, encoding="utf-8")) if pr.exists() else {}
    known_src = {} if os.environ.get("PRON_IGNORE_FIXES") else fixes   # test switch: start from the raw script spelling
    core = lambda w: w.rstrip("?!.,।…'\"").lstrip("'\"")
    known = [known_src.get(core(w)) for w in ws]                     # spelling already known to work, per word
    td = d / f"takes_{who}_{hashlib.md5(script.encode()).hexdigest()[:8]}"; td.mkdir(exist_ok=True)
    takes = sorted(td.glob("take*.json"), key=lambda p: int(p.stem[4:]))
    takes = [json.load(open(p, encoding="utf-8")) for p in takes]
    for t in takes: t["check"] = pc.check(script, t.get("words") or t["heard"])   # saved takes re-judged with the current checker
    # spelling per word for the next take: known fix, else the original; each flagged word walks down its respellings
    def plan(prev):
        sp = [known[i] + w[len(core(w)):] if known[i] else w for i, w in enumerate(ws)]
        tried = {}
        for t in prev:
            for i, r in enumerate(t["check"]):
                tried.setdefault(i, []).append(t["spoken"][i])
        last = prev[-1] if prev else None
        if last:
            sp = list(last["spoken"])
            for i, r in enumerate(last["check"]):
                if r["score"] is not None and r["score"] < pc.PASS and not r.get("word_ok"):   # word_ok: only an extra sound before it -> plain retake
                    if not known[i] and tried.get(i, []).count(ws[i]) < 2:
                        sp[i] = ws[i]          # first failure: plain retake (most slips are random); respell only if it fails twice
                    else:
                        opts = [o for o in pc.respellings(ws[i]) if o not in tried.get(i, [])] or [ws[i]]
                        sp[i] = opts[0]
        return sp
    while not takes or (pc.flagged(takes[-1]["check"]) and len(takes) < max_takes):
        if takes and time.time() - t_start > budget:
            print(f"{len(takes)} take(s) so far, out of time for this call: RUN THE SAME COMMAND AGAIN to continue"); sys.exit(3)
        n = len(takes) + 1; spoken = plan(takes); text = " ".join(spoken)
        body = json.dumps({"text": text, "model_id": v.get("model_id", "eleven_v3"),
                           "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}).encode()
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{v['voice_id']}/with-timestamps?output_format=mp3_44100_128",
                                     data=body, headers={"xi-api-key": env("ELEVENLABS_API_KEY"), "Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=170))
        mp3 = td / f"take{n}.mp3"; mp3.write_bytes(base64.b64decode(r["audio_base64"]))
        heard = pc.scribe(mp3)
        chk = pc.check(script, [w for w in heard.get("words", []) if w.get("type") == "word"])
        t = {"n": n, "text": text, "spoken": spoken, "heard": heard["text"], "check": chk, "words": [w for w in heard.get("words", []) if w.get("type") == "word"],
             "alignment": r.get("alignment") or r.get("normalized_alignment") or {}}
        json.dump(t, open(td / f"take{n}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        takes.append(t)
        bad = pc.flagged(chk)
        print(f"take {n}: " + ("all words OK" if not bad else "flagged " + ", ".join(f"{b['word']} (heard {b['heard'] or '-'}, {b['score']})" for b in bad)), flush=True)
    score = lambda t: (len(pc.flagged(t["check"])), -sum(r["score"] for r in t["check"] if r["score"] is not None))
    best = min(takes, key=score); bad = pc.flagged(best["check"])
    rep = {"script": script, "takes": [{"n": t["n"], "text": t["text"], "heard": t["heard"],
                                       "flagged": [(b["word"], b["heard"], b["score"]) for b in pc.flagged(t["check"])]} for t in takes],
           "chosen": best["n"], "ok": not bad, "who": who}
    # respellings that made a word come out right are kept for every future reel
    learned = {}
    first = takes[0]
    for i, w in enumerate(ws):
        rb = best["check"][i]
        fails_plain = sum(1 for t in takes if t["spoken"][i] == w and t["check"][i]["score"] is not None and t["check"][i]["score"] < pc.PASS)
        if fails_plain >= 2 and rb["score"] is not None and rb["score"] >= pc.PASS \
                and core(best["spoken"][i]) != core(w) and _re.search(r"[ఀ-౿]", w):     # learn only a word that fails every time as written
            learned[core(w)] = core(best["spoken"][i])
    if learned and not bad:
        fixes.update(learned); json.dump(fixes, open(pr, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("learned respellings ->", pr.name, learned)
    rep["learned"] = learned
    json.dump(rep, open(d / "voice_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    raw_take = td / f"take{best['n']}.mp3"
    if bad:
        for k, b in enumerate(bad):
            if b.get("t"):
                s0, e0 = max(0, b["t"][0] - 1.0), b["t"][1] + 1.0
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s0:.2f}", "-to", f"{e0:.2f}", "-i", str(raw_take), str(td / f"check_{k + 1}.mp3")])
        print(f"STOP: after {len(takes)} takes these words are still not said right (best take {best['n']}):")
        for b in bad: print(f"   {b['word']}  ->  heard '{b['heard'] or '(nothing)'}'  score {b['score']}  at {b.get('t')}")
        print("clips:", ", ".join(p.name for p in sorted(td.glob("check_*.mp3"))), "| no voice.mp3 written; fix the script word or add a respelling to voice/pronounce.json")
        sys.exit(4)
    # words.json (subtitle timings) from the chosen take's TTS alignment
    al = best["alignment"]; words, cur, t0, last = [], "", None, 0
    for c, s, e in zip(al.get("characters", []), al.get("character_start_times_seconds", []), al.get("character_end_times_seconds", [])):
        if c.isspace():
            if cur: words.append({"w": cur, "s": t0, "e": last}); cur = ""
            continue
        if not cur: t0 = s
        cur += c; last = e
    if cur: words.append({"w": cur, "s": t0, "e": last})
    for w in words: w["s"] /= speed; w["e"] /= speed
    json.dump(words, open(d / "words.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    raw = d / "voice_raw.mp3"; raw.write_bytes(raw_take.read_bytes())
    sh("ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"atempo={speed},loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", str(d / "voice.mp3"))
    print(f"PRONUNCIATION OK (take {best['n']} of {len(takes)}, every Telugu word checked). voice.mp3 {dur(d / 'voice.mp3'):.1f}s")
    if dur(d / "voice.mp3") > 19: print("WARNING: over 19 s; shorten the script (target 14-18 s)")


# ---------------------------------------------------------------- still
def still(d, room, look, action, light, slot=None):
    loose = ""
    if room in ch.VIEWS:                       # a room KIND (kitchen/hall/...) -> rotate the view + pick loose items for the scene
        room, loose = ch.choose_room(room, slot or "evening", d.name); print("room:", room, "| items:", loose)
    if not look:
        look = ch.choose_look(slot or "evening", d.name); print("wardrobe:", look)
    os.environ["FAL_KEY"] = mc.load_key(); import fal_client
    base = ch.set_plate(room)
    close = base.with_name(f"{room}_close{base.suffix}")
    plate = close if close.exists() else base
    out = d / "still.png"; n = mm.NREF
    up = fal_client.upload_file
    prompt = (f"Images 1-{n} show the woman, Padma: her face and body must be identical to those images. Image {n+1} {ch.ROOM_REAL}. "
              f"A phone is propped up on a shelf or counter at her chest height about 1.2 metres away, filming her "
              f"as she talks to it like a selfie vlog: waist-up to three-quarter body in a vertical 9:16 frame, she faces the camera with a warm "
              f"teasing smile, mouth closed and relaxed (she is about to speak), eyes looking straight into the lens, {action}. "
              f"It is a calm held pose, not the middle of a movement: nothing is being poured, thrown or lifted. "
              f"{ch.loose_txt(loose) if loose else ''} Her look: {look}. {TALK_STYLE} {ch.CAMERA_MATCH} {ch.LIGHT[light]}. {ch.LIGHT_MATCH} {mm.PHONE} "
              f"Face clearly visible and well lit by the room, nothing in front of her mouth, hands visible. One person only. "
              f"{ch.FACE_TXT['padma']} {ch.BODY_TXT['padma']}")
    for attempt in range(3):
        if out.exists():
            ok, line = mm.gate(out, "padma", min_=mm.STILL_SANITY); print("sanity gate:", line)
            if ok: break
            out.rename(out.with_name(f"still_fail{attempt}.png"))
        r = fal_client.subscribe(mm.EDIT_EP, arguments={"thinking_level": "minimal", "aspect_ratio": "9:16", "resolution": mm.STILL_RES,
            "num_images": 1, "output_format": "png", "image_urls": [up(str(p)) for p in mm.refs2("padma")] + [up(str(plate))], "prompt": prompt})
        fetch(r["images"][0]["url"], out); fal_cost.spend(mm.EDIT_EP, 1, f"{d.name}_still")
    json.dump({"solo": "padma", "set": room, "look": look, "action": action, "light": light, "framing": {"s01": "wide"}},
              open(d / "meta.json", "w"), indent=1)
    fx = mm.still_fix(out, "padma")
    if fx: print("fixed still gate:", mm.gate(fx, "padma")[1])


# ---------------------------------------------------------------- animate
def animate(d, sync):
    vc = d / "voice_check.json"      # no paid lip-sync on a voice that has not passed the pronunciation check
    if not vc.exists() or not json.load(open(vc, encoding="utf-8")).get("ok") or vc.stat().st_mtime + 1 < (d / "voice.mp3").stat().st_mtime - 5:
        sys.exit("voice not pronunciation-checked (or failed): run  make_talk.py voice  first")
    os.environ["FAL_KEY"] = mc.load_key(); import fal_client
    rq = d / "requests.json"; reqs = json.load(open(rq)) if rq.exists() else {}
    src = d / "still_fx.png" if (d / "still_fx.png").exists() else d / "still.png"
    jpg = d / "still_omni.jpg"
    sh("ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-q:v", "2", str(jpg))
    meta = json.load(open(d / "meta.json")) if (d / "meta.json").exists() else {}
    secs = round(dur(d / "voice.mp3"), 2)
    if "omni" not in reqs:
        h = fal_client.submit(OMNI_EP, arguments={"image_url": fal_client.upload_file(str(jpg)), "audio_url": fal_client.upload_file(str(d / "voice.mp3")),
            "resolution": "1080p",
            "prompt": (f"Static camera, the phone does not move. A woman talking naturally and warmly to the camera at home, clear and precise "
                       f"mouth movements for every word, small natural head movements and expressive face. Her hands stay as they are in the image "
                       f"({meta.get('action', 'resting')}) with only small natural gestures; she does not pour, drink, eat or repeat any action while talking.")})
        reqs["omni"] = h.request_id; fal_cost.spend(OMNI_EP, secs, f"{d.name}_omni"); json.dump(reqs, open(rq, "w")); print("omni submitted", secs, "s")
    if sync and "sync" not in reqs and (d / "omni.mp4").exists():
        h = fal_client.submit(SYNC_EP, arguments={"video_url": fal_client.upload_file(str(d / "omni.mp4")),
                                                 "audio_url": fal_client.upload_file(str(d / "voice.mp3")), "sync_mode": "cut_off"})
        reqs["sync"] = h.request_id; fal_cost.spend(SYNC_EP, secs, f"{d.name}_sync"); json.dump(reqs, open(rq, "w")); print("sync submitted")
    elif sync and not (d / "omni.mp4").exists():
        print("sync waits for omni.mp4: run poll, then animate --sync again")


def poll(d):
    os.environ["FAL_KEY"] = mc.load_key(); import fal_client
    reqs = json.load(open(d / "requests.json"))
    for key, ep in (("omni", OMNI_EP), ("sync", SYNC_EP)):
        if key not in reqs or (d / f"{key}.mp4").exists(): continue
        st = type(fal_client.status(ep, reqs[key], with_logs=False)).__name__
        if st != "Completed": print(key, st); continue
        r = fal_client.result(ep, reqs[key]); tmp = d / f"{key}.part.mp4"
        fetch(r["video"]["url"], tmp)
        errs = subprocess.run(["ffmpeg", "-v", "error", "-i", str(tmp), "-f", "null", "-"], capture_output=True, text=True).stderr.strip()
        if errs: tmp.unlink(); print(key, "download damaged; poll again"); continue
        tmp.rename(d / f"{key}.mp4"); print(key, "saved", f"{dur(d / f'{key}.mp4'):.1f}s")


# ---------------------------------------------------------------- restore (mouth kept from the lip-sync model)
def restore(d, wait=900):
    d = d.resolve(); rel = d.relative_to(ROOT)
    srcv = d / "sync.mp4" if (d / "sync.mp4").exists() else d / "omni.mp4"
    src = d / f"src_{d.name}.mp4"
    sh("ffmpeg", "-v", "error", "-y", "-i", str(srcv), "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(src))
    job = ROOT / "jobs" / f"{d.name}_talk_restore.json"
    if not job.exists():
        job.write_text(json.dumps({"type": "face_restore", "target": f"{rel}/{src.name}".replace("\\", "/"), "output": f"{rel}/restored.mp4".replace("\\", "/"),
            "passes": mm.restore_passes("padma"), "mask_types": ["box", "region"],
            "mask_regions": ["skin", "left-eyebrow", "right-eyebrow", "left-eye", "right-eye", "glasses", "nose"], "enhancer_blend": 30}, indent=1))
        print("queued", job.name, "(mouth excluded)")
    t0 = time.time()
    while time.time() - t0 < wait:
        if job.with_suffix(".done").exists() and (d / "restored.mp4").exists():
            sh("ffmpeg", "-v", "error", "-y", "-i", str(d / "restored.mp4"), "-vf", "scale=720:1280,fps=30", "-an", "-c:v", "libx264", "-crf", "16",
               "-pix_fmt", "yuv420p", str(d / "joined.mp4"))
            print("restored -> joined.mp4"); return
        if job.with_suffix(".err").exists(): sys.exit("restore ERR " + job.with_suffix(".err").read_text()[-400:])
        time.sleep(5)
    print("restore still running; run restore again to wait")


# ---------------------------------------------------------------- subtitles + voice -> post.mp4
def ass_time(t): h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60; return f"{h}:{m:02d}:{s:05.2f}"


def subtitles(d):
    words = json.load(open(d / "words.json", encoding="utf-8"))
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or w["w"].endswith((".", "!", "?", ",", "...")): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: Cap,Noto Sans Telugu,64,&H00FFFFFF,&H00FFFFFF,&H00202020,&H64000000,1,0,0,0,100,100,0,0,1,3,2,2,80,80,430,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for c in chunks:
        txt = " ".join(w["w"] for w in c).replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{ass_time(c[0]['s'])},{ass_time(c[-1]['e'] + 0.08)},Cap,,0,0,0,,{txt}")
    (d / "subs.ass").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d / "subs.ass"


def is_telugu(ch_):
    return "ఀ" <= ch_ <= "౿"


def sub_pngs(d):
    """Subtitle chunks rendered with Pillow + raqm (proper Telugu shaping; the PC's libass drops vowel signs, 4 Nov).
    Telugu runs use Noto Sans Telugu, Latin runs DejaVu Sans Bold. Returns [(png, start, end)] for a 1080x1920 frame."""
    from PIL import Image, ImageDraw, ImageFont
    words = json.load(open(d / "words.json", encoding="utf-8"))
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or w["w"].endswith((".", "!", "?", ",", "...")): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    te = ImageFont.truetype(str(FONT_DIR / "NotoSansTelugu-Bold.ttf"), 62, layout_engine=ImageFont.Layout.RAQM)
    la = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56, layout_engine=ImageFont.Layout.RAQM)
    sd = d / "subs"; sd.mkdir(exist_ok=True); out = []
    for i, c in enumerate(chunks):
        text = " ".join(w["w"] for w in c)
        runs, buf, mode = [], "", None                       # split into script runs
        for ch_ in text:
            m = "te" if is_telugu(ch_) else ("sp" if ch_ == " " else "la")
            if m == "sp": m = mode or "la"
            if mode is None or m == mode: buf += ch_; mode = m
            else: runs.append((mode, buf)); buf, mode = ch_, m
        if buf: runs.append((mode, buf))
        widths = [ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(t, font=te if m == "te" else la) for m, t in runs]
        W = int(sum(widths)) + 40; img = Image.new("RGBA", (1080, 140), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
        x = (1080 - W) // 2 + 20
        for (m, t), w_ in zip(runs, widths):
            dr.text((x, 70), t, font=te if m == "te" else la, fill=(255, 255, 255, 255), anchor="lm",
                    stroke_width=5, stroke_fill=(20, 20, 20, 230))
            x += w_
        p = sd / f"s{i:02d}.png"; img.save(p); out.append((p, c[0]["s"], c[-1]["e"] + 0.08))
    return out


def post(d, subs_on=False):
    r = subprocess.run([sys.executable, str(HERE / "finish.py"), str(d), "--who", "padma"], capture_output=True, text=True)
    print(r.stdout.strip()); print(r.stderr.strip()[-400:]) if r.returncode else None
    if r.returncode: sys.exit("finish failed")
    subs = sub_pngs(d) if subs_on else []          # Pradeep 4 Nov: no subtitles by default
    ins, fc, last = ["-i", "final.mp4", "-i", "voice.mp3"], "", "[0:v]"
    for k, (p, s, e) in enumerate(subs):
        ins += ["-i", str(p.relative_to(d))]
        fc += f"{last}[{k + 2}:v]overlay=0:H-430-70:enable='between(t,{s:.2f},{e:.2f})'[v{k}];"; last = f"[v{k}]"
    fc = fc.rstrip(";") or "[0:v]null[v0]"; last = last if subs else "[v0]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", last, "-map", "1:a",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "post.mp4"], cwd=d, check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "post.mp4", "-c:v", "libx264", "-crf", "21", "-maxrate", "4.5M", "-bufsize", "9M",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "post_ig.mp4"], cwd=d, check=True)
    print("post.mp4", f"{dur(d / 'post.mp4'):.1f}s", f"| post_ig.mp4 {(d / 'post_ig.mp4').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["new", "voice", "still", "animate", "poll", "restore", "post"])
    ap.add_argument("path")
    ap.add_argument("--text"); ap.add_argument("--speed", type=float, default=1.06)
    ap.add_argument("--who", default="padma", choices=["padma", "satyam"], help="whose voice (voice/<who>_voice.json); pronunciation fixes in voice/pronounce.json are shared")
    ap.add_argument("--set", default="kitchen", help="room kind (kitchen/hall/bedroom/balcony/door: rotates views + loose items) or a fixed view like kitchen_b"); ap.add_argument("--light", default="evening", choices=list(ch.LIGHT))
    ap.add_argument("--look", default="", help="leave empty: the outfit comes from the wardrobe rotation for --slot")
    ap.add_argument("--slot", default="evening", choices=["morning", "late_morning", "evening", "out", "night"], help="time of day the scene is set in")
    ap.add_argument("--action", default="stirring something in a pan on the stove")
    ap.add_argument("--sync", action="store_true", help="also run lipsync-2-pro on the OmniHuman output (use on every talking reel)")
    ap.add_argument("--subs", action="store_true", help="burn Telugu subtitles (off by default, Pradeep 4 Nov)")
    a = ap.parse_args()
    if a.cmd == "new":
        new(a.path, a.text or sys.exit("--text required"))
    else:
        d = pathlib.Path(a.path)
        {"voice": lambda: voice(d, a.speed, who=a.who), "still": lambda: still(d, a.set, a.look, a.action, a.light, a.slot),
         "animate": lambda: animate(d, a.sync), "poll": lambda: poll(d), "restore": lambda: restore(d), "post": lambda: post(d, a.subs)}[a.cmd]()
