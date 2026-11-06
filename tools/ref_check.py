"""Gate 0: is this reference something Kling can turn into a real-looking Padma reel?  Free, runs before any spend.
   python ref_check.py <ref.mp4> [--start S --dur D]      -> verdict + reasons + best window suggestion
Learned 3-5 Nov 2026: close-up expressive faces, back views, hands over face, night/low light, cuts and
multiple people are where AI shows; full-body, frontal, bright, steady-camera dance travels."""
import sys, json, argparse, subprocess, pathlib, cv2, numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
HERE = pathlib.Path(__file__).parent
FPS = 6
LIMITS = dict(people=0.20, fullbody=0.60, face_big=0.16, back=0.25, hands_face=0.30, dark=60, cam=25.0, fast=0.30, backlit=1.6)

def cuts(path):
    r = subprocess.run(["ffmpeg", "-i", str(path), "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [float(l.split("pts_time:")[1].split()[0]) for l in r.splitlines() if "pts_time:" in l]

def frames(path):
    cap = cv2.VideoCapture(str(path)); fps = cap.get(5) or 30; step = max(1, round(fps / FPS)); i = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        if i % step == 0: yield i / fps, f
        i += 1

def analyse(path):
    opts = vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=str(HERE/"models/pose_landmarker_full.task")),
                                        running_mode=vision.RunningMode.IMAGE, num_poses=3, min_pose_detection_confidence=0.5)
    lm = vision.PoseLandmarker.create_from_options(opts); rows = []; prev_g = None; prev_k = None
    for t, f in frames(path):
        h, w = f.shape[:2]; g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
        poses = [p for p in res.pose_landmarks if np.mean([q.visibility for q in p[11:13]]) > 0.5]
        row = dict(t=round(t, 2), people=len(poses), luma=float(g.mean()))
        # camera motion from the top strip (mostly background)
        strip = np.float32(g[: h // 5])
        row["cam"] = float(np.hypot(*cv2.phaseCorrelate(prev_g, strip)[0]) / w * 100) if prev_g is not None else 0.0   # % of width
        prev_g = strip
        if poses:
            p = max(poses, key=lambda p: abs(p[11].x - p[12].x))       # main dancer = widest shoulders
            vis = lambda i: p[i].visibility > 0.5 and 0 <= p[i].y <= 1
            ank = max(p[27].y, p[28].y); top = min(p[0].y, p[7].y, p[8].y)   # predicted even under a saree
            row["fullbody"] = bool(top > -0.02 and ank < 1.02 and (ank - top) > 0.40)  # head-to-feet in frame, dancer not tiny
            face_w = abs(p[7].x - p[8].x)                               # ear to ear, fraction of width
            row["face_w"] = face_w
            row["back"] = p[11].x < p[12].x and p[0].visibility < 0.6    # left shoulder on image-left + no clear face
            nose = np.array([p[0].x, p[0].y]); r = max(face_w, 0.03) * 0.9
            row["hands_face"] = any(np.linalg.norm(np.array([p[i].x, p[i].y]) - nose) < r for i in (15, 16, 19, 20))
            xs = [min(max(q.x, 0), 1) for q in p]; ys = [min(max(q.y, 0), 1) for q in p]
            x0, x1, y0, y1 = int(min(xs) * w), int(max(xs) * w), int(min(ys) * h), int(max(ys) * h)
            if x1 - x0 > 10 and y1 - y0 > 10:
                mask = np.zeros((h, w), bool); mask[y0:y1, x0:x1] = True
                row["backlit"] = float(g[~mask].mean() / max(1.0, g[mask].mean()))   # background brightness / subject brightness
            body_h = max(0.2, max(q.y for q in p) - min(q.y for q in p))
            k = np.array([[p[i].x, p[i].y] for i in (15, 16, 27, 28)])
            row["speed"] = float(np.linalg.norm(k - prev_k, axis=1).mean() / body_h) if prev_k is not None else 0.0
            prev_k = k
        else:
            row.update(fullbody=False, face_w=0.0, back=False, hands_face=False, speed=0.0); prev_k = None
        rows.append(row)
    return rows

def score(rows):
    n = max(1, len(rows)); fr = lambda k: sum(1 for r in rows if r.get(k)) / n
    m = dict(people=sum(1 for r in rows if r["people"] > 1) / n, fullbody=fr("fullbody"), back=fr("back"), hands_face=fr("hands_face"),
             face_big=float(np.median([r["face_w"] for r in rows])), dark=float(np.median([r["luma"] for r in rows])),
             cam=float(np.percentile([r["cam"] for r in rows], 90)), fast=float(np.percentile([r["speed"] for r in rows], 90)),
             nobody=sum(1 for r in rows if r["people"] == 0) / n,
             backlit=float(np.median([r["backlit"] for r in rows if "backlit" in r] or [1.0])))
    L = LIMITS; why = []
    if m["people"] > L["people"]: why.append(f"more than one person in {m['people']:.0%} of frames")
    if m["nobody"] > 0.2: why.append(f"no dancer detected in {m['nobody']:.0%} of frames")
    if m["fullbody"] < L["fullbody"]: why.append(f"full body visible only {m['fullbody']:.0%} of the time (close-up: AI face shows)")
    if m["face_big"] > L["face_big"]: why.append(f"face fills {m['face_big']:.0%} of frame width (close-up)")
    if m["back"] > L["back"]: why.append(f"back to camera {m['back']:.0%} of the time")
    if m["hands_face"] > L["hands_face"]: why.append(f"hands over face {m['hands_face']:.0%} of the time (finger/face melt risk)")
    if m["dark"] < L["dark"]: why.append(f"dark scene (brightness {m['dark']:.0f}/255)")
    warn = []
    if m["backlit"] > L["backlit"]: warn.append(f"backlit (background {m['backlit']:.1f}x brighter than her): the still model front-lights her, the #1 AI tell on 5 Nov")
    if m["cam"] > L["cam"]: warn.append(f"shaky/moving camera (p90 shift {m['cam']:.1f}% of width per step)")
    if m["fast"] > L["fast"]: warn.append(f"very fast moves (p90 {m['fast']:.2f} body-heights/step): limb smear risk")
    return m, why, warn

def best_window(rows, cut_ts, total, lo=13.0, hi=16.0):
    if total < lo: lo = hi = round(total - 0.1, 1)
    good = np.array([r["fullbody"] and r["people"] == 1 and not r["back"] and not r["hands_face"] for r in rows], float)
    ts = np.array([r["t"] for r in rows]); best = None
    for s in np.arange(0, max(0.01, total - lo), 0.5):
        for d in (hi, 15.0, 14.0, lo):
            e = s + d
            if e > total + 0.05: continue
            inner = [c for c in cut_ts if s + 0.2 < c < e - 0.2]
            segs = np.diff([s] + inner + [e])
            if (segs < 3.0).any(): continue                  # Kling needs >= 3 s per shot
            sel = (ts >= s) & (ts < e)
            if not sel.any(): continue
            sc = good[sel].mean() - 0.05 * len(inner)
            if best is None or sc > best[0]: best = (round(float(sc), 3), round(float(s), 1), round(float(d), 1), len(inner))
    return best

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("ref"); ap.add_argument("--start", type=float); ap.add_argument("--dur", type=float); a = ap.parse_args()
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.ref], capture_output=True, text=True).stdout)
    rows = analyse(a.ref); cut_ts = cuts(a.ref)
    bw = best_window(rows, cut_ts, total)
    if a.start is not None: win = [r for r in rows if a.start <= r["t"] < a.start + (a.dur or 99)]
    elif bw: win = [r for r in rows if bw[1] <= r["t"] < bw[1] + bw[2]]        # judge the best usable 13-16 s, not the whole clip
    else: win = rows
    m, why, warn = score(win)
    verdict = "FAIL" if why else ("WARN" if warn else "PASS")
    print(json.dumps(dict(ref=pathlib.Path(a.ref).name, verdict=verdict, reasons=why, warnings=warn, cuts=[round(c, 2) for c in cut_ts],
                          best_window=dict(start=bw[1], dur=bw[2], cuts_inside=bw[3], good_frames=bw[0]) if bw else None,
                          metrics={k: round(v, 3) for k, v in m.items()}), indent=1))
    sys.exit(1 if why else 0)
