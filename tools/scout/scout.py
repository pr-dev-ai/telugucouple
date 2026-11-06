"""Padma trend scout (couple app), PC part. Resumable: each call works for --budget seconds, then prints 'remaining N'. Re-run until 'DONE'.
   python scout.py run  --date 2026-11-06 [--budget 150]     # needs <day>/_work/candidates.json written by the agent from collect.js
   python scout.py final --date 2026-11-06                  # rank, copy picks, picks.md, sheet.jpg, update seen/learned audios
Padma (satyam_padma.reels) copy of Siri's scout. Steps per candidate: yt-dlp -> ref_check.py (Gate 0) -> Claude vision fit vs Padma's winner."""
import sys, os, re, json, time, math, base64, shutil, argparse, pathlib, subprocess, cv2, numpy as np, httpx
HERE = pathlib.Path(__file__).parent; TOOLS = HERE.parent; ROOT = TOOLS.parent
OUT = ROOT/"ready-to-create"; SEEDS = HERE/"seeds.json"; SEEN = HERE/"seen.json"
YTDLP = str(pathlib.Path.home()/".local/bin/yt-dlp")
ENV = dict(os.environ, LD_LIBRARY_PATH=str(pathlib.Path.home()/"libegl/root/usr/lib/x86_64-linux-gnu"))
VISION_MODEL = "claude-sonnet-5-5"
FIT = """Images 1-4 are frames from OUR creator Padma's best reel (Sakkani Chinnodi Kosam, our most-liked reel): the style that works for us:
one glamorous curvy Telugu woman (a young aunty, late 20s), silk saree / half-saree / langa voni with the waist showing, full-body dance to a
trending Telugu folk or DJ song, ordinary real home or local place, even daylight or warm indoor light.
The remaining images are frames in time order from a CANDIDATE trending reel we might remake (our creator would copy only the dance moves, the song and the kind of place).
Return ONLY JSON: {"one_woman": true/false (exactly one person dancing, no group, no man), "outfit": "saree|half-saree|langa|lehenga|salwar|western|other",
"full_body_dance": true/false (real dance moves with the full body visible most of the time, not just poses, lip-sync or walking),
"talking_or_comedy": true/false, "even_light": true/false (not backlit sunset, not night, not dark), "energy": 1-10, "similarity": 1-10 (to our winner),
"note": "one short line on why it would or would not work for Padma"}"""

def sh(*a, **k): return subprocess.run(a, capture_output=True, text=True, **k)
def key(): return re.search(r"^ANTHROPIC_API_KEY=(.+)$", (ROOT/".env").read_text(), re.M).group(1).strip()
def b64(img, w=480):
    h0, w0 = img.shape[:2]; img = cv2.resize(img, (w, int(h0 * w / w0)))
    return base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode()
def frames(path, n):
    cap = cv2.VideoCapture(str(path)); t = int(cap.get(7)); out = []
    for f in np.linspace(3, max(4, t - 3), n).astype(int):
        cap.set(1, int(f)); ok, im = cap.read()
        if ok: out.append(im)
    return out

def fit_check(mp4):
    ex = [cv2.imread(str(p)) for p in sorted((HERE/"exemplars").glob("*.jpg"))]
    imgs = ex + frames(mp4, 4)
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(i)}} for i in imgs] + [{"type": "text", "text": FIT}]
    for _ in range(3):
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=120, headers={"x-api-key": key(), "anthropic-version": "2023-06-01", "content-type": "application/json"},
                           json={"model": VISION_MODEL, "max_tokens": 3000, "messages": [{"role": "user", "content": content}]})
            r.raise_for_status()
            try:
                import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parents[1])); import fal_cost as _fc; _fc.log_claude(r.json(), "scout")
            except Exception as _e: print("cost log skipped:", _e)
            t = "".join(c.get("text", "") for c in r.json()["content"] if c.get("type") == "text")
            return json.loads(t[t.index("{"): t.rindex("}") + 1])
        except Exception as e: err = str(e)
    return {"error": err}

def run(day, budget):
    work = day/"_work"; cands = json.load(open(work/"candidates.json")); st_p = work/"state.json"
    st = json.load(open(st_p)) if st_p.exists() else {}
    t0 = time.time()
    for c in cands:
        code = c["code"]
        if code in st: continue
        if time.time() - t0 > budget: break
        rec = dict(c); mp4 = work/f"{code}.mp4"
        if not mp4.exists():
            sh(YTDLP, "-q", "--no-warnings", "-f", "b[ext=mp4]/bv*+ba/b", "--merge-output-format", "mp4", "-o", str(mp4), c["url"])
        if not mp4.exists(): rec["status"] = "download failed"; st[code] = rec; json.dump(st, open(st_p, "w"), indent=1); continue
        g = sh(sys.executable, str(TOOLS/"ref_check.py"), str(mp4), env=ENV); out = g.stdout
        try: rec["gate0"] = json.loads(out[out.index("{"): out.rindex("}") + 1])
        except Exception: rec["gate0"] = {"verdict": "ERROR", "reasons": [g.stderr[-200:]]}
        if rec["gate0"]["verdict"] in ("PASS", "WARN"): rec["fit"] = fit_check(mp4)
        rec["status"] = "checked"; st[code] = rec; json.dump(st, open(st_p, "w"), indent=1)
        print(code, rec["gate0"]["verdict"], (rec.get("fit") or {}).get("similarity"), rec["views"], flush=True)
    left = sum(1 for c in cands if c["code"] not in st)
    print("DONE" if left == 0 else f"remaining {left}")

def points(r):
    g = r.get("gate0", {}); f = r.get("fit") or {}
    if g.get("verdict") not in ("PASS", "WARN") or f.get("error"): return None, "gate0: " + "; ".join(g.get("reasons", [])[:2]) if g else "no check"
    if not f.get("one_woman"): return None, "not a single woman"
    if f.get("talking_or_comedy"): return None, "talking/comedy"
    if f.get("outfit") in ("western", "other", "salwar"): return None, f"outfit {f.get('outfit')}"
    if not f.get("full_body_dance"): return None, "not a full-body dance"
    if not f.get("even_light"): return None, "dark/night or backlit light (main AI tell)"
    if f.get("similarity", 0) < 5: return None, "not similar enough to Padma's winner"
    p = 2 * f.get("similarity", 0) + f.get("energy", 0) + 2 * math.log10(max(10, r["vpd"])) + (2 if g["verdict"] == "PASS" else 1) + (1 if f.get("even_light") else 0)
    return round(p, 1), f.get("note", "")

def slug(s): return re.sub(r"[^a-z0-9]+", "_", (s or "audio").lower()).strip("_")[:28] or "audio"

def final(day, n):
    work = day/"_work"; st = json.load(open(work/"state.json")); cfg = json.load(open(SEEDS))
    scored = []
    for r in st.values():
        p, why = points(r); r["points"] = p; r["why"] = why
        if p is not None: scored.append(r)
    siri_codes = set()
    for p in (pathlib.Path.home()/"mnt/siri/ready-to-create").glob("*/picks.json"):
        try: siri_codes |= {x["code"] for x in json.load(open(p))}
        except Exception: pass
    scored = [r for r in scored if r["code"] not in siri_codes]      # Siri already gets these: keep the two accounts different
    scored.sort(key=lambda r: -r["points"]); picks = []; per_song = {}
    for r in scored:                                   # variety: at most 2 picks per song
        k = r.get("audio_id") or r["code"]
        if per_song.get(k, 0) >= 2: continue
        per_song[k] = per_song.get(k, 0) + 1; picks.append(r)
        if len(picks) >= n: break
    lines = [f"# Ready to create, {day.name}", "",
             f"Scouted {len(st)} trending reels (10K+ views, last {cfg['max_age_days']} days); {len(scored)} passed every check; top {len(picks)} below.",
             "Every pick passed Gate 0 (full body, one person, not dark/close-up) and a vision check against Padma's best reel (Sakkani).", "",
             "| # | Song | Views | Views/day | Likes | Age | Len | Gate 0 | Similar | Energy | Best window | Creator | Link |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    sheet_rows = []
    for i, r in enumerate(picks, 1):
        name = f"{i:02d}_{slug(r['song'])}_{r['code']}.mp4"; shutil.copyfile(work/f"{r['code']}.mp4", day/name); r["file"] = name
        (day/"preview").mkdir(exist_ok=True)      # small phone-friendly copy with sound, numbered, for review in the Claude app
        sh("ffmpeg", "-v", "error", "-y", "-i", str(day/name), "-vf", "scale=540:-2,drawtext=text='%d':x=20:y=20:fontsize=64:fontcolor=yellow:box=1:boxcolor=black@0.6" % i,
           "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(day/"preview"/f"{i:02d}_{slug(r['song'])}.mp4"))
        bw = r["gate0"].get("best_window") or {}; f = r["fit"]
        lines.append(f"| {i} | {r['song'] or 'original audio'} {('- ' + r['artist']) if r['artist'] else ''} | {r['views']:,} | {r['vpd']:,} | {r['likes']:,} | {r['age_days']:.0f} d | {r['dur']:.0f} s | {r['gate0']['verdict']} | {f.get('similarity')} | {f.get('energy')} | "
                     f"{bw.get('start', 0)}–{round(bw.get('start', 0) + bw.get('dur', r['dur']), 1)} s | @{r['user']} | [open]({r['url']}) |")
        strip = [cv2.resize(im, (160, 284)) for im in frames(day/name, 6)]
        strip = np.hstack(strip); cv2.rectangle(strip, (0, 0), (70, 40), (0, 0, 0), -1)
        cv2.putText(strip, str(i), (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2); sheet_rows.append(strip)
    lines += ["", "## Notes per pick"] + [f"{i}. **{r['song'] or 'original audio'}** ({r['code']}): {r['fit'].get('note', '')} {'Warnings: ' + '; '.join(r['gate0'].get('warnings', [])) if r['gate0'].get('warnings') else ''}" for i, r in enumerate(picks, 1)]
    rej = {}
    for r in st.values():
        if r.get("points") is None: rej[r.get("why") or r.get("status")] = rej.get(r.get("why") or r.get("status"), 0) + 1
    lines += ["", "## Rejected", *[f"- {v} × {k}" for k, v in sorted(rej.items(), key=lambda x: -x[1])[:12]]]
    (day/"picks.md").write_text("\n".join(lines), encoding="utf-8")
    json.dump(picks, open(day/"picks.json", "w"), indent=1, ensure_ascii=False)
    if sheet_rows: cv2.imwrite(str(day/"sheet.jpg"), np.vstack(sheet_rows), [cv2.IMWRITE_JPEG_QUALITY, 82])
    seen = json.load(open(SEEN)) if SEEN.exists() else []
    seen = sorted(set(seen) | set(st.keys())); json.dump(seen, open(SEEN, "w"))
    for r in picks[:3]:                                              # learn new winning audios for tomorrow's sweep
        if r.get("audio_type") == "licensed_music" and r.get("audio_id") and r["audio_id"] not in cfg["audios"].values() \
           and r["audio_id"] not in cfg.get("blocked_audios", {}).values():
            cfg["learned_audios"][f"{r['song']} ({day.name})"] = r["audio_id"]
    cfg["learned_audios"] = dict(list(cfg["learned_audios"].items())[-12:]); json.dump(cfg, open(SEEDS, "w"), indent=1, ensure_ascii=False)
    print(f"picks {len(picks)} -> {day}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "final"]); ap.add_argument("--date", required=True); ap.add_argument("--budget", type=float, default=150)
    a = ap.parse_args(); day = OUT/a.date; (day/"_work").mkdir(parents=True, exist_ok=True)
    run(day, a.budget) if a.cmd == "run" else final(day, json.load(open(SEEDS))["picks"])
