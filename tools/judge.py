"""Gates 1 and 3: automatic realism check before spending (still) and before posting (video).
   python judge.py still <still.png> <ref_frame.jpg>
   python judge.py video <out.mp4> [--ref <kling_input_ref.mp4>] [--label name]
Vision judge = Claude (Anthropic key in .env) with a strict 'spot the AI' rubric; video also gets numbers:
face identity per frame (ArcFace vs canonical), pose error vs the reference dance, limb jitter ratio."""
import sys, os, re, json, base64, argparse, pathlib, cv2, numpy as np, httpx
HERE = pathlib.Path(__file__).parent; ROOT = HERE.parent
MODEL = "claude-opus-5-5"
RUBRIC = """You are a strict reviewer for a Telugu Instagram creator. Real viewers have repeatedly spotted these videos as AI-generated,
so your only job is to catch anything that would make a normal Indian Instagram viewer think "this is AI".
Judge the woman AND the scene. Score each 1-10 (10 = indistinguishable from a real phone video):
- phone_real: looks like an ordinary handheld phone video/photo, not a render, CGI, beauty filter or photoshoot
- lighting: light on her (direction, colour, softness, shadows, skin highlights) matches the background light; no cut-out or studio look
- skin_face: natural skin texture and pores, no plastic/airbrushed skin, natural eyes/teeth/expression, nothing odd between the eyebrows
- hands_body: hands and fingers correct (count, shape), arms/legs/neck natural, no melted or extra limbs, clothing drapes like real fabric
- background: coherent real place, no warped lines, melting objects, nonsense text or repeated patterns
- motion (only if several frames from a video are given): body positions look like a real person dancing, no rubbery limbs, no sliding feet, no face morphing between frames
Return ONLY JSON: {"phone_real":n,"lighting":n,"skin_face":n,"hands_body":n,"background":n,"motion":n_or_null,"overall":n,
"ai_tells":["short concrete tell", ...],"fix":"one short instruction for the next attempt"}"""
# Calibrated 5 Nov 2026: this judge is harsh (our best real-world reel, pink saree road 26K views, scored overall 5).
# Pass = overall >= 6 and no category below 5. Use the scores mainly to RANK candidates; Pradeep's eye is the final gate.
PASS_OVERALL = 6; FLOOR = 5

def key():
    env = (ROOT/".env").read_text(); return re.search(r"^ANTHROPIC_API_KEY=(.+)$", env, re.M).group(1).strip()

def b64(img_bgr, w=640):
    h0, w0 = img_bgr.shape[:2]; img = cv2.resize(img_bgr, (w, int(h0 * w / w0)))
    return base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])[1]).decode()

def ask(images, note):
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64(i)}} for i in images]
    content.append({"type": "text", "text": note + "\n\n" + RUBRIC})
    for attempt in range(3):
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=180,
                           headers={"x-api-key": key(), "anthropic-version": "2023-06-01", "content-type": "application/json"},
                           json={"model": MODEL, "max_tokens": 6000, "messages": [{"role": "user", "content": content}]})
            r.raise_for_status()
            try:
                import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parents[0])); import fal_cost as _fc; _fc.log_claude(r.json(), "judge")
            except Exception as _e: print("cost log skipped:", _e)
            t = "".join(c.get("text", "") for c in r.json()["content"] if c.get("type") == "text")
            return json.loads(t[t.index("{"): t.rindex("}") + 1])
        except Exception as e:
            err = e
    raise SystemExit(f"judge failed: {err}")

def verdict(j):
    keys = [k for k in ("phone_real", "lighting", "skin_face", "hands_body", "background", "motion", "overall") if j.get(k) is not None]
    low = [k for k in keys if j[k] < FLOOR] + (["overall"] if j.get("overall", 0) < PASS_OVERALL and "overall" not in [k for k in keys if j[k] < FLOOR] else [])
    return ("PASS" if not low else "FAIL"), low

def sample(path, n, start=0.0, end=None):
    cap = cv2.VideoCapture(str(path)); total = int(cap.get(7)); fps = cap.get(5) or 24
    a = int(start * fps); b = int(end * fps) if end else total - 1
    out = []
    for f in np.linspace(a + 2, max(a + 3, b - 2), n).astype(int):
        cap.set(1, int(f)); ok, img = cap.read()
        if ok: out.append(img)
    return out

def face_track(path, stride=3):
    sys.path.insert(0, str(HERE)); import face_gate as fg
    cap = cv2.VideoCapture(str(path)); s = []; i = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        if i % stride == 0:
            v = fg.score_single(f, 'padma', 60)[0]   # couple app: Padma's canonical face
            if v is not None: s.append(v)
        i += 1
    return (round(float(np.median(s)), 3), round(float(min(s)), 3), round(float(np.std(s)), 3), len(s)) if s else (None, None, None, 0)

def poses(path, fps_s=8):
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    lm = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(HERE/"models/pose_landmarker_full.task")), running_mode=vision.RunningMode.IMAGE, num_poses=1))
    cap = cv2.VideoCapture(str(path)); fps = cap.get(5) or 24; step = max(1, round(fps / fps_s)); i = 0; out = []
    J = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
    while True:
        ok, f = cap.read()
        if not ok: break
        if i % step == 0:
            r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
            if r.pose_landmarks:
                p = r.pose_landmarks[0]; k = np.array([[p[j].x, p[j].y] for j in J])
                hip = (k[6] + k[7]) / 2; sh = (k[0] + k[1]) / 2; scale = max(1e-3, np.linalg.norm(sh - hip))
                out.append((k - hip) / scale)
            else: out.append(None)
        i += 1
    return out

def motion_metrics(out_mp4, ref_mp4):
    a, b = poses(out_mp4), poses(ref_mp4); n = min(len(a), len(b))
    pairs = [(a[i], b[i]) for i in range(n) if a[i] is not None and b[i] is not None]
    if len(pairs) < 5: return dict(pose_err=None, jitter=None, lost=round(1 - len(pairs) / max(1, n), 2))
    err = float(np.mean([np.linalg.norm(x - y, axis=1).mean() for x, y in pairs]))
    A = np.array([x for x, _ in pairs]); B = np.array([y for _, y in pairs])
    jit = lambda K: np.abs(np.diff(K, n=2, axis=0)).mean()
    return dict(pose_err=round(err, 3), jitter=round(float(jit(A) / max(1e-6, jit(B))), 2), lost=round(1 - len(pairs) / max(1, n), 2))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("kind", choices=["still", "video"]); ap.add_argument("path"); ap.add_argument("ref", nargs="?")
    ap.add_argument("--ref", dest="ref_video"); ap.add_argument("--label", default=""); a = ap.parse_args()
    if a.kind == "still":
        imgs = [cv2.imread(a.path)] + ([cv2.imread(a.ref)] if a.ref else [])
        j = ask(imgs, "Image 1 is the generated still of our creator (it will be animated into a dance video). "
                      + ("Image 2 is the real reference frame whose pose/place it copies; judge ONLY image 1." if a.ref else ""))
        res = dict(file=pathlib.Path(a.path).name, **j)
    else:
        frames = sample(a.path, 6)
        j = ask(frames, "These are 6 frames in time order from one generated dance reel of our creator.")
        res = dict(file=pathlib.Path(a.path).name, label=a.label, **j)
        med, mn, sd, nf = face_track(a.path); res["face"] = dict(median=med, min=mn, std=sd, frames=nf)
        if a.ref_video: res["motion_vs_ref"] = motion_metrics(a.path, a.ref_video)
    v, low = verdict(res); res["verdict"] = v; res["low"] = low
    if a.kind == "video" and res["face"]["median"] is not None and (res["face"]["median"] < 0.55 or res["face"]["std"] > 0.08):
        res["verdict"] = "FAIL"; res["low"].append("face identity drift")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    log = ROOT/"jobs"/"_judge_log.jsonl"; open(log, "a", encoding="utf-8").write(json.dumps(res, ensure_ascii=False) + "\n")
    sys.exit(0 if res["verdict"] == "PASS" else 1)
